"""Your tasks: add, change, mark done. Every change is recorded and can be undone (What the secretary did).

Used by the schedule page (W5) and the "Done" button on deadline reminders.
Tasks also arrive from email (features/mail/extract.py, kind "task.add") and Classroom
(features/classroom/sync.py). The planner picks any change up on its next run.
"""

from __future__ import annotations

from datetime import datetime

from app.core import actions
from app.core.db import session
from app.core.tables import Task
from app.core.timefmt import thai_datetime

EDITABLE = ("title", "due_at", "est_minutes", "plan_mode", "block_minutes", "daily_minutes", "details")
MODES = {"early": "เริ่มเร็ว", "late": "ชิดเดดไลน์"}
SOURCE_NAMES = {"email": "อีเมล", "classroom": "Classroom", "you": "คุณเพิ่ม", "project": "โปรเจค", "calendar": "ปฏิทิน",
                "idea": "กลุ่มไอเดีย"}  # B6: a grown idea group you made a task
DETAILS_MAX = 5000  # characters of task details

# The minutes a task may ask for (None always means "the default"). The upper ends only
# catch typing mistakes: 200 hours of work, an 8-hour block, 16 hours in one day.
LIMITS = {"est_minutes": ("เวลาทำรวม", 15, 200 * 60), "block_minutes": ("ความยาวบล็อก", 15, 8 * 60),
          "daily_minutes": ("เวลาต่อวัน", 15, 16 * 60)}


def hours(minutes: int) -> str:
    """90 -> "1 ชม. 30 นาที" (the same words as the schedule page)."""
    h, m = divmod(minutes, 60)
    return " ".join(x for x in (f"{h} ชม." if h else "", f"{m} นาที" if m else "") if x) or "0 นาที"


def _check(values: dict) -> None:
    if values.get("plan_mode", "early") not in MODES:
        raise ValueError(f"plan_mode ต้องเป็น {', '.join(MODES)}")
    if "title" in values and not (values["title"] or "").strip():
        raise ValueError("ใส่ชื่องานก่อน")
    if len(values.get("details") or "") > DETAILS_MAX:
        raise ValueError(f"รายละเอียดยาวเกิน {DETAILS_MAX:,} ตัวอักษร")
    for key, (name, lo, hi) in LIMITS.items():
        v = values.get(key)
        if v is not None and not lo <= v <= hi:
            raise ValueError(f"{name}ต้องอยู่ระหว่าง {hours(lo)} ถึง {hours(hi)}")


def add(title: str, *, due_at: datetime | None = None, est_minutes: int | None = None, plan_mode: str = "early",
        block_minutes: int | None = None, daily_minutes: int | None = None, details: str = "",
        via: tuple[str, str] = ("หน้าเว็บ", "")) -> tuple[int, int]:
    """A task you typed in yourself. -> (task id, action id)."""
    _check({"title": title, "est_minutes": est_minutes, "plan_mode": plan_mode,
            "block_minutes": block_minutes, "daily_minutes": daily_minutes, "details": details})
    with session() as s:
        task = Task(title=title.strip(), due_at=due_at, est_minutes=est_minutes, plan_mode=plan_mode, source="you",
                    block_minutes=block_minutes, daily_minutes=daily_minutes, details=details.strip())
        s.add(task)
        s.flush()
        task_id = task.id
    words = [f"ส่ง {thai_datetime(due_at)}" if due_at else "ไม่มีกำหนดส่ง"]
    if est_minutes:
        words.append(f"ใช้เวลา {hours(est_minutes)}")
    action_id = actions.record("task.add", f"เพิ่มงาน: {title.strip()}", " · ".join(words),
                               source_label=via[0], source_url=via[1], undo={"task_id": task_id})
    return task_id, action_id


def edit(task_id: int, *, via: tuple[str, str] = ("หน้าเว็บ", ""), **changes) -> int:
    """Change a task's title, due date, estimate, placing mode or block sizes. -> action id."""
    unknown = set(changes) - set(EDITABLE)
    if unknown:
        raise ValueError(f"แก้ไม่ได้: {', '.join(unknown)}")
    _check(changes)
    if "title" in changes:
        changes["title"] = changes["title"].strip()
    if "details" in changes:
        changes["details"] = (changes["details"] or "").strip()
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
        words.append(f"ใช้เวลา {hours(changes['est_minutes'])}" if changes["est_minutes"] else "ใช้เวลาตามค่าเริ่มต้น")
    if "block_minutes" in changes:
        words.append(f"บล็อกละ {hours(changes['block_minutes'])}" if changes["block_minutes"] else "บล็อกตามกติกา")
    if "daily_minutes" in changes:
        words.append(f"วันละไม่เกิน {hours(changes['daily_minutes'])}" if changes["daily_minutes"] else "ต่อวันตามกติกา")
    if "due_at" in changes:
        words.append(f"ส่ง {thai_datetime(changes['due_at'])}" if changes["due_at"] else "ไม่มีกำหนดส่ง")
    if "title" in changes:
        words.append("เปลี่ยนชื่อ")
    if "details" in changes:
        words.append("แก้รายละเอียด" if changes["details"] else "ลบรายละเอียด")
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
    if {"title", "details"} & undo["old"].keys():
        from app.features.schedule import sync  # here, not at the top: sync imports this module

        await sync.retext(undo["task_id"])


async def _undo_done(undo: dict) -> None:
    with session() as s:
        if task := s.get(Task, undo["task_id"]):
            task.status = "open"


async def _undo_add(undo: dict) -> None:
    """A task added by you, by an email (mail/extract.py) or by an order in the chat: dropped,
    so the planner frees its time."""
    with session() as s:
        if task := s.get(Task, undo["task_id"]):
            task.status = "dropped"


actions.register_undo("task.add", _undo_add)
actions.register_undo("task.edit", _undo_edit)
actions.register_undo("task.done", _undo_done)
