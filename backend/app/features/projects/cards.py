"""Projects in Discord: "ตั้งระดับโปรเจคใหม่" in #อนุมัติ (D5 ⑥), with a menu for potential S–F and
one for urgency 5–0. The levels are saved once both are picked; until then the project works
with C · 2. The same question is in the bell and on the projects page.
"""

from __future__ import annotations

from datetime import datetime

import discord

from app.connectors import discord_bot as dc
from app.core.db import session
from app.core.tables import Decision
from app.core.timefmt import thai_date
from app.features.projects import scan
from app.features.projects.tables import POTENTIALS, Project

URGENCY_WORDS = {5: "5 · เร่งสุด", 4: "4", 3: "3", 2: "2", 1: "1", 0: "0 · ไม่รีบ"}


def _ready() -> bool:
    return dc.bot.ready_event.is_set() and not dc.bot.is_closed()


class LevelMenu(discord.ui.DynamicItem[discord.ui.Select], template=r"plevel:(?P<id>\d+):(?P<what>pot|urg)"):
    def __init__(self, decision_id: int, what: str) -> None:
        self.decision_id, self.what = decision_id, what
        if what == "pot":
            options = [discord.SelectOption(label=f"potential {p}", value=p) for p in POTENTIALS]
            placeholder = "potential (S สูงสุด – F)"
        else:
            options = [discord.SelectOption(label=f"เร่งด่วน {URGENCY_WORDS[u]}", value=str(u)) for u in range(5, -1, -1)]
            placeholder = "ความเร่งด่วน (5 เร่งสุด – 0)"
        super().__init__(discord.ui.Select(placeholder=placeholder, options=options, custom_id=f"plevel:{decision_id}:{what}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]), match["what"])

    async def callback(self, interaction: discord.Interaction) -> None:
        if not dc.bot.is_owner(interaction.user):
            await interaction.response.send_message("เมนูนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
            return
        value = self.item.values[0]
        with session() as s:
            d = s.get(Decision, self.decision_id)
            if d is None or d.status != "pending":
                await interaction.response.send_message("ตั้งระดับโปรเจคนี้ไปแล้ว", ephemeral=True)
                return
            picked = dict(d.detail.get("picked", {}))
            picked[self.what] = value
            d.detail = {**d.detail, "picked": picked}
        if not {"pot", "urg"} <= picked.keys():
            other = "ความเร่งด่วน" if self.what == "pot" else "potential"
            await interaction.response.send_message(f"จดแล้ว · เลือก{other}ต่อได้เลย", ephemeral=True)
            return
        via = ("#อนุมัติ", interaction.message.jump_url if interaction.message else "")
        try:
            d = scan.set_levels(self.decision_id, picked["pot"], int(picked["urg"]), via=via)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await interaction.response.edit_message(content=f"✅ ตั้งระดับแล้ว: {picked['pot']} · เร่งด่วน {picked['urg']}", view=None)


async def ask_level(project_id: int, decision_id: int) -> None:
    """scan.ASKED hook: a new folder under ~/Projects."""
    if not _ready():
        return
    with session() as s:
        p = s.get(Project, project_id)
        name, path, prog, last = p.name, p.path, dict(p.progress or {}), p.last_activity
    fields = [("ล่าสุด", thai_date(last) if isinstance(last, datetime) else "—", True),
              ("ระหว่างรอ", "ใช้ระดับ C · 2", True)]
    if prog.get("next"):
        fields.append(("ขั้นถัดไปใน PROGRESS.md", prog["next"], False))
    card = dc.embed(f"พบ {name} ใน ~/Projects", "ตั้ง potential และความเร่งด่วน: ใช้จัดลำดับงานเบื้องหลัง คำแนะนำ และข่าวด่วน",
                    tone="info", author="โปรเจคใหม่", fields=fields, footer=path)
    row, _ = await dc.bot.send("approve", embed=card, view=dc.buttons(LevelMenu(decision_id, "pot"), LevelMenu(decision_id, "urg")),
                               kind="project_level", ref=f"decision:{decision_id}", text_copy=f"โปรเจคใหม่ {name}")
    with session() as s:
        s.get(Decision, decision_id).message_id = row.id


def setup() -> None:
    dc.register_buttons(LevelMenu)
    if ask_level not in scan.ASKED:
        scan.ASKED.append(ask_level)
