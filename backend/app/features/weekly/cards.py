"""The weekly review in #สรุป (D4): the overview with "รับทุกเรื่องตามที่เสนอ", then one message per
topic with its own buttons, and the idea groups waiting for you with theirs (B6's).

A topic's message says why, จะทำอะไร, ทำยังไง and แค่ไหน (D4 ④). The people topic has a menu to change
one person's choice before รับ (D4 ③). Answering a topic edits its message to say what was done; the
same topics wait in the bell and on the today page, and an answer in either place settles the card.
"""

from __future__ import annotations

import asyncio
import logging

import discord

from app.connectors import discord_bot as dc
from app.core.db import session
from app.core.tables import Decision
from app.core.timefmt import local
from app.features.briefs.tables import Brief
from app.features.weekly import review
from app.features.weekly import topics as T

log = logging.getLogger(__name__)

WAIT_FOR_BOT = 300
_posting: set[asyncio.Task] = set()


def overview_card(b: Brief, can_accept: bool) -> tuple[discord.Embed, discord.ui.View | None]:
    embed = dc.embed(b.title, "\n".join(text for _, text in b.fields), author=f"ทบทวนรายสัปดาห์ · {local(b.made_at):%a %H:%M}",
                     footer=b.footer)
    return embed, (dc.buttons(AllButton(b.id)) if can_accept else None)


def topic_card(d: Decision) -> tuple[discord.Embed, discord.ui.View]:
    x = d.detail
    embed = dc.embed(x["title"], x["why"], tone=x.get("tone", "info"), author=f"{x['n']}/{x['of']} · {x['label']}",
                     fields=[("จะทำอะไร", x["what"], True), ("ทำยังไง", x["how"], True), ("แค่ไหน", x["extent"], True)])
    items: list[discord.ui.Item] = [WeeklyButton(d.id, act, label) for act, label in x["acts"]]
    if x["topic"] == "people":
        items.insert(0, PeopleMenu(d.id, x["proposal"]["items"]))
    return embed, dc.buttons(*items)


def _via(message: discord.Message | None) -> tuple[str, str]:
    return ("#สรุป", message.jump_url if message else "")


async def post(brief_id: int) -> None:
    """review.MADE hook: post once Discord is up (the clock may catch up before it connects)."""
    if not dc.configured():
        return
    task = asyncio.create_task(_post(brief_id), name=f"weekly-{brief_id}")
    _posting.add(task)
    task.add_done_callback(_posting.discard)


async def _post(brief_id: int) -> None:
    from app.features.ideas.cards import ripe_card

    try:
        await asyncio.wait_for(dc.bot.ready_event.wait(), WAIT_FOR_BOT)
    except TimeoutError:
        log.warning("weekly review %s not posted: Discord didn't connect (it waits in the bell)", brief_id)
        return
    with session() as s:
        b = s.get(Brief, brief_id)
        s.expunge(b)
    waiting = review.of_brief(brief_id)
    embed, view = overview_card(b, any(d.detail.get("default") for d in waiting))
    row, _ = await dc.bot.send("summary", embed=embed, view=view, kind="brief_weekly", ref=f"brief:{brief_id}",
                               text_copy=f"{b.title}\n{b.headline}")
    with session() as s:
        s.get(Brief, brief_id).message_id = row.id
    for d in waiting:
        embed, view = topic_card(d)
        row, _ = await dc.bot.send("summary", embed=embed, view=view, kind="weekly", ref=f"decision:{d.id}",
                                   text_copy=f"{d.detail['label']}: {d.title}")
        with session() as s:
            s.get(Decision, d.id).message_id = row.id
    ideas = T.ideas()
    total = len(waiting) + len(ideas)
    for i, group_id in enumerate(ideas, len(waiting) + 1):
        embed, view = ripe_card(group_id)
        embed.set_author(name=f"{i}/{total} · ไอเดีย · กลุ่มที่โตพอ")
        await dc.bot.send("summary", embed=embed, view=view, kind="idea", text_copy=f"ไอเดีย: {embed.title}")


def _owner(interaction: discord.Interaction) -> bool:
    return dc.bot.is_owner(interaction.user)


class AllButton(discord.ui.DynamicItem[discord.ui.Button], template=r"weekly:all:(?P<id>\d+)"):
    """รับทุกเรื่องตามที่เสนอ (D4 ②)."""

    def __init__(self, brief_id: int) -> None:
        self.brief_id = brief_id
        super().__init__(discord.ui.Button(label="รับทุกเรื่องตามที่เสนอ", style=discord.ButtonStyle.success,
                                           custom_id=f"weekly:all:{brief_id}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if not _owner(interaction):
            await interaction.response.send_message("ปุ่มนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
            return
        await interaction.response.defer()
        done = await review.accept_all(self.brief_id, via=_via(interaction.message))
        if interaction.message:
            await interaction.message.edit(view=None)
        await interaction.followup.send("รับทุกเรื่องแล้ว\n" + "\n".join(f"• {x}" for x in done) if done else
                                        "ไม่มีเรื่องที่รอแล้ว (ตัดสินไปแล้ว หรือเป็นเรื่องที่ต้องเลือกเอง)")


class WeeklyButton(discord.ui.DynamicItem[discord.ui.Button], template=r"weekly:(?P<id>\d+):(?P<act>[a-z]+)"):
    STYLES = {"approve": discord.ButtonStyle.success, "both": discord.ButtonStyle.success, "book": discord.ButtonStyle.secondary,
              "reject": discord.ButtonStyle.secondary}

    def __init__(self, decision_id: int, act: str, label: str = "") -> None:
        self.decision_id, self.act = decision_id, act
        super().__init__(discord.ui.Button(label=label or act, style=self.STYLES.get(act, discord.ButtonStyle.secondary),
                                           custom_id=f"weekly:{decision_id}:{act}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]), match["act"], item.label or "")

    async def callback(self, interaction: discord.Interaction) -> None:
        if not _owner(interaction):
            await interaction.response.send_message("ปุ่มนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
            return
        await interaction.response.defer()  # re-planning talks to Google: more than Discord's 3 seconds
        try:
            said = await review.answer(self.decision_id, self.act, via=_via(interaction.message))
        except review.AnswerError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        if interaction.message:
            await interaction.message.edit(content=said, view=None)


class PeopleMenu(discord.ui.DynamicItem[discord.ui.Select], template=r"weeklyppl:(?P<id>\d+)"):
    """D4 ③: change one person's choice ("ต่ออายุ อ.ธนา 1 เดือน") before รับ."""

    def __init__(self, decision_id: int, items: list[dict] | None = None) -> None:
        self.decision_id = decision_id
        options = [discord.SelectOption(label=f"{i['name']}: {label}"[:100], value=f"{i['person_id']}:{key}",
                                        default=False)
                   for i in (items or []) for key, label in i["choices"] if key != i["choice"]][:25]
        super().__init__(discord.ui.Select(placeholder="เลือกรายคน เช่น “ต่ออายุ 1 เดือน”",
                                           options=options or [discord.SelectOption(label="-", value="0:-")],
                                           custom_id=f"weeklyppl:{decision_id}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if not _owner(interaction):
            await interaction.response.send_message("เมนูนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
            return
        person_id, choice = self.item.values[0].split(":", 1)
        try:
            review.choose_person(self.decision_id, int(person_id), choice)
        except review.AnswerError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        with session() as s:
            d = s.get(Decision, self.decision_id)
            s.expunge(d)
        embed, view = topic_card(d)
        await interaction.response.edit_message(embed=embed, view=view)


def setup() -> None:
    dc.register_buttons(AllButton, WeeklyButton, PeopleMenu)
    if post not in review.MADE:
        review.MADE.append(post)
