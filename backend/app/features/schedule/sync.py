"""Keep the schedule and Google Calendar in step (ซิงก์ตาราง, B3 step 4). The round "schedule", every 15 minutes.

Each run:

1. **Read the calendar** (refresh_calendar). Your primary calendar is copied into the
   events table (source "calendar"), so busy time and reminders come from one place; an
   event deleted there is marked removed. In the "เลขา" calendar, a block you **moved**
   becomes pinned (the planner keeps it where you put it); a block you **deleted** is
   marked deleted and its time counts as busy from then on ("that time isn't free"), so
   its work goes somewhere else. Anything else you put in the "เลขา" calendar is busy too.
2. **Re-plan only if something changed.** The inputs (open tasks, busy times, pinned
   blocks, rules, today's date) are boiled down to a fingerprint; the same fingerprint as
   last time means nothing to do, so blocks don't shuffle every 15 minutes.
3. **Write the difference.** Blocks starting within the next hour (FREEZE), or already
   running, stay as they are. Past blocks count as work done on their task, except a block
   B6 found missed (you were at the computer, on something else): it counts only the minutes
   you really worked on it, so the rest goes back to the task and gets new time
   (features/time/followed.py). Only future blocks that changed are deleted and added.

Nothing here uses a model. Writes go to the "เลขา" calendar only; your own calendar is
only read.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict
from datetime import datetime, time, timedelta

from sqlalchemy import select

from app.connectors import gcal, google
from app.core import actions, settings
from app.core.config import get_config
from app.core.db import now, session
from app.core.tables import Block, Event, Task
from app.core.timefmt import local, thai_datetime
from app.features.schedule.planner import Placed, Plan, Rules, Work, plan
from app.features.schedule.tasks import SOURCE_NAMES
from app.features.time.followed import counted_minutes

log = logging.getLogger(__name__)

RULES_KEY = "schedule.rules"  # your overrides of planner.Rules, e.g. {"day_start": "08:30"}
ESTIMATES_KEY = "schedule.estimates"  # minutes for a task with no estimate of its own, per source
DEFAULT_ESTIMATES = {"classroom": 120, "email": 30, "you": 60, "project": 60}  # agreed at the B3 plan
STATE_KEY = "state.schedule"  # {"fingerprint", "planned_at", "short": {task id: minutes}}
FREEZE = timedelta(hours=1)  # blocks starting sooner than this are left alone

lock = asyncio.Lock()  # the round and the "วางตารางใหม่" button never plan at the same time


# ------------------------------------------------------------------ rules and estimates
def rules() -> Rules:
    saved = settings.get(RULES_KEY, {})
    fields = {k: v for k, v in saved.items() if k in Rules.__dataclass_fields__}
    for k in ("day_start", "day_end"):
        if isinstance(fields.get(k), str):
            fields[k] = time.fromisoformat(fields[k])
    return Rules(**fields)


def rules_dict() -> dict:
    """The rules as the web page shows them (times as "HH:MM")."""
    return {k: (v.strftime("%H:%M") if isinstance(v, time) else v) for k, v in asdict(rules()).items()}


def estimates() -> dict[str, int]:
    return {**DEFAULT_ESTIMATES, **settings.get(ESTIMATES_KEY, {})}


def estimate(task: Task, est: dict[str, int] | None = None) -> int:
    return task.est_minutes or (est or estimates()).get(task.source, 60)


# ------------------------------------------------------------------ 1. read the calendar (in a thread)
def refresh_calendar(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Copy the calendars into the store (see the module docstring). -> busy intervals."""
    busy: list[tuple[datetime, datetime]] = []
    seen: set[str] = set()
    with session() as s:
        for e in gcal.window(start, end):
            seen.add(e.id)
            if not e.busy:
                continue  # marked "free", or you declined it: not busy time, not reminded
            ev = s.scalar(select(Event).where(Event.gcal_id == e.id))
            if ev is None:
                ev = Event(title=e.title, starts_at=e.start, ends_at=e.end, source="calendar", source_ref=e.id, gcal_id=e.id)
                s.add(ev)
            ev.title, ev.starts_at, ev.ends_at, ev.all_day = e.title, e.start, e.end, e.all_day
            ev.location, ev.link, ev.recurring, ev.status = e.location, e.link, e.recurring, "placed"
            ev.description = e.description
            if not e.all_day:  # a whole-day entry (a holiday, a trip note) doesn't block hours
                busy.append((e.start, e.end))
        for ev in s.scalars(select(Event).where(Event.status == "placed", Event.gcal_id != "",
                                                Event.starts_at >= start, Event.starts_at < end)):
            if ev.gcal_id not in seen:
                ev.status = "removed"  # deleted (or declined) in Google Calendar

    cal_id = gcal.blocks_calendar(create=False)
    with session() as s:
        live = s.scalars(select(Block).where(Block.status.in_(("planned", "pinned")), Block.gcal_id != "")).all()
        if cal_id is None:  # the "เลขา" calendar is gone, and with it every block
            for b in live:
                b.status = "removed"
            return busy
        theirs = {e.id: e for e in gcal.window(start, end, calendar=cal_id)}
        mine = {b.gcal_id for b in live}
        for b in live:
            if not (start <= b.starts_at < end):
                continue
            e = theirs.get(b.gcal_id)
            if e is None:
                b.status = "deleted"  # you deleted it: that time isn't free (see _inputs)
            elif (e.start, e.end) != (b.starts_at, b.ends_at):
                b.starts_at, b.ends_at, b.status = e.start, e.end, "pinned"  # you moved it: keep it there
        busy += [(e.start, e.end) for gid, e in theirs.items() if gid not in mine and not e.all_day]
    return busy


# ------------------------------------------------------------------ 2. what to plan
def _inputs(at: datetime, busy: list[tuple[datetime, datetime]]) -> tuple[list[Work], list, list[Placed], list[Block], str]:
    """-> (work still to place, busy incl. kept blocks, kept blocks, movable future blocks, fingerprint)."""
    est = estimates()
    with session() as s:
        tasks = s.scalars(select(Task).where(Task.status == "open")).all()
        blocks = s.scalars(select(Block).where(Block.status.in_(("planned", "pinned")))).all()
        deleted = s.scalars(select(Block).where(Block.status == "deleted", Block.ends_at > at)).all()
        s.expunge_all()
    open_ids = {t.id for t in tasks}
    kept = [b for b in blocks if b.task_id in open_ids and (b.status == "pinned" or b.starts_at < at + FREEZE)]
    movable = [b for b in blocks if b not in kept]
    covered: dict[int, int] = {}
    for b in kept:  # past, running, about to start, or pinned by you: already counted (a missed one: what you did)
        covered[b.task_id] = covered.get(b.task_id, 0) + counted_minutes(b)
    work = [Work(t.id, estimate(t, est) - covered.get(t.id, 0), t.due_at, t.plan_mode, t.block_minutes, t.daily_minutes,
                 t.not_before if t.not_before and t.not_before > at else None)
            for t in tasks]
    all_busy = (busy + [(b.starts_at, b.ends_at) for b in kept if b.ends_at > at]
                + [(b.starts_at, b.ends_at) for b in deleted])
    fingerprint = hashlib.sha256(json.dumps({
        "day": local(at).date().isoformat(),
        "tasks": sorted((t.id, t.due_at.isoformat() if t.due_at else "", estimate(t, est), t.plan_mode,
                         t.block_minutes or 0, t.daily_minutes or 0,
                         t.not_before.isoformat() if t.not_before and t.not_before > at else "") for t in tasks),
        "missed": sorted((b.id, b.worked_minutes or 0) for b in kept if b.outcome == "missed"),
        "busy": sorted((s_.isoformat(), e.isoformat()) for s_, e in busy),
        "pinned": sorted((b.id, b.starts_at.isoformat(), b.ends_at.isoformat()) for b in blocks if b.status == "pinned"),
        "deleted": sorted(b.id for b in deleted),
        "rules": rules_dict(),
    }, sort_keys=True).encode()).hexdigest()[:16]
    return work, all_busy, [Placed(b.task_id, b.starts_at, b.ends_at) for b in kept], movable, fingerprint


# ------------------------------------------------------------------ 3. write the difference
def block_text(task: Task) -> str:
    """What a block in the "เลขา" calendar says under its title: your รายละเอียดงาน (what to do,
    where to hand it in), when it's due and where it came from, so the calendar on your
    phone is enough to start working."""
    due = " · ".join(x for x in (f"ส่ง {thai_datetime(task.due_at)}" if task.due_at else "",
                                 f"ที่มา: {SOURCE_NAMES.get(task.source, task.source)}") if x)
    return "\n\n".join(x for x in (task.details.strip(), due,
                                     "บล็อกงานจากเลขา · ย้ายเวลาได้เลย เลขาจะไม่ย้ายกลับ · ลบทิ้งได้ถ้าช่วงนั้นไม่ว่าง") if x)


def retext_blocks(task_id: int) -> int:
    """A task's title or details changed: rewrite its upcoming blocks (blocking). -> how many."""
    with session() as s:
        task = s.get(Task, task_id)
        if task is None:
            return 0
        title, text = task.title, block_text(task)
        ids = list(s.scalars(select(Block.gcal_id).where(Block.task_id == task_id, Block.status.in_(("planned", "pinned")),
                                                         Block.gcal_id != "", Block.ends_at > now())))
    cal_id = gcal.blocks_calendar(create=False) if ids else None
    return sum(gcal.retext(gid, title, text, calendar=cal_id) for gid in ids) if cal_id else 0


async def retext(task_id: int) -> None:
    """retext_blocks, best effort: if the calendar can't be reached, the task itself still has
    the change and only the calendar's copy is behind."""
    try:
        await asyncio.to_thread(retext_blocks, task_id)
    except Exception as exc:
        log.warning("couldn't rewrite the blocks of task %s: %s", task_id, exc)


def _write(result: Plan, movable: list[Block], at: datetime) -> tuple[int, int]:
    """Make the calendar match the plan. -> (added, removed)."""
    wanted = {(p.task_id, p.start, p.end) for p in result.blocks}
    have = {(b.task_id, b.starts_at, b.ends_at): b for b in movable if b.starts_at >= at}
    gone = [b for key, b in have.items() if key not in wanted]
    new = [p for p in result.blocks if (p.task_id, p.start, p.end) not in have]
    if not (gone or new):
        return 0, 0
    cal_id = gcal.blocks_calendar()
    for b in gone:
        if b.gcal_id:
            gcal.delete(b.gcal_id, calendar=cal_id)
        with session() as s:
            s.get(Block, b.id).status = "removed"
    with session() as s:
        texts = {t.id: (t.title, block_text(t)) for t in s.scalars(select(Task).where(Task.id.in_({p.task_id for p in new})))}
    for p in new:
        title, text = texts[p.task_id]
        gcal_id, _ = gcal.insert(title, p.start, p.end, calendar=cal_id, mark="block", description=text)
        with session() as s:
            s.add(Block(task_id=p.task_id, starts_at=p.start, ends_at=p.end, gcal_id=gcal_id))
    return len(new), len(gone)


def _plan_now(force: bool) -> str | None:
    """One full sync (blocking: runs in a thread). -> a line for the log, or None if nothing changed."""
    at = now()
    r = rules()
    busy = refresh_calendar(at - timedelta(days=1), at + timedelta(days=r.horizon_days + 1))
    work, all_busy, kept, movable, fingerprint = _inputs(at, busy)
    state = settings.get(STATE_KEY, {})
    if not force and state.get("fingerprint") == fingerprint:
        return None
    result = plan(work, all_busy, now=at, rules=r, tz=get_config().tz, kept=kept)
    added, removed = _write(result, movable, at)
    settings.put(STATE_KEY, {"fingerprint": fingerprint, "planned_at": at.isoformat(),
                             "short": {str(k): v for k, v in result.short.items()}})
    if not (added or removed or result.short != {int(k): v for k, v in state.get("short", {}).items()}):
        return None
    parts = [f"บล็อกใหม่ {added}"] + ([f"เอาออก {removed}"] if removed else [])
    if result.short:
        with session() as s:
            names = {t.id: t.title for t in s.scalars(select(Task).where(Task.id.in_(result.short)))}
        parts.append("เวลาไม่พอ: " + ", ".join(f"{names.get(k, k)} ขาด {v // 60} ชม. {v % 60} นาที".replace(" 0 นาที", "")
                                               for k, v in result.short.items()))
    return " · ".join(parts)


async def run(force: bool = False) -> str | None:
    """The "schedule" round (and the วางตารางใหม่ button with force=True)."""
    async with lock:
        try:
            return await asyncio.to_thread(_plan_now, force)
        except google.NeedsConsent as exc:
            return f"ข้าม: {exc}"


async def replan_now(via: tuple[str, str] = ("หน้าเว็บ", "")) -> str:
    """You pressed วางตารางใหม่: plan from scratch even if nothing changed, and record it."""
    line = await run(force=True) or "ตารางเดิมยังดีอยู่ ไม่มีอะไรต้องย้าย"
    actions.record("schedule.plan", "วางตารางใหม่", line, source_label=via[0], source_url=via[1])
    return line


def setup() -> None:
    from app.core import clock
    clock.attach("schedule", run)
