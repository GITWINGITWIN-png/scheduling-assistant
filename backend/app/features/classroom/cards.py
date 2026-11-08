"""Classroom in Discord: "ติดตามวิชานี้ไหม" in #อนุมัติ, with ติดตาม / ไม่ติดตาม buttons.

The same question is in the web bell; answering in either place answers both.
"""

from __future__ import annotations

import discord

from app.connectors import discord_bot as dc
from app.core.db import session
from app.core.tables import Decision
from app.features import decisions
from app.features.actions_discord import UndoButton
from app.features.classroom import sync


def _ready() -> bool:
    return dc.bot.ready_event.is_set() and not dc.bot.is_closed()


class CourseButton(discord.ui.DynamicItem[discord.ui.Button], template=r"course:(?P<id>\d+):(?P<act>yes|no)"):
    def __init__(self, decision_id: int, act: str) -> None:
        self.decision_id, self.act = decision_id, act
        label, style = ("ติดตาม", discord.ButtonStyle.success) if act == "yes" else ("ไม่ติดตาม", discord.ButtonStyle.secondary)
        super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"course:{decision_id}:{act}"))

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
            d, action_id = await sync.decide(self.decision_id, self.act == "yes", via=via)
        except decisions.Answered as exc:  # answered elsewhere (the web, say): the card says how, without buttons
            await interaction.edit_original_response(content=str(exc), view=None)
            return
        except ValueError as exc:  # couldn't be done: the buttons stay
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        note = (f"✅ ติดตามแล้ว · สื่อไปที่ `{d.detail['folder']}` · งานที่มีกำหนดส่งจะเข้าตารางในรอบถัดไป"
                if self.act == "yes" else "ไม่ติดตามวิชานี้ · จะไม่ถามอีก")
        await interaction.edit_original_response(content=note, view=dc.buttons(UndoButton(action_id)))


async def ask_course(course_id: str, decision_id: int) -> None:
    """sync.ASKED hook: put a new (or busy again) course to you."""
    if not _ready():
        return
    with session() as s:
        d = s.get(Decision, decision_id)
        detail, name = dict(d.detail), d.title
    where = f"`{detail['folder']}`" + ("" if detail.get("exists") else "\nยังไม่มีโฟลเดอร์ของวิชานี้ · กดติดตามแล้วเลขาสร้างให้")
    card = dc.embed(name, "ติดตามวิชานี้ไหม: งานที่มีกำหนดส่งเข้าตาราง และสื่อการเรียนใหม่ดาวน์โหลดลงโฟลเดอร์วิชา",
                    tone="info", author="วิชาใน Classroom", fields=[("เก็บสื่อที่", where, False)],
                    footer="เปลี่ยนโฟลเดอร์ได้ในหน้าตาราง ก่อนกดติดตาม")
    items: list[discord.ui.Item] = [CourseButton(decision_id, "yes"), CourseButton(decision_id, "no")]
    if detail.get("link", "").startswith("http"):
        items.append(discord.ui.Button(label="เปิดใน Classroom", style=discord.ButtonStyle.link, url=detail["link"]))
    row, _ = await dc.bot.send("approve", embed=card, view=dc.buttons(*items), kind="course",
                               ref=f"decision:{decision_id}", text_copy=f"ติดตามวิชา {name} ไหม")
    with session() as s:
        s.get(Decision, decision_id).message_id = row.id


def setup() -> None:
    dc.register_buttons(CourseButton)
    if ask_course not in sync.ASKED:
        sync.ASKED.append(ask_course)
