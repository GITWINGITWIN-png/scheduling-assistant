"""Classroom → your task list and course folders (U1). The round "classroom", every 2 hours.

Courses:
- The first sync records every course as **ended** (the user, 2026-11-05: the semester is
  over and every course then had finished), so nothing old turns into tasks.
- A course that appears later, or an ended one with new coursework or materials, is put
  to you in #อนุมัติ: "ติดตามวิชานี้ไหม", with the folder its materials would go to (an
  existing course folder under ~/Projects when one matches, else a new one, which is
  only created once you say yes: "วิชาที่ยังไม่มีโฟลเดอร์ถามก่อนสร้าง").
- Ignored courses are never asked about again.

For each **followed** course:
- every assignment with a due date still ahead becomes a task (source "classroom", 2 h
  by default), so the planner books time for it; once you turn it in, the task closes.
- new materials are downloaded into the course folder (materials.py, B3 step 7).

No model, no tokens.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from sqlalchemy import select

from app.connectors import classroom as cr
from app.connectors import google
from app.core import actions
from app.core.config import get_config
from app.core.db import now, session
from app.core.tables import Decision, Task
from app.features import decisions
from app.features.classroom.tables import Course, CourseItem

log = logging.getLogger(__name__)

MATERIALS_DIR = "สื่อ"  # the subfolder of a course folder that materials go into (the plan: datacom/สื่อ/)
ASKED: list = []  # hooks: async fn(course_id, decision_id) after a course is put to you (cards.py)
AFTER_FOLLOWED: list = []  # hooks: fn(course_id) -> str|None, run for followed courses in the round (materials.py)

lock = asyncio.Lock()


# ------------------------------------------------------------------ which folder
def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def propose_folder(course_name: str) -> tuple[Path, bool]:
    """Where this course's materials would go -> (folder, whether the course folder exists).

    Matches the course name's words against the folders in ~/Projects: "ComSys Lab 2569/1"
    → Comsyslab, "Algorithmic DSP 2569" → DSP, "01204332-2026-OS" → OS. The longest match
    wins ("data mining" over "data"); otherwise a new folder named after the course."""
    words = re.findall(r"[a-z]+", course_name.lower())
    candidates = set(words) | {a + b for a, b in zip(words, words[1:])}
    root = get_config().projects_dir
    best = None
    for d in root.iterdir() if root.exists() else ():
        if not d.is_dir() or d.name.startswith("."):
            continue
        k = _key(d.name)
        if k and (k in candidates or (len(k) >= 5 and any(c.startswith(k) for c in candidates))):
            if best is None or len(k) > len(_key(best.name)):
                best = d
    if best is not None:
        return best / MATERIALS_DIR, True
    safe = re.sub(r'[\\/:*?"<>|]', " ", course_name).strip() or "วิชาใหม่"
    return root / safe / MATERIALS_DIR, False


# ------------------------------------------------------------------ the round
def _latest(course_id: str) -> object:
    """The newest coursework/material time in a course (two small calls)."""
    stamps = [cr.stamp(x) for x in cr.coursework(course_id, limit=1)]
    try:
        stamps += [cr.stamp(x) for x in cr.materials(course_id, limit=1)]
    except google.NeedsConsent:
        pass  # materials permission not granted yet: coursework alone still tells
    return max((s for s in stamps if s), default=None)


def _ask(s, course: Course) -> int:
    folder, exists = propose_folder(course.name)
    course.state, course.folder = "asking", str(folder)
    d = Decision(kind="course", title=course.name,
                 detail={"course_id": course.id, "folder": str(folder), "exists": exists, "link": course.link})
    s.add(d)
    s.flush()
    return d.id


DETAILS_MAX = 1500  # characters of the teacher's instructions copied into the task


def details_of(cw: dict) -> str:
    """A new Classroom task's รายละเอียดงาน: the teacher's instructions, then where to hand it in
    (the assignment's page, where ส่งงาน is). Written once; after that it's yours to edit."""
    text = (cw.get("description") or "").strip()
    if len(text) > DETAILS_MAX:
        text = text[:DETAILS_MAX].rstrip() + "…"
    link = cw.get("alternateLink", "")
    return "\n\n".join(x for x in (text, f"ส่งงานที่: {link}" if link else "") if x)


def _deadlines(course: Course) -> tuple[int, int]:
    """Assignments of a followed course → tasks. -> (tasks added, tasks closed as turned in)."""
    states = cr.submissions(course.id)
    added = closed = 0
    at = now()
    for cw in cr.coursework(course.id):
        if cw.get("state", "PUBLISHED") != "PUBLISHED":
            continue
        due = cr.due_at(cw)
        turned_in = states.get(cw["id"], "NEW") in cr.SUBMITTED
        with session() as s:
            item = s.get(CourseItem, cw["id"])
            if item is None:
                item = CourseItem(id=cw["id"], course_id=course.id, kind="work")
                s.add(item)
            item.title, item.due_at, item.link = cw.get("title", ""), due, cw.get("alternateLink", "")
            item.turned_in, item.updated_at, item.synced_at = turned_in, cr.stamp(cw), at
            task = s.get(Task, item.task_id) if item.task_id else None
            if task is None and due and due > at and not turned_in:
                task = Task(title=f"{item.title} ({course.name})", due_at=due, source="classroom", source_ref=item.id,
                            details=details_of(cw))
                s.add(task)
                s.flush()
                item.task_id = task.id
                added += 1
            elif task is not None:
                task.due_at = due or task.due_at  # the teacher moved the due date
                if turned_in and task.status == "open":
                    task.status = "done"
                    closed += 1
    return added, closed


def _sync() -> tuple[str | None, list[tuple[str, int]]]:
    """One round (blocking). -> (a line for the log or None, [(course id, decision id) asked])."""
    found = cr.courses()
    asked: list[tuple[str, int]] = []
    with session() as s:
        first = s.scalar(select(Course.id).limit(1)) is None
    if first:
        with session() as s:
            for c in found:
                s.add(Course(id=c["id"], name=c["name"], section=c.get("section", ""), link=c.get("alternateLink", ""),
                             state="ended", last_activity=_latest(c["id"])))
        return f"จดวิชาที่มีอยู่ {len(found)} วิชาเป็น “จบแล้ว” · จะถามเมื่อมีวิชาใหม่หรืองานใหม่", []

    added = closed = 0
    extra: list[str] = []
    for c in found:
        with session() as s:
            course = s.get(Course, c["id"])
            if course is None:
                course = Course(id=c["id"], name=c["name"], section=c.get("section", ""), link=c.get("alternateLink", ""))
                s.add(course)
                s.flush()
                asked.append((course.id, _ask(s, course)))
                continue
            state = course.state
        if state in ("ended", "ignored"):
            latest = _latest(c["id"])
            with session() as s:
                course = s.get(Course, c["id"])
                if latest and (course.last_activity is None or latest > course.last_activity):
                    course.last_activity = latest
                    if state == "ended":  # busy again: maybe it's running another semester
                        asked.append((course.id, _ask(s, course)))
        elif state == "followed":
            with session() as s:
                course = s.get(Course, c["id"])
                s.expunge(course)
            a, cl = _deadlines(course)
            added, closed = added + a, closed + cl
            for hook in AFTER_FOLLOWED:
                try:
                    if line := hook(course.id):
                        extra.append(line)
                except google.NeedsConsent as exc:
                    extra.append(f"ข้ามสื่อ ({exc})")
                except Exception:
                    log.exception("after-followed hook failed for %s", course.id)
    parts = ([f"งานใหม่ {added}"] if added else []) + ([f"ส่งแล้ว {closed}"] if closed else []) + \
            ([f"ถามวิชาใหม่ {len(asked)}"] if asked else []) + extra
    return (" · ".join(parts) or None), asked


async def run() -> str | None:
    async with lock:
        try:
            line, asked = await asyncio.to_thread(_sync)
        except google.NeedsConsent as exc:
            return f"ข้าม: {exc}"
    for course_id, decision_id in asked:
        for hook in ASKED:
            try:
                await hook(course_id, decision_id)
            except Exception:
                log.exception("course-asked hook failed")
    return line


# ------------------------------------------------------------------ your answer
async def decide(decision_id: int, follow: bool, *, folder: str | None = None,
                 via: tuple[str, str] = ("หน้าเว็บ", "")) -> tuple[Decision, int]:
    """ติดตาม (deadlines and materials from now on, folder created if needed) or ไม่ติดตาม.
    -> (the decision, the action id). Undo puts the course back to waiting for your answer."""
    with session() as s:
        d = s.get(Decision, decision_id)
        if d is None or d.kind != "course":
            raise decisions.answered(None, "วิชา")
        if d.status != "pending":  # answered elsewhere: say how (the buttons then give way to it)
            raise decisions.answered(d, "วิชา")
        course = s.get(Course, d.detail["course_id"])
        target = Path(folder or d.detail["folder"]).expanduser()
        created = None  # the topmost folder this creates, so undo removes only what it made
        if follow and not target.exists():
            created = target
            while not created.parent.exists():
                created = created.parent
            target.mkdir(parents=True)
        d.status, d.answered_at = ("approved" if follow else "rejected"), now()
        course.state = "followed" if follow else "ignored"
        if follow:
            course.folder = str(target)
        name, course_id = course.name, course.id
    action_id = actions.record("classroom.follow" if follow else "classroom.ignore",
                               f"ติดตามวิชา: {name}" if follow else f"ไม่ติดตามวิชา: {name}",
                               f"สื่อไปที่ {target}" + (" (สร้างโฟลเดอร์ใหม่)" if created else "") if follow else "",
                               source_label=via[0], source_url=via[1],
                               undo={"course_id": course_id, "decision_id": decision_id,
                                     "target": str(target), "created": str(created) if created else ""})
    with session() as s:
        return s.get(Decision, decision_id), action_id


async def _undo_answer(undo: dict) -> None:
    with session() as s:
        s.get(Course, undo["course_id"]).state = "asking"
        d = s.get(Decision, undo["decision_id"])
        d.status, d.answered_at = "pending", None
    if undo.get("created"):  # remove the folders the follow created, while they're still empty
        top, path = Path(undo["created"]), Path(undo["target"])
        while path.exists() and not any(path.iterdir()):
            path.rmdir()
            if path == top:
                break
            path = path.parent


actions.register_undo("classroom.follow", _undo_answer)
actions.register_undo("classroom.ignore", _undo_answer)


def setup() -> None:
    from app.core import clock
    clock.attach("classroom", run)
