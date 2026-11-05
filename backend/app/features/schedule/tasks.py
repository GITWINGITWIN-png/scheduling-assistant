"""Your tasks: add, change, mark done. Every change is recorded and can be undone (สิ่งที่เลขาทำ).

Used by the schedule page (W5) and the "ทำเสร็จแล้ว" button on deadline reminders.
Tasks also arrive from email (features/mail/extract.py, kind "task.add") and Classroom
(features/classroom/sync.py). The planner picks any change up on its next run.
"""

from __future__ import annotations

from datetime import datetime

from app.core import actions
from app.core.db import session
from app.core.tables import Task
from app.core.timefmt import thai_datetime

EDITABLE = ("title", "due_at", "est_minutes", "plan_mode")
MODES = {"early": "เริ่มเร็ว", "late": "ชิดเดดไลน์"}


def add(title: str, *, due_at: datetime | None = None, est_minutes: int | None = None, plan_mode: str = "early",
        via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    """A task you typed in yourself. -> task id."""
    if plan_mode not in MODES:
        raise ValueError(f"plan_mode ต้องเป็น {', '.join(MODES)}")
    with session() as s:
        task = Task(title=title.strip(), due_at=due_at, est_minutes=est_minutes, plan_mode=plan_mode, source="you")
        s.add(task)
        s.flush()
        task_id = task.id
    actions.record("task.add", f"เพิ่มงาน: {title.strip()}", f"ส่ง {thai_datetime(due_at)}" if due_at else "",
                   source_label=via[0], source_url=via[1], undo={"task_id": task_id})
    return task_id


def edit(task_id: int, *, via: tuple[str, str] = ("หน้าเว็บ", ""), **changes) -> int:
    """Change a task's title, due date, estimate or placing mode. -> action id."""
    unknown = set(changes) - set(EDITABLE)
    if unknown:
        raise ValueError(f"แก้ไม่ได้: {', '.join(unknown)}")
    if changes.get("plan_mode", "early") not in MODES:
        raise ValueError(f"plan_mode ต้องเป็น {', '.join(MODES)}")
    with session() as s:
        task = s.get(Task, task_id)
        if task is None:
            raise ValueError("ไม่พบงานนี้")
        old = {k: getattr(task, k) for k in changes}
        for k, v in changes.items():
            setattr(task, k, v)
        title = task.title
    words = []
    if "plan_mode" in changes:
        words.append(f"วางแบบ{MODES[changes['plan_mode']]}")
    if "est_minutes" in changes:
        words.append(f"ใช้เวลา {changes['est_minutes']} นาที" if changes["est_minutes"] else "ใช้เวลาตามค่าเริ่มต้น")
    if "due_at" in changes:
        words.append(f"ส่ง {thai_datetime(changes['due_at'])}" if changes["due_at"] else "ไม่มีกำหนดส่ง")
    if "title" in changes:
        words.append("เปลี่ยนชื่อ")
    return actions.record("task.edit", f"แก้งาน: {title}", " · ".join(words), source_label=via[0], source_url=via[1],
                          undo={"task_id": task_id, "old": {k: v.isoformat() if isinstance(v, datetime) else v
                                                            for k, v in old.items()}})


def done(task_id: int, *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    """Mark it done: no more blocks or reminders for it. -> action id."""
    with session() as s:
        task = s.get(Task, task_id)
        if task is None:
            raise ValueError("ไม่พบงานนี้")
        if task.status != "open":
            raise ValueError("งานนี้ปิดไปแล้ว")
        task.status, title = "done", task.title
    return actions.record("task.done", f"ทำเสร็จแล้ว: {title}", "", source_label=via[0], source_url=via[1],
                          undo={"task_id": task_id})


async def _undo_edit(undo: dict) -> None:
    with session() as s:
        if task := s.get(Task, undo["task_id"]):
            for k, v in undo["old"].items():
                setattr(task, k, datetime.fromisoformat(v) if k == "due_at" and v else v)


async def _undo_done(undo: dict) -> None:
    with session() as s:
        if task := s.get(Task, undo["task_id"]):
            task.status = "open"


actions.register_undo("task.edit", _undo_edit)
actions.register_undo("task.done", _undo_done)
