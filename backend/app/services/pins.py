"""Pinned emails (M6) — promote an interesting email to a project-like item.

When the user checks "pin" on an email, we save it here so it appears on the
Projects page (a separate "From email" section). If the email carried a date, we
also create a calendar event for it and remember the event id, so un-pinning can
clean that event up too.

Two ways emails get pinned:
  - **Auto** (`auto_pin_items`) — after a scan, anything that looks schedule-worthy
    (has a date, or is a deadline/meeting/event) is pinned automatically so the user
    can review it later and unpin what they don't care about.
  - **Manual** (`pin`) — the user clicks pin on a specific email. The router enriches
    a manual pin with a deep re-read first (see mail_extract.deep_extract) so even an
    old, never-scanned email gets a date + summary.

Gmail stays read-only throughout; "pinning" is purely local state. The only
calendar *write* is on a pin (auto or manual) that has a date — and unpinning
removes it again.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import PinnedEmail
from app.services import calendar

log = logging.getLogger(__name__)

# An item is worth auto-pinning if it has a real date, or it's a kind of thing the
# user wants to look back on (deadline / meeting / event) even without a time yet.
_AUTO_PIN_TYPES = {"deadline", "meeting", "event"}


def _qualifies(item: dict) -> bool:
    return bool(item.get("datetime")) or item.get("type") in _AUTO_PIN_TYPES


def _serialize(p: PinnedEmail) -> dict:
    return {
        "email_id": p.email_id,
        "subject": p.subject,
        "sender": p.sender,
        "link": p.link,
        "note": p.note,
        "date": p.date,
        "on_calendar": bool(p.calendar_event_id),
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def pinned_ids() -> set[str]:
    """The set of currently-pinned email ids (for the UI to show pin state)."""
    with SessionLocal() as db:
        return set(db.scalars(select(PinnedEmail.email_id)).all())


def list_pins() -> list[dict]:
    """All pinned emails, newest first."""
    with SessionLocal() as db:
        rows = db.scalars(select(PinnedEmail).order_by(PinnedEmail.created_at.desc())).all()
        return [_serialize(p) for p in rows]


def _add_to_calendar(subject: str, date: str, sender: str) -> str | None:
    """Create a calendar event for a dated pin; return its id (or None on failure).

    Handles date-only ("2026-06-28" → all-day) and full datetimes
    ("2026-06-28T15:00" → a 1-hour event). Calendar errors are logged but don't
    block the pin — the email is still pinned, just without an event.
    """
    title = f"📧 {subject}" if subject else "📧 (email)"
    description = f"Pinned from email — {sender}" if sender else "Pinned from email"
    try:
        if len(date) <= 10:  # "YYYY-MM-DD" → all-day
            event = calendar.create_all_day_event(title, date, description)
        else:
            start = datetime.fromisoformat(date)
            event = calendar.create_event(title, start, start + timedelta(hours=1), description)
        return event.get("id")
    except Exception:
        log.exception("could not add pinned email to calendar")
        return None


def pin(*, email_id: str, subject: str = "", sender: str = "", link: str = "",
        date: str | None = None, note: str = "") -> dict:
    """Pin an email. If it has a date, also create a calendar event for it.

    Idempotent: pinning an already-pinned email returns it unchanged (no duplicate
    calendar event).
    """
    with SessionLocal() as db:
        existing = db.get(PinnedEmail, email_id)
        if existing:
            return _serialize(existing)

        event_id = _add_to_calendar(subject, date, sender) if date else None
        row = PinnedEmail(
            email_id=email_id,
            subject=subject,
            sender=sender,
            link=link,
            note=note,
            date=date,
            calendar_event_id=event_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _serialize(row)


def _item_note(item: dict) -> str:
    """A readable note from a scan item: its title plus any extra context."""
    title = item.get("title", "")
    extra = item.get("note", "")
    return f"{title} — {extra}" if title and extra else (title or extra)


def auto_pin_items(items: list[dict]) -> set[str]:
    """Pin every schedule-worthy scan item (dated/deadline/meeting/event).

    Dated items also land on the calendar. One pin per email (dated items win the
    tie, so the calendar gets the real date). Returns the set of email ids that are
    now pinned among the qualifying ones, so the caller can mark them in the UI.
    """
    pinned: set[str] = set()
    seen: set[str] = set()
    existing = pinned_ids()
    # Dated items first, so if an email has both a dated and an undated item, the
    # pin we create carries the date (and therefore the calendar event).
    for item in sorted(items, key=lambda x: x.get("datetime") is None):
        eid = item.get("email_id")
        if not eid or eid in seen or not _qualifies(item):
            continue
        seen.add(eid)
        if eid not in existing:
            pin(
                email_id=eid,
                subject=item.get("email_subject", ""),
                sender=item.get("email_from", ""),
                link=item.get("link", ""),
                date=item.get("datetime"),
                note=_item_note(item),
            )
        pinned.add(eid)
    return pinned


def unpin(email_id: str) -> None:
    """Un-pin an email, deleting any calendar event we created for it."""
    with SessionLocal() as db:
        row = db.get(PinnedEmail, email_id)
        if not row:
            return
        if row.calendar_event_id:
            try:
                calendar.delete_event(row.calendar_event_id)
            except Exception:  # event may already be gone — don't block the unpin
                log.exception("could not delete calendar event for unpinned email")
        db.delete(row)
        db.commit()
