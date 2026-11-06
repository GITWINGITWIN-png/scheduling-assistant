"""The secretary's advice from each project's PROGRESS.md (2.4, W3 ⑤).

Two kinds, best first (potential, then urgency):

- นิ่งนาน: PROGRESS.md still has unchecked steps, but nothing moved for STALE_DAYS. It says
  the next step, and the due date when the project has an open task with one.
- ได้เวลาน้อยกว่าที่ควร: a project that matters (potential S–A or urgency 4–5) got less time
  in this week's schedule than its target (WEEKLY_TARGET; S = 10 hours as in the W3 mockup).
  The time is the blocks the planner booked for the project's tasks (planned or pinned), as
  said at the B5 plan; real hours come with ActivityWatch in B6. No commit in 14 days is
  added to the line as a hint, not counted.

"จองเวลา" turns a piece of advice into a task (2 hours by default), so the planner books a
block for it; like any task you add, it is recorded and can be undone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from sqlalchemy import select

from app.core.db import now, session
from app.core.config import get_config
from app.core.tables import Block, Task
from app.core.timefmt import MONTHS, local
from app.features.projects.tables import Project

STALE_DAYS = 7
WEEKLY_TARGET = {"S": 10, "A": 6}  # hours a week in the schedule (S from the W3 mockup)
URGENT_TARGET = 4  # hours a week for urgency 4–5 when the potential is lower than A
ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "F": 5}


@dataclass
class Advice:
    project_id: int
    project: str
    kind: str  # stale · short
    title: str
    detail: str
    next: str  # the next step in its PROGRESS.md ("" when it has none)
    due: datetime | None


def target(p: Project) -> int:
    """Hours a week a project should get in the schedule; 0 for one that doesn't matter."""
    return WEEKLY_TARGET.get(p.potential) or (URGENT_TARGET if p.urgency >= 4 else 0)


def week(at: datetime) -> tuple[datetime, datetime]:
    """Monday 00:00 to the next Monday, in local time."""
    tz = get_config().tz
    monday = at.astimezone(tz).date() - timedelta(days=at.astimezone(tz).weekday())
    start = datetime.combine(monday, time(0), tz)
    return start, start + timedelta(days=7)


def booked_minutes(s, at: datetime) -> dict[str, int]:
    """Minutes of this week's blocks per project (from its tasks)."""
    lo, hi = week(at)
    rows = s.execute(select(Task.project, Block.starts_at, Block.ends_at).join(Task, Task.id == Block.task_id)
                     .where(Task.project != "", Block.status.in_(("planned", "pinned")),
                            Block.starts_at < hi, Block.ends_at > lo)).all()
    out: dict[str, int] = {}
    for project, start, end in rows:
        out[project] = out.get(project, 0) + int((min(end, hi) - max(start, lo)).total_seconds() // 60)
    return out


def _hours(minutes: int) -> str:
    h = minutes / 60
    return f"{h:.0f}" if h == int(h) else f"{h:.1f}"


def advice(at: datetime | None = None) -> list[Advice]:
    at = at or now()
    out: list[Advice] = []
    with session() as s:
        projects = s.scalars(select(Project).where(Project.hidden.is_(False), Project.missing.is_(False),
                                                   Project.status != "done")).all()
        dues = {}
        for t in s.scalars(select(Task).where(Task.status == "open", Task.project != "", Task.due_at.is_not(None))):
            if t.project not in dues or t.due_at < dues[t.project]:
                dues[t.project] = t.due_at
        booked = booked_minutes(s, at)
        for p in projects:
            prog = p.progress or {}
            idle = (at - p.last_activity).days if p.last_activity else None
            due = dues.get(p.name)
            due_words = f"แต่ส่ง {local(due).day} {MONTHS[local(due).month - 1]}" if due else ""
            if prog.get("todo") and idle is not None and idle >= STALE_DAYS:
                out.append(Advice(p.id, p.name, "stale", f"{p.name} นิ่ง {idle} วัน",
                                  " · ".join(x for x in (due_words, f"ขั้นถัดไป: {prog.get('next', '')}" if prog.get("next") else "") if x),
                                  prog.get("next", ""), due))
            elif (goal := target(p)) and (got := booked.get(p.name, 0)) < goal * 60:
                hint = " · 2 สัปดาห์ไม่มี commit" if p.is_git and p.commits_14d == 0 else ""
                out.append(Advice(p.id, p.name, "short", f"{p.name} potential {p.potential} · เร่งด่วน {p.urgency}",
                                  f"สัปดาห์นี้ได้เวลาในตาราง {_hours(got)} ชม. ต่ำกว่าเป้า {goal} ชม.{hint}",
                                  prog.get("next", ""), due))
        rank = {p.id: (ORDER.get(p.potential, 9), -p.urgency) for p in projects}
    return sorted(out, key=lambda a: rank[a.project_id])


def book(project_id: int, minutes: int = 120, *, via: tuple[str, str] = ("หน้าโปรเจค", "")) -> int:
    """จองเวลา: a task for the project's next step, no due date, so the planner books the first
    free time ("จองบล็อก 2 ชม. พรุ่งนี้เช้า" in the mockup). -> task id."""
    from app.features.schedule import tasks

    with session() as s:
        p = s.get(Project, project_id)
        if p is None:
            raise ValueError("ไม่พบโปรเจคนี้")
        nxt = (p.progress or {}).get("next", "")
        name = p.name
    task_id, _ = tasks.add(f"{name}: {nxt or 'ทำต่อ'}", est_minutes=minutes, via=via,
                           details=f"จากคำแนะนำของเลขา · ขั้นถัดไปใน PROGRESS.md ของ {name}" if nxt else "")
    with session() as s:
        t = s.get(Task, task_id)
        t.project, t.source = name, "project"
    return task_id
