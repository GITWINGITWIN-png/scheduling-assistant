"""#ไอเดีย on Discord (D6): every message you write there is one idea, marked ✅ once it's kept,
and the noon and midnight rounds' cards.

- The ✅ is the only answer: no message back, so the channel stays a list of your ideas (D6 ②).
  If the bot may not add reactions in your server, it replies "✓ จดแล้ว" instead. Editing a
  message changes its idea, and deleting the message deletes the idea.
- After a round with something new: "จัดกลุ่มไอเดีย · รอบเที่ยง" lists where the new ideas
  went (D6 ③). Each group that has grown gets its own card with เปิดโปรเจค · ทำเป็นงาน ·
  ยังก่อน (D6 ④). เปิดโปรเจค first asks for the folder's name, filled in from the tag.
  The bell, the today page and the ideas page ask the same question, and an answer in one
  place settles the others.
"""

from __future__ import annotations

import logging

import discord
from sqlalchemy import select

from app.connectors import discord_bot as dc
from app.core.db import now, session
from app.core.tables import Action, Decision
from app.core.timefmt import local
from app.features.actions_discord import UndoButton, after_undo
from app.features.ideas import groups, store
from app.features.ideas.tables import Idea, IdeaGroup

log = logging.getLogger(__name__)

KEPT = "✅"


def _text(message: discord.Message) -> str:
    """The message, with the links of any pictures or files you attached."""
    files = [a.url for a in message.attachments]
    return "\n".join(x for x in (message.content.strip(), *files) if x)


async def on_idea(message: discord.Message) -> None:
    text = _text(message)
    if not text:
        return
    store.add(text, source="discord", source_ref=str(message.id))
    try:
        await message.add_reaction(KEPT)
    except discord.HTTPException as exc:  # no Add Reactions in this server: say it in words instead
        log.warning("couldn't add the ✅ to an idea (%s); replying instead", exc)
        sent = await message.reply("✓ จดแล้ว", mention_author=False)
        dc.bot.record("ideas", sent, kind="idea_kept")


async def on_edit(message_id: int, content: str) -> None:
    if (idea_id := store.by_ref(str(message_id))) is not None:
        store.change_text(idea_id, content)


async def on_delete(message_id: int) -> None:
    if (idea_id := store.by_ref(str(message_id))) is not None:
        store.remove(idea_id, via=("#ไอเดีย", ""), log_it=False)  # you deleted it yourself: nothing to tell


# ------------------------------------------------------------------ the round's cards (D6 ③ ④)
def _ready() -> bool:
    return dc.bot.ready_event.is_set() and not dc.bot.is_closed()


def _short(text: str, n: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def round_card(r: groups.Round) -> discord.Embed:
    with session() as s:
        lines = []
        for idea_id, group_id in r.placed[:12]:
            idea, g = s.get(Idea, idea_id), s.get(IdeaGroup, group_id)
            lines.append(f"• {_short(idea.text, 50)} → “{g.name}” ({groups.size(s, g.id)})")
    if len(r.placed) > 12:
        lines.append(f"และอีก {len(r.placed) - 12} ไอเดีย")
    which = "รอบเที่ยงคืน" if local(now()).hour < 6 else "รอบเที่ยง"
    footer = (f"ยังไม่มีแท็ก {r.left} ไอเดีย · ใส่ #แท็ก ในข้อความ หรือแท็กที่หน้าไอเดีย" if r.left
              else "จัดตามแท็ก #… และชื่อโปรเจคในข้อความ (ยังไม่ใช้โมเดล)")
    return dc.embed(f"เข้ากลุ่มแล้ว {len(r.placed)} ไอเดีย", "\n".join(lines), tone="ok", author=f"จัดกลุ่มไอเดีย · {which}",
                    footer=footer)


def ripe_card(group_id: int) -> tuple[discord.Embed, discord.ui.View]:
    with session() as s:
        g = s.get(IdeaGroup, group_id)
        n, about = groups.size(s, g.id), groups.about_project(s, g.id)
        ideas = s.scalars(select(Idea.text).where(Idea.group_id == g.id).order_by(Idea.created_at.desc()).limit(6)).all()
        name = g.name
    body = "เปิดเป็นโปรเจคใหม่ หรือเป็นงานในตาราง" + (f" · เกี่ยวกับ {about}" if about else "")
    body += "\n" + "\n".join(f"• {_short(t)}" for t in ideas)
    embed = dc.embed(f"{name} · {n} ไอเดีย", body, tone="warn", author="กลุ่มที่โตพอ",
                     footer="เปิดโปรเจค: โฟลเดอร์ใหม่ใน ~/Projects พร้อม README และ PROGRESS จากไอเดียในกลุ่ม")
    return embed, dc.buttons(*(IdeaButton(group_id, a) for a in ACTS))


async def post_round(r: groups.Round) -> None:
    """groups.POSTED hook: the round card, then one card per group that has grown."""
    if not _ready():
        return
    if r.placed:
        await dc.bot.send("ideas", embed=round_card(r), kind="ideas_round", text_copy=f"จัดกลุ่มไอเดีย: เข้ากลุ่ม {len(r.placed)}")
    for group_id, decision_id in r.asked:
        embed, view = ripe_card(group_id)
        row, _ = await dc.bot.send("ideas", embed=embed, view=view, kind="idea", ref=f"decision:{decision_id}",
                                   text_copy=f"กลุ่มไอเดียที่โตพอ: {embed.title}")
        with session() as s:
            s.get(Decision, decision_id).message_id = row.id


ACTS = {"project": ("เปิดโปรเจค", discord.ButtonStyle.primary), "task": ("ทำเป็นงาน", discord.ButtonStyle.secondary),
        "later": ("ยังก่อน", discord.ButtonStyle.secondary)}


def _via(message: discord.Message | None) -> tuple[str, str]:
    return ("#ไอเดีย", message.jump_url if message else "")


class IdeaButton(discord.ui.DynamicItem[discord.ui.Button], template=r"idea:(?P<id>\d+):(?P<act>project|task|later)"):
    def __init__(self, group_id: int, act: str) -> None:
        self.group_id, self.act = group_id, act
        label, style = ACTS[act]
        super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"idea:{group_id}:{act}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]), match["act"])

    async def callback(self, interaction: discord.Interaction) -> None:
        if not dc.bot.is_owner(interaction.user):
            await interaction.response.send_message("ปุ่มนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
            return
        if self.act == "project":
            await interaction.response.send_modal(ProjectModal(self.group_id))
            return
        try:
            if self.act == "task":
                _, action_id = groups.make_task(self.group_id, via=_via(interaction.message))
                done = "✅ ทำเป็นงานในตารางแล้ว · เลขาจะหาเวลาให้ (ดูที่หน้าตาราง)"
            else:
                action_id = groups.later(self.group_id, via=_via(interaction.message))
                done = f"ยังก่อน · เลขาจะถามใหม่เมื่อกลุ่มนี้มีเพิ่มอีก {groups.AGAIN_AFTER} ไอเดีย"
        except groups.AnswerError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await interaction.response.edit_message(content=done, view=dc.buttons(UndoButton(action_id)))


class ProjectModal(discord.ui.Modal, title="เปิดเป็นโปรเจคใหม่"):
    def __init__(self, group_id: int) -> None:
        super().__init__()
        self.group_id = group_id
        self.name = discord.ui.TextInput(label="ชื่อโฟลเดอร์ใน ~/Projects", default=groups.suggested_folder(group_id),
                                         max_length=80, placeholder="เช่น backtest-lab")
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            groups.open_project(self.group_id, self.name.value, via=_via(interaction.message))
        except groups.AnswerError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        folder = " ".join(self.name.value.split())
        await interaction.response.edit_message(
            content=f"✅ เปิดเป็นโปรเจคแล้ว: ~/Projects/{folder} (README.md และ PROGRESS.md จากไอเดียในกลุ่ม) · อยู่ในหน้าโปรเจคเป็น “ไอเดีย”",
            view=None)


async def _reopened(a: Action) -> tuple[str, discord.ui.View | None]:
    """After undoing ทำเป็นงาน or ยังก่อน: the question waits for you again, with its buttons."""
    group_id = (a.undo or {}).get("group_id")
    with session() as s:
        g = s.get(IdeaGroup, group_id)
        waiting = g is not None and g.status == "asked"
    if not waiting:
        return "↩️ ย้อนกลับแล้ว", None
    return "↩️ ย้อนกลับแล้ว · กลุ่มนี้รอคุณตัดสินอีกครั้ง", ripe_card(group_id)[1]


def setup() -> None:
    dc.bot.on_channel_message["ideas"] = on_idea
    dc.bot.on_channel_edit["ideas"] = on_edit
    dc.bot.on_channel_delete["ideas"] = on_delete
    dc.register_buttons(IdeaButton)
    if post_round not in groups.POSTED:
        groups.POSTED.append(post_round)
    after_undo["idea.task"] = after_undo["idea.later"] = _reopened
