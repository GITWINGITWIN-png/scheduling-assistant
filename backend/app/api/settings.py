"""The settings page (W10), the theme (W11), and the small status the shell shows on every page."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from app.connectors import discord_bot, google
from app.core import codestamp, llm, themes
from app.core import clock as clock_mod
from app.core.clock import clock
from app.core.db import now, session
from app.core.rules import book as rules_book
from app.core.rules.check import APPROVAL_DAYS
from app.core.tables import Decision, LLMUsage
from app.features.decisions import clashes, rule_notes
from app.features.briefs import day as briefs_day
from app.features.mail import watch

router = APIRouter(prefix="/api", tags=["settings"])

# Model choices agreed for later phases: shown greyed out until their phase (W10 ①)
PLANNED_TASKS = [
    {"label": "เตือนนัด · ซิงก์ปฏิทิน", "model": "สคริปต์", "effort": "—", "phase": ""},  # built in B3: no phase, not greyed
    {"label": "งานเบื้องหลัง", "model": "Opus", "effort": "ต่อแผน", "phase": "B5"},
    {"label": "ย่อข่าวโปรเจค", "model": "OmniRoute", "effort": "—", "phase": "B5"},
    # B6, rules only until OmniRoute runs (the user's choice at the B6 plan)
    {"label": "จัดหมวดหน้าต่าง", "model": "กติกา (OmniRoute ยังไม่ต่อ)", "effort": "—", "phase": ""},
    {"label": "แท็กและจัดกลุ่มไอเดีย", "model": "กติกา (OmniRoute ยังไม่ต่อ)", "effort": "—", "phase": ""},
]


def services() -> list[dict]:
    """Connections (W10 ④): ActivityWatch's state is live (B6); OmniRoute waits for you to run it."""
    from app.features.time import recorder

    if not recorder.installed():
        aw = ("ยังไม่ติดตั้ง", "warn")
    elif recorder.enabled() and clock_mod.enabled("activity"):
        aw = ("บันทึกอยู่", "ok")
    else:
        aw = ("ปิดอยู่", "muted")
    return [{"icon": "eye", "name": "ActivityWatch", "detail": "บนเครื่องนี้ + ตัวกรอง · เปิดปิดที่หน้าการใช้เวลา", "phase": "",
             "state": aw[0], "tone": aw[1]},
            {"icon": "robot", "name": "OmniRoute", "detail": "API แบบ OpenAI · งานเล็ก · ระหว่างนี้ใช้กติกา", "phase": "",
             "state": "ยังไม่ต่อ", "tone": "muted"}]


@router.get("/settings")
def get_settings() -> dict:
    tasks = []
    for task, default in llm.DEFAULT_TASKS.items():
        current = llm.task_settings(task)
        tasks.append({"task": task, "label": default["label"], "model": current["model"], "effort": current["effort"],
                      "default_model": default["model"], "default_effort": default["effort"]})
    return {
        "tasks": tasks, "models": list(llm.MODELS), "efforts": list(llm.EFFORTS), "planned_tasks": PLANNED_TASKS,
        "theme": themes.current_theme(),
        "themes": [{"id": k, "name": n, "sub": sub} for k, (n, sub, _) in themes.THEMES.items()],
        "clock": clock.status(),
        "discord": discord_bot.status(),
        # live since B2: Gmail (every account) + Calendar (google.CALENDAR_ACCOUNT), with your address
        # on each (the mail settings card that listed them moved here, W10)
        "google": [{**g, "address": watch.address_of(g["id"])} for g in google.status()],
        "services": services(),
        # B5: the rule "งานเบื้องหลังทำเองได้เมื่อโควตาเหลือเกิน 70%" (W10's อนุมัติเอง; changed in the rule book)
        "jobs_rule": {"auto": rules_book.auto(), "line": rules_book.line(), "approval_days": APPROVAL_DAYS},
    }


class RoundIn(BaseModel):
    on: bool


@router.put("/settings/rounds/{round_id}")
def put_round(round_id: str, body: RoundIn) -> dict:
    """The on/off switch of one clock round (a new phase's rounds start off)."""
    try:
        action_id = clock_mod.set_enabled(round_id, body.on)
    except KeyError:
        raise HTTPException(404, "no such round")
    return {"round": round_id, "on": body.on, "action_id": action_id}


class TaskIn(BaseModel):
    model: str
    effort: str


@router.put("/settings/llm/{task}")
def put_task(task: str, body: TaskIn) -> dict:
    try:
        action_id = llm.set_task(task, body.model, body.effort)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"task": task, **llm.task_settings(task), "action_id": action_id}


class ThemeIn(BaseModel):
    theme: str


@router.put("/settings/theme")
def put_theme(body: ThemeIn) -> dict:
    try:
        themes.set_theme(body.theme)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"theme": body.theme}


@router.get("/status")
def status() -> dict:
    """For the shell on every page: the bell's count, this week's tokens, whether Discord is up,
    whether the backend code on disk is newer than the running one (restart banner), and the
    side menu's counts (the plan's W screens: the red number next to a page).

    counts.people: today's เรื่องสำคัญ (mail from important people, or matching a keyword), the
    same count as the today page and the morning brief (briefs/day.py); the user's reading of
    the plan's "คนและอีเมล 2", 2026-11-06. counts.decisions: what waits for you (วันนี้ 3)."""
    with session() as s:
        pending = s.scalar(select(func.count()).select_from(Decision).where(Decision.status == "pending")) or 0
        week = s.scalar(select(func.sum(LLMUsage.tokens_in + LLMUsage.tokens_out))
                        .where(LLMUsage.at >= now() - timedelta(days=7))) or 0
    from app.features.jobs import quota  # the side menu's quota (B5)
    reading = quota.latest(max_age=None)
    return {"pending": pending, "tokens_week": int(week), "discord": discord_bot.status()["connected"],
            "theme": themes.current_theme(), "stale": codestamp.stale(),
            "counts": {"people": briefs_day.important_today(), "decisions": pending, **work_counts()},
            "quota": {"week_left": reading.week_left, "at": reading.at.isoformat(), "line": rules_book.line(),
                      "auto": rules_book.auto()} if reading else None}


def work_counts() -> dict:
    """counts.jobs: background plans waiting for you (red, W4) · counts.projects: projects on the go
    (grey, W3: กำลังทำ and รันอัตโนมัติ, not hidden)."""
    from app.features.jobs.tables import Job
    from app.features.projects.tables import Project

    with session() as s:
        asking = s.scalar(select(func.count()).select_from(Job).where(Job.status == "asking")) or 0
        going = s.scalar(select(func.count()).select_from(Project).where(Project.status.in_(("active", "auto")),
                                                                         Project.hidden.is_(False), Project.missing.is_(False))) or 0
    return {"jobs": asking, "projects": going}


@router.get("/decisions")
def decisions(status: str = "pending") -> dict:
    """What waits for you (the bell and the today page): plans (B1), appointments from email (B2),
    Classroom courses (B3). An appointment says what else is at that time (clash: "" = nothing)."""
    with session() as s:
        rows = s.scalars(select(Decision).where(Decision.status == status).order_by(Decision.created_at.desc()).limit(50)).all()
    clash, against = clashes(rows), rule_notes(rows)
    return {"items": [{"id": d.id, "kind": d.kind, "title": d.title, "plan": d.detail.get("plan", ""),
                       "request": d.detail.get("request", ""), "model": d.detail.get("model", ""),
                       "effort": d.detail.get("effort", ""), "tokens": d.detail.get("tokens"),
                       "when": d.detail.get("when", ""), "from": d.detail.get("from", ""),  # appointment (B2)
                       "subject": d.detail.get("subject", ""),
                       "job_id": d.detail.get("job_id"), "budget": d.detail.get("budget"),  # background plan (B5)
                       "risks": d.detail.get("risks", []), "why": d.detail.get("why", ""), "stuck_at": d.detail.get("stuck_at", ""),
                       "project_id": d.detail.get("project_id"),  # new project (B5)
                       "group_id": d.detail.get("group_id"), "size": d.detail.get("size"),  # a grown idea group (B6)
                       "about": d.detail.get("project", ""),
                       "topic": d.detail.get("topic", ""), "label": d.detail.get("label", ""),  # a weekly review topic (B7)
                       "what": d.detail.get("what", ""), "acts": d.detail.get("acts", []),
                       "folder": d.detail.get("folder", ""), "exists": d.detail.get("exists", False),  # course (B3)
                       "link": d.detail.get("link", ""), "clash": clash.get(d.id), "rule": against.get(d.id, ""),
                       "created_at": d.created_at.isoformat()} for d in rows]}
