"""The quota watcher (2.2, W4 ①): how much of your Claude plan is left this week.

Of the three ways the plan's risk note listed, the first works (checked 2026-11-06): with every
call the Claude Code CLI reports a RateLimitEvent whose raw data has `unifiedWindows` with the
share used of the 7-day and the 5-hour windows and when each resets. So every call the
secretary already makes keeps this fresh (core/llm.py passes the events here), and before
background work a tiny call (`probe`, a handful of tokens) refreshes a reading that's too old.

The 70% line: above it, low-risk background work may start on its own; at or below it, every
plan asks you. When there's no fresh reading at all, the quota counts as unknown, and then every
plan asks too (the agreed rule). The line and its switch are a rule in the rule book
(core/rules/book.py `line()`, `auto()`), so you can change them on its page.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.db import now, session
from app.features.jobs.tables import QuotaReading

log = logging.getLogger(__name__)

KEEP_EVERY = timedelta(minutes=10)  # an unchanged reading is kept this often
FRESH = timedelta(hours=1)  # older than this, background work reads it again first


def _ts(value) -> datetime | None:
    return datetime.fromtimestamp(int(value), tz=timezone.utc) if value else None


def parse(raw: dict) -> dict | None:
    """RateLimitEvent's raw dict -> the numbers kept, or None if it has no 7-day window."""
    windows = raw.get("unifiedWindows") or {}
    week = windows.get("seven_day") or {}
    if week.get("utilization") is None:
        return None
    five = windows.get("five_hour") or {}
    return {"week_left": round(100 * (1 - float(week["utilization"])), 1), "week_resets_at": _ts(week.get("resetsAt")),
            "five_left": round(100 * (1 - float(five["utilization"])), 1) if five.get("utilization") is not None else None,
            "five_resets_at": _ts(five.get("resetsAt"))}


def observe(raw: dict) -> None:
    """core/llm.py hook: every RateLimitEvent the CLI sends."""
    numbers = parse(raw)
    if numbers is None:
        return
    with session() as s:
        last = s.scalar(select(QuotaReading).order_by(QuotaReading.at.desc()))
        same = last is not None and (last.week_left, last.five_left) == (numbers["week_left"], numbers["five_left"])
        if same and now() - last.at < KEEP_EVERY:
            return
        s.add(QuotaReading(source="sdk", raw=raw, **numbers))


def latest(max_age: timedelta | None = FRESH) -> QuotaReading | None:
    """The newest reading, if it's not older than max_age (None: any age)."""
    with session() as s:
        row = s.scalar(select(QuotaReading).order_by(QuotaReading.at.desc()))
        if row is None or (max_age is not None and now() - row.at > max_age):
            return None
        s.expunge(row)
        return row


async def probe() -> QuotaReading | None:
    """A tiny call just to hear the CLI's RateLimitEvent (a few tokens). -> the fresh reading."""
    from app.core import llm
    try:
        await llm.run("quota", "ตอบคำว่า ok", system="ตอบคำเดียว", model="sonnet", effort="low", max_turns=1)
    except llm.LLMError as exc:
        log.warning("quota probe failed: %s", exc)
    return latest()


async def week_left(max_age: timedelta = FRESH) -> float | None:
    """Percent of the week left, read again first when the last reading is too old. None: unknown."""
    reading = latest(max_age) or await probe()
    return reading.week_left if reading else None


def setup() -> None:
    from app.core import llm
    if observe not in llm.RATE_LIMITS:
        llm.RATE_LIMITS.append(observe)
