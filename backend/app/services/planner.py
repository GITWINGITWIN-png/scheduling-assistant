"""The backward planner (M4) — deterministic core.

Given a project's remaining effort and deadline, it finds the free gaps in your
calendar and lays down work blocks before the deadline. This core is pure Python
(no Claude tokens, instant, predictable). A Claude layer can later sit *on top*
to reprioritize across projects — but the gap-filling math lives here.

Constraints (all tunable): a daily working window, a fixed block length, a daily
cap per project, and it never overlaps an existing event.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from app.services import calendar as cal

# Sensible defaults; the endpoint/UI can override these.
DEFAULTS = {
    "work_start": 9,          # earliest hour to schedule (local time)
    "work_end": 21,           # latest hour a block may end
    "block_hours": 1.5,       # length of one work block
    "max_hours_per_day": 3.0, # cap per project per day, so it spreads out
}


def _busy_intervals(events: list[dict], tz) -> list[tuple[datetime, datetime]]:
    """Turn Google events into sorted (start, end) busy intervals in `tz`.

    All-day events (date only, no time) are skipped — they don't block a
    particular hour of the day.
    """
    intervals: list[tuple[datetime, datetime]] = []
    for e in events:
        start = e.get("start", {}).get("dateTime")
        end = e.get("end", {}).get("dateTime")
        if not start or not end:
            continue
        intervals.append(
            (datetime.fromisoformat(start).astimezone(tz),
             datetime.fromisoformat(end).astimezone(tz))
        )
    intervals.sort()
    return intervals


def _free_intervals(window_start, window_end, busy):
    """Gaps inside [window_start, window_end] not covered by `busy`."""
    free: list[tuple[datetime, datetime]] = []
    cursor = window_start
    for bs, be in busy:
        if be <= cursor or bs >= window_end:
            continue
        bs, be = max(bs, window_start), min(be, window_end)
        if bs > cursor:
            free.append((cursor, bs))
        cursor = max(cursor, be)
    if cursor < window_end:
        free.append((cursor, window_end))
    return free


def plan_blocks(
    project_name, hours, deadline, busy, *,
    now, work_start, work_end, block_hours, max_hours_per_day,
):
    """Place `hours` of work into free gaps from `now` until `deadline`.

    Returns proposed blocks plus how many hours we could and couldn't fit. No
    calendar writes happen here — this is a pure proposal you can preview.
    """
    tz = now.tzinfo
    block = timedelta(hours=block_hours)
    blocks: list[dict] = []
    remaining = hours
    day = now.date()
    last_day = deadline.date()

    while remaining > 0 and day <= last_day:
        window_start = max(datetime.combine(day, time(work_start), tzinfo=tz), now)
        window_end = min(datetime.combine(day, time(work_end), tzinfo=tz), deadline)
        if window_start < window_end:
            day_busy = [iv for iv in busy if iv[1] > window_start and iv[0] < window_end]
            day_hours = 0.0
            for free_start, free_end in _free_intervals(window_start, window_end, day_busy):
                cursor = free_start
                while (
                    remaining > 0
                    and day_hours < max_hours_per_day
                    and cursor + block <= free_end
                ):
                    blocks.append({
                        "title": f"Work: {project_name}",
                        "start": cursor.isoformat(),
                        "end": (cursor + block).isoformat(),
                    })
                    cursor += block
                    remaining -= block_hours
                    day_hours += block_hours
                if remaining <= 0 or day_hours >= max_hours_per_day:
                    break
        day += timedelta(days=1)

    return {
        "blocks": blocks,
        "hours_scheduled": round(hours - max(remaining, 0.0), 2),
        "hours_unscheduled": round(max(remaining, 0.0), 2),
    }


def free_slots(now, until, busy, *, work_start, work_end, block_hours):
    """Project-agnostic list of block-sized free slots from `now` to `until`.

    The deterministic core owns this (real gaps in the working window); the
    Claude layer then chooses which project fills which slot, so the model picks
    from a fixed menu of real times instead of inventing them.
    """
    tz = now.tzinfo
    block = timedelta(hours=block_hours)
    slots: list[tuple[datetime, datetime]] = []
    day = now.date()
    last_day = until.date()

    while day <= last_day:
        window_start = max(datetime.combine(day, time(work_start), tzinfo=tz), now)
        window_end = min(datetime.combine(day, time(work_end), tzinfo=tz), until)
        if window_start < window_end:
            day_busy = [iv for iv in busy if iv[1] > window_start and iv[0] < window_end]
            for free_start, free_end in _free_intervals(window_start, window_end, day_busy):
                cursor = free_start
                while cursor + block <= free_end:
                    slots.append((cursor, cursor + block))
                    cursor += block
        day += timedelta(days=1)

    return slots


def make_plan(project, *, now: datetime | None = None, **overrides) -> dict:
    """Build a plan for one project, reading its deadline + the live calendar."""
    now = now or datetime.now().astimezone()  # aware, local timezone

    if not project.deadline:
        return {"error": "This project has no deadline to plan toward."}
    if not project.estimated_hours or project.estimated_hours <= 0:
        return {"error": "This project has no estimated hours to schedule."}

    # Stored deadlines are naive; interpret them in the user's local timezone.
    deadline = project.deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=now.tzinfo)
    if deadline <= now:
        return {"error": "This project's deadline has already passed."}

    events = cal.list_events(now, deadline, max_results=250)
    busy = _busy_intervals(events, now.tzinfo)

    opts = {**DEFAULTS, **overrides}
    result = plan_blocks(
        project.name, project.estimated_hours, deadline, busy, now=now, **opts
    )
    result["deadline"] = deadline.isoformat()
    return result
