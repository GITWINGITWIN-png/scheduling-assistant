"""B3's web API: the schedule page (W5), tasks, planner rules, and Classroom courses."""

from datetime import datetime, time, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core import actions, clock, settings
from app.core.config import get_config
from app.core.db import now, session
from app.core.tables import Block, Decision, Event, Task
from app.features.classroom import sync as classroom
from app.features.classroom.tables import STATES, Course, CourseItem
from app.features.mail.extract import gmail_link
from app.features.mail.tables import Email
from app.features.schedule import remind, sync, tasks

router = APIRouter(prefix="/api")

SOURCE_NAMES = {"email": "อีเมล", "classroom": "Classroom", "you": "คุณเพิ่ม", "project": "โปรเจค", "calendar": "ปฏิทิน"}


def _local(value: str | None) -> datetime | None:
    """A time from the page ("2026-11-10T17:00", no zone) is your local time."""
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=get_config().tz)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _link(s, source: str, ref: str) -> str:
    if source == "email" and (e := s.get(Email, ref)):
        return gmail_link(e)
    if source == "classroom" and (i := s.get(CourseItem, ref)):
        return i.link
    return ""


# ------------------------------------------------------------------ the week
@router.get("/schedule")
def week(start: str, end: str) -> dict:
    """Everything between start and end: appointments, work blocks, due dates, and the last plan."""
    lo, hi = _local(start), _local(end)
    with session() as s:
        events = s.scalars(select(Event).where(Event.status == "placed", Event.starts_at < hi, Event.ends_at > lo)).all()
        blocks = s.execute(select(Block, Task.title).join(Task, Task.id == Block.task_id)
                           .where(Block.status.in_(("planned", "pinned")), Block.starts_at < hi, Block.ends_at > lo)).all()
        due = s.scalars(select(Task).where(Task.status == "open", Task.due_at >= lo, Task.due_at < hi)).all()
        out = {
            "events": [{"id": e.id, "title": e.title, "start": _iso(e.starts_at), "end": _iso(e.ends_at), "all_day": e.all_day,
                        "location": e.location, "source": e.source, "recurring": e.recurring,
                        "link": _link(s, "email", e.source_ref) if e.source == "email" else e.link} for e in events],
            "blocks": [{"id": b.id, "task_id": b.task_id, "title": title, "start": _iso(b.starts_at), "end": _iso(b.ends_at),
                        "pinned": b.status == "pinned", "past": b.ends_at <= now()} for b, title in blocks],
            "deadlines": [{"task_id": t.id, "title": t.title, "due": _iso(t.due_at), "source": SOURCE_NAMES.get(t.source, t.source),
                           "link": _link(s, t.source, t.source_ref)} for t in due],
        }
    state = settings.get(sync.STATE_KEY, {})
    with session() as s:
        names = {t.id: t.title for t in s.scalars(select(Task).where(Task.id.in_([int(k) for k in state.get("short", {})])))}
    out["plan"] = {"planned_at": state.get("planned_at"),
                   "short": [{"task_id": int(k), "title": names.get(int(k), ""), "minutes": v} for k, v in state.get("short", {}).items()]}
    return out


@router.post("/schedule/replan")
async def replan() -> dict:
    """วางตารางใหม่: re-plan now, even if nothing changed."""
    return {"line": await sync.replan_now(("หน้าตาราง", ""))}


# ------------------------------------------------------------------ tasks
async def _replan_if_on() -> str | None:
    """A task changed on this page: if the schedule round is switched on, plan now rather
    than in up to 15 minutes. If it's off, the calendar is left alone (วางตารางใหม่ still works)."""
    if not clock.enabled("schedule"):
        return None
    line = await sync.run()
    if line:
        actions.record("schedule.plan", "วางตารางตามงานที่เปลี่ยน", line, source_label="หน้าตาราง")
    return line


@router.get("/tasks")
def list_tasks() -> dict:
    """Open tasks (due first), with the time booked and done so far, and the ones closed this week."""
    at, est = now(), sync.estimates()
    with session() as s:
        rows = s.scalars(select(Task).where((Task.status == "open") | (Task.created_at > at - timedelta(days=7)))
                         .order_by(Task.status.desc(), Task.due_at.is_(None), Task.due_at, Task.id)).all()
        blocks = s.scalars(select(Block).where(Block.status.in_(("planned", "pinned")), Block.task_id.in_([t.id for t in rows]))).all()
        booked: dict[int, list[int]] = {}
        for b in blocks:
            minutes = int((b.ends_at - b.starts_at).total_seconds() // 60)
            slot = booked.setdefault(b.task_id, [0, 0])
            slot[0 if b.ends_at <= at else 1] += minutes
        items = [{"id": t.id, "title": t.title, "due": _iso(t.due_at), "status": t.status, "source": SOURCE_NAMES.get(t.source, t.source),
                  "est_minutes": t.est_minutes, "est_default": est.get(t.source, 60), "plan_mode": t.plan_mode,
                  "done_minutes": booked.get(t.id, [0, 0])[0], "booked_minutes": booked.get(t.id, [0, 0])[1],
                  "link": _link(s, t.source, t.source_ref)} for t in rows]
    return {"items": items}


class TaskIn(BaseModel):
    title: str
    due: str | None = None  # local time, "2026-11-10T17:00"
    est_minutes: int | None = None
    plan_mode: str = "early"


@router.post("/tasks")
async def add_task(body: TaskIn) -> dict:
    if not body.title.strip():
        raise HTTPException(400, "ใส่ชื่องานก่อน")
    try:
        task_id = tasks.add(body.title, due_at=_local(body.due), est_minutes=body.est_minutes, plan_mode=body.plan_mode,
                            via=("หน้าตาราง", ""))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": task_id, "plan": await _replan_if_on()}


class TaskEdit(BaseModel):
    title: str | None = None
    due: str | None = None
    clear_due: bool = False
    est_minutes: int | None = None
    clear_est: bool = False
    plan_mode: str | None = None


@router.patch("/tasks/{task_id}")
async def edit_task(task_id: int, body: TaskEdit) -> dict:
    changes: dict = {}
    if body.title is not None:
        changes["title"] = body.title.strip()
    if body.due is not None or body.clear_due:
        changes["due_at"] = None if body.clear_due else _local(body.due)
    if body.est_minutes is not None or body.clear_est:
        changes["est_minutes"] = None if body.clear_est else body.est_minutes
    if body.plan_mode is not None:
        changes["plan_mode"] = body.plan_mode
    if not changes:
        raise HTTPException(400, "ไม่มีอะไรให้แก้")
    try:
        action_id = tasks.edit(task_id, via=("หน้าตาราง", ""), **changes)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"action_id": action_id, "plan": await _replan_if_on()}


@router.post("/tasks/{task_id}/done")
async def task_done(task_id: int) -> dict:
    try:
        action_id = tasks.done(task_id, via=("หน้าตาราง", ""))
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {"action_id": action_id, "plan": await _replan_if_on()}


# ------------------------------------------------------------------ rules
@router.get("/schedule/rules")
def get_rules() -> dict:
    return {"rules": sync.rules_dict(), "estimates": sync.estimates(), "reminders": list(remind.leads())}


class RulesIn(BaseModel):
    day_start: str
    day_end: str
    max_block: int
    per_task_per_day: int
    gap: int
    estimates: dict[str, int]
    reminders: list[str]


@router.put("/schedule/rules")
def put_rules(body: RulesIn) -> dict:
    """Save the planner rules, default estimates and reminder leads (recorded, undoable)."""
    try:
        start, end = time.fromisoformat(body.day_start), time.fromisoformat(body.day_end)
    except ValueError:
        raise HTTPException(400, "เวลาต้องเป็นแบบ 09:00")
    if start >= end:
        raise HTTPException(400, "เวลาเริ่มต้องก่อนเวลาเลิก")
    if not (30 <= body.max_block <= 480 and 30 <= body.per_task_per_day <= 720 and 0 <= body.gap <= 120):
        raise HTTPException(400, "ตัวเลขเกินช่วงที่ใช้ได้")
    old = {k: settings.get(k) for k in (sync.RULES_KEY, sync.ESTIMATES_KEY, remind.LEADS_KEY)}
    settings.put(sync.RULES_KEY, {"day_start": body.day_start, "day_end": body.day_end, "max_block": body.max_block,
                                  "per_task_per_day": body.per_task_per_day, "gap": body.gap})
    settings.put(sync.ESTIMATES_KEY, {k: v for k, v in body.estimates.items() if k in sync.DEFAULT_ESTIMATES and 0 < v <= 1440})
    settings.put(remind.LEADS_KEY, [x for x in body.reminders if x in remind.LEADS])
    action_id = actions.record("settings.schedule", "เปลี่ยนกติกาตาราง",
                               f"{body.day_start}–{body.day_end} · บล็อกไม่เกิน {body.max_block} นาที",
                               source_label="หน้าตาราง", undo={"old": old})
    return {"action_id": action_id}


async def _undo_rules(undo: dict) -> None:
    for key, value in undo["old"].items():
        settings.put(key, value)


actions.register_undo("settings.schedule", _undo_rules)


# ------------------------------------------------------------------ Classroom courses
@router.get("/courses")
def courses() -> dict:
    """Courses the secretary knows, followed first, with the newest downloaded files."""
    order = {"asking": 0, "followed": 1, "ended": 2, "ignored": 3}
    with session() as s:
        rows = sorted(s.scalars(select(Course)).all(), key=lambda c: (order.get(c.state, 9), c.name))
        files: dict[str, list[dict]] = {}
        for item in s.scalars(select(CourseItem).order_by(CourseItem.synced_at.desc())):
            for f in item.files or []:
                if f.get("path"):
                    files.setdefault(item.course_id, []).append({"name": f["name"], "path": f["path"]})
        pending = {d.detail.get("course_id"): d.id for d in s.scalars(select(Decision).where(Decision.kind == "course",
                                                                                            Decision.status == "pending"))}
    return {"items": [{"id": c.id, "name": c.name, "state": c.state, "state_name": STATES.get(c.state, c.state),
                       "folder": c.folder, "link": c.link, "decision_id": pending.get(c.id),
                       "files": files.get(c.id, [])[:5], "file_count": len(files.get(c.id, []))} for c in rows]}


class CourseAnswer(BaseModel):
    follow: bool
    folder: str | None = None


@router.post("/courses/decisions/{decision_id}")
async def answer_course(decision_id: int, body: CourseAnswer) -> dict:
    try:
        d, action_id = await classroom.decide(decision_id, body.follow, folder=body.folder, via=("หน้าเว็บ", ""))
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {"status": d.status, "action_id": action_id}
