"""สรุปเช้า (D2): one message in #สรุป at 07:00, built from what the secretary already read.

What it says, as the plan's mockup: a line with the day's numbers, เรื่องสำคัญ (with what the
secretary did), ใครส่งอะไรมา by the three levels, today's appointments and blocks, new
Classroom files, what waits for you (the requests themselves stay in #อนุมัติ), and in the
footer how much mail was read and what that reading cost. No model call: the mail rounds
already wrote every summary (the user's choice, 2026-11-06). Project news comes with B5.

The window is "since the last morning brief" (or a day back), so nothing between two briefs
is missed. Mail that arrived after the 00:00 round and isn't important is only counted: it is
read at 12:00 (the user's choice).

When the machine was off at 07:00, the clock runs the round when it starts: until noon the
brief still goes out (B4's check: off at 07:00, on at 08:00, the brief arrives); after that
it's skipped. A brief that exists for today is never made twice. The clock catches up
*before* Discord connects, so the brief is stored first and sent by a task that waits for
the bot, and the clock is never held up.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time

import discord
from sqlalchemy import select

from app.connectors import discord_bot as dc
from app.core import settings
from app.core.config import get_config
from app.core.db import now, session
from app.core.timefmt import DAYS, MONTHS, local
from app.features.briefs import day
from app.features.briefs.tables import Brief
from app.features.mail import rounds

log = logging.getLogger(__name__)

OPEN = (time(7, 0), time(12, 0))  # the morning brief goes out from 07:00 until noon
WAIT_FOR_BOT = 300  # seconds a caught-up brief waits for Discord to connect


def open_now(at: datetime, window: tuple[time, time] = OPEN) -> bool:
    return window[0] <= local(at).time() < window[1]


def day_name(at: datetime) -> str:
    """"พุธ 4 พ.ย."""
    d = local(at)
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"


def compose(at: datetime) -> dict:
    """The brief's parts at `at` (pure reading, nothing is stored or sent)."""
    since = day.since_last("morning", at)
    important = day.important_mail(since, at)
    who = day.who_sent(since, at)
    items = day.agenda(day.today(at))
    waiting = day.waiting()
    materials = day.new_materials(since, at)
    meets = day.appointments(items)
    due_today = sum(1 for i in items if i.kind == "dead")

    numbers = [f"เรื่องสำคัญ {len(important)}", f"นัดวันนี้ {meets}", f"รอคุณตัดสิน {len(waiting)}"]
    if due_today:
        numbers.append(f"งานส่งวันนี้ {due_today}")
    fields: list[list[str]] = []
    if important:
        fields.append(["เรื่องสำคัญ", "\n".join(f"• {m.line()}" for m in important[:8])
                       + (f"\n• และอีก {len(important) - 8} ฉบับ" if len(important) > 8 else "")])
    if text := day.who_sent_text(who, next_round="12:00"):
        fields.append(["ใครส่งอะไรมา", text])
    fields.append(["นัดวันนี้", " · ".join(i.words() for i in items) or "ไม่มีนัดและบล็อกงานวันนี้"])
    if materials:
        fields.append(["สื่อการเรียนใหม่", " · ".join(materials)])
    if waiting:
        fields.append(["รอคุณตัดสิน", day.waiting_text(waiting) + " → #อนุมัติ"])
    used = day.tokens_used(since, at)
    footer = " · ".join(x for x in (
        f"อ่าน {who.read} ฉบับตั้งแต่สรุปครั้งก่อน" if who.read else "ไม่มีอีเมลที่อ่านตั้งแต่สรุปครั้งก่อน",
        day.tokens_words(used) if used else "",  # what the reading cost (the rounds and the watch)
        "สรุปนี้ไม่ใช้โทเคน") if x)
    return {"title": f"{day_name(at)} · วันนี้มี {meets} นัด", "headline": " · ".join(numbers), "fields": fields,
            "footer": footer}


def make(at: datetime) -> int | None:
    """Store today's brief. -> its id, or None if today already has one."""
    key = day.today(at).isoformat()
    parts = compose(at)
    with session() as s:
        if s.scalar(select(Brief.id).where(Brief.kind == "morning", Brief.day == key)):
            return None
        brief = Brief(kind="morning", day=key, made_at=at, **parts)
        s.add(brief)
        s.flush()
        return brief.id


# ------------------------------------------------------------------ Discord
def card(b: Brief) -> tuple[discord.Embed, discord.ui.View]:
    embed = dc.embed(b.title, b.headline, tone="info", author=f"สรุปเช้า · {local(b.made_at):%H:%M}",
                     fields=[(name, text, False) for name, text in b.fields], footer=b.footer)
    items: list[discord.ui.Item] = []
    approve = dc.bot.channels.get("approve")
    if approve is not None:
        items.append(discord.ui.Button(label="ไป #อนุมัติ", style=discord.ButtonStyle.link, url=approve.jump_url))
    items.append(discord.ui.Button(label="เปิดหน้าวันนี้", style=discord.ButtonStyle.link, url=get_config().web_url + "/"))
    return embed, dc.buttons(*items)


_sending: set[asyncio.Task] = set()  # keep a reference, or the task may be collected before it runs


def send_soon(brief_id: int, kind: str, make_card) -> None:
    """Post the brief once Discord is up (at most WAIT_FOR_BOT seconds from now)."""
    if not dc.configured():
        return
    task = asyncio.create_task(_send(brief_id, kind, make_card), name=f"brief-{brief_id}")
    _sending.add(task)
    task.add_done_callback(_sending.discard)


async def _send(brief_id: int, kind: str, make_card) -> None:
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
    embed, view = make_card(b)
    try:
        row, _ = await dc.bot.send("summary", embed=embed, view=view, kind=f"brief_{kind}", ref=f"brief:{brief_id}",
                                   text_copy=f"{b.title}\n{b.headline}")
    except Exception:
        log.exception("brief %s couldn't be posted", brief_id)
        return
    with session() as s:
        s.get(Brief, brief_id).message_id = row.id


# ------------------------------------------------------------------ the round
async def run() -> str | None:
    """The "morning" round (07:00)."""
    at = now()
    if not open_now(at):
        return f"ข้าม: สรุปเช้าส่งได้ {OPEN[0]:%H:%M}–{OPEN[1]:%H:%M} · ตอนนี้ {local(at):%H:%M}"
    brief_id = await asyncio.to_thread(make, at)
    if brief_id is None:
        return None  # today's is already out
    send_soon(brief_id, "morning", card)
    with session() as s:
        b = s.get(Brief, brief_id)
        return b.headline + (" · ส่งเข้า #สรุป" if dc.configured() else " · เก็บไว้ในหน้าวันนี้ (Discord ยังไม่ได้ตั้งค่า)")


async def remember_night(r: rounds.RoundResult) -> None:
    """ROUND_DONE hook: keep what the 00:00 round picked out of the ignored mail (its #สรุป card,
    which said it, isn't sent any more: the morning brief carries the night, the user's choice)."""
    if r.big:
        settings.put(day.NIGHT_KEY, {"at": now().isoformat(), "noteworthy": [list(x) for x in r.noteworthy],
                                     "skimmed": r.skimmed, "tokens": r.tokens})


def setup() -> None:
    from app.core import clock
    clock.attach("morning", run)
    if remember_night not in rounds.ROUND_DONE:
        rounds.ROUND_DONE.append(remember_night)
