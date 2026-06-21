"""Background scheduler (M5) — the proactive engine's clock.

Currently it pre-warms the daily brief each morning so it's ready before you
open the app. (Lazy generation still covers the case where the server was off at
that time.) Nightly replan is "suggest-only" and computed live in nudges, so it
needs no scheduled job. When a delivery channel exists (email/Telegram, M7),
proactive pushes can be added here.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services import brief_store, mail_store

log = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


async def _morning_brief_job() -> None:
    try:
        await brief_store.get_or_create_today()
    except Exception:  # best-effort; the dashboard will lazily generate it instead
        log.exception("morning brief job failed")


async def _daily_mail_scan_job() -> None:
    """Pre-warm today's local-LLM mail scan so the Mail page is ready.

    Runs on the local model (free, on-device) and writes nothing to the calendar
    — it only caches suggestions for the user to review and pin.
    """
    try:
        await mail_store.get_or_create_today(force=True)
    except Exception:  # best-effort; the Mail page can scan on demand instead
        log.exception("daily mail scan job failed")


def start_scheduler() -> None:
    """Start the scheduler (call from app startup, inside the event loop)."""
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(_morning_brief_job, "cron", hour=7, minute=0, id="morning_brief")
    # Scan today's mail a little after the brief, so the day's items are ready.
    _scheduler.add_job(_daily_mail_scan_job, "cron", hour=7, minute=10, id="daily_mail_scan")
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
