"""กิจกรรม you add yourself (the schedule page's form, or an order in the chat, B9).

It goes straight into your main Google Calendar, the same way an appointment from email does
(mail/extract.place): recorded in สิ่งที่เลขาทำ, ย้อนกลับ deletes it, the secretary reminds
you of it, and blocks are re-planned around it.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.core.config import get_config
from app.core.db import session
from app.core.tables import Event
from app.features.mail import extract


def whole_days(first: date, last: date) -> tuple[datetime, datetime]:
    """An all-day entry from `first` to `last` (inclusive, as the page shows it): local midnight
    to the midnight after the last day."""
    tz = get_config().tz
    return datetime.combine(first, time(0), tz), datetime.combine(last + timedelta(days=1), time(0), tz)


async def add(title: str, start: datetime, end: datetime, *, all_day: bool = False, location: str = "",
              description: str = "", via: tuple[str, str] = ("หน้าตาราง", "")) -> tuple[int, int]:
    """Put a กิจกรรม in the calendar. -> (event id, action id).

    Raises ValueError for what you typed (no title, the end before the start). If Google can't
    take it, the event is forgotten and Google's error is raised as it is (google.NeedsConsent
    when a permission is missing), so the caller can say why."""
    title = title.strip()
    if not title:
        raise ValueError("ใส่ชื่อกิจกรรมก่อน")
    if end <= start:
        raise ValueError("เวลาจบต้องหลังเวลาเริ่ม")
    with session() as s:
        ev = Event(title=title, starts_at=start, ends_at=end, all_day=all_day, location=location.strip(),
                   description=description.strip(), source="you", status="proposed")
        s.add(ev)
        s.flush()
        event_id = ev.id
    try:
        action_id = await extract.place(event_id, via=via, note=description)
    except Exception:  # not written: forget it, and let the caller say why
        with session() as s:
            s.delete(s.get(Event, event_id))
        raise
    return event_id, action_id
