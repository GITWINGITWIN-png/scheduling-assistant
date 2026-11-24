"""The Discord bot: the secretary's main channel to you (feature P1).

How it reaches Discord: the bot opens an *outgoing* connection to Discord's
gateway and keeps it open. Nothing on this machine is exposed to the internet:
no public URL, no open port.

What it sets up: in your private server it makes sure a category "เลขา" (secretary) with
five channels exists, and creates whatever is missing:

    #คุยกับเลขา (chat), #ด่วน (urgent), #สรุป (summary), #อนุมัติ (approve), #ไอเดีย (ideas)

Everything happens in the server, so one place holds the whole history (your
choice, 2026-11-05). A DM to the bot, or a message in a channel nothing reads
(like #general), gets a pointer to #คุยกับเลขา (chat) instead of silence.

Who it listens to: only you (SECRETARY_DISCORD_OWNER_ID). Messages from anyone
else are ignored, so nobody else can ask your secretary anything.

What features use (this module is only the connector; *what* to say is the
features' job):
- `bot.send(channel, ...)` posts and records the message in the `messages` table
- `embed(...)` builds a message card in the theme's colour
- `bot.on_channel_message["chat"]` and `["ideas"]` receive your messages; `on_channel_edit` and
  `on_channel_delete` hear when you edit or delete one (raw events, so also after a restart)
- `register_buttons(...)` registers button classes that keep working after a
  restart. They are DynamicItems: a button's custom_id carries what it acts on
  (for example "ask:deep:42"), so it needs no memory from before the restart.

Setup steps for you: docs/setup/discord.md.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable

import discord

from app.core.config import get_config
from app.core.db import session
from app.core.tables import Message
from app.core.themes import accent

log = logging.getLogger(__name__)

CATEGORY = "เลขา"
CHANNELS = {"chat": "คุยกับเลขา", "urgent": "ด่วน", "summary": "สรุป", "approve": "อนุมัติ", "ideas": "ไอเดีย"}
# What the bot needs in your server: see and post in channels, post cards, read history,
# create (and order) its channels the first time, and mark an idea in #ideas as kept (✅, B6).
PERMISSIONS = discord.Permissions(view_channel=True, send_messages=True, embed_links=True,
                                  read_message_history=True, manage_channels=True, add_reactions=True)

TONES = {"ok": 0x16A34A, "warn": 0xD97706, "bad": 0xDC2626, "muted": 0x6B7280}  # "info" = theme accent

MessageHandler = Callable[[discord.Message], Awaitable[None]]
EditHandler = Callable[[int, str], Awaitable[None]]  # (message id, the new text)
DeleteHandler = Callable[[int], Awaitable[None]]  # (message id)


def _cut(text: str, limit: int) -> str:
    """Discord rejects over-long fields, so cut with an ellipsis instead of failing."""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def embed(title: str = "", description: str = "", *, tone: str = "info",
          fields: Iterable[tuple[str, str, bool]] = (), footer: str = "", author: str = "") -> discord.Embed:
    """A message card. tone: info (theme colour) · ok · warn · bad · muted. fields: (name, value, inline)."""
    card = discord.Embed(title=_cut(title, 256) or None, description=_cut(description, 4000) or None,
                         colour=TONES.get(tone) or accent())
    for name, value, inline in fields:
        card.add_field(name=_cut(name, 256), value=_cut(value, 1024), inline=inline)
    if footer:
        card.set_footer(text=_cut(footer, 2048))
    if author:
        card.set_author(name=_cut(author, 256))
    return card


def buttons(*items: discord.ui.Item) -> discord.ui.View:
    """A row of buttons/menus that never times out (the clicks are handled by DynamicItems)."""
    view = discord.ui.View(timeout=None)
    for item in items:
        view.add_item(item)
    return view


class SecretaryBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # to read #ideas (B6); DMs to the bot are readable anyway
        super().__init__(intents=intents)
        self.channels: dict[str, discord.TextChannel] = {}
        self.on_channel_message: dict[str, MessageHandler] = {}
        self.on_channel_edit: dict[str, EditHandler] = {}
        self.on_channel_delete: dict[str, DeleteHandler] = {}
        self.dynamic_items: list[type[discord.ui.DynamicItem]] = []
        self.ready_event = asyncio.Event()
        self.problem = ""  # why it isn't working, in your words (shown on the settings page)
        self._pointed: set[int] = set()  # channels/DMs where we already said "talk to me in #talk-to-secretary"

    async def setup_hook(self) -> None:
        self.add_dynamic_items(*self.dynamic_items)

    async def on_ready(self) -> None:
        cfg = get_config()
        guild = self.get_guild(cfg.discord_guild_id)
        if guild is None:
            invite = discord.utils.oauth_url(self.application_id, permissions=PERMISSIONS)
            self.problem = f"บอทยังไม่อยู่ในเซิร์ฟเวอร์ {cfg.discord_guild_id} · เชิญด้วยลิงก์นี้: {invite}"
            log.warning(self.problem)
            return
        try:
            await self._ensure_channels(guild)
        except discord.Forbidden:
            self.problem = "บอทไม่มีสิทธิ์สร้างห้อง (Manage Channels) · เชิญใหม่ด้วยลิงก์ในคู่มือ"
            log.warning(self.problem)
            return
        self.problem = ""
        self.ready_event.set()
        log.info("discord ready as %s in %s: %s", self.user, guild.name, ", ".join(f"#{c.name}" for c in self.channels.values()))

    async def _ensure_channels(self, guild: discord.Guild) -> None:
        category = discord.utils.get(guild.categories, name=CATEGORY) or await guild.create_category(CATEGORY)
        for key, name in CHANNELS.items():
            channel = discord.utils.get(guild.text_channels, name=name)
            if channel is None:
                channel = await guild.create_text_channel(name, category=category)
                if key == "chat":  # the one you use most goes first (it's new on servers set up before it existed)
                    await channel.move(beginning=True)
                log.info("created #%s", name)
            self.channels[key] = channel

    def _key(self, channel_id: int) -> str | None:
        return next((k for k, c in self.channels.items() if c.id == channel_id), None)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.author.id != get_config().discord_owner_id:
            return  # only you
        key = self._key(message.channel.id)
        handler = self.on_channel_message.get(key) if key else None  # a DM matches no channel
        if handler is None:
            await self._point_to_chat(message)
            return
        try:
            await handler(message)
        except Exception:
            log.exception("handling a Discord message failed")
            await message.channel.send("ขอโทษครับ เลขาเจอปัญหาตอนทำเรื่องนี้ · ดูรายละเอียดใน log ของเซิร์ฟเวอร์")

    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        """You edited a message (raw: it works for messages from before a restart too)."""
        handler = self.on_channel_edit.get(self._key(payload.channel_id) or "")
        author = (payload.data.get("author") or {}).get("id")
        if handler is None or author is None or int(author) != get_config().discord_owner_id or "content" not in payload.data:
            return
        try:
            await handler(payload.message_id, payload.data["content"])
        except Exception:
            log.exception("handling an edited Discord message failed")

    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        handler = self.on_channel_delete.get(self._key(payload.channel_id) or "")
        if handler is None:
            return
        try:
            await handler(payload.message_id)
        except Exception:
            log.exception("handling a deleted Discord message failed")

    async def _point_to_chat(self, message: discord.Message) -> None:
        """You wrote somewhere nothing listens (a DM, #general, #ด่วน (urgent)...). Say where the chat is
        instead of staying silent, which looks like the bot is broken. Once per channel per
        run, so a channel you also use for other things doesn't fill up with the same hint."""
        if message.channel.id in self._pointed:
            return
        self._pointed.add(message.channel.id)
        where = "dm" if isinstance(message.channel, discord.DMChannel) else f"#{message.channel.name}"
        log.info("owner wrote in %s, which the secretary doesn't read; pointed them to the chat channel", where)
        chat = self.channels.get("chat")
        sent = await message.reply(f"เลขาคุยในห้อง {chat.mention if chat else '#' + CHANNELS['chat']} ครับ · พิมพ์ถามที่นั่นได้เลย",
                                   mention_author=False)
        self.record(where, sent, kind="hint")

    async def _target(self, channel: str) -> discord.abc.Messageable:
        return self.channels[channel]

    async def send(self, channel: str, *, content: str | None = None, embed: discord.Embed | None = None,
                   view: discord.ui.View | None = None, kind: str = "note", ref: str = "",
                   text_copy: str = "", reply_to: discord.Message | None = None) -> tuple[Message, discord.Message]:
        """Post to a channel ("chat", "urgent", "summary", "approve" or "ideas") and record it.

        reply_to: answer as a reply to that message, so a button pressed later can find what it
        was about (message.reference) without the secretary storing anything extra.
        """
        target = await self._target(channel)
        sent = await target.send(content=content, embed=embed, view=view,
                                 reference=reply_to, mention_author=False)
        return self.record(channel, sent, kind=kind, ref=ref, text_copy=text_copy), sent

    def record(self, channel: str, sent: discord.Message, *, kind: str, ref: str = "", text_copy: str = "") -> Message:
        """Write a message the bot posted to the `messages` table (send() does this for you)."""
        first = sent.embeds[0] if sent.embeds else None
        copy = text_copy or sent.content or (first.description if first and first.description else "")
        with session() as s:
            row = Message(channel=channel, discord_id=sent.id, kind=kind, ref=ref, content=copy)
            s.add(row)
        return row

    @staticmethod
    def is_owner(user: discord.abc.User) -> bool:
        return user.id == get_config().discord_owner_id


bot = SecretaryBot()
_task: asyncio.Task | None = None


def register_buttons(*items: type[discord.ui.DynamicItem]) -> None:
    """Call before start(): these button classes then handle clicks, even after a restart."""
    bot.dynamic_items.extend(items)


def configured() -> bool:
    cfg = get_config()
    return bool(cfg.discord_token and cfg.discord_guild_id and cfg.discord_owner_id)


async def start() -> None:
    """Connect in the background, so the web page works even when Discord is down or not set up."""
    global _task
    if not configured():
        bot.problem = "ยังไม่ได้ตั้งค่า Discord · ทำตาม docs/setup/discord.md แล้วรีสตาร์ท"
        log.info("discord off: %s", bot.problem)
        return
    _task = asyncio.create_task(_run(), name="discord")


async def _run() -> None:
    try:
        await bot.start(get_config().discord_token)  # reconnects by itself after network drops
    except discord.LoginFailure:
        bot.problem = "token ของบอทไม่ถูกต้อง · คัดลอกใหม่จาก Developer Portal"
    except discord.PrivilegedIntentsRequired:
        bot.problem = "ยังไม่ได้เปิด Message Content Intent ใน Developer Portal (หน้า Bot)"
    except Exception as exc:  # keep the rest of the secretary running
        bot.problem = f"เชื่อม Discord ไม่ได้: {exc}"
    log.warning("discord stopped: %s", bot.problem)


async def stop() -> None:
    if not bot.is_closed():
        await bot.close()
    if _task:
        _task.cancel()


def status() -> dict:
    """For the settings page: is it connected, where, and if not, why not."""
    return {
        "configured": configured(),
        "connected": bot.ready_event.is_set() and not bot.is_closed(),
        "user": str(bot.user) if bot.user else "",
        "channels": [f"#{c.name}" for c in bot.channels.values()],
        "problem": bot.problem,
    }
