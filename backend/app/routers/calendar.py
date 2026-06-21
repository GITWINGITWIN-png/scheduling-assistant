"""HTTP endpoints for calendar access (M0 smoke test).

These let us confirm the Google plumbing works end to end before building the
agent or the UI. Try them from the auto-generated docs at /docs.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.services import cache
from app.services import calendar as cal

router = APIRouter(prefix="/calendar", tags=["calendar"])

# Calendar can change from other devices, so keep the snapshot short-lived. Writes
# through the calendar service also clear "calendar:*", so edits show immediately.
_CALENDAR_TTL = 120


class EventIn(BaseModel):
    summary: str
    start: datetime
    end: datetime
    description: str = ""


@router.get("/upcoming")
def upcoming(days: int = 7):
    """List events from now through the next `days` days."""
    now = datetime.now(timezone.utc)
    try:
        return cal.list_events(now, now + timedelta(days=days))
    except Exception as e:  # surface setup errors (e.g. missing credentials) clearly
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/range")
def events_range(start: datetime, end: datetime, background_tasks: BackgroundTasks, refresh: bool = False):
    """List events in an explicit [start, end] window (ISO 8601 query params).

    The dashboard calls this for whatever range the calendar is currently showing.
    Each range is cached separately (stale-while-revalidate); calendar writes clear
    the cache so edits appear right away. Returns a {data, fetched_at, stale} envelope.
    """
    try:
        return cache.serve(
            f"calendar:{start.isoformat()}:{end.isoformat()}",
            lambda: cal.list_events(start, end, max_results=250),
            ttl=_CALENDAR_TTL,
            refresh=refresh,
            add_task=background_tasks.add_task,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/events")
def add_event(event: EventIn):
    """Create a single timed event."""
    try:
        return cal.create_event(event.summary, event.start, event.end, event.description)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
