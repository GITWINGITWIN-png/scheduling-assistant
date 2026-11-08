"""เตือนก่อนถึงกำหนด (P5): "tomorrow" and "in an hour" messages in #ด่วน. The round "remind", every 5 minutes.

What gets reminded:
- appointments on your primary calendar (copied in by sync.py), and the ones the
  secretary placed from email. Not repeating ones (a weekly class: you know it, and 20
  pings a week would bury the real ones), not whole-day entries.
- the due date of every open task (email, Classroom, your own).

When: the smallest lead that already applies, from LEADS ("1d" when it is a day or less
away, "1h" when it is an hour or less away), each sent once per time (a moved
appointment is reminded again for its new time). The day-before reminder is skipped
for something that arrived from email less than an hour ago: its #ด่วน card just told you.

No model, no tokens. If Discord isn't connected nothing is sent or recorded, so the
reminder still goes out once the bot is back (if it's still in time).
"""

from __future__ import annotations

import logging
from datetime import timedelta

import discord
from sqlalchemy import select

from app.connectors import discord_bot as dc
from app.core import settings
from app.core.db import now, session
from app.core.tables import Event, Reminder, Task
from app.core.timefmt import local, thai_datetime
from app.features.classroom.tables import CourseItem
from app.features.mail.extract import gmail_link
from app.features.mail.tables import Email
from app.features.schedule import tasks as task_ops

log = logging.getLogger(__name__)

LEADS = {"1h": timedelta(hours=1), "1d": timedelta(days=1)}  # smallest first
LEADS_KEY = "schedule.reminders"  # which leads are on, e.g. ["1d", "1h"] (the plan's default: both)
JUST_ARRIVED = timedelta(hours=1)


def leads() -> dict[str, timedelta]:
    on = settings.get(LEADS_KEY, list(LEADS))
    return {k: v for k, v in LEADS.items() if k in on}


def _lead_for(left: timedelta, active: dict[str, timedelta]) -> str | None:
    """The smallest lead the time left already falls under ("1h" beats "1d")."""
    return next((k for k, v in active.items() if left <= v), None)


def _when_words(start, all_day: bool = False) -> str:
    day = local(start).date()
    today = local(now()).date()
    name = "วันนี้" if day == today else "พรุ่งนี้" if day == today + timedelta(days=1) else thai_datetime(start).split(" ")[0]
    return name if all_day else f"{name} {local(start):%H:%M}"


def _ready() -> bool:
    return dc.bot.ready_event.is_set() and not dc.bot.is_closed()


# ------------------------------------------------------------------ the button
class TaskDoneButton(discord.ui.DynamicItem[discord.ui.Button], template=r"taskdone:(?P<id>\d+)"):
    def __init__(self, task_id: int) -> None:
        self.task_id = task_id
        super().__init__(discord.ui.Button(label="ทำเสร็จแล้ว", style=discord.ButtonStyle.success,
                                           custom_id=f"taskdone:{task_id}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if not dc.bot.is_owner(interaction.user):
            await interaction.response.send_message("ปุ่มนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
            return
        try:
            action_id = task_ops.done(self.task_id, via=("#ด่วน", interaction.message.jump_url if interaction.message else ""))
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        from app.features.actions_discord import UndoButton
        await interaction.response.edit_message(content="✅ ปิดงานแล้ว · บล็อกที่เหลือจะหายจากปฏิทินในรอบถัดไป",
                                                view=dc.buttons(UndoButton(action_id)))


# ------------------------------------------------------------------ what's due
def _due_events(at, horizon, active) -> list[tuple[Event, str]]:
    with session() as s:
        rows = s.scalars(select(Event).where(Event.status == "placed", Event.all_day.is_(False), Event.recurring.is_(False),
                                             Event.starts_at > at, Event.starts_at <= at + horizon)).all()
        s.expunge_all()
    out = []
    for ev in rows:
        lead = _lead_for(ev.starts_at - at, active)
        if lead == "1d" and ev.source == "email" and ev.created_at > at - JUST_ARRIVED:
            continue
        if lead:
            out.append((ev, lead))
    return out


def _due_tasks(at, horizon, active) -> list[tuple[Task, str]]:
    with session() as s:
        rows = s.scalars(select(Task).where(Task.status == "open", Task.due_at.is_not(None),
                                            Task.due_at > at, Task.due_at <= at + horizon)).all()
        s.expunge_all()
    out = []
    for t in rows:
        lead = _lead_for(t.due_at - at, active)
        if lead == "1d" and t.source == "email" and t.created_at > at - JUST_ARRIVED:
            continue
        if lead:
            out.append((t, lead))
    return out


def _sent(kind: str, ref_id: int, lead: str, due) -> bool:
    with session() as s:
        return s.scalar(select(Reminder.id).where(Reminder.kind == kind, Reminder.ref_id == ref_id,
                                                  Reminder.lead == lead, Reminder.due_at == due)) is not None


def _link_button(label: str, url: str) -> list[discord.ui.Item]:
    return [discord.ui.Button(label=label, style=discord.ButtonStyle.link, url=url)] if url.startswith("http") else []


def _source_link(source: str, ref: str) -> tuple[str, str]:
    """(button label, url) for where a task or appointment came from."""
    with session() as s:
        if source == "email" and (email := s.get(Email, ref)):
            return "เปิดอีเมล", gmail_link(email)
        if source == "classroom" and (item := s.get(CourseItem, ref)):
            return "ส่งงานใน Classroom", item.link
    return "", ""


async def _send_event(ev: Event, lead: str) -> int:
    label, url = _source_link(ev.source, ev.source_ref) if ev.source == "email" else ("เปิดในปฏิทิน", ev.link)
    head = "อีก 1 ชั่วโมง" if lead == "1h" else _when_words(ev.starts_at)
    card = dc.embed(ev.title, f"**{local(ev.starts_at):%H:%M}–{local(ev.ends_at):%H:%M}**" + (f" · {ev.location}" if ev.location else ""),
                    tone="warn" if lead == "1h" else "info", author=f"นัด · {head}",
                    footer="เตือนก่อนถึงกำหนด" + (" · นัดนี้มาจากอีเมล" if ev.source == "email" else ""))
    row, _ = await dc.bot.send("urgent", embed=card, view=dc.buttons(*_link_button(label or "เปิดในปฏิทิน", url)) if url else None,
                               kind="reminder", ref=f"event:{ev.id}", text_copy=f"{head}: {ev.title}")
    return row.id


async def _send_task(t: Task, lead: str) -> int:
    label, url = _source_link(t.source, t.source_ref)
    head = "อีก 1 ชั่วโมง" if lead == "1h" else _when_words(t.due_at)
    card = dc.embed(t.title, f"ต้องส่ง **{thai_datetime(t.due_at)}**", tone="bad" if lead == "1h" else "warn",
                    author=f"เดดไลน์ · {head}", fields=[("รายละเอียด", t.details, False)] if t.details.strip() else (),
                    footer="เตือนก่อนถึงกำหนด · กดทำเสร็จแล้ว ตารางจะเอาบล็อกที่เหลือออก")
    row, _ = await dc.bot.send("urgent", embed=card, view=dc.buttons(TaskDoneButton(t.id), *_link_button(label, url)),
                               kind="reminder", ref=f"task:{t.id}", text_copy=f"เดดไลน์ {head}: {t.title}")
    return row.id


async def run() -> str | None:
    """The "remind" round. -> "เตือน 2 เรื่อง", or None when nothing was due."""
    if not _ready():
        return None
    at, active = now(), leads()
    if not active:
        return None
    horizon = max(active.values())
    sent = []
    for kind, items, send in (("event", _due_events(at, horizon, active), _send_event),
                              ("task", _due_tasks(at, horizon, active), _send_task)):
        for item, lead in items:
            due = item.starts_at if kind == "event" else item.due_at
            if _sent(kind, item.id, lead, due):
                continue
            message_id = await send(item, lead)
            with session() as s:
                s.add(Reminder(kind=kind, ref_id=item.id, lead=lead, due_at=due, message_id=message_id))
            sent.append(item.title)
    return f"เตือน {len(sent)} เรื่อง: {', '.join(sent)}" if sent else None


def setup() -> None:
    from app.core import clock
    dc.register_buttons(TaskDoneButton)
    clock.attach("remind", run)
