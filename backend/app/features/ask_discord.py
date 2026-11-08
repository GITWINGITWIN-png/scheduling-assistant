"""Ask the secretary in #คุยกับเลขา on your Discord server (D7).

(Planned as a DM; moved into the server on 2026-11-05 so everything is in one place.)

- You write in #คุยกับเลขา, and the answer comes back as a *reply* to your message,
  with the model, effort, time and sources underneath.
- "ให้ Opus คิดต่อ" under a quick answer: Opus answers the same question.
  The button finds the question through the reply link, so it still works
  days later or after a restart.
- A plan from Opus comes with ใช้แผนนี้ · แก้ · ไม่เอา. "แก้" opens a box
  where you type the change, and Opus rewrites the plan.
- B9: an order Opus carried out lists what it did, with "ย้อนกลับ N" for each thing
  (pressing one keeps the others), and "ทำเลย · ไม่เอา" for what can't be undone.
  A plan you approve is carried out, and its result is posted as a reply under the plan.

The logic is in features/ask.py; this file only turns it into Discord messages.
"""

import logging
import re

import discord
from sqlalchemy import select

from app.connectors import discord_bot as dc
from app.core import actions
from app.core.tables import Action, Decision, Message
from app.core.db import session
from app.features import ask, ask_orders
from app.features.actions_discord import UndoButton, after_undo

log = logging.getLogger(__name__)
MAX_BUTTONS = 25  # Discord's limit for one message


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
        items: list[discord.ui.Item] = [PlanButton(a.decision_id, act) for act in ("approve", "edit", "reject")]
        _order_parts(card, items, a)  # in case Opus also did something before planning
        return card, dc.buttons(*items)
    if a.kind == "done":
        card = dc.embed(a.title and f"ผลของแผน: {a.title}", a.text, footer=a.footer)
        items = []
        _order_parts(card, items, a)
        return card, (dc.buttons(*items) if items else None)
    card = dc.embed(description=a.text, footer=a.footer)
    return card, (dc.buttons(DeepButton()) if deep_button and a.model != "Opus" else None)


def _order_parts(card: discord.Embed, items: list[discord.ui.Item], a: ask.Answer) -> None:
    """B9: what an order did (numbered, with ย้อนกลับ N) and what waits for ยืนยัน (A, B, ...)."""
    if a.confirms:
        card.add_field(name="รอคุณกดยืนยัน (ย้อนกลับไม่ได้)", inline=False,
                       value="\n".join(f"{_letter(i)}. {c['title']}" for i, c in enumerate(a.confirms))[:1024])
        for i, c in enumerate(a.confirms):
            items += [ConfirmButton(c["id"], "yes", f"ทำเลย {_letter(i)}"), ConfirmButton(c["id"], "no", f"ไม่เอา {_letter(i)}")]
    if a.done:
        card.add_field(name="เลขาทำแล้ว", inline=False, value="\n".join(
            f"{n}. {d['summary']}" + (f" · {d['target']}" if d["target"] else "") for n, d in enumerate(a.done, 1))[:1024])
        room = MAX_BUTTONS - len(items)
        undoable = [(n, d) for n, d in enumerate(a.done, 1) if d["can_undo"]]
        items += [OrderUndoButton(d["id"], f"ย้อนกลับ {n}") for n, d in undoable[:room]]
        if len(undoable) > room:
            card.add_field(name="ย้อนรายการที่เหลือ", value="ที่หน้าสิ่งที่เลขาทำ", inline=False)


def _letter(i: int) -> str:
    return chr(ord("A") + i % 26)


def _rebuilt(message: discord.Message, pressed: dict[str, str]) -> discord.ui.View:
    """The message's B9 buttons again, the pressed ones greyed out with a new label (the others
    keep working). Built from the message itself, so it works after a restart too."""
    view = discord.ui.View(timeout=None)
    for row in message.components:
        for c in getattr(row, "children", []):
            cid = getattr(c, "custom_id", None) or ""
            if m := re.fullmatch(r"oundo:(\d+)", cid):
                item = OrderUndoButton(int(m[1]), c.label or "ย้อนกลับ")
            elif m := re.fullmatch(r"order:(\d+):(yes|no)", cid):
                item = ConfirmButton(int(m[1]), m[2], c.label or "")
            else:
                continue
            if cid in pressed:
                item.item.label, item.item.disabled = pressed[cid], True
            elif c.disabled:
                item.item.disabled = True
            view.add_item(item)
    return view


async def on_chat(message: discord.Message) -> None:
    if not message.content.strip():
        return
    async with message.channel.typing():  # "เลขากำลังพิมพ์…" while Sonnet/Opus works
        a = await ask.ask(message.content, await _history(message), via=_via(message))
    card, view = answer_card(a)
    handed = a.kind in ("plan", "done") or a.model == "Opus"
    await dc.bot.send("chat", content=f"✨ {ask.HANDOFF_NOTE}" if handed else None, embed=card, view=view,
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
        dc.bot.record("chat", sent, kind=a.kind, ref=f"decision:{a.decision_id}" if a.decision_id else "ask_deep", text_copy=a.text)


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
        if self.act == "approve":  # B9: it is being carried out; each thing it does comes with its own ย้อนกลับ
            await interaction.response.edit_message(content="✅ ใช้แผนนี้แล้ว · เลขากำลังลงมือทำตามแผน ผลจะตอบใต้แผนนี้",
                                                    view=None)
            return
        await interaction.response.edit_message(content="ไม่เอาแผนนี้", view=dc.buttons(UndoButton(action_id)))


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
        dc.bot.record("chat", sent, kind="plan", ref=f"decision:{a.decision_id}", text_copy=a.text)


class OrderUndoButton(discord.ui.DynamicItem[discord.ui.Button], template=r"oundo:(?P<id>\d+)"):
    """ย้อนกลับ N under what an order did: undoes that one thing, and the other buttons stay."""

    def __init__(self, action_id: int, label: str = "ย้อนกลับ") -> None:
        self.action_id = action_id
        super().__init__(discord.ui.Button(label=label[:80], style=discord.ButtonStyle.secondary, custom_id=f"oundo:{action_id}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]), item.label or "ย้อนกลับ")

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _owner_only(interaction):
            return
        try:
            await actions.undo(self.action_id)
        except actions.UndoError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        label = self.item.label.replace("ย้อนกลับ", "ย้อนแล้ว") if self.item.label else "ย้อนแล้ว"
        view = _rebuilt(interaction.message, {f"oundo:{self.action_id}": f"↩️ {label}"}) if interaction.message else None
        await interaction.response.edit_message(view=view)


class ConfirmButton(discord.ui.DynamicItem[discord.ui.Button], template=r"order:(?P<id>\d+):(?P<yes>yes|no)"):
    """ทำเลย · ไม่เอา for an order that can't be undone (B9): only this press carries it out."""

    def __init__(self, decision_id: int, yes: str, label: str = "") -> None:
        self.decision_id, self.yes = decision_id, yes
        style = discord.ButtonStyle.success if yes == "yes" else discord.ButtonStyle.secondary
        super().__init__(discord.ui.Button(label=(label or ("ทำเลย" if yes == "yes" else "ไม่เอา"))[:80], style=style,
                                           custom_id=f"order:{decision_id}:{yes}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]), match["yes"], item.label or "")

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _owner_only(interaction):
            return
        await interaction.response.defer()  # replanning or a weekly topic can take longer than Discord's 3 seconds
        try:
            said = await ask_orders.confirm(self.decision_id, self.yes == "yes", via=_via(interaction.message))
        except ask_orders.ConfirmError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        yes, no = f"order:{self.decision_id}:yes", f"order:{self.decision_id}:no"
        pressed = {yes: "✅ ทำแล้ว", no: "ไม่เอา"} if self.yes == "yes" else {yes: "ทำเลย", no: "❌ ไม่ทำ"}
        if interaction.message:
            await interaction.message.edit(view=_rebuilt(interaction.message, pressed))
        await interaction.followup.send(said)


async def post_plan_result(decision_id: int, a: ask.Answer) -> None:
    """ask.CARRIED_OUT hook: the result of a plan you approved, as a reply under the plan (or in
    #คุยกับเลขา when the plan was made on the web), with ย้อนกลับ for each thing it did."""
    if not dc.configured() or not dc.bot.ready_event.is_set() or dc.bot.is_closed():
        return
    with session() as s:
        m = s.scalar(select(Message).where(Message.kind == "plan", Message.ref == f"decision:{decision_id}")
                     .order_by(Message.id.desc()).limit(1))
        target = (m.channel, m.discord_id) if m is not None else None
    reply_to = None
    if target and (channel := dc.bot.channels.get(target[0])) is not None:
        try:
            reply_to = await channel.fetch_message(target[1])
        except discord.HTTPException:
            log.info("plan %s's message is gone: its result goes to #คุยกับเลขา", decision_id)
    card, view = answer_card(a)
    await dc.bot.send("chat", embed=card, view=view, kind="plan_run", ref=f"decision:{decision_id}", reply_to=reply_to,
                      text_copy=a.text)


def _via(message: discord.Message | None) -> ask.Via:
    """"ที่มา" for the action log: a link straight back to the Discord message."""
    return ("#คุยกับเลขา", message.jump_url if message else "")


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
    dc.bot.on_channel_message["chat"] = on_chat
    dc.register_buttons(DeepButton, PlanButton, OrderUndoButton, ConfirmButton)
    after_undo["plan.approve"] = after_undo["plan.reject"] = _plan_reopened
    if post_plan_result not in ask.CARRIED_OUT:
        ask.CARRIED_OUT.append(post_plan_result)
