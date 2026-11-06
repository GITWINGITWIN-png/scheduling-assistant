"""Appointments and tasks from email (features 1.3 and P4): the AFTER_READ hook.

For each "นัด" line the model wrote, core/when.py works out the real time (no tokens), then:

- from someone important, or a reply you were waiting for: straight into your calendar,
  recorded with ย้อนกลับ ("คนสำคัญลงปฏิทินเลยแล้วแจ้ง")
- from anyone else: a proposal waiting in #อนุมัติ, because you may not want to go
  ("ร่างไว้ให้คุณกดรับก่อน")

If the calendar can't be reached (the main account isn't connected, or its sign-in expired),
an appointment that would have gone in directly waits in #อนุมัติ instead, with the reason,
so nothing is lost; รับนัด then places it once the calendar works again.

Every calendar entry links back to the original email. A line whose time can't be worked
out is skipped and logged, rather than guessed. "งาน" lines become tasks (P4), with a
due date when one is given. The same email read twice never adds anything twice.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select

from app.connectors import gcal, google
from app.core import actions, when
from app.core.rules import learn
from app.core.db import now, session
from app.core.tables import Decision, Event, Task
from app.core.timefmt import thai_datetime
from app.features.mail.tables import Email
from app.features.mail.watch import AFTER_READ, ReadEmail, address_of

log = logging.getLogger(__name__)

PLACED: list = []  # hooks: async fn(event_id, action_id, email) after an event goes in the calendar
PROPOSED: list = []  # hooks: async fn(event_id, decision_id, email) after a proposal is made

# What was done for each email, for the #ด่วน card's "เลขาทำให้แล้ว" and its ย้อนกลับ:
# {email id: [(in your words, action id), ...]}. The card takes (pops) its email's entry.
DONE: dict[str, list[tuple[str, int]]] = {}
# Appointments from an email that are waiting in #อนุมัติ: {email id: why, in your words}.
# The #ด่วน card takes (pops) it for its "รอคุณรับ" field.
ASKED: dict[str, str] = {}

_deciding = asyncio.Lock()  # one answer at a time, so a double click can't place an event twice


def gmail_link(e: Email) -> str:
    """Opens the email in the mailbox that received it (authuser picks the signed-in account)."""
    me = address_of(e.account)
    return f"https://mail.google.com/mail/?authuser={me}#all/{e.id}" if me else f"https://mail.google.com/mail/#all/{e.id}"


def done_for(s, email_ids: list[str]) -> dict[str, list[str]]:
    """What the secretary did with each of these emails, in the words the people page and the
    briefs use: ลงปฏิทินแล้ว · นัดรอคุณรับ · เพิ่มเป็นงานแล้ว."""
    placed = set(s.scalars(select(Event.source_ref).where(Event.source_ref.in_(email_ids), Event.status == "placed")))
    proposed = set(s.scalars(select(Event.source_ref).where(Event.source_ref.in_(email_ids), Event.status == "proposed")))
    tasked = set(s.scalars(select(Task.source_ref).where(Task.source_ref.in_(email_ids), Task.status == "open")))
    return {i: [label for label, on in (("ลงปฏิทินแล้ว", i in placed), ("นัดรอคุณรับ", i in proposed),
                                         ("เพิ่มเป็นงานแล้ว", i in tasked)) if on] for i in email_ids}


def _direct(e: Email) -> bool:
    return e.level == "important" or e.flagged == "awaiting"


async def place(event_id: int, *, via: tuple[str, str] = ("อีเมล", ""), note: str = "") -> int:
    """Put a stored event into Google Calendar and record it (undo deletes it). -> action id.

    Used for appointments found in email and, from the schedule page, ones you add yourself
    (`note` is then your description)."""
    with session() as s:
        ev = s.get(Event, event_id)
        title, start, end, all_day, place_, ref = ev.title, ev.starts_at, ev.ends_at, ev.all_day, ev.location, ev.source_ref
        email = s.get(Email, ref) if ev.source == "email" else None
    link = gmail_link(email) if email else ""
    description = (f"จากอีเมล: {email.sender_name or email.sender} · {email.subject}\n{link}\n\n{gcal.SIGNATURE}" if email
                   else "\n\n".join(x for x in (note.strip(), gcal.SIGNATURE) if x))
    gcal_id, cal_link = await asyncio.to_thread(gcal.insert, title, start, end, all_day=all_day, location=place_,
                                                description=description)
    with session() as s:
        ev = s.get(Event, event_id)
        ev.gcal_id, ev.status, ev.link = gcal_id, "placed", cal_link
    return actions.record("calendar.place", f"ลงปฏิทิน: {title}", thai_datetime(start) if not all_day else thai_datetime(start).split(" ")[0] + " ทั้งวัน",
                          source_label=via[0], source_url=via[1] or link or cal_link, undo={"event_id": event_id})


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


def _when_words(start, has_time: bool) -> str:
    return thai_datetime(start) if has_time else thai_datetime(start).split(" ")[0] + " ทั้งวัน"


def _ask(event_id: int, e: Email, why: str = "") -> int:
    """Make the proposal that waits for รับนัด / ไม่ไป. -> decision id."""
    with session() as s:
        ev = s.get(Event, event_id)
        d = Decision(kind="appointment", title=ev.title,
                     detail={"event_id": event_id, "email_id": e.id, "from": e.sender_name or e.sender,
                             "when": _when_words(ev.starts_at, not ev.all_day), "subject": e.subject, "why": why})
        s.add(d)
        s.flush()
        return d.id


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
        why = ""
        if _direct(e):
            try:
                action_id = await place(event_id, via=(f"อีเมลจาก {e.sender_name or e.sender}", gmail_link(e)))
            except Exception as exc:  # never lose the appointment: ask instead, and say why
                log.exception("couldn't place event %s directly; asking in #อนุมัติ instead", event_id)
                why = ("ลงปฏิทินเองไม่ได้: บัญชีหลักยังไม่ได้เชื่อมหรือหมดอายุ" if isinstance(exc, google.NeedsConsent)
                       else "ลงปฏิทินเองไม่ได้: ติดต่อ Google Calendar ไม่สำเร็จ")
            else:
                DONE.setdefault(e.id, []).append((f"ลงนัด {_when_words(w.start, w.has_time).removesuffix(' ทั้งวัน')}: {title}", action_id))
                for hook in PLACED:
                    await hook(event_id, action_id, e)
                continue
        decision_id = _ask(event_id, e, why)
        ASKED[e.id] = why or "นัดอยู่ใน #อนุมัติ"
        for hook in PROPOSED:
            await hook(event_id, decision_id, e)
    for title, due_text in r.reading.tasks:
        due = when.parse(due_text, e.sent_at) if due_text else None
        with session() as s:
            if s.scalar(select(Task.id).where(Task.source_ref == e.id, Task.title == title)):
                continue
            task = Task(title=title, due_at=due.start if due else None, source="email", source_ref=e.id)
            s.add(task)
            s.flush()
            task_id = task.id
        due_words = f" ส่ง {thai_datetime(due.start)}" if due else ""
        action_id = actions.record("task.add", f"เพิ่มงาน: {title}", due_words.strip(), source_label=f"อีเมลจาก {e.sender_name or e.sender}",
                                   source_url=gmail_link(e), undo={"task_id": task_id})
        DONE.setdefault(e.id, []).append((f"เพิ่มงาน “{title}”{due_words}", action_id))


async def decide(decision_id: int, accept: bool, *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> tuple[Decision, int | None]:
    """You answered a proposed appointment: รับ puts it in the calendar, ไม่ไป declines it.
    -> (the decision, the calendar action id if placed).

    รับ is only recorded once the event is really in the calendar: if Google can't be
    reached, you get the reason (ValueError) and the appointment keeps waiting."""
    async with _deciding:
        with session() as s:
            d = s.get(Decision, decision_id)
            if d is None or d.kind != "appointment":
                raise ValueError("ไม่พบนัดนี้")
            if d.status != "pending":
                raise ValueError("ตัดสินนัดนี้ไปแล้ว")
            event_id, title, when_words = d.detail["event_id"], d.title, d.detail.get("when", "")
        action_id = None
        if accept:
            try:
                action_id = await place(event_id, via=via)
            except google.NeedsConsent as exc:
                raise ValueError(f"ยังลงปฏิทินไม่ได้ · {exc}") from exc
        with session() as s:
            d = s.get(Decision, decision_id)
            d.status, d.answered_at = ("approved" if accept else "rejected"), now()
            if not accept:
                s.get(Event, event_id).status = "declined"
        if not accept:
            actions.record("calendar.decline", f"ไม่ไปนัด: {title}", when_words, source_label=via[0], source_url=via[1])
        try:
            learn.refresh()  # B5: a pattern in your answers ("คุณมักไม่รับนัดวันเสาร์") waits in the rule book
        except Exception:
            log.exception("couldn't look for patterns after an appointment answer")
        with session() as s:
            return s.get(Decision, decision_id), action_id


async def _undo_task(undo: dict) -> None:
    with session() as s:
        if task := s.get(Task, undo["task_id"]):
            task.status = "dropped"


actions.register_undo("calendar.place", _undo_place)
actions.register_undo("task.add", _undo_task)


def setup() -> None:
    if on_read not in AFTER_READ:
        AFTER_READ.append(on_read)
