"""Store + lazy-generate the daily brief (M5).

One brief per day, cached in the database. Both the dashboard (lazy, on first
open) and the scheduler (pre-warm in the morning) call `get_or_create_today`, so
the Claude call happens at most once a day unless `force` is set.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.agent import brief as brief_agent
from app.db import SessionLocal
from app.models import DailyBrief


def _today() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def _serialize(b: DailyBrief) -> dict:
    return {"for_date": b.for_date, "content": b.content, "created_at": b.created_at}


async def get_or_create_today(force: bool = False) -> dict:
    """Return today's brief, generating + caching it if missing (or forced)."""
    today = _today()

    if not force:
        with SessionLocal() as db:
            existing = db.scalar(select(DailyBrief).where(DailyBrief.for_date == today))
            if existing:
                return _serialize(existing)

    # Generate (the Claude call) outside any open session.
    content = await brief_agent.generate_brief()

    with SessionLocal() as db:
        existing = db.scalar(select(DailyBrief).where(DailyBrief.for_date == today))
        if existing:
            existing.content = content
        else:
            existing = DailyBrief(for_date=today, content=content)
            db.add(existing)
        db.commit()
        db.refresh(existing)
        return _serialize(existing)
