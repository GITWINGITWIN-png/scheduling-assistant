"""B2 in Discord: #ด่วน alerts (D1), appointment requests in #อนุมัติ, the round summary in #สรุป.

- #ด่วน: an email that can't wait (someone important, a keyword, a reply you were
  waiting for). The card has the 1–2 sentence summary, what the secretary already did
  ("เลขาทำให้แล้ว": the appointment it put in your calendar, the task it added), why it
  alerted, and the buttons เปิดอีเมล · ย้อนกลับที่ทำ (undoes all of it at once).
- #อนุมัติ: an appointment from someone who isn't important: รับนัด puts it in the
  calendar (with ย้อนกลับ afterwards), ไม่ไป declines it.
- #สรุป: after each 00:00 / 12:00 round, one card: per person, what they wrote about;
  subjects worth a look among ignored senders; tokens used.

If the bot isn't connected, nothing is posted (the web page still shows everything).
"""

from __future__ import annotations

import logging

import discord

from app.connectors import discord_bot as dc
from app.core import actions
from app.core.db import session
from app.core.tables import Decision, Event
from app.core.timefmt import local
from app.features.actions_discord import UndoButton
from app.features.mail import extract, rounds, watch
from app.features.mail.tables import LEVELS, Email

log = logging.getLogger(__name__)


def _ready() -> bool:
    return dc.bot.ready_event.is_set() and not dc.bot.is_closed()


def _open_email(e: Email) -> discord.ui.Button:
    return discord.ui.Button(label="เปิดอีเมล", style=discord.ButtonStyle.link, url=extract.gmail_link(e))


class UndoAllButton(discord.ui.DynamicItem[discord.ui.Button], template=r"undos:(?P<ids>\d+(?:,\d+)*)"):
    """ย้อนกลับที่ทำ: undoes every action listed on the card (an appointment and a task, say)."""

    def __init__(self, action_ids: list[int]) -> None:
        self.action_ids = action_ids
        super().__init__(discord.ui.Button(label="ย้อนกลับที่ทำ", style=discord.ButtonStyle.secondary,
                                           custom_id="undos:" + ",".join(map(str, action_ids))))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls([int(x) for x in match["ids"].split(",")])

    async def callback(self, interaction: discord.Interaction) -> None:
        if not dc.bot.is_owner(interaction.user):
            await interaction.response.send_message("ปุ่มนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
            return
        await interaction.response.defer()
        done, failed = [], []
        for action_id in self.action_ids:
            try:
                done.append((await actions.undo(action_id)).summary)
            except actions.UndoError as exc:
                failed.append(str(exc))
        note = "↩️ ย้อนกลับแล้ว: " + " · ".join(done) if done else ""
        if failed:
            note += ("\n" if note else "") + "ย้อนไม่ได้: " + " · ".join(failed)
        keep = [i for i in (interaction.message.components[0].children if interaction.message and interaction.message.components else [])
                if getattr(i, "url", None)]  # keep เปิดอีเมล
        view = dc.buttons(*(discord.ui.Button(label=b.label, style=discord.ButtonStyle.link, url=b.url) for b in keep)) if keep else None
        await interaction.edit_original_response(content=note, view=view)


async def alert(r: watch.ReadEmail) -> None:
    """AFTER_READ hook (runs after extract.on_read): the #ด่วน card for an email that can't wait."""
    e = r.email
    done = extract.DONE.pop(e.id, [])
    if not (e.flagged or e.level == "important") or not _ready():
        return
    who = e.sender_name or e.sender
    heading = {"important": f"อีเมลจากคนสำคัญ · {who}", "awaiting": f"ตอบเรื่องที่คุณรอ · {who}"}.get(
        e.flagged, f"อีเมลจาก{LEVELS.get(e.level, '')} · {who}")
    fields = [("เลขาทำให้แล้ว", "\n".join(f"• {text}" for text, _ in done), False)] if done else []
    if r.reading.needs_reply:
        fields.append(("ต้องตอบ", "เรื่องนี้รอคำตอบจากคุณ", True))
    if r.reading.events and not extract._direct(e):  # not important: its appointments wait in #อนุมัติ
        fields.append(("รอคุณรับ", "นัดอยู่ใน #อนุมัติ", True))
    card = dc.embed(e.subject or "(ไม่มีหัวข้อ)", r.reading.summary, tone="bad" if e.flagged in ("important", "awaiting") else "warn",
                    fields=fields, author=heading, footer=f"{watch.flag_label(e.flagged)} · ส่งเมื่อ {local(e.sent_at):%H:%M}")
    items: list[discord.ui.Item] = [_open_email(e)]
    if done:
        items.append(UndoAllButton([a for _, a in done]))
    await dc.bot.send("urgent", embed=card, view=dc.buttons(*items), kind="mail_alert", ref=f"email:{e.id}", text_copy=r.reading.summary)


class AppointmentButton(discord.ui.DynamicItem[discord.ui.Button], template=r"appt:(?P<id>\d+):(?P<act>yes|no)"):
    def __init__(self, decision_id: int, act: str) -> None:
        self.decision_id, self.act = decision_id, act
        label, style = ("รับนัด", discord.ButtonStyle.success) if act == "yes" else ("ไม่ไป", discord.ButtonStyle.secondary)
        super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"appt:{decision_id}:{act}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]), match["act"])

    async def callback(self, interaction: discord.Interaction) -> None:
        if not dc.bot.is_owner(interaction.user):
            await interaction.response.send_message("ปุ่มนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
            return
        await interaction.response.defer()
        via = ("#อนุมัติ", interaction.message.jump_url if interaction.message else "")
        try:
            d, action_id = await extract.decide(self.decision_id, self.act == "yes", via=via)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        if action_id:
            await interaction.edit_original_response(content="✅ รับนัดแล้ว · ลงปฏิทินให้แล้ว", view=dc.buttons(UndoButton(action_id)))
        else:
            await interaction.edit_original_response(content="ไม่ไปนัดนี้", view=None)


async def ask_appointment(event_id: int, decision_id: int, e: Email) -> None:
    """PROPOSED hook: an appointment from someone not important, waiting for you in #อนุมัติ."""
    if not _ready():
        return
    with session() as s:
        ev, d = s.get(Event, event_id), s.get(Decision, decision_id)
        title, when, place = ev.title, d.detail.get("when", ""), ev.location
    card = dc.embed(title, f"**{when}**" + (f" · {place}" if place else ""), tone="info",
                    author=f"นัดรอคุณรับ · {e.sender_name or e.sender} ({LEVELS.get(e.level, e.level)})",
                    fields=[("จากอีเมล", e.subject or "(ไม่มีหัวข้อ)", False)], footer="กดรับแล้วเลขาลงปฏิทินให้ · ย้อนกลับได้")
    sent_row, _ = await dc.bot.send("approve", embed=card, view=dc.buttons(AppointmentButton(decision_id, "yes"),
                                    AppointmentButton(decision_id, "no"), _open_email(e)),
                                    kind="appointment", ref=f"decision:{decision_id}", text_copy=f"{title} · {when}")
    with session() as s:
        s.get(Decision, decision_id).message_id = sent_row.id


async def round_summary(r: rounds.RoundResult) -> None:
    """ROUND_DONE hook: the #สรุป card ("สรุปรายคนรายวัน")."""
    if not _ready() or not (r.people or r.noteworthy or r.important):
        return
    lines = []
    for p in r.people:
        extra = []
        if p.reading.events:
            extra.append(f"นัด {len(p.reading.events)}")
        if p.reading.tasks:
            extra.append(f"งาน {len(p.reading.tasks)}")
        if p.reading.needs_reply:
            extra.append("ต้องตอบ")
        lines.append(f"**{p.name}** ({p.count} ฉบับ{' · ' + ' · '.join(extra) if extra else ''}): {p.reading.summary or '—'}")
    fields = []
    if r.noteworthy:
        fields.append(("น่าดูจากผู้ส่งที่ไม่สนใจ", "\n".join(f"• {who}: {subject} ({why})" for who, subject, why in r.noteworthy[:8]), False))
    title = f"อีเมลรอบ {'00:00' if r.big else '12:00'}"
    card = dc.embed(title, "\n".join(lines) or "ไม่มีอีเมลจากคนที่สนใจ", tone="info",
                    author="สรุปอีเมล · คนที่สนใจ รายคน", fields=fields,
                    footer=r.line() + (" · นัดที่ต้องรับอยู่ใน #อนุมัติ" if any(p.reading.events for p in r.people) else ""))
    await dc.bot.send("summary", embed=card, kind="mail_round", ref="round:big" if r.big else "round:small", text_copy="\n".join(lines))


def setup() -> None:
    dc.register_buttons(UndoAllButton, AppointmentButton)
    for hooks, fn in ((watch.AFTER_READ, alert), (extract.PROPOSED, ask_appointment), (rounds.ROUND_DONE, round_summary)):
        if fn not in hooks:
            hooks.append(fn)
