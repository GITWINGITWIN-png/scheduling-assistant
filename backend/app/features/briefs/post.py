"""Keeping and posting a brief: one per kind per day in `briefs`, then #summary once Discord is up.

The clock catches up missed rounds *before* Discord connects (main.start_background), so a
brief caught up at startup can't wait for the bot inside its round: it is stored first, and a
task posts it when the bot is ready (at most WAIT_FOR_BOT seconds). If Discord never comes
up, the brief is still there for the today page.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, time

import discord
from sqlalchemy import select

from app.connectors import discord_bot as dc
from app.core.db import session
from app.core.timefmt import local
from app.features.briefs import day
from app.features.briefs.tables import Brief

log = logging.getLogger(__name__)

WAIT_FOR_BOT = 300  # seconds a brief waits for Discord to connect

Card = Callable[[Brief], tuple[discord.Embed, discord.ui.View]]


def open_now(at: datetime, window: tuple[time, time]) -> bool:
    """Is it time for this brief? (window: from, until; until is not included)"""
    return window[0] <= local(at).time() < window[1]


def store(kind: str, at: datetime, parts: dict) -> int | None:
    """Keep today's brief of this kind. -> its id, or None if today already has one."""
    key = day.today(at).isoformat()
    with session() as s:
        if s.scalar(select(Brief.id).where(Brief.kind == kind, Brief.day == key)):
            return None
        brief = Brief(kind=kind, day=key, made_at=at, **parts)
        s.add(brief)
        s.flush()
        return brief.id


def headline(brief_id: int) -> str:
    with session() as s:
        return s.get(Brief, brief_id).headline


_sending: set[asyncio.Task] = set()  # keep a reference, or the task may be collected before it runs


def send_soon(brief_id: int, kind: str, card: Card) -> bool:
    """Post the brief once Discord is up. -> False when Discord isn't set up at all."""
    if not dc.configured():
        return False
    task = asyncio.create_task(_send(brief_id, kind, card), name=f"brief-{brief_id}")
    _sending.add(task)
    task.add_done_callback(_sending.discard)
    return True


async def _send(brief_id: int, kind: str, card: Card) -> None:
    try:
        await asyncio.wait_for(dc.bot.ready_event.wait(), WAIT_FOR_BOT)
    except TimeoutError:
        log.warning("brief %s not sent: Discord didn't connect within %ss (it's on the today page)", brief_id, WAIT_FOR_BOT)
        return
    with session() as s:
        b = s.get(Brief, brief_id)
        if b is None or b.message_id:
            return
        s.expunge(b)
    embed, view = card(b)
    try:
        row, _ = await dc.bot.send("summary", embed=embed, view=view, kind=f"brief_{kind}", ref=f"brief:{brief_id}",
                                   text_copy=f"{b.title}\n{b.headline}")
    except Exception:
        log.exception("brief %s couldn't be posted", brief_id)
        return
    with session() as s:
        s.get(Brief, brief_id).message_id = row.id


def where(sent: bool) -> str:
    return " · ส่งเข้า #สรุป" if sent else " · เก็บไว้ในหน้าวันนี้ (Discord ยังไม่ได้ตั้งค่า)"
