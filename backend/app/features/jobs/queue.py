"""The background work queue (2.2, 3.2, B5.6): where each project is stuck, as a job.

A job comes from one of two places (the user's answers at the B5 plan):

- the next unchecked step in the PROGRESS.md of a project you switched to "ให้เลขาทำต่อได้"
  (where a project is stuck comes from its PROGRESS.md only);
- ทำต่อ, which you press for such a project, with a note on what to do if you like.

One open job per project at a time. The queue is in the order the projects matter: potential
S first, then urgency 5 first, then the oldest.

A step is taken up by itself once: when its job ended (done but not merged yet, stopped,
failed) or you said no (ไม่เอา, or took it out of the queue), the queue doesn't bring the same
step back every night; ทำต่อ always can. A project that leaves the gate (switched off, hidden,
gone, finished) pauses its waiting job, and the job comes back when the project does.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core import actions
from app.core.db import now, session
from app.core.tables import Decision
from app.features.jobs.tables import Job
from app.features.projects.scan import is_self
from app.features.projects.tables import Project

OPEN = ("queued", "asking", "ready", "running")  # a project has at most one of these
WAITING = ("queued", "asking", "ready")  # not started yet: these can still be dropped or paused
ENDED = ("done", "stopped", "failed", "rejected", "dropped")  # its step isn't taken up by itself again
ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "F": 5}

Via = tuple[str, str]


def close_ask(s, job: Job) -> None:
    """A job left the queue while its plan waited for you: the request is withdrawn too."""
    if job.decision_id and (d := s.get(Decision, job.decision_id)) is not None and d.status == "pending":
        d.status, d.answered_at = "cancelled", now()


def blocked(p: Project | None) -> str:
    """Why the secretary may not work on this project in the background ("" when it may)."""
    if p is None:
        return "ไม่พบโปรเจคนี้"
    if is_self(p.path):
        return "เลขาไม่แก้โค้ดของตัวเองขณะทำงาน"
    if p.missing or p.hidden:
        return "โปรเจคนี้ถูกซ่อนหรือโฟลเดอร์หายไป"
    if p.status == "done":
        return "โปรเจคนี้จบแล้ว"
    if not p.is_git:
        return "โปรเจคนี้ไม่มี git จึงไม่มี branch ให้ทำงานแยก"
    if not p.allow_jobs:
        return "ยังไม่ได้เปิด “ให้เลขาทำต่อได้” ที่หน้าโปรเจค"
    return ""


def replan(job: Job) -> None:
    """Back to the start of the queue: the plan has to be made (and checked) again."""
    job.status, job.title, job.steps, job.planned_at, job.decision_id = "queued", "", [], None, None
    job.rule_ok, job.rule_why, job.approved_until, job.result = None, "", None, ""


def refresh(at: datetime | None = None) -> list[int]:
    """Bring the queue up to date with the projects. -> the ids of the new jobs."""
    at = at or now()
    new: list[int] = []
    with session() as s:
        open_by = {j.project_id: j for j in s.scalars(select(Job).where(Job.status.in_(OPEN)))}
        paused_by = {j.project_id: j for j in s.scalars(select(Job).where(Job.status == "paused").order_by(Job.id))}
        ended = set(s.execute(select(Job.project_id, Job.stuck_at).where(Job.status.in_(ENDED), Job.source == "progress")).all())
        for p in s.scalars(select(Project)):
            job = open_by.get(p.id)
            if why := blocked(p):
                if job is not None and job.status in WAITING:
                    job.status, job.result = "paused", why
                    close_ask(s, job)
                continue
            nxt = (p.progress or {}).get("next", "")
            if job is None and (paused := paused_by.get(p.id)) is not None:
                replan(paused)  # the project is back: so is its job (planned again, things may have moved)
                if paused.source == "progress" and nxt:
                    paused.stuck_at = nxt
            elif job is None and nxt and (p.id, nxt) not in ended:
                job = Job(project_id=p.id, project=p.name, source="progress", stuck_at=nxt, created_at=at)
                s.add(job)
                s.flush()
                new.append(job.id)
            elif job is not None and job.status == "queued" and job.source == "progress" and nxt and job.stuck_at != nxt:
                job.stuck_at = nxt  # the project moved on before the job was planned
    return new


def add(project_id: int, note: str = "", *, via: Via = ("หน้างานเบื้องหลัง", "")) -> tuple[int, int]:
    """ทำต่อ: a job for this project now (its next step, and your note). -> (job id, action id)."""
    with session() as s:
        p = s.get(Project, project_id)
        if why := blocked(p):
            raise ValueError(why)
        if s.scalar(select(Job.id).where(Job.project_id == project_id, Job.status.in_(OPEN))):
            raise ValueError(f"{p.name} มีงานอยู่ในคิวแล้ว")
        for old in s.scalars(select(Job).where(Job.project_id == project_id, Job.status == "paused")):
            old.status, old.result = "dropped", "แทนด้วยคำสั่งทำต่อ"
        nxt = (p.progress or {}).get("next", "")
        if not (nxt or note.strip()):
            raise ValueError("PROGRESS.md ของโปรเจคนี้ไม่มีขั้นที่ค้าง · บอกด้วยว่าให้ทำอะไร")
        job = Job(project_id=p.id, project=p.name, source="you", stuck_at=nxt, note=note.strip()[:1000])
        s.add(job)
        s.flush()
        job_id, name = job.id, p.name
    action_id = actions.record("job.add", "สั่งทำต่อ", f"{name}: {note.strip() or nxt}", source_label=via[0], source_url=via[1],
                               undo={"job_id": job_id})
    return job_id, action_id


def ordered(statuses: tuple[str, ...] = WAITING) -> list[Job]:
    """The queue in its order (detached rows)."""
    with session() as s:
        rows = s.execute(select(Job, Project.potential, Project.urgency).join(Project, Project.id == Job.project_id)
                         .where(Job.status.in_(statuses))).all()
        s.expunge_all()
    rows.sort(key=lambda r: (ORDER.get(r[1], 9), -r[2], r[0].created_at, r[0].id))
    return [r[0] for r in rows]


def drop(job_id: int, *, via: Via = ("หน้างานเบื้องหลัง", "")) -> int:
    """Take a job that hasn't started out of the queue. -> the action id."""
    with session() as s:
        job = s.get(Job, job_id)
        if job is None:
            raise ValueError("ไม่พบงานนี้")
        if job.status not in WAITING:
            raise ValueError("งานนี้เริ่มไปแล้วหรือจบแล้ว")
        old, job.status, job.result = job.status, "dropped", "คุณเอาออกจากคิว"
        close_ask(s, job)
        name = job.project
    return actions.record("job.drop", "เอางานออกจากคิว", name, source_label=via[0], source_url=via[1],
                          undo={"job_id": job_id, "status": old})


async def _undo_add(undo: dict) -> None:
    with session() as s:
        job = s.get(Job, undo["job_id"])
        if job is not None and job.status in WAITING:
            job.status, job.result = "dropped", "ย้อนกลับคำสั่งทำต่อ"
        elif job is not None:
            raise actions.UndoError("งานนี้เริ่มไปแล้ว ย้อนไม่ได้ · หยุดได้ที่หน้างานเบื้องหลัง")


async def _undo_drop(undo: dict) -> None:
    with session() as s:
        job = s.get(Job, undo["job_id"])
        if job is None or job.status != "dropped":
            raise actions.UndoError("งานนี้ไม่ได้อยู่ในสถานะที่ย้อนได้")
        if s.scalar(select(Job.id).where(Job.project_id == job.project_id, Job.status.in_(OPEN))):
            raise actions.UndoError(f"{job.project} มีงานอื่นในคิวแล้ว")
        job.status, job.result = undo["status"], ""
        if job.decision_id and (d := s.get(Decision, job.decision_id)) is not None and d.status == "cancelled":
            d.status, d.answered_at = "pending", None  # its request waits for you again


actions.register_undo("job.add", _undo_add)
actions.register_undo("job.drop", _undo_drop)
