"""ทบทวนเย็น (D3): 21:00 in #สรุป: today's work blocks and the tasks you closed, tomorrow,
work that doesn't fit before its due date, and what the secretary does tonight.

How much of the plan you really followed, and where your time went, need ActivityWatch: they
come with B6 (the user's choice at the B4 plan, 2026-11-06: "รอ B6"), and so do the plan's
buttons that move a missed block. Until then the review only reports.

Like the morning brief: templates only, one per day, and when the machine was off at 21:00
the clock's catch-up still sends it until midnight (after that the morning brief takes over).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta

import discord
from sqlalchemy import select

from app.connectors import discord_bot as dc
from app.core import settings
from app.core.config import get_config
from app.core.db import now, session
from app.core.tables import Action, Task
from app.core.timefmt import local
from app.features.briefs import day, post
from app.features.briefs.morning import day_name
from app.features.briefs.tables import Brief
from app.features.schedule.tasks import hours

OPEN = (time(21, 0), time(23, 59, 59))  # 21:00 until midnight
SCHEDULE_STATE = "state.schedule"  # the planner's last plan (features/schedule/sync.py STATE_KEY)


def open_now(at: datetime) -> bool:
    return post.open_now(at, OPEN)


def closed_today(at: datetime) -> list[str]:
    """Tasks you marked done today (ทำเสร็จแล้ว, on the page or in #ด่วน), not undone."""
    with session() as s:
        rows = s.scalars(select(Action).where(Action.kind == "task.done", Action.at >= day.day_start(day.today(at)),
                                              Action.at < at, Action.undone_at.is_(None)).order_by(Action.at)).all()
    return [r.summary.removeprefix("ทำเสร็จแล้ว: ") for r in rows]


def short_of_time() -> list[str]:
    """Work the planner couldn't fit before its due date, as its last plan said."""
    short = (settings.get(SCHEDULE_STATE, {}) or {}).get("short", {})
    if not short:
        return []
    with session() as s:
        names = {t.id: (t.title, t.due_at) for t in s.scalars(select(Task).where(Task.id.in_([int(k) for k in short])))}
    return [f"{names[int(k)][0]} ขาด {hours(v)}" for k, v in short.items() if int(k) in names]


def tonight(at: datetime) -> str:
    """คืนนี้เลขาจะทำ: the rounds you switched on that run between now and 07:00 tomorrow, and the
    background work waiting in the queue (B5)."""
    from app.core import clock

    end = datetime.combine(day.today(at) + timedelta(days=1), time(7, 0), get_config().tz)
    once: list[tuple[datetime, str]] = []
    often: list[str] = []
    for rnd in clock.ROUNDS.values():
        if rnd.handler is None or rnd.id == "evening" or not clock.enabled(rnd.id):
            continue
        trigger, fires, nxt = rnd.trigger(), [], None
        nxt = trigger.get_next_fire_time(None, at)
        while nxt is not None and nxt <= end and len(fires) < 3:
            fires.append(nxt)
            nxt = trigger.get_next_fire_time(nxt, nxt + timedelta(seconds=1))
        if len(fires) >= 3:  # every few minutes or hours: say how often, not every time
            often.append(f"{rnd.title} ({rnd.when})")
        else:
            once += [(f, rnd.title) for f in fires]
    parts = [" · ".join(f"{local(f):%H:%M} {title}" for f, title in sorted(once))] if once else []
    if often:
        parts.append("รอบประจำ: " + " · ".join(often))
    if jobs := day.jobs_waiting():
        parts.append(("งานเบื้องหลัง 01:00–06:00: " if clock.enabled("jobs") else "งานเบื้องหลัง (รอบปิดอยู่ ไม่ทำคืนนี้): ") + jobs)
    return "\n".join(parts) or "ไม่มีรอบที่เปิดไว้คืนนี้"


def compose(at: datetime) -> dict:
    d = day.today(at)
    blocks = [i for i in day.agenda(d) if i.kind == "block"]
    minutes = sum(int((b.end - b.start).total_seconds() // 60) for b in blocks)
    closed = closed_today(at)
    tomorrow = day.agenda(d + timedelta(days=1))
    short = short_of_time()

    title = f"วันนี้มีบล็อกงาน {len(blocks)} บล็อก รวม {hours(minutes)}" if blocks else "วันนี้ไม่มีบล็อกงาน"
    numbers = [f"ปิดงาน {len(closed)} งาน", f"พรุ่งนี้ {day.appointments(tomorrow)} นัด",
               f"บล็อก {sum(1 for i in tomorrow if i.kind == 'block')}"]
    fields: list[list[str]] = []
    if blocks:
        fields.append(["บล็อกวันนี้", " · ".join(i.words() for i in blocks)])
    if closed:
        fields.append(["ปิดงานวันนี้", " · ".join(closed)])
    fields.append(["พรุ่งนี้", " · ".join(i.words() for i in tomorrow) or "ยังว่าง"])
    if short:
        fields.append(["เวลาไม่พอก่อนกำหนดส่ง", " · ".join(short)])
    fields.append(["คืนนี้เลขาจะทำ", tonight(at)])
    return {"title": title, "headline": " · ".join(numbers), "fields": fields,
            "footer": f"{day_name(at)} · ทำตามแผนได้แค่ไหนและเวลาจริงจาก ActivityWatch มาในช่วง B6 · สรุปนี้ไม่ใช้โทเคน"}


def make(at: datetime) -> int | None:
    return post.store("evening", at, compose(at))


def card(b: Brief) -> tuple[discord.Embed, discord.ui.View]:
    embed = dc.embed(b.title, b.headline, tone="ok", author=f"ทบทวนเย็น · {local(b.made_at):%H:%M}",
                     fields=[(name, text, False) for name, text in b.fields], footer=b.footer)
    view = dc.buttons(discord.ui.Button(label="เปิดหน้าตาราง", style=discord.ButtonStyle.link,
                                        url=get_config().web_url + "/schedule"))
    return embed, view


async def run() -> str | None:
    """The "evening" round (21:00)."""
    at = now()
    if not open_now(at):
        return f"ข้าม: ทบทวนเย็นส่งได้ {OPEN[0]:%H:%M}–เที่ยงคืน · ตอนนี้ {local(at):%H:%M}"
    brief_id = await asyncio.to_thread(make, at)
    if brief_id is None:
        return None
    return post.headline(brief_id) + post.where(post.send_soon(brief_id, "evening", card))


def setup() -> None:
    from app.core import clock
    clock.attach("evening", run)
