"""Google Calendar: add an appointment, and remove it again (for ย้อนกลับ).

B2 only writes the appointments it found in email; B3 adds the full two-way sync.
Everything goes into the primary calendar of the "หลัก" account
(google.CALENDAR_ACCOUNT). Synchronous, like gmail.py: call through asyncio.to_thread.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.connectors import google
from app.core.config import get_config


def _service():
    return build("calendar", "v3", credentials=google.credentials(google.CALENDAR_ACCOUNT), cache_discovery=False)


def insert(title: str, start: datetime, end: datetime, *, all_day: bool = False, location: str = "",
           description: str = "") -> tuple[str, str]:
    """Create the event. -> (event id, link to open it in Google Calendar)."""
    tz = get_config().timezone
    if all_day:
        when = {"start": {"date": start.date().isoformat()},
                "end": {"date": (max(end, start + timedelta(days=1))).date().isoformat()}}
    else:
        when = {"start": {"dateTime": start.isoformat(), "timeZone": tz},
                "end": {"dateTime": end.isoformat(), "timeZone": tz}}
    body = {"summary": title, "location": location, "description": description, **when,
            "source": {"title": "เลขา", "url": "http://localhost:8000/log"}}
    ev = _service().events().insert(calendarId="primary", body=body).execute()
    return ev["id"], ev.get("htmlLink", "")


def delete(event_id: str) -> None:
    """Remove the event; an event already deleted by hand counts as done."""
    try:
        _service().events().delete(calendarId="primary", eventId=event_id).execute()
    except HttpError as exc:
        if exc.resp.status not in (404, 410):
            raise
