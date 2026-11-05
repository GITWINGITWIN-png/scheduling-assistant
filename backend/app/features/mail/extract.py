"""Appointments and tasks from email (features 1.3 and P4): the AFTER_READ hook.

For each "นัด" line the model wrote, core/when.py works out the real time (no tokens), then:

- from someone important, or a reply you were waiting for: straight into your calendar,
  recorded with ย้อนกลับ ("คนสำคัญลงปฏิทินเลยแล้วแจ้ง")
- from anyone else: a proposal waiting in #อนุมัติ, because you may not want to go
  ("ร่างไว้ให้คุณกดรับก่อน")

Every calendar entry links back to the original email. A line whose time can't be worked
out is skipped and logged, rather than guessed. "งาน" lines become tasks (P4), with a
due date when one is given. The same email read twice never adds anything twice.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select

from app.connectors import gcal
from app.core import actions, when
from app.core.db import now, session
from app.core.tables import Decision, Event, Task
from app.core.timefmt import thai_datetime
from app.features.mail.tables import Email
from app.features.mail.watch import AFTER_READ, ReadEmail, my_addresses

log = logging.getLogger(__name__)

PLACED: list = []  # hooks: async fn(event_id, action_id, email) after an event goes in the calendar
PROPOSED: list = []  # hooks: async fn(event_id, decision_id, email) after a proposal is made


def gmail_link(e: Email) -> str:
    me = next(iter(my_addresses()), "")
    return f"https://mail.google.com/mail/?authuser={me}#all/{e.id}" if me else f"https://mail.google.com/mail/#all/{e.id}"


def _direct(e: Email) -> bool:
    return e.level == "important" or e.flagged == "awaiting"


async def place(event_id: int, *, via: tuple[str, str] = ("อีเมล", "")) -> int:
    """Put a stored event into Google Calendar and record it (undo deletes it). -> action id."""
    with session() as s:
        ev = s.get(Event, event_id)
        title, start, end, all_day, place_, ref = ev.title, ev.starts_at, ev.ends_at, ev.all_day, ev.location, ev.source_ref
        email = s.get(Email, ref) if ev.source == "email" else None
    link = gmail_link(email) if email else ""
    description = (f"จากอีเมล: {email.sender_name or email.sender} · {email.subject}\n{link}\n\nลงโดยเลขา" if email else "ลงโดยเลขา")
    gcal_id, _ = await asyncio.to_thread(gcal.insert, title, start, end, all_day=all_day, location=place_, description=description)
    with session() as s:
        ev = s.get(Event, event_id)
        ev.gcal_id, ev.status = gcal_id, "placed"
    return actions.record("calendar.place", f"ลงปฏิทิน: {title}", thai_datetime(start) if not all_day else thai_datetime(start).split(" ")[0] + " ทั้งวัน",
                          source_label=via[0], source_url=via[1] or link, undo={"event_id": event_id})


async def _undo_place(undo: dict) -> None:
    with session() as s:
        ev = s.get(Event, undo["event_id"])
        if ev is None or not ev.gcal_id:
            return
        gcal_id = ev.gcal_id
    await asyncio.to_thread(gcal.delete, gcal_id)
    with session() as s:
        ev = s.get(Event, undo["event_id"])
        ev.status, ev.gcal_id = "removed", ""


async def on_read(r: ReadEmail) -> None:
    e = r.email
    for title, when_text, minutes, location in r.reading.events:
        w = when.parse(when_text, e.sent_at)
        if w is None:
            log.info("skipped appointment %r from %s: can't tell when (%r)", title, e.id, when_text)
            continue
        with session() as s:
            dup = s.scalar(select(Event.id).where(Event.source_ref == e.id, Event.title == title, Event.starts_at == w.start))
            if dup:
                continue
            ev = Event(title=title, starts_at=w.start, ends_at=w.start + (timedelta(days=1) if not w.has_time else timedelta(minutes=minutes)),
                       all_day=not w.has_time, location=location, source="email", source_ref=e.id, status="proposed")
            s.add(ev)
            s.flush()
            event_id = ev.id
            if not _direct(e):
                d = Decision(kind="appointment", title=title,
                             detail={"event_id": event_id, "email_id": e.id, "from": e.sender_name or e.sender,
                                     "when": thai_datetime(w.start) if w.has_time else thai_datetime(w.start).split(" ")[0] + " ทั้งวัน",
                                     "subject": e.subject})
                s.add(d)
                s.flush()
                decision_id = d.id
        if _direct(e):
            action_id = await place(event_id, via=(f"อีเมลจาก {e.sender_name or e.sender}", gmail_link(e)))
            for hook in PLACED:
                await hook(event_id, action_id, e)
        else:
            for hook in PROPOSED:
                await hook(event_id, decision_id, e)
    for title, due_text in r.reading.tasks:
        due = when.parse(due_text, e.sent_at) if due_text else None
        with session() as s:
            if s.scalar(select(Task.id).where(Task.source_ref == e.id, Task.title == title)):
                continue
            s.add(Task(title=title, due_at=due.start if due else None, source="email", source_ref=e.id))


async def decide(decision_id: int, accept: bool, *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> tuple[Decision, int | None]:
    """You answered a proposed appointment: รับ puts it in the calendar, ไม่ไป declines it.
    -> (the decision, the calendar action id if placed)."""
    with session() as s:
        d = s.get(Decision, decision_id)
        if d is None or d.kind != "appointment":
            raise ValueError("ไม่พบนัดนี้")
        if d.status != "pending":
            raise ValueError("ตัดสินนัดนี้ไปแล้ว")
        d.status, d.answered_at = ("approved" if accept else "rejected"), now()
        event_id = d.detail["event_id"]
        if not accept:
            s.get(Event, event_id).status = "declined"
    if accept:
        action_id = await place(event_id, via=via)
    else:
        action_id = None
        actions.record("calendar.decline", f"ไม่ไปนัด: {d.title}", d.detail.get("when", ""), source_label=via[0], source_url=via[1])
    with session() as s:
        return s.get(Decision, decision_id), action_id


actions.register_undo("calendar.place", _undo_place)


def setup() -> None:
    if on_read not in AFTER_READ:
        AFTER_READ.append(on_read)
