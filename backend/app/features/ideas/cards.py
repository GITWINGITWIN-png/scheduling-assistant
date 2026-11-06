"""#ไอเดีย on Discord (D6): every message you write there is one idea, marked ✅ once it's kept.

The ✅ is the only answer: no message back, so the channel stays a list of your ideas (D6 ②).
If the bot may not add reactions in your server, it replies "✓ จดแล้ว" instead, so you still
know. Editing a message changes its idea; deleting the message deletes the idea.
"""

from __future__ import annotations

import logging

import discord

from app.connectors import discord_bot as dc
from app.features.ideas import store

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


def setup() -> None:
    dc.bot.on_channel_message["ideas"] = on_idea
    dc.bot.on_channel_edit["ideas"] = on_edit
    dc.bot.on_channel_delete["ideas"] = on_delete
