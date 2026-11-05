"""The 5-minute watch (round "watch"): see every new email, act at once on the ones that matter.

Each run, per connected account:
1. ask Gmail what's new since last time (connectors/gmail.py; no model, no tokens)
2. store each message's header and file the sender in the registry. New people start as
   interested, except when their first email sits in Gmail's Promotions, Social or Forums
   tab: those start as ignored (subjects skimmed at 00:00), so newsletters don't use the
   rounds' tokens. You can raise anyone on the people page.
3. flag what can't wait: someone important · a reply on a thread where you were waiting
   for them · a watched keyword in the subject or the first lines (not from someone
   ignored: "ด่วน! ลดราคา" from a shop shouldn't reach #ด่วน)
4. read the flagged ones in full right away with the model; everything else waits for
   the 00:00 / 12:00 rounds (rounds.py), which is what keeps the token use low

The first run on an account doesn't alert about old mail. It sets the starting point, and
files the last 7 days' senders and threads (stage "old"), so the people page and
follow-ups start with something. Mail from the last 15 minutes (FRESH) is the exception:
it is handled like any new mail, because the first run happens up to 5 minutes after you
switch the watch on or connect an account, and what arrives in between is new to you.

Features hook into AFTER_READ (appointments and tasks from the email, the #ด่วน card),
so this file only decides *what* to read.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import select

from app.connectors import gmail, google
from app.core.db import now, session
from app.core.tables import Setting
from app.features.mail import people
from app.features.mail.read import Reading, read_one
from app.features.mail.tables import LEVELS, Email, Followup

log = logging.getLogger(__name__)

STATE_KEY = "state.mail"  # {account: {"history_id": "...", "me": "you@..."}}
KEYWORDS_KEY = "mail.keywords"
DEFAULT_KEYWORDS = ["ด่วน", "urgent", "deadline", "สอบ", "ยกเลิก", "เลื่อน"]
BACKFILL = "newer_than:7d"
FRESH = timedelta(minutes=15)  # on a first run, mail this recent is new, not "old"

# One mail job at a time: the 00:00/12:00 rounds and the watch both fire at minute 0.
lock = asyncio.Lock()


@dataclass
class ReadEmail:
    """What AFTER_READ hooks get: the stored email and what the model made of it."""
    email: Email
    reading: Reading


AFTER_READ: list[Callable[[ReadEmail], Awaitable[None]]] = []
# After each sync, in the sync thread: (account, new headers). Follow-ups track threads here.
SYNCED: list[Callable[[str, list], None]] = []


# ------------------------------------------------------------------ settings and state
def _get(key: str, default):
    with session() as s:
        row = s.get(Setting, key)
        return row.value if row and row.value is not None else default


def _put(key: str, value) -> None:
    with session() as s:
        s.merge(Setting(key=key, value=value))


def keywords() -> list[str]:
    return [k for k in _get(KEYWORDS_KEY, DEFAULT_KEYWORDS) if k.strip()]


def set_keywords(words: list[str]) -> None:
    _put(KEYWORDS_KEY, [w.strip() for w in words if w.strip()])


def my_addresses() -> set[str]:
    return {st["me"] for st in _get(STATE_KEY, {}).values() if st.get("me")}


def address_of(account: str) -> str:
    """Your address on one account ("" until its first watch), e.g. to open its mailbox."""
    return (_get(STATE_KEY, {}).get(account) or {}).get("me", "")


# ------------------------------------------------------------------ flagging
def first_level(h: gmail.Header) -> tuple[str, str]:
    """(level, source) for someone writing for the first time."""
    return ("ignored", "bulk_tab") if h.bulk_tab else ("interested", "first_mail")


def flag(*, level: str, subject: str, snippet: str, awaiting: bool) -> str:
    """Why this email should be read now, or "" if it can wait for the round."""
    if level == "important":
        return "important"
    if awaiting:
        return "awaiting"
    if level == "ignored":  # you (or the bulk tab) said this sender doesn't matter: no keyword alarms
        return ""
    text = f"{subject}\n{snippet}".lower()
    for word in keywords():
        if word.lower() in text:
            return f"keyword:{word}"
    return ""


def flag_label(flagged: str) -> str:
    """In your words, for cards and the log."""
    if flagged.startswith("keyword:"):
        return f"มีคำว่า “{flagged.split(':', 1)[1]}”"
    return {"important": "คนสำคัญ", "awaiting": "ตอบเรื่องที่คุณรออยู่"}.get(flagged, "")


# ------------------------------------------------------------------ syncing (runs in a thread)
def _store(account: str, h: gmail.Header, *, stage: str = "seen") -> Email | None:
    """Save one header and file its sender. Returns the row, or None if already stored."""
    with session() as s:
        if s.get(Email, h.id):
            return None
        mine = h.from_me or h.sender in my_addresses()
        row = Email(id=h.id, account=account, thread_id=h.thread_id, sender=h.sender, sender_name=h.sender_name,
                    subject=h.subject, sent_at=h.sent_at, from_me=mine, stage="sent" if mine else stage)
        if mine:  # the person is who you wrote to, so a follow-up knows whose reply you await
            to = next((a for a in h.to if a not in my_addresses()), "")
            if to:
                row.person_id = people.ensure(s, to).id
        else:
            level, source = first_level(h)
            person = people.ensure(s, h.sender, h.sender_name, level=level, source=source)
            person.last_mail_at = max(filter(None, (person.last_mail_at, h.sent_at)))
            awaiting = s.scalar(select(Followup.id).where(
                Followup.thread_id == h.thread_id, Followup.waiting_on == "them", Followup.closed_at.is_(None))) is not None
            row.person_id, row.level = person.id, person.level
            if stage == "seen":
                row.flagged = flag(level=person.level, subject=h.subject, snippet=h.snippet, awaiting=awaiting)
        s.add(row)
        return row


def _new_headers(account: str) -> tuple[list[gmail.Header], bool]:
    """Fetch what's new on one account. -> (headers, first run?). Saves the new history point."""
    state = _get(STATE_KEY, {})
    st = dict(state.get(account) or {})
    first = not st.get("history_id")
    if first:
        st["me"], st["history_id"] = gmail.profile(account)
        ids = gmail.search(account, BACKFILL)
    else:
        found = gmail.added_since(account, st["history_id"])
        if found is None:  # off for more than about a week: look back a few days instead
            _, st["history_id"] = gmail.profile(account)
            ids = gmail.search(account, "newer_than:3d")
        else:
            ids, st["history_id"] = found
    with session() as s:
        known = set(s.scalars(select(Email.id).where(Email.id.in_(ids)))) if ids else set()
    headers = [h for i in ids if i not in known and (h := gmail.header(account, i))]
    state[account] = st
    _put(STATE_KEY, state)
    return headers, first


def sync(account: str) -> tuple[int, list[str]]:
    """New mail on one account into the store. -> (how many new, ids flagged to read now)."""
    headers, first = _new_headers(account)
    fresh_from = now() - FRESH
    flagged, count = [], 0
    for h in sorted(headers, key=lambda x: x.sent_at):
        row = _store(account, h, stage="old" if first and h.sent_at < fresh_from else "seen")
        if row is not None:
            count += 1
            if row.flagged:
                flagged.append(row.id)
    after_sync(account, headers)
    return count, flagged


def after_sync(account: str, headers: list[gmail.Header]) -> None:
    for hook in SYNCED:
        try:
            hook(account, headers)
        except Exception:
            log.exception("after-sync hook %s failed", getattr(hook, "__name__", hook))


# ------------------------------------------------------------------ reading now
async def read_now(email_id: str) -> Reading | None:
    with session() as s:
        e = s.get(Email, email_id)
        if e is None or e.stage != "seen":
            return None
        account, sender, name, subject, sent_at = e.account, e.sender, e.sender_name, e.subject, e.sent_at
        level = LEVELS.get(e.level, e.level)
    text = await asyncio.to_thread(gmail.body, account, email_id)
    reading = await read_one(sender=sender, sender_name=name, level=level, subject=subject, sent_at=sent_at, body=text)
    with session() as s:
        e = s.get(Email, email_id)
        e.stage, e.summary, e.needs_reply = "read", reading.summary, reading.needs_reply
    with session() as s:
        e = s.get(Email, email_id)
    for hook in AFTER_READ:
        try:
            await hook(ReadEmail(e, reading))
        except Exception:
            log.exception("after-read hook %s failed for %s", getattr(hook, "__name__", hook), email_id)
    return reading


async def run() -> str:
    """The watch round. Returns a short line for the action log."""
    async with lock:
        new, read, skipped = 0, 0, []
        for account in google.ACCOUNTS:
            try:
                count, flagged = await asyncio.to_thread(sync, account)
            except google.NeedsConsent:
                skipped.append(google.ACCOUNTS[account].label)
                continue
            new += count
            for email_id in flagged:
                if await read_now(email_id):
                    read += 1
    parts = [f"ใหม่ {new} ฉบับ"] + ([f"อ่านทันที {read}"] if read else [])
    if skipped:
        parts.append(f"ข้ามบัญชี {', '.join(skipped)} (ยังไม่ได้เชื่อม)")
    return " · ".join(parts)


def setup() -> None:
    from app.core import clock
    clock.attach("watch", run)
