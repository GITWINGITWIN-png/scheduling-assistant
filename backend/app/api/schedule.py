"""B3's web API: the schedule page (W5), tasks, planner rules, and Classroom courses."""

import asyncio
import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.connectors import google
from app.core import actions, clock, settings
from app.core.db import now, session
from app.core.timefmt import from_local
from app.core.tables import Block, Decision, Event, Task
from app.features import decisions
from app.features.classroom import sync as classroom
from app.features.classroom.tables import STATES, Course, CourseItem
from app.features.mail.extract import gmail_link
from app.features.mail.tables import Email
from app.features.schedule import events, remind, sync, tasks
from app.features.time import followed
from app.features.time.followed import counted_minutes

router = APIRouter(prefix="/api")
log = logging.getLogger(__name__)


class Strict(BaseModel):
    """A request body that refuses fields it doesn't know (main.py says why in words)."""

    model_config = ConfigDict(extra="forbid")

SOURCE_NAMES = tasks.SOURCE_NAMES


_local = from_local  # a time from the page ("2026-11-10T17:00", no zone) is your local time


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
    """Everything between start and end: appointments (and the ones waiting for you to รับ, drawn
    dashed as in the plan's W5 ④), work blocks, due dates, and the last plan."""
    lo, hi, at = _local(start), _local(end), now()
    with session() as s:
        asked = {d.detail.get("event_id"): d for d in s.scalars(select(Decision).where(Decision.kind == "appointment",
                                                                                      Decision.status == "pending"))}
        events = s.scalars(select(Event).where(
            (Event.status == "placed") | ((Event.status == "proposed") & Event.id.in_([k for k in asked if k])),
            Event.starts_at < hi, Event.ends_at > lo)).all()
        blocks = s.execute(select(Block, Task.title, Task.status).join(Task, Task.id == Block.task_id)
                           .where(Block.status.in_(("planned", "pinned")), Block.starts_at < hi, Block.ends_at > lo)).all()
        due = s.scalars(select(Task).where(Task.status == "open", Task.due_at >= lo, Task.due_at < hi)).all()
        out = {
            "events": [{"id": e.id, "title": e.title, "start": _iso(e.starts_at), "end": _iso(e.ends_at), "all_day": e.all_day,
                        "location": e.location, "description": e.description,
                        "source": e.source, "source_name": SOURCE_NAMES.get(e.source, e.source),
                        "recurring": e.recurring, "link": e.link,
                        "mail": _link(s, "email", e.source_ref) if e.source == "email" else "",
                        "status": e.status, "decision_id": asked[e.id].id if e.id in asked else None,
                        "from": asked[e.id].detail.get("from", "") if e.id in asked else ""} for e in events],
            "blocks": [{"id": b.id, "task_id": b.task_id, "title": title, "start": _iso(b.starts_at), "end": _iso(b.ends_at),
                        "pinned": b.status == "pinned", "past": b.ends_at <= at, "running": b.starts_at <= at < b.ends_at,
                        "task_status": task_status,
                        # B6: what really happened (features/time/followed.py)
                        "outcome": b.outcome, "worked": b.worked_minutes, "instead": b.instead} for b, title, task_status in blocks],
            "deadlines": [{"task_id": t.id, "title": t.title, "due": _iso(t.due_at), "source": SOURCE_NAMES.get(t.source, t.source),
                           "link": _link(s, t.source, t.source_ref)} for t in due],
        }
    state = settings.get(sync.STATE_KEY, {})
    with session() as s:
        names = {t.id: t.title for t in s.scalars(select(Task).where(Task.id.in_([int(k) for k in state.get("short", {})])))}
    out["plan"] = {"planned_at": state.get("planned_at"),
                   "short": [{"task_id": int(k), "title": names.get(int(k), ""), "minutes": v} for k, v in state.get("short", {}).items()]}
    return out


# ------------------------------------------------------------------ กิจกรรม (appointments you add)
class EventIn(Strict):
    title: str
    start: str  # local: "2026-11-12T10:00", or "2026-11-12" for an all-day event
    end: str  # for an all-day event, the last day (inclusive), as the page shows it
    all_day: bool = False
    location: str = ""
    description: str = ""


@router.post("/events")
async def add_event(body: EventIn) -> dict:
    """A กิจกรรม from the schedule page goes straight into your main Google Calendar
    (features/schedule/events.py says how), then blocks are re-planned around it."""
    try:
        if body.all_day:
            start, end = events.whole_days(date.fromisoformat(body.start[:10]), date.fromisoformat(body.end[:10]))
        else:
            start, end = _local(body.start), _local(body.end)
    except ValueError:
        raise HTTPException(400, "วันหรือเวลาไม่ถูกต้อง")
    try:
        event_id, action_id = await events.add(body.title, start, end, all_day=body.all_day, location=body.location,
                                               description=body.description, via=("หน้าตาราง", ""))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:  # Google didn't take it: the event was forgotten
        raise HTTPException(409 if isinstance(exc, google.NeedsConsent) else 502, f"ลงปฏิทินไม่ได้: {exc}")
    return {"id": event_id, "action_id": action_id, "plan": await sync.replan_if_on(("หน้าตาราง", ""))}


@router.post("/schedule/replan")
async def replan() -> dict:
    """วางตารางใหม่: re-plan now, even if nothing changed."""
    return {"line": await sync.replan_now(("หน้าตาราง", ""))}


# ------------------------------------------------------------------ tasks
@router.get("/tasks")
def list_tasks() -> dict:
    """Open tasks (due first), with the time booked and done so far, and the ones closed this week."""
    at, est = now(), sync.estimates()
    with session() as s:
        rows = s.scalars(select(Task).where((Task.status == "open") | (Task.created_at > at - timedelta(days=7)))
                         .order_by(Task.status.desc(), Task.due_at.is_(None), Task.due_at, Task.id)).all()
        blocks = s.scalars(select(Block).where(Block.status.in_(("planned", "pinned")), Block.task_id.in_([t.id for t in rows]))).all()
        booked: dict[int, list[int]] = {}
        for b in blocks:  # a missed block counts what you worked of it, as the planner counts it (B6)
            slot = booked.setdefault(b.task_id, [0, 0])
            if b.ends_at <= at:
                slot[0] += counted_minutes(b)
            else:
                slot[1] += int((b.ends_at - b.starts_at).total_seconds() // 60)
        items = [{"id": t.id, "title": t.title, "due": _iso(t.due_at), "status": t.status, "source": SOURCE_NAMES.get(t.source, t.source),
                  "est_minutes": t.est_minutes, "est_default": est.get(t.source, 60), "plan_mode": t.plan_mode,
                  "block_minutes": t.block_minutes, "daily_minutes": t.daily_minutes, "details": t.details,
                  "done_minutes": booked.get(t.id, [0, 0])[0], "booked_minutes": booked.get(t.id, [0, 0])[1],
                  "link": _link(s, t.source, t.source_ref)} for t in rows]
    return {"items": items}


class TaskIn(Strict):
    title: str
    due: str | None = None  # local time, "2026-11-10T17:00"
    est_minutes: int | None = None  # None: the default for tasks you add (กติกาตาราง)
    plan_mode: str = "early"
    block_minutes: int | None = None  # None: the rules' longest block
    daily_minutes: int | None = None  # None: the rules' limit per task per day
    details: str = ""  # รายละเอียดงาน: what, where, where to hand it in; links allowed


@router.post("/tasks")
async def add_task(body: TaskIn) -> dict:
    try:
        task_id, action_id = tasks.add(body.title, due_at=_local(body.due), est_minutes=body.est_minutes,
                                       plan_mode=body.plan_mode, block_minutes=body.block_minutes,
                                       daily_minutes=body.daily_minutes, details=body.details, via=("หน้าตาราง", ""))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": task_id, "action_id": action_id, "plan": await sync.replan_if_on(("หน้าตาราง", ""))}


class TaskEdit(Strict):
    """Only the fields sent change. Sending null puts one back to its default: no due date,
    the default estimate, or the rules' block length and daily limit."""

    title: str | None = None
    due: str | None = None
    est_minutes: int | None = None
    plan_mode: str | None = None
    block_minutes: int | None = None
    daily_minutes: int | None = None
    details: str | None = None


EDIT_FIELDS = {"title": "title", "due": "due_at", "est_minutes": "est_minutes", "plan_mode": "plan_mode",
               "block_minutes": "block_minutes", "daily_minutes": "daily_minutes", "details": "details"}


@router.patch("/tasks/{task_id}")
async def edit_task(task_id: int, body: TaskEdit) -> dict:
    changes: dict = {}
    for name in body.model_fields_set:
        value = getattr(body, name)
        if value is None and name in ("title", "plan_mode"):
            raise HTTPException(400, "ชื่องานและวิธีจองเวลาเว้นว่างไม่ได้")
        changes[EDIT_FIELDS[name]] = _local(value) if name == "due" else value
    if not changes:
        raise HTTPException(400, "ไม่มีอะไรให้แก้")
    try:
        action_id = tasks.edit(task_id, via=("หน้าตาราง", ""), **changes)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if {"title", "details"} & changes.keys():  # the blocks already in the calendar say the new text too
        await sync.retext(task_id)
    return {"action_id": action_id, "plan": await sync.replan_if_on(("หน้าตาราง", ""))}


@router.post("/tasks/{task_id}/done")
async def task_done(task_id: int) -> dict:
    try:
        action_id = tasks.done(task_id, via=("หน้าตาราง", ""))
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {"action_id": action_id, "plan": await sync.replan_if_on(("หน้าตาราง", ""))}


# ------------------------------------------------------------------ rules
@router.get("/schedule/rules")
def get_rules() -> dict:
    return {"rules": sync.rules_dict(), "estimates": sync.estimates(), "reminders": list(remind.leads())}


class RulesIn(Strict):
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


class CourseAnswer(Strict):
    follow: bool
    folder: str | None = None


@router.post("/courses/decisions/{decision_id}")
async def answer_course(decision_id: int, body: CourseAnswer) -> dict:
    try:
        d, action_id = await classroom.decide(decision_id, body.follow, folder=body.folder, via=("หน้าเว็บ", ""))
        await decisions.settle_card(decision_id)  # its #อนุมัติ card says so too
    except decisions.Answered as exc:  # answered already: the page shows how, in place of the buttons
        raise HTTPException(409, str(exc))
    except ValueError as exc:  # couldn't be done: it still waits
        raise HTTPException(422, str(exc))
    return {"status": d.status, "action_id": action_id}


# ------------------------------------------------------------------ ทำตามแผนได้ · ข้อสังเกต (W5 ⑤ ⑥, B6)
TARGET_KEY = "schedule.follow_target"  # your target, percent of blocks followed in a week


@router.get("/schedule/followed")
def followed_week() -> dict:
    """⑤ This week: the share of checked blocks you followed, per day, against your target; ⑥ what
    repeats (the last 4 weeks)."""
    from app.features.time import insights

    at = now()
    start, end, label = insights.span("week", at)
    f = followed.followed(start, min(end, at))
    days = []
    for i in range(7):
        a, b = start + timedelta(days=i), start + timedelta(days=i + 1)
        mins = lambda rows: sum(int((x.ends_at - x.starts_at).total_seconds() // 60) for x, _ in rows  # noqa: E731
                                if a <= x.starts_at < b)
        days.append({"label": insights.DAYS[i], "done": mins(f["done"]), "missed": mins(f["missed"])})
    return {"label": label, "percent": f["percent"], "checked": f["checked"], "target": settings.get(TARGET_KEY, 80),
            "days": days, "notes": followed.patterns(at), "recording": clock.enabled("activity")}


class TargetIn(Strict):
    target: int


@router.put("/schedule/followed/target")
def set_target(body: TargetIn) -> dict:
    if not 10 <= body.target <= 100:
        raise HTTPException(422, "เป้าต้องอยู่ระหว่าง 10 ถึง 100%")
    old = settings.get(TARGET_KEY, 80)
    settings.put(TARGET_KEY, body.target)
    action_id = actions.record("schedule.target", f"ตั้งเป้าทำตามแผน {body.target}%", f"เดิม {old}%", source_label="หน้าตาราง",
                               undo={"target": old})
    return {"target": body.target, "action_id": action_id}


async def _undo_target(undo: dict) -> None:
    settings.put(TARGET_KEY, undo["target"])


actions.register_undo("schedule.target", _undo_target)


class AvoidIn(Strict):
    weekday: int  # 0 = Monday
    part: str  # เช้า · บ่าย · เย็น


@router.post("/schedule/avoid")
async def avoid(body: AvoidIn) -> dict:
    """⑥ ไม่วางบล็อกช่วงนี้ (B7): a rule of yours, then the plan changes at once."""
    try:
        _, action_id = followed.avoid_rule(body.weekday, body.part)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    line = await sync.run(force=True)
    return {"action_id": action_id, "line": line or ""}


@router.post("/blocks/{block_id}/done")
def block_done(block_id: int) -> dict:
    """นับว่าทำแล้ว: a block the rules called missed, that you did where they couldn't see."""
    try:
        return {"action_id": followed.mark_done(block_id, via=("หน้าตาราง", ""))}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
