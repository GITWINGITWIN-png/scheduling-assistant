"""เทียบแผนกับที่ทำจริง (3.1 with 4.1, B6): did you work in the blocks the planner set aside?

After every read of ActivityWatch, each block that has ended (and wasn't checked yet) gets one of:
- done: at least HALF of the block on its task;
- missed: not that, though you were at the computer at least half of it. You were on something
  else; `instead` says what (the project or category that took most of it);
- away: you weren't at the computer most of the block. It may well have been done offline
  (reading, a lab), so it still counts as done and isn't said to be missed;
- unknown: the recorder wasn't running for most of it (switched off, paused, not yet installed).
  Nothing is decided, and it counts as done as before B6.

What counts as "on its task", by rules:
- a task of a project (B5's จองเวลา, an idea group made a task, the projects' inbox): time on that project;
- a Classroom task: time sorted as เรียน; an email task: time on mail;
- any task: a window whose title has a word of the task's title (latin words of 3+ letters
  standing alone, Thai words of 3+ characters).

What it changes: the planner counts a missed block as only the minutes you worked on it, so the
rest of the task's time goes back to it and the next plan books it again (schedule/sync.py).
The evening review tells the missed ones, and offers ย้ายไปพรุ่งนี้ (Task.not_before).
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core import actions
from app.core.db import now, session
from app.core.tables import Block, Task
from app.features.time.categorize import CATEGORIES
from app.features.time.tables import Activity

log = logging.getLogger(__name__)

HALF = 0.5
SETTLE = timedelta(minutes=2)  # a block is checked once the read has gone this far past its end
GIVE_UP = timedelta(days=2)  # a block older than this that was never read stays unchecked
STOP = {"the", "and", "for", "with", "from", "into", "งาน", "ส่ง", "ทำ"}
SOURCE_CATEGORY = {"classroom": "study", "email": "chat"}

Span = tuple[datetime, datetime]


def overlap(a: Span, spans: list[Span]) -> float:
    """Minutes of `a` covered by `spans` (which don't overlap each other)."""
    return sum(max(0.0, (min(a[1], e) - max(a[0], s)).total_seconds()) for s, e in spans) / 60


def words(title: str) -> list[str]:
    """The words of a task's title the rules look for in window titles."""
    out = []
    for w in re.split(r"[\s:·,()\[\]/|\-–—]+", title.lower()):
        w = w.strip(".'\"")
        latin = re.fullmatch(r"[a-z0-9_.+#]+", w) is not None
        if w and w not in STOP and len(w) >= 3 and (not latin or re.search(r"[a-z]", w)):
            out.append(w)
    return out


def matches(task: Task, row: Activity, title_words: list[str]) -> bool:
    if task.project and row.project.lower() == task.project.lower():
        return True
    if SOURCE_CATEGORY.get(task.source) == row.category:
        return True
    text = row.title.lower()
    for w in title_words:
        if re.fullmatch(r"[a-z0-9_.+#]+", w):
            if re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text):
                return True
        elif w in text:
            return True
    return False


def judge(block: Block, task: Task, rows: list[Activity], present: list[Span], covered: list[Span]) -> tuple[str, int, int, str]:
    """-> (outcome, worked minutes, present minutes, what instead)."""
    span = (block.starts_at, block.ends_at)
    length = (span[1] - span[0]).total_seconds() / 60
    if length <= 0:
        return "unknown", 0, 0, ""
    if overlap(span, covered) < HALF * length:
        return "unknown", 0, 0, ""
    tw = words(task.title)
    worked, other = 0.0, defaultdict(float)
    for r in rows:
        m = overlap(span, [(r.start, r.end)])
        if m <= 0:
            continue
        if matches(task, r, tw):
            worked += m
        else:
            other[r.project or CATEGORIES.get(r.category or "other", "อื่นๆ")] += m
    here = overlap(span, present)
    if worked >= HALF * length:
        return "done", round(worked), round(here), ""
    if here >= HALF * length:
        instead = max(other, key=other.get) if other else ""
        return "missed", round(worked), round(here), instead
    return "away", round(worked), round(here), ""


def check(upto: datetime, present=None, covered=None) -> list[int]:
    """Judge the blocks that ended before `upto` (the last read's end) and weren't checked yet.
    What you worked on comes from what's kept (every read has filled it); whether you were at the
    computer, and whether the recorder ran, is asked of ActivityWatch for each block's own span
    (present / covered: aw's functions; tests give their own). -> the missed blocks' ids."""
    from app.connectors import activitywatch as aw
    from app.features.time import privacy

    present, covered = present or aw.present, covered or aw.covered
    pauses = privacy.pauses()
    upto = upto - SETTLE
    missed = []
    with session() as s:
        blocks = s.scalars(select(Block).where(Block.status.in_(("planned", "pinned")), Block.outcome == "",
                                               Block.ends_at <= upto, Block.ends_at > upto - GIVE_UP)).all()
        if not blocks:
            return []
        lo, hi = min(b.starts_at for b in blocks), max(b.ends_at for b in blocks)
        rows = s.scalars(select(Activity).where(Activity.end > lo, Activity.start < hi).order_by(Activity.start)).all()
        tasks = {t.id: t for t in s.scalars(select(Task).where(Task.id.in_({b.task_id for b in blocks})))}
        for b in blocks:
            cut = lambda spans: [p for a, z in spans for p in privacy.cut_pauses(a, z, pauses)]  # noqa: E731
            here, ran = cut(present(b.starts_at, b.ends_at)), cut(covered(b.starts_at, b.ends_at))
            outcome, worked, minutes_here, instead = judge(b, tasks[b.task_id], rows, here, ran)
            b.outcome, b.worked_minutes, b.present_minutes, b.instead = outcome, worked, minutes_here, instead
            if outcome == "missed":
                missed.append(b.id)
    if missed:
        log.info("blocks missed: %s", missed)
    return missed


async def after_read(read) -> None:
    """pull.READ hook: right after a read, while ActivityWatch is known to answer."""
    import asyncio

    await asyncio.to_thread(check, read.end)


def counted_minutes(b: Block) -> int:
    """How much of a past block counts as work done on its task (the planner's view)."""
    full = int((b.ends_at - b.starts_at).total_seconds() // 60)
    return min(full, b.worked_minutes or 0) if b.outcome == "missed" else full


def mark_done(block_id: int, *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    """นับว่าทำแล้ว: you did it away from what the rules could see. -> action id."""
    with session() as s:
        b = s.get(Block, block_id)
        if b is None:
            raise ValueError("ไม่พบบล็อกนี้")
        old = (b.outcome, b.instead)
        b.outcome, b.instead = "done", ""
        title = s.get(Task, b.task_id).title
    return actions.record("block.done", f"นับว่าทำแล้ว: {title}", "บล็อกนี้ไม่นับว่าหลุด", source_label=via[0], source_url=via[1],
                          undo={"block_id": block_id, "outcome": old[0], "instead": old[1]})


def tomorrow_start(at: datetime) -> datetime:
    from app.core.config import get_config
    from app.core.timefmt import local

    d = local(at).date() + timedelta(days=1)
    return datetime.combine(d, datetime.min.time(), get_config().tz)


def move_to_tomorrow(task_id: int, *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    """ย้ายไปพรุ่งนี้: the task's time is booked from tomorrow on. -> action id."""
    with session() as s:
        t = s.get(Task, task_id)
        if t is None or t.status != "open":
            raise ValueError("ไม่พบงานนี้ หรือปิดไปแล้ว")
        old = t.not_before.isoformat() if t.not_before else None
        t.not_before = tomorrow_start(now())
        title = t.title
    return actions.record("task.tomorrow", f"ย้ายไปพรุ่งนี้: {title}", "เลขาจะหาเวลาใหม่ตั้งแต่พรุ่งนี้", source_label=via[0],
                          source_url=via[1], undo={"task_id": task_id, "not_before": old})


async def _undo_done(undo: dict) -> None:
    with session() as s:
        if (b := s.get(Block, undo["block_id"])) is not None:
            b.outcome, b.instead = undo["outcome"], undo["instead"]


async def _undo_tomorrow(undo: dict) -> None:
    with session() as s:
        if (t := s.get(Task, undo["task_id"])) is not None:
            t.not_before = datetime.fromisoformat(undo["not_before"]) if undo["not_before"] else None


actions.register_undo("block.done", _undo_done)
actions.register_undo("task.tomorrow", _undo_tomorrow)


# ------------------------------------------------------------------ for the pages and the briefs
def day_blocks(start: datetime, end: datetime) -> list[tuple[Block, Task]]:
    with session() as s:
        got = s.execute(select(Block, Task).join(Task, Task.id == Block.task_id)
                        .where(Block.status.in_(("planned", "pinned")), Block.starts_at < end, Block.ends_at > start)
                        .order_by(Block.starts_at)).all()
        s.expunge_all()
    return [(b, t) for b, t in got]


def followed(start: datetime, end: datetime) -> dict:
    """How much of the plan you followed in [start, end): blocks checked, done, missed, away."""
    got = day_blocks(start, end)
    judged = [(b, t) for b, t in got if b.outcome in ("done", "missed", "away")]
    done = [x for x in judged if x[0].outcome == "done"]
    missed = [x for x in judged if x[0].outcome == "missed"]
    away = [x for x in judged if x[0].outcome == "away"]
    counted = len(done) + len(missed)
    return {"checked": len(judged), "done": done, "missed": missed, "away": away,
            "percent": round(100 * len(done) / counted) if counted else None}


# The parts of a day a pattern is about, and the hours a rule keeps free for each.
PARTS = {"เช้า": ("06:00", "12:00"), "บ่าย": ("12:00", "17:00"), "เย็น": ("17:00", "23:59")}
WEEKDAYS = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์", "วันเสาร์", "วันอาทิตย์"]


def part_of(hour: int) -> str:
    return "เช้า" if hour < 12 else "บ่าย" if hour < 17 else "เย็น"


def patterns(at: datetime, weeks: int = 4) -> list[dict]:
    """ข้อสังเกต (W5 ⑥): a part of a weekday where blocks were missed in 2 or more of the last weeks.
    -> [{weekday, part, weeks, title, sub, avoided}] (avoided: a rule of yours already keeps it free)."""
    from app.core.rules import book
    from app.core.timefmt import local

    start = at - timedelta(weeks=weeks)
    seen: dict[tuple[int, str], set] = defaultdict(set)
    for b, _ in day_blocks(start, at):
        if b.outcome != "missed":
            continue
        when = local(b.starts_at)
        seen[(when.weekday(), part_of(when.hour))].add(when.isocalendar()[:2])
    have = {(int(a["weekday"]), a["from"], a["to"]) for a in book.block_avoid()}
    out = []
    for (weekday, part), wks in sorted(seen.items(), key=lambda kv: -len(kv[1])):
        if len(wks) >= 2:
            avoided = (weekday, *PARTS[part]) in have
            out.append({"weekday": weekday, "part": part, "weeks": len(wks), "avoided": avoided,
                        "title": f"{part}{WEEKDAYS[weekday]}หลุดแผน {len(wks)} สัปดาห์",
                        "sub": ("เลขาไม่วางบล็อกช่วงนี้แล้ว (กติกาในสมุดกติกา)" if avoided else
                                "ช่วงนี้อาจไม่เหมาะกับบล็อกงาน · ให้เลขาไม่วางบล็อกช่วงนี้ หรือย้ายเองใน Google Calendar")})
    return out[:3]


def avoid_rule(weekday: int, part: str, *, via: tuple[str, str] = ("หน้าตาราง", "")) -> tuple[int, int]:
    """"ไม่วางบล็อกงานบ่ายวันอังคาร": a rule of yours the planner follows (book.block_avoid).
    -> (rule id, action id)."""
    from app.core.rules import book

    if part not in PARTS or not 0 <= weekday <= 6:
        raise ValueError("ไม่รู้จักช่วงนี้")
    lo, hi = PARTS[part]
    if any(int(a["weekday"]) == weekday and (a["from"], a["to"]) == (lo, hi) for a in book.block_avoid()):
        raise ValueError("มีกติกานี้อยู่แล้ว")
    return book.add(f"ไม่วางบล็อกงาน{part}{WEEKDAYS[weekday]} ({lo}–{hi})", ["planner"],
                    effect={"type": "block_avoid", "weekday": weekday, "from": lo, "to": hi}, via=via)


def focus_rule(start: str, end: str, *, via: tuple[str, str] = ("หน้าตาราง", "")) -> tuple[int, int]:
    """"วางบล็อกงานช่วงโฟกัส 09:00–11:30 ก่อน": the planner fills these hours first each day.
    -> (rule id, action id). An older focus rule stays in the book; the newest one is used."""
    from datetime import time as _time

    from app.core.rules import book

    lo, hi = _time.fromisoformat(start), _time.fromisoformat(end)
    if not lo < hi:
        raise ValueError("ช่วงโฟกัสต้องเริ่มก่อนจบ")
    return book.add(f"วางบล็อกงานช่วงโฟกัส {lo:%H:%M}–{hi:%H:%M} ก่อนช่วงอื่น (ไม่รวมงานตอบอีเมล)", ["planner"],
                    effect={"type": "focus_first", "from": f"{lo:%H:%M}", "to": f"{hi:%H:%M}"}, via=via)
