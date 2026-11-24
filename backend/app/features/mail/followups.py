"""Follow-ups (feature P6): threads where someone owes a reply, and a reminder when it's been too long.

- waiting on you: opened when the model reads an email and says it needs your reply
  (not for every email, or every newsletter would be a follow-up)
- waiting on them: opened when you were the last to write in a thread. Their reply
  then counts as important (watch.py flags it "awaiting") and alerts at once.

Both close by themselves when the other side writes in the thread. After FOLLOWUP_DAYS
(setting "mail.followup_days", default 3) the 12:00 round sends a reminder to #urgent;
"remind tomorrow" waits a day, "replied" closes it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core import actions
from app.core.db import now, session
from app.features.mail import watch
from app.features.mail.tables import Email, Followup, Person

DAYS_KEY = "mail.followup_days"
REMIND: list[Callable[[Followup, str, int], Awaitable[None]]] = []  # hooks: (followup, person name, days) -> the card


def days() -> int:
    return int(watch._get(DAYS_KEY, 3))


def _open(s, thread_id: str, waiting_on: str) -> Followup | None:
    return s.scalar(select(Followup).where(Followup.thread_id == thread_id, Followup.waiting_on == waiting_on,
                                           Followup.closed_at.is_(None)))


def track(account: str, headers) -> None:
    """watch.SYNCED hook (runs in the sync thread): look at who wrote last in each touched thread."""
    threads = {h.thread_id for h in headers}
    with session() as s:
        for thread_id in threads:
            last = s.scalar(select(Email).where(Email.thread_id == thread_id).order_by(Email.sent_at.desc()).limit(1))
            if last is None:
                continue
            if last.from_me:
                if f := _open(s, thread_id, "you"):
                    f.closed_at = now()  # you answered
                if not _open(s, thread_id, "them") and last.person_id:
                    s.add(Followup(account=account, thread_id=thread_id, person_id=last.person_id, subject=last.subject,
                                   waiting_on="them", since=last.sent_at, remind_after_days=days()))
            elif f := _open(s, thread_id, "them"):
                f.closed_at = now()  # they answered


async def on_read(r: watch.ReadEmail) -> None:
    """AFTER_READ hook: an email that needs your reply opens a 'waiting on you' follow-up."""
    e = r.email
    if not r.reading.needs_reply or e.from_me:
        return
    with session() as s:
        if not _open(s, e.thread_id, "you"):
            s.add(Followup(account=e.account, thread_id=e.thread_id, person_id=e.person_id, subject=e.subject,
                           waiting_on="you", since=e.sent_at, remind_after_days=days()))


def due(at: datetime | None = None) -> list[Followup]:
    """Open follow-ups to remind about now: past their days, and not reminded in the last day."""
    at = at or now()
    with session() as s:
        rows = s.scalars(select(Followup).where(Followup.closed_at.is_(None))).all()
        return [f for f in rows
                if f.since + timedelta(days=f.remind_after_days) <= at
                and (f.reminded_at is None or f.reminded_at + timedelta(days=1) <= at)]


async def remind() -> int:
    """Called by the 12:00 round: one #urgent card per follow-up that's due. -> how many."""
    count = 0
    for f in due():
        with session() as s:
            p = s.get(Person, f.person_id) if f.person_id else None
            name = p.name if p else "ไม่ทราบชื่อ"
            row = s.get(Followup, f.id)
            row.reminded_at = now()
            waited = (now() - f.since).days
        for hook in REMIND:
            await hook(f, name, waited)
        count += 1
    return count


def close(followup_id: int) -> Followup | None:
    """replied / no need to follow up anymore."""
    with session() as s:
        f = s.get(Followup, followup_id)
        if f and f.closed_at is None:
            f.closed_at = now()
        return f


def done(followup_id: int, *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    """Replied, recorded so undo reopens it (the page's button and an order in the
    chat, B9). -> action id. Raises ValueError when it's gone or already closed."""
    with session() as s:
        f = s.get(Followup, followup_id)
        if f is None:
            raise ValueError("ไม่พบเรื่องค้างนี้")
        if f.closed_at is not None:
            raise ValueError("เรื่องนี้ปิดไปแล้ว")
        f.closed_at = now()
        person = s.get(Person, f.person_id)
        target = f"{person.name if person else 'ไม่ทราบชื่อ'}: {f.subject}"
    return actions.record("followup.close", "ปิดเรื่องค้าง", target, source_label=via[0], source_url=via[1],
                          undo={"followup_id": followup_id})


async def _undo_done(undo: dict) -> None:
    with session() as s:
        if (f := s.get(Followup, undo["followup_id"])) is None:
            raise actions.UndoError("ไม่พบเรื่องค้างนี้แล้ว")
        f.closed_at = None


actions.register_undo("followup.close", _undo_done)


def snooze(followup_id: int) -> None:
    """เตือนพรุ่งนี้: the next reminder comes in a day."""
    with session() as s:
        if f := s.get(Followup, followup_id):
            f.reminded_at = now()


def setup() -> None:
    if track not in watch.SYNCED:
        watch.SYNCED.append(track)
    if on_read not in watch.AFTER_READ:
        watch.AFTER_READ.append(on_read)
