"""HTTP endpoints for calendar access (M0 smoke test).

These let us confirm the Google plumbing works end to end before building the
agent or the UI. Try them from the auto-generated docs at /docs.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import calendar as cal

router = APIRouter(prefix="/calendar", tags=["calendar"])


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
def events_range(start: datetime, end: datetime):
    """List events in an explicit [start, end] window (ISO 8601 query params).

    The dashboard calls this for whatever range the calendar is currently
    showing, so navigating to past/future weeks fetches the right events.
    """
    try:
        return cal.list_events(start, end, max_results=250)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/events")
def add_event(event: EventIn):
    """Create a single timed event."""
    try:
        return cal.create_event(event.summary, event.start, event.end, event.description)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
