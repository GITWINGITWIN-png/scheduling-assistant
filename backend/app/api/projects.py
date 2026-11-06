"""B5's web API for the projects page (W3): the registry, setting a project's levels and
switches, scanning now, and answering "ตั้งระดับโปรเจคใหม่"."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.core import actions
from app.core.config import get_config
from app.core.db import session
from app.core.tables import Decision
from app.features import decisions
from app.features.projects import advice, scan
from app.features.jobs import queue
from app.features.jobs.tables import Job
from app.features.projects.tables import POTENTIALS, STATUSES, Project, ProjectNews

router = APIRouter(prefix="/api")


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _row(p: Project, asked: dict[int, int], news: dict[int, ProjectNews] | None = None, jobs: dict[int, Job] | None = None) -> dict:
    n = (news or {}).get(p.id)
    j = (jobs or {}).get(p.id)
    return {"news": {"title": n.title, "at": _iso(n.at), "urgent": n.urgent, "kind": n.kind} if n else None,
            "job": {"id": j.id, "status": j.status, "title": j.title or j.stuck_at} if j else None,"id": p.id, "name": p.name, "path": p.path, "status": p.status, "status_name": STATUSES.get(p.status, p.status),
            "potential": p.potential, "urgency": p.urgency, "level_set": p.level_set, "hidden": p.hidden,
            "allow_jobs": p.allow_jobs, "can_work": p.is_git and not scan.is_self(p.path) and not p.missing,
            "is_self": scan.is_self(p.path), "is_git": p.is_git, "last_activity": _iso(p.last_activity),
            "commits_14d": p.commits_14d, "progress": p.progress or {}, "missing": p.missing,
            "decision_id": asked.get(p.id)}


ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "F": 5}


@router.get("/projects")
def projects() -> dict:
    """The registry: not hidden first, by potential, urgency (5 first) and how recently it moved."""
    with session() as s:
        rows = s.scalars(select(Project)).all()
        asked = {d.detail.get("project_id"): d.id for d in s.scalars(
            select(Decision).where(Decision.kind == "project_level", Decision.status == "pending"))}
        news: dict[int, ProjectNews] = {}
        for n in s.scalars(select(ProjectNews).where(ProjectNews.project_id.is_not(None)).order_by(ProjectNews.at)):
            news[n.project_id] = n  # the newest wins
        jobs = {j.project_id: j for j in s.scalars(select(Job).where(Job.status.in_(queue.OPEN)))}
        items = [_row(p, asked, news, jobs) for p in rows]
    items.sort(key=lambda p: p["last_activity"] or "", reverse=True)  # most recent first within a level (a stable sort)
    items.sort(key=lambda p: (p["hidden"], p["missing"], ORDER.get(p["potential"], 9), -p["urgency"]))
    tips = [{"project_id": a.project_id, "project": a.project, "kind": a.kind, "title": a.title, "detail": a.detail,
             "next": a.next} for a in advice.advice()]
    return {"items": items, "advice": tips, "root": str(get_config().projects_dir), "scanned": bool(rows)}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectEdit(Strict):
    status: str | None = None
    potential: str | None = None
    urgency: int | None = None
    hidden: bool | None = None
    allow_jobs: bool | None = None


WORDS = {"status": "สถานะ", "potential": "potential", "urgency": "ความเร่งด่วน", "hidden": "ซ่อน", "allow_jobs": "ให้เลขาทำต่อได้"}


@router.patch("/projects/{project_id}")
def edit_project(project_id: int, body: ProjectEdit) -> dict:
    """Change what you see on a project's row (recorded, ย้อนกลับ in สิ่งที่เลขาทำ)."""
    changes = {k: getattr(body, k) for k in body.model_fields_set}
    if not changes:
        raise HTTPException(400, "ไม่มีอะไรให้แก้")
    if changes.get("status", "active") not in STATUSES or changes.get("potential", "C") not in POTENTIALS \
            or not 0 <= changes.get("urgency", 0) <= 5:
        raise HTTPException(400, "สถานะ potential S–F หรือความเร่งด่วน 0–5 ไม่ถูกต้อง")
    with session() as s:
        p = s.get(Project, project_id)
        if p is None:
            raise HTTPException(404, "ไม่พบโปรเจคนี้")
        if changes.get("allow_jobs"):
            if scan.is_self(p.path):
                raise HTTPException(409, "เลขาไม่ทำงานเบื้องหลังในโค้ดของตัวเอง")
            if not p.is_git:
                raise HTTPException(409, "โปรเจคนี้ยังไม่มี git · เลขาทำงานบน branch แยก จึงต้องมี git ก่อน")
        old = {k: getattr(p, k) for k in changes}
        for k, v in changes.items():
            setattr(p, k, v)
        if "potential" in changes or "urgency" in changes:
            p.level_set = True
        name = p.name
    what = " · ".join(f"{WORDS[k]} {STATUSES.get(v, v) if k == 'status' else ('เปิด' if v is True else 'ปิด' if v is False else v)}"
                      for k, v in changes.items())
    action_id = actions.record("project.edit", f"แก้โปรเจค {name}", what, source_label="หน้าโปรเจค",
                               undo={"project_id": project_id, "old": old})
    return {"action_id": action_id}


async def _undo_edit(undo: dict) -> None:
    with session() as s:
        if p := s.get(Project, undo["project_id"]):
            for k, v in undo["old"].items():
                setattr(p, k, v)


actions.register_undo("project.edit", _undo_edit)


@router.post("/projects/scan")
async def scan_now() -> dict:
    """สแกนตอนนี้: the morning round's work, at once (the first time, or after a new folder)."""
    result = await asyncio.to_thread(scan.scan)
    for project_id, decision_id in result.new:
        for hook in scan.ASKED:
            await hook(project_id, decision_id)
    line = result.line() or "ไม่มีอะไรใหม่"
    actions.record("projects.scan", "สแกนโปรเจค", line, source_label="หน้าโปรเจค")
    return {"line": line}


class BookIn(Strict):
    minutes: int = 120


@router.post("/projects/{project_id}/book")
async def book(project_id: int, body: BookIn) -> dict:
    """จองเวลา for the project's next step (a task the planner books; ย้อนกลับ removes it)."""
    if not 15 <= body.minutes <= 600:
        raise HTTPException(400, "เวลา 15 นาทีถึง 10 ชั่วโมง")
    try:
        task_id = advice.book(project_id, body.minutes)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    from app.api.schedule import _replan_if_on
    return {"task_id": task_id, "plan": await _replan_if_on()}


class LevelIn(Strict):
    potential: str
    urgency: int


@router.post("/projects/decisions/{decision_id}")
async def answer_level(decision_id: int, body: LevelIn) -> dict:
    try:
        scan.set_levels(decision_id, body.potential, body.urgency)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    await decisions.settle_card(decision_id)
    return {"ok": True}


@router.get("/projects/connect")
def connect_guide() -> dict:
    """คู่มือเชื่อมต่อ (W3 ⑥): CONNECT.md to read on the page, and where the inbox is."""
    from pathlib import Path

    from app.core.config import REPO_DIR
    from app.features.projects import inbox

    guide = REPO_DIR / "docs" / "CONNECT.md"
    where = str(inbox.inbox_dir()).replace(str(Path.home()), "~", 1)
    example = '{"kind": "report", "title": "feed วันนี้มาแล้ว", "body": "12 paper ใหม่", "link": "https://example.com"}'
    return {"text": guide.read_text() if guide.is_file() else "", "inbox": f"{where}/<โปรเจค>/*.json", "example": example}
