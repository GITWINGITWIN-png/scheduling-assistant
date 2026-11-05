"""Ask the secretary in your private Discord chat (D7).

- You write in the DM, and the answer comes back as a *reply* to your message,
  with the model, effort, time and sources underneath.
- "ให้ Opus คิดต่อ" under a quick answer: Opus answers the same question.
  The button finds the question through the reply link, so it still works
  days later or after a restart.
- A plan from Opus comes with ใช้แผนนี้ · แก้ · ไม่เอา. "แก้" opens a box
  where you type the change, and Opus rewrites the plan.

The logic is in features/ask.py; this file only turns it into Discord messages.
"""

import discord

from app.connectors import discord_bot as dc
from app.core.tables import Action, Decision
from app.core.db import session
from app.features import ask
from app.features.actions_discord import UndoButton, after_undo


async def _history(message: discord.Message, limit: int = 6) -> list[tuple[str, str]]:
    """The last few messages before this one, so a follow-up like "แล้วเมื่อวานล่ะ" makes sense."""
    items: list[tuple[str, str]] = []
    async for m in message.channel.history(limit=limit, before=message):
        if m.author.bot:
            card = m.embeds[0] if m.embeds else None
            said = " ".join(x for x in ((card.title if card else ""), (card.description if card else ""), m.content) if x)
            items.append(("เลขา", said))
        else:
            items.append(("คุณ", m.content))
    return list(reversed(items))


def answer_card(a: ask.Answer, deep_button: bool = True) -> tuple[discord.Embed, discord.ui.View | None]:
    if a.kind == "plan":
        card = dc.embed(a.title, a.text, footer=a.footer)
        return card, dc.buttons(*(PlanButton(a.decision_id, act) for act in ("approve", "edit", "reject")))
    card = dc.embed(description=a.text, footer=a.footer)
    return card, (dc.buttons(DeepButton()) if deep_button else None)


async def on_dm(message: discord.Message) -> None:
    if not message.content.strip():
        return
    async with message.channel.typing():  # "เลขากำลังพิมพ์…" while Sonnet/Opus works
        a = await ask.ask(message.content, await _history(message), via=_via(message))
    card, view = answer_card(a)
    await dc.bot.send("dm", content=f"✨ {ask.HANDOFF_NOTE}" if a.kind == "plan" else None, embed=card, view=view,
                      kind=a.kind, ref=f"decision:{a.decision_id}" if a.decision_id else "ask",
                      reply_to=message, text_copy=a.text)


async def _owner_only(interaction: discord.Interaction) -> bool:
    if dc.bot.is_owner(interaction.user):
        return True
    await interaction.response.send_message("ปุ่มนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
    return False


class DeepButton(discord.ui.DynamicItem[discord.ui.Button], template=r"ask:deep"):
    """ให้ Opus คิดต่อ."""

    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="ให้ Opus คิดต่อ", style=discord.ButtonStyle.secondary, custom_id="ask:deep"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _owner_only(interaction):
            return
        ref = interaction.message.reference if interaction.message else None
        if not ref or not ref.message_id:
            await interaction.response.send_message("หาคำถามเดิมไม่เจอ ลองพิมพ์ถามใหม่", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)  # Discord wants a response within 3 s
        question = ref.resolved if isinstance(ref.resolved, discord.Message) else await interaction.channel.fetch_message(ref.message_id)
        a = await ask.deepen(question.content, await _history(question), via=_via(question))
        card, view = answer_card(a, deep_button=False)  # already Opus
        kwargs = {"view": view} if view else {}
        sent = await interaction.followup.send(embed=card, wait=True, **kwargs)
        dc.bot.record("dm", sent, kind=a.kind, ref=f"decision:{a.decision_id}" if a.decision_id else "ask_deep", text_copy=a.text)


PLAN_ACTIONS = {
    "approve": ("ใช้แผนนี้", discord.ButtonStyle.success),
    "edit": ("แก้", discord.ButtonStyle.secondary),
    "reject": ("ไม่เอา", discord.ButtonStyle.secondary),
}


class PlanButton(discord.ui.DynamicItem[discord.ui.Button], template=r"plan:(?P<id>\d+):(?P<act>approve|edit|reject)"):
    def __init__(self, decision_id: int, act: str) -> None:
        self.decision_id, self.act = decision_id, act
        label, style = PLAN_ACTIONS[act]
        super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"plan:{decision_id}:{act}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]), match["act"])

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _owner_only(interaction):
            return
        if self.act == "edit":
            await interaction.response.send_modal(EditPlanModal(self.decision_id))
            return
        try:
            _, action_id = ask.decide(self.decision_id, self.act, via=_via(interaction.message))
        except ask.DecisionError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        done = ("✅ ใช้แผนนี้แล้ว · เก็บไว้ในเรื่องที่ตัดสินแล้ว (เลขาเริ่มงานเองได้เมื่อถึง B5)"
                if self.act == "approve" else "ไม่เอาแผนนี้")
        # the three buttons go away; ย้อนกลับ stays until the plan starts
        await interaction.response.edit_message(content=done, view=dc.buttons(UndoButton(action_id)))


class EditPlanModal(discord.ui.Modal, title="แก้แผน"):
    change = discord.ui.TextInput(label="อยากให้แก้ตรงไหน", style=discord.TextStyle.paragraph, max_length=1000,
                                  placeholder="เช่น ย้ายเวลาทำสไลด์เป็นวันพุธ")

    def __init__(self, decision_id: int) -> None:
        super().__init__()
        self.decision_id = decision_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            a = await ask.revise(self.decision_id, self.change.value, via=_via(interaction.message))
        except ask.DecisionError as exc:
            await interaction.followup.send(str(exc))
            return
        if interaction.message:  # the old plan: no more buttons on it
            await interaction.message.edit(content="✏️ แก้แล้ว · ดูแผนใหม่ด้านล่าง", view=None)
        card, view = answer_card(a)
        sent = await interaction.followup.send(content="✏️ แผนที่แก้แล้ว", embed=card, view=view, wait=True)
        dc.bot.record("dm", sent, kind="plan", ref=f"decision:{a.decision_id}", text_copy=a.text)


def _via(message: discord.Message | None) -> ask.Via:
    """"ที่มา" for the action log: a link straight back to the Discord message."""
    return ("แชทส่วนตัว", message.jump_url if message else "")


async def _plan_reopened(a: Action) -> tuple[str, discord.ui.View]:
    """After undoing a plan decision, the plan is open again: show its buttons again."""
    decision_id = (a.undo or {}).get("decision_id")
    with session() as s:
        d = s.get(Decision, decision_id)
    title = d.title if d else ""
    return (f"↩️ ย้อนกลับแล้ว · แผน “{title}” รอคุณตัดสินอีกครั้ง",
            dc.buttons(*(PlanButton(decision_id, act) for act in ("approve", "edit", "reject"))))


def setup() -> None:
    """Hook the chat into the bot. Called by main.py before the bot connects."""
    dc.bot.on_dm = on_dm
    dc.register_buttons(DeepButton, PlanButton)
    after_undo["plan.approve"] = after_undo["plan.reject"] = _plan_reopened
