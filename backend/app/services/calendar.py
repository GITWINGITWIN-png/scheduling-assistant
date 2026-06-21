"""Google Calendar access.

This is the M0 milestone: prove we can authenticate to Google and read/write
events. Everything else (the chat agent, the planner) eventually calls these
two methods, so we keep the Google-specific details isolated here.

Auth model: we use the OAuth "installed app" flow. On first run it opens a
browser for you to grant access, then caches a token so future runs are silent.
When we move to the full web app (M2) we'll switch to the web OAuth flow, but
this is the simplest thing that works for local development.
"""

from __future__ import annotations

from datetime import datetime, timezone

from googleapiclient.discovery import build

from app.config import settings
from app.services import cache
from app.services.google_auth import get_credentials

# Full read/write access to calendars. Narrow this later if you only need reads.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# The calendar lives on the user's personal Google account.
ACCOUNT = "personal"

# Cached calendar ranges live under this key prefix; any write clears them all so
# the next read reflects the change (incl. events the chat agent created).
_CACHE_PREFIX = "calendar:"


def _invalidate_cache() -> None:
    """Drop all cached calendar ranges after a write."""
    cache.clear_prefix(_CACHE_PREFIX)


def _service():
    """Build a Google Calendar API client (personal account)."""
    return build("calendar", "v3", credentials=get_credentials(ACCOUNT, SCOPES))


def _rfc3339(dt: datetime) -> str:
    """Format a datetime as RFC 3339 for the Google API.

    Naive datetimes are assumed to be UTC. Aware datetimes keep their offset.
    (Avoids the old `isoformat() + "Z"` trick, which breaks on aware datetimes.)
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def list_events(time_min: datetime, time_max: datetime, max_results: int = 50) -> list[dict]:
    """Return events between two datetimes, soonest first."""
    result = (
        _service()
        .events()
        .list(
            calendarId=settings.calendar_id,
            timeMin=_rfc3339(time_min),
            timeMax=_rfc3339(time_max),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return result.get("items", [])


def create_event(
    summary: str,
    start: datetime,
    end: datetime,
    description: str = "",
) -> dict:
    """Create a timed event and return the created resource."""
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }
    event = (
        _service()
        .events()
        .insert(calendarId=settings.calendar_id, body=body)
        .execute()
    )
    _invalidate_cache()
    return event


def create_all_day_event(summary: str, date: str, description: str = "") -> dict:
    """Create an all-day event on a given date ("YYYY-MM-DD") and return it.

    Used for email-derived items that have a date but no specific time. Google's
    all-day events use `date` (not `dateTime`), and `end.date` is exclusive, so a
    one-day event ends on the next day.
    """
    from datetime import date as _date, timedelta

    d = _date.fromisoformat(date)
    body = {
        "summary": summary,
        "description": description,
        "start": {"date": d.isoformat()},
        "end": {"date": (d + timedelta(days=1)).isoformat()},
    }
    event = (
        _service()
        .events()
        .insert(calendarId=settings.calendar_id, body=body)
        .execute()
    )
    _invalidate_cache()
    return event


def update_event(
    event_id: str,
    *,
    summary: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    description: str | None = None,
) -> dict:
    """Update an existing event. Only the provided fields are changed (patch)."""
    body: dict = {}
    if summary is not None:
        body["summary"] = summary
    if description is not None:
        body["description"] = description
    if start is not None:
        body["start"] = {"dateTime": start.isoformat()}
    if end is not None:
        body["end"] = {"dateTime": end.isoformat()}
    event = (
        _service()
        .events()
        .patch(calendarId=settings.calendar_id, eventId=event_id, body=body)
        .execute()
    )
    _invalidate_cache()
    return event


def delete_event(event_id: str) -> None:
    """Delete an event by id. Irreversible — callers should confirm first."""
    _service().events().delete(
        calendarId=settings.calendar_id, eventId=event_id
    ).execute()
    _invalidate_cache()
