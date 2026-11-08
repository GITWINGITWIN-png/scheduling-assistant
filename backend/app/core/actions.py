"""The action log (บันทึกสิ่งที่เลขาทำ, feature P9): one recorder for everything the secretary does.

Rules that keep the log trustworthy:
- **Everything goes through `record()`.** A feature that does something (adds an
  event, changes a person's level, approves a plan, runs a round) records it
  here in the same step. The log is plain code, no model, so it costs no tokens.
- **Undo is opt-in per kind.** An action that can be reversed passes `undo=`:
  the data needed to reverse it. Its feature registers how with
  `register_undo(kind, fn)`. W9's ย้อนกลับ button and Discord's both call
  `undo(id)`.
- **Undoing is recorded too** (kind "undo"), so the log stays a complete history.
  Nothing is deleted.

What can be undone, as agreed: events it added itself, changes to a person's
level, and commands that haven't started. In B1 that means plan decisions.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from sqlalchemy import or_, select

from app.core.db import now, session
from app.core.tables import Action
from app.core.timefmt import local, thai_date

log = logging.getLogger(__name__)

UndoFn = Callable[[dict], Awaitable[None]]
_undo_fns: dict[str, UndoFn] = {}

# The filter on the log page (W9): label -> kind prefixes
GROUPS: dict[str, tuple[str, tuple[str, ...]]] = {
    "calendar": ("ลงปฏิทิน", ("calendar.",)),
    "person": ("เปลี่ยนระดับคน", ("person.",)),
    "job": ("สั่งงาน", ("plan.", "job.")),
}


class UndoError(ValueError):
    """The action can't be undone (already undone, not undoable, gone). The message says why."""


class AlreadyUndone(UndoError):
    """Undone already (from another copy of its button, the log page or Discord): nothing to do."""


def register_undo(kind: str, fn: UndoFn) -> None:
    _undo_fns[kind] = fn


def record(kind: str, summary: str, target: str = "", *, source_label: str = "", source_url: str = "",
           undo: dict | None = None, tokens: int | None = None) -> int:
    """Write one action and return its id. summary = ทำอะไร, target = กับอะไร (in your words)."""
    with session() as s:
        a = Action(kind=kind, summary=summary, target=target[:500], source_label=source_label,
                   source_url=source_url, undo=undo, tokens=tokens)
        s.add(a)
        s.flush()
        return a.id


def undoable(a: Action) -> bool:
    return a.undo is not None and a.undone_at is None and a.kind in _undo_fns


async def undo(action_id: int) -> Action:
    with session() as s:
        a = s.get(Action, action_id)
    if a is None:
        raise UndoError("ไม่พบรายการนี้")
    if a.undone_at is not None:
        raise AlreadyUndone("รายการนี้ย้อนกลับไปแล้ว")
    if not undoable(a):
        raise UndoError("รายการนี้ย้อนกลับไม่ได้")
    await _undo_fns[a.kind](a.undo or {})  # the feature reverses it; raises UndoError if it can't any more
    with session() as s:
        row = s.get(Action, action_id)
        row.undone_at = now()
        a = row
    record("undo", f"ย้อนกลับ: {a.summary}", a.target, source_label="ปุ่มย้อนกลับ")
    log.info("undid action %s (%s)", action_id, a.kind)
    return a


def as_dict(a: Action) -> dict:
    at = local(a.at)
    return {
        "id": a.id, "at": a.at.isoformat(), "time": f"{at:%H:%M}", "date": thai_date(a.at),
        "kind": a.kind, "summary": a.summary, "target": a.target,
        "source_label": a.source_label, "source_url": a.source_url, "tokens": a.tokens,
        "can_undo": undoable(a), "undone_at": a.undone_at.isoformat() if a.undone_at else None,
    }


def list_actions(range_: str = "today", group: str = "all", limit: int = 500) -> list[dict]:
    """For the log page. range_: today · 7d · all. group: all or a GROUPS key."""
    q = select(Action).order_by(Action.at.desc()).limit(limit)
    if range_ == "today":
        start = local(now()).replace(hour=0, minute=0, second=0, microsecond=0)
        q = q.where(Action.at >= start)
    elif range_ == "7d":
        q = q.where(Action.at >= now() - timedelta(days=7))
    if group in GROUPS:
        q = q.where(or_(*(Action.kind.startswith(p) for p in GROUPS[group][1])))
    with session() as s:
        return [as_dict(a) for a in s.scalars(q).all()]


def since(when: datetime) -> list[Action]:
    with session() as s:
        return list(s.scalars(select(Action).where(Action.at >= when).order_by(Action.at)).all())
