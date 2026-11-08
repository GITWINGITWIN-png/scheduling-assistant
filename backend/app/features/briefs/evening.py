"""ทบทวนเย็น (D3): 21:00 in #สรุป: how much of today's plan you followed, the blocks you missed
and what you did instead, where your time really went, the tasks you closed, tomorrow, work that
doesn't fit before its due date, and what the secretary does tonight.

With ActivityWatch (B6; the user's choice at the B4 plan was to wait for it): the title says
"ทำตามตารางได้ 4 จาก 5 บล็อก (80%)", and a missed block says what took its place and where the
planner put its time. A missed task booked again for tonight gets "ย้าย … ไปพรุ่งนี้" (D3 ⑤);
"โอเค" just takes the buttons away. Without recorded time (recording off), it's B4's review.

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
from app.core.tables import Action, Block, Task
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


def next_block(task_id: int, after: datetime) -> datetime | None:
    """Where the planner put a task's time next (after a missed block)."""
    with session() as s:
        return s.scalar(select(Block.starts_at).where(Block.task_id == task_id, Block.status.in_(("planned", "pinned")),
                                                      Block.starts_at >= after).order_by(Block.starts_at))


def missed_words(b: Block, t: Task, at: datetime) -> str:
    """"finance review 16:00 · คุณทำ my_secretary ต่อแทน · เลขาหาเวลาใหม่: พรุ่งนี้ 09:00"."""
    from app.features.time.categorize import CATEGORIES

    parts = [f"{t.title} {local(b.starts_at):%H:%M}"]
    if b.instead:  # a project's name, or a category's when it wasn't a project
        parts.append(f"ช่วงนั้นเป็น{b.instead}" if b.instead in CATEGORIES.values() else f"คุณทำ {b.instead} แทน")
    nxt = next_block(t.id, at)
    if t.status != "open":
        parts.append("งานปิดแล้ว")
    elif nxt is not None:
        when = "คืนนี้" if day.today(nxt) == day.today(at) else ("พรุ่งนี้" if day.today(nxt) == day.today(at) + timedelta(days=1)
                                                               else day_name(nxt))
        parts.append(f"เลขาหาเวลาใหม่: {when} {local(nxt):%H:%M}")
    else:
        parts.append("ยังไม่มีเวลาว่างให้ (ดูหน้าตาราง)")
    return " · ".join(parts)


def actual_today(at: datetime) -> str:
    """เวลาจริงวันนี้: "โค้ด 5.5 ชม. · เรียน 1 · ประชุม 1 · เว็บ 1.2" (by category, the biggest first)."""
    from app.features.time import insights
    from app.features.time.categorize import CATEGORIES

    rows = insights.rows(day.day_start(day.today(at)), at)
    per: dict[str, float] = {}
    for r in rows:
        per[r.category or "other"] = per.get(r.category or "other", 0) + insights.minutes(r)
    short = {"code": "โค้ด", "study": "เรียน", "meeting": "ประชุม", "chat": "อีเมลและแชท", "web": "เว็บ", "other": "อื่นๆ"}
    items = sorted(((k, v) for k, v in per.items() if v >= 5), key=lambda kv: -kv[1])
    out = []
    for i, (k, v) in enumerate(items):
        h = round(v / 60, 1)
        out.append(f"{short.get(k, CATEGORIES.get(k, k))} {h:g}" + (" ชม." if i == 0 else ""))
    return " · ".join(out)


def to_move(at: datetime) -> list[tuple[int, str]]:
    """Missed tasks whose time the planner put back tonight: offered "ย้ายไปพรุ่งนี้". -> [(task id, title)]."""
    from app.features.time import followed

    lo = day.day_start(day.today(at))
    out: list[tuple[int, str]] = []
    for b, t in followed.followed(lo, at)["missed"]:
        nxt = next_block(t.id, at)
        if t.status == "open" and nxt is not None and day.today(nxt) == day.today(at) and t.id not in [x for x, _ in out]:
            out.append((t.id, t.title))
    return out[:3]


def compose(at: datetime) -> dict:
    from app.features.time import followed

    d = day.today(at)
    blocks = [i for i in day.agenda(d) if i.kind == "block"]
    minutes = sum(int((b.end - b.start).total_seconds() // 60) for b in blocks)
    closed = closed_today(at)
    tomorrow = day.agenda(d + timedelta(days=1))
    short = short_of_time()
    f = followed.followed(day.day_start(d), at)
    real = actual_today(at)

    counted = len(f["done"]) + len(f["missed"])
    if counted:
        title = f"วันนี้ทำตามตารางได้ {len(f['done'])} จาก {counted} บล็อก ({f['percent']}%)"
    else:
        title = f"วันนี้มีบล็อกงาน {len(blocks)} บล็อก รวม {hours(minutes)}" if blocks else "วันนี้ไม่มีบล็อกงาน"
    numbers = [f"ปิดงาน {len(closed)} งาน", f"พรุ่งนี้ {day.appointments(tomorrow)} นัด",
               f"บล็อก {sum(1 for i in tomorrow if i.kind == 'block')}"]
    fields: list[list[str]] = []
    if f["missed"]:
        fields.append(["หลุดแผน", "\n".join(missed_words(b, t, at) for b, t in f["missed"])])
    if f["away"]:
        fields.append(["ไม่ได้ใช้คอมช่วงบล็อก (นับว่าทำแล้ว)", " · ".join(f"{t.title} {local(b.starts_at):%H:%M}" for b, t in f["away"])])
    if real:
        fields.append(["เวลาจริงวันนี้", real])
    if blocks and not counted:
        fields.append(["บล็อกวันนี้", " · ".join(i.words() for i in blocks)])
    if closed:
        fields.append(["ปิดงานวันนี้", " · ".join(closed)])
    fields.append(["พรุ่งนี้", " · ".join(i.words() for i in tomorrow) or "ยังว่าง"])
    if short:
        fields.append(["เวลาไม่พอก่อนกำหนดส่ง", " · ".join(short)])
    fields.append(["คืนนี้เลขาจะทำ", tonight(at)])
    source = "เทียบกับ ActivityWatch ผ่านตัวกรองความเป็นส่วนตัว" if (counted or real) else "ยังไม่ได้เปิดบันทึกกิจกรรม (หน้าการใช้เวลา)"
    return {"title": title, "headline": " · ".join(numbers), "fields": fields,
            "footer": f"{day_name(at)} · {source} · สรุปนี้ไม่ใช้โทเคน"}


def make(at: datetime) -> int | None:
    return post.store("evening", at, compose(at))


def card(b: Brief) -> tuple[discord.Embed, discord.ui.View]:
    embed = dc.embed(b.title, b.headline, tone="ok", author=f"ทบทวนเย็น · {local(b.made_at):%H:%M}",
                     fields=[(name, text, False) for name, text in b.fields], footer=b.footer)
    moves = [MoveButton(task_id, title) for task_id, title in to_move(now())] if day.today(now()).isoformat() == b.day else []
    view = dc.buttons(*moves, *([OkButton()] if moves else []),
                      discord.ui.Button(label="เปิดหน้าตาราง", style=discord.ButtonStyle.link, url=get_config().web_url + "/schedule"))
    return embed, view


class MoveButton(discord.ui.DynamicItem[discord.ui.Button], template=r"tomorrow:(?P<id>\d+)"):
    """ย้าย … ไปพรุ่งนี้ (D3 ⑤): the task's time is booked from tomorrow on, and the plan changes at once."""

    def __init__(self, task_id: int, title: str = "") -> None:
        self.task_id = task_id
        label = f"ย้าย {title[:40]} ไปพรุ่งนี้" if title else "ย้ายไปพรุ่งนี้"
        super().__init__(discord.ui.Button(label=label, style=discord.ButtonStyle.primary, custom_id=f"tomorrow:{task_id}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        from app.features.actions_discord import UndoButton
        from app.features.schedule import sync
        from app.features.time import followed

        if not dc.bot.is_owner(interaction.user):
            await interaction.response.send_message("ปุ่มนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
            return
        try:
            action_id = followed.move_to_tomorrow(self.task_id, via=("#สรุป", interaction.message.jump_url if interaction.message else ""))
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await interaction.response.defer()
        await sync.run(force=True)
        nxt = next_block(self.task_id, now())
        with session() as s:
            title = s.get(Task, self.task_id).title
        said = f"✅ ย้าย {title} ไปพรุ่งนี้แล้ว" + (f" · เลขาวางไว้ {day_name(nxt)} {local(nxt):%H:%M}" if nxt else "")
        await interaction.followup.send(said, view=dc.buttons(UndoButton(action_id)))


class OkButton(discord.ui.DynamicItem[discord.ui.Button], template=r"evening:ok"):
    """โอเค: nothing to change; the buttons go."""

    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="โอเค", style=discord.ButtonStyle.secondary, custom_id="evening:ok"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        if not dc.bot.is_owner(interaction.user):
            await interaction.response.send_message("ปุ่มนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
            return
        await interaction.response.edit_message(view=None)


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
    dc.register_buttons(MoveButton, OkButton)
