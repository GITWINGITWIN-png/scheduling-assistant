"""Proactive endpoints (M5): the daily brief and deadline nudges.

These back the Home page's brief + deadlines cards. The brief is lazily
generated once a day (a Claude call); nudges are tokenless.
"""

from fastapi import APIRouter, HTTPException

from app.services import brief_store, nudges

router = APIRouter(tags=["proactive"])


@router.get("/brief/today")
async def brief_today():
    """Today's brief — generated + cached on first call of the day."""
    try:
        return await brief_store.get_or_create_today()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/brief/regenerate")
async def brief_regenerate():
    """Force a fresh brief (re-runs the Claude call)."""
    try:
        return await brief_store.get_or_create_today(force=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/nudges")
def get_nudges(days: int = 7):
    """Overdue items, things due within `days`, and replan suggestions."""
    try:
        return nudges.compute_nudges(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
