"""The ย้อนกลับ button in Discord, for anything in the action log that can be undone (D7, item 7).

Any feature that tells you "เลขาทำเองแล้ว" attaches `UndoButton(action_id)`.
Pressing it calls core.actions.undo(), the same undo as the log page's button.

A feature can also say what the message should show after an undo with
`after_undo[kind] = fn`. For example, a plan reopened by undo shows its
ใช้แผนนี้ · แก้ · ไม่เอา buttons again.
"""

from collections.abc import Awaitable, Callable

import discord

from app.connectors import discord_bot as dc
from app.core import actions
from app.core.tables import Action

# kind -> what to put back on the message after it is undone: (content, view)
after_undo: dict[str, Callable[[Action], Awaitable[tuple[str, discord.ui.View | None]]]] = {}


class UndoButton(discord.ui.DynamicItem[discord.ui.Button], template=r"undo:(?P<id>\d+)"):
    def __init__(self, action_id: int) -> None:
        self.action_id = action_id
        super().__init__(discord.ui.Button(label="ย้อนกลับ", style=discord.ButtonStyle.secondary, custom_id=f"undo:{action_id}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if not dc.bot.is_owner(interaction.user):
            await interaction.response.send_message("ปุ่มนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
            return
        try:
            a = await actions.undo(self.action_id)
        except actions.UndoError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        content, view = f"↩️ ย้อนกลับแล้ว: {a.summary}", None
        if a.kind in after_undo:
            content, view = await after_undo[a.kind](a)
        await interaction.response.edit_message(content=content, view=view)


def setup() -> None:
    dc.register_buttons(UndoButton)
