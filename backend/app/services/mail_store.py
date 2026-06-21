"""Store + lazy-run the daily mail scan (M6).

The local-LLM scan over today's mail is free but takes a little time, so we cache
one result per day — exactly like the daily brief. The scheduler pre-warms it
each morning; the Mail page reads it lazily on first open. `force` re-runs it
(e.g. the "Scan again" button) when the user wants fresh results mid-day.
"""

from __future__ import annotations

import json
from datetime import datetime

import anyio
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DailyMailScan
from app.services import mail_extract, pins


def _today() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def _serialize(row: DailyMailScan) -> dict:
    data = json.loads(row.content)
    data["for_date"] = row.for_date
    data["created_at"] = row.created_at.isoformat() if row.created_at else None
    return data


async def get_or_create_today(force: bool = False) -> dict:
    """Return today's mail scan, running + caching it if missing (or forced)."""
    today = _today()

    if not force:
        with SessionLocal() as db:
            existing = db.scalar(select(DailyMailScan).where(DailyMailScan.for_date == today))
            if existing:
                return _serialize(existing)

    # Run the local-LLM scan (no Claude, nothing leaves the machine).
    result = await mail_extract.scan(scope="today")
    # Auto-pin schedule-worthy items (dated ones also go on the calendar), same as
    # a manual scan — so the morning's items are waiting in the Projects list.
    pinned = await anyio.to_thread.run_sync(pins.auto_pin_items, result["items"])
    for it in result["items"]:
        it["pinned"] = it["email_id"] in pinned
    result["auto_pinned"] = len(pinned)
    content = json.dumps(result)

    with SessionLocal() as db:
        existing = db.scalar(select(DailyMailScan).where(DailyMailScan.for_date == today))
        if existing:
            existing.content = content
        else:
            existing = DailyMailScan(for_date=today, content=content)
            db.add(existing)
        db.commit()
        db.refresh(existing)
        return _serialize(existing)
