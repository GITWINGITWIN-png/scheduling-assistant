"""The planner (ตัววางตาราง, feature 3.1): where each task's work goes. Pure: no Google, no database.

Given the work still to do, the times you're busy and your rules, `plan()` returns work
blocks. sync.py feeds it from the calendar and writes the result back, and
tests/test_planner.py checks it. Everything here is plain arithmetic on times, so a
plan costs no tokens and the same inputs always give the same blocks.

How it decides:

1. Free time = each day's window (09:00–22:00 by default) from now to the horizon
   (14 days), minus busy events with a gap kept around them (15 minutes).
2. Tasks with a due date go first, earliest due date first; tasks without one get
   what's left, oldest first.
3. "early" (the default): fill the earliest free time, so the work is done as soon as
   your free time allows, normally days before it's due. (An explicit "finish a day
   early" target was tried and removed: filling earliest-first already gives exactly
   that whenever it's possible, and the tests showed the target changed nothing.)
   "late" (on request): fill the free time closest to the due date, working backwards.
4. A block is 30–120 minutes and starts on a quarter hour. One task gets at most 3 hours
   a day, so big work spreads over several days instead of eating one. A task can set its
   own longest block and daily limit (`Work.max_block`, `Work.per_day`); the rules are
   only the default. Blocks already fixed (`kept`: running, about to start, or moved by
   you) count towards their task's daily limit too. Two blocks of the same task are never
   back to back: the gap (15 minutes) is kept between them as a break, otherwise "1-hour
   blocks" would just be one long sitting.
5. Whatever doesn't fit before the due date is reported (`Plan.short`), never placed late.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Rules:
    day_start: time = time(9, 0)
    day_end: time = time(22, 0)
    min_block: int = 30  # minutes
    max_block: int = 120
    gap: int = 15  # minutes kept free before and after each busy event
    per_task_per_day: int = 180  # minutes one task may take in a day
    horizon_days: int = 14
    step: int = 15  # blocks start on multiples of this many minutes


@dataclass(frozen=True)
class Work:
    task_id: int
    minutes: int  # still to place
    due: datetime | None = None
    mode: str = "early"  # early · late
    max_block: int | None = None  # this task's longest block (minutes); None: rules.max_block
    per_day: int | None = None  # the most this task may take in a day; None: rules.per_task_per_day


@dataclass(frozen=True)
class Placed:
    task_id: int
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass
class Plan:
    blocks: list[Placed] = field(default_factory=list)
    short: dict[int, int] = field(default_factory=dict)  # task id -> minutes that didn't fit in time


Interval = tuple[datetime, datetime]


def _ceil(t: datetime, step: int) -> datetime:
    """Round up to the next multiple of `step` minutes (seconds dropped)."""
    t = t.replace(second=0, microsecond=0) + (timedelta(minutes=1) if t.second or t.microsecond else timedelta())
    extra = t.minute % step
    return t + timedelta(minutes=step - extra) if extra else t


def _floor(t: datetime, step: int) -> datetime:
    t = t.replace(second=0, microsecond=0)
    return t - timedelta(minutes=t.minute % step)


def free_time(busy: list[Interval], *, now: datetime, rules: Rules, tz: ZoneInfo) -> list[Interval]:
    """The free intervals from now to the horizon, inside each day's window, away from busy time."""
    start = _ceil(now.astimezone(tz), rules.step)
    today = start.date()
    gap = timedelta(minutes=rules.gap)
    blocked = sorted((s.astimezone(tz) - gap, e.astimezone(tz) + gap) for s, e in busy)
    out: list[Interval] = []
    for i in range(rules.horizon_days):
        day = today + timedelta(days=i)
        lo = max(datetime.combine(day, rules.day_start, tz), start)
        hi = datetime.combine(day, rules.day_end, tz)
        for b_start, b_end in blocked:
            if b_end <= lo or b_start >= hi:
                continue
            if b_start > lo:
                out.append((lo, b_start))
            lo = max(lo, b_end)
        if lo < hi:
            out.append((lo, hi))
    return [(s, e) for s, e in out if e > s]


def _take(free: list[Interval], piece: Interval) -> None:
    """Remove `piece` from the free list (it lies inside one interval)."""
    for i, (s, e) in enumerate(free):
        if s <= piece[0] and piece[1] <= e:
            rest = [(s, piece[0]), (piece[1], e)]
            free[i:i + 1] = [(a, b) for a, b in rest if b > a]
            return
    raise ValueError("piece is not free")


def _length(room: int, remaining: int, day_left: int, longest: int, rules: Rules) -> int:
    """How long the next block can be (0 = none here)."""
    length = min(longest, remaining, room, day_left)
    if length < remaining:  # not the last piece: keep it on the quarter-hour grid
        length -= length % rules.step
    # A short leftover may be shorter than a normal block, and so may every block of a task
    # whose own longest block is under the rules' minimum (you asked for 15-minute pieces).
    smallest = min(rules.min_block, longest, remaining)
    return length if length >= smallest else 0


def _fill(work: Work, free: list[Interval], until: datetime, remaining: int, used: dict[tuple[int, date], int],
          rules: Rules, *, backwards: bool) -> tuple[list[Placed], int]:
    placed: list[Placed] = []
    longest = work.max_block or rules.max_block
    per_day = work.per_day or rules.per_task_per_day
    order = sorted(free, reverse=backwards)
    for s, e in order:
        if remaining <= 0:
            break
        e = min(e, until)
        while remaining > 0 and e > s:
            if backwards:
                end = _floor(e, rules.step)  # e.g. due 16:59 -> the block ends 16:45
                room = int((end - _ceil(s, rules.step)).total_seconds() // 60)
                day = (end - timedelta(minutes=1)).date()
            else:
                begin = _ceil(s, rules.step)
                room = int((e - begin).total_seconds() // 60)
                day = begin.date()
            day_left = per_day - used.get((work.task_id, day), 0)
            length = _length(room, remaining, day_left, longest, rules)
            if length <= 0:
                break
            if backwards:
                piece = (end - timedelta(minutes=length), end)
                e = piece[0] - timedelta(minutes=rules.gap)  # a break before this task's next block
            else:
                piece = (begin, begin + timedelta(minutes=length))
                s = piece[1] + timedelta(minutes=rules.gap)
            _take(free, piece)
            used[(work.task_id, day)] = used.get((work.task_id, day), 0) + length
            placed.append(Placed(work.task_id, *piece))
            remaining -= length
    return placed, remaining


def plan(work: list[Work], busy: list[Interval], *, now: datetime, rules: Rules = Rules(),
         tz: ZoneInfo = ZoneInfo("Asia/Bangkok"), kept: list[Placed] = ()) -> Plan:
    """Blocks for all the work, in the free time around `busy`. See the module docstring.

    `kept` are blocks that stay where they are (their time is already in `busy`); they only
    count towards their task's limit for that day."""
    free = free_time(busy, now=now, rules=rules, tz=tz)
    horizon = datetime.combine(_ceil(now.astimezone(tz), rules.step).date() + timedelta(days=rules.horizon_days),
                               time(0), tz)
    used: dict[tuple[int, date], int] = {}
    for b in kept:
        day = (b.task_id, b.start.astimezone(tz).date())
        used[day] = used.get(day, 0) + b.minutes
    result = Plan()
    ordered = sorted(work, key=lambda w: (w.due is None, w.due or horizon, w.task_id))
    for w in ordered:
        if w.minutes <= 0:
            continue
        due = min(w.due.astimezone(tz), horizon) if w.due else horizon
        backwards = w.mode == "late" and w.due is not None  # "late" without a due date means nothing
        blocks, left = _fill(w, free, due, w.minutes, used, rules, backwards=backwards)
        result.blocks += blocks
        if left > 0 and w.due and w.due.astimezone(tz) <= horizon:
            result.short[w.task_id] = left
    result.blocks.sort(key=lambda b: b.start)
    return result
