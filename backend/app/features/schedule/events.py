"""Events you add yourself (the schedule page's form, or an order in the chat, B9).

It goes straight into your main Google Calendar, the same way an appointment from email does
(mail/extract.place): recorded in What the secretary did, Undo deletes it, the secretary reminds
you of it, and blocks are re-planned around it.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta

from app.connectors import gcal
from app.core import actions
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
    """Put an event in the calendar. -> (event id, action id).

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


async def recolor(event_ids: list[int], color_id: str, *, via: tuple[str, str] = ("หน้าตาราง", "")) -> int:
    """Colour: give events one of Google Calendar's colours (gcal.COLORS; "" = the calendar's own), in
    Google and here, so the pages draw them in it. One recorded action for all of them, and undo
    gives each one its old colour back. -> the action id.

    Raises ValueError for a colour that isn't one of Google's, or events that aren't in the calendar."""
    if color_id and color_id not in gcal.COLORS:
        raise ValueError("ไม่รู้จักสีนี้")
    with session() as s:
        rows = [s.get(Event, i) for i in dict.fromkeys(event_ids)]
        placed = [(e.id, e.gcal_id, e.color) for e in rows if e is not None and e.status == "placed" and e.gcal_id]
    if not placed:
        raise ValueError("ไม่พบกิจกรรมในปฏิทินให้เปลี่ยนสี")
    hex_ = gcal.COLORS[color_id][0] if color_id else ""
    old: dict[str, str] = {}
    for event_id, gcal_id, color in placed:
        if not await asyncio.to_thread(gcal.recolor, gcal_id, color_id):
            continue  # deleted in Google meanwhile: nothing to colour
        old[str(event_id)] = gcal.COLOR_IDS.get(color, "")
        with session() as s:
            s.get(Event, event_id).color = hex_
    name = gcal.COLORS[color_id][1] if color_id else "สีของปฏิทิน"
    return actions.record("calendar.color", f"เปลี่ยนสี {len(old)} กิจกรรม", f"เป็นสี{name}",
                          source_label=via[0], source_url=via[1], undo={"old": old})


async def _undo_recolor(undo: dict) -> None:
    for event_id, color_id in undo["old"].items():
        with session() as s:
            ev = s.get(Event, int(event_id))
            gcal_id = ev.gcal_id if ev is not None and ev.status == "placed" else ""
        if gcal_id and await asyncio.to_thread(gcal.recolor, gcal_id, color_id):
            with session() as s:
                s.get(Event, int(event_id)).color = gcal.COLORS[color_id][0] if color_id else ""


actions.register_undo("calendar.color", _undo_recolor)
