"""The privacy filter between ActivityWatch and the secretary (P12): a blocklist, words that hide a
title, and a pause.

It works in two places, so a blocked window never reaches the secretary's log:
1. In awatcher itself. The secretary writes awatcher's config (`write_awatcher_config`) from the
   blocklist. A blocked app or title is then never sent to ActivityWatch, and a title with a
   blocked word is sent as HIDDEN. So ActivityWatch's own database on this computer doesn't keep
   them either.
2. When the secretary reads ActivityWatch (`verdict`), the same rules run again. This covers what
   was recorded before a rule existed, or before awatcher restarted with it.

Changing the list also cleans what the secretary already kept (`reapply`), rewrites awatcher's
config, and restarts the recorder if it's running.

Matching (the same in both places, see `pattern`): case never matters. A latin value must stand
on its own, so "scb" isn't found in "scbx". A Thai value is found anywhere in the text, because
Thai has no spaces between words.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select

from app.core import actions, settings
from app.core.db import now, session
from app.features.time.tables import HIDDEN, KINDS, Activity, PrivacyRule

PAUSES_KEY = "activity.pauses"  # [[start, end], ...] (ISO): nothing in these is kept
SEEDED_KEY = "state.privacy_seeded"

# The defaults agreed at the B6 plan ("3. ตามนั้นเลย"): password managers, banks and payments,
# LINE / Messenger / WhatsApp, private browsing windows, and four words that hide a title.
DEFAULTS: list[tuple[str, str, str]] = [
    *(("app", v, "ตัวจัดการรหัสผ่าน") for v in ("keepassxc", "keepass", "bitwarden", "1password", "enpass", "seahorse",
                                                "secrets", "passwordsafe", "proton pass")),
    *(("title", v, "ตัวจัดการรหัสผ่าน") for v in ("bitwarden", "1password", "lastpass", "proton pass")),  # on the web
    *(("title", v, "ธนาคาร") for v in ("kasikorn", "kbank", "k plus", "scb", "krungthai", "krungthai next", "bangkok bank",
                                       "bualuang", "krungsri", "ttb", "mymo", "gsb", "uob", "kkp", "cimb", "baac")),
    *(("title", v, "จ่ายเงิน") for v in ("paypal", "truemoney", "promptpay", "shopeepay", "rabbit line pay")),
    *(("app", v, "แชทส่วนตัว") for v in ("line", "whatsapp", "messenger", "caprine", "zapzap", "altus")),
    *(("title", v, "แชทส่วนตัว") for v in ("whatsapp", "messenger", "line.me")),
    *(("title", v, "หน้าต่างโหมดส่วนตัว") for v in ("private browsing", "incognito", "inprivate", "การท่องเว็บแบบส่วนตัว",
                                                    "ไม่ระบุตัวตน")),
    *(("word", v, "") for v in ("รหัสผ่าน", "otp", "ธนาคาร", "password")),
]


def seed() -> int:
    """Put the defaults in once (on the first start of B6). Deleting one later keeps it deleted."""
    if settings.get(SEEDED_KEY):
        return 0
    with session() as s:
        for kind, value, note in DEFAULTS:
            s.add(PrivacyRule(kind=kind, value=value, note=note))
    settings.put(SEEDED_KEY, now().isoformat())
    return len(DEFAULTS)


# ------------------------------------------------------------------ matching
LATIN = re.compile(r"[a-z0-9]")


def clean(value: str) -> str:
    return " ".join(value.strip().lower().split())[:120]


def pattern(value: str) -> str:
    """The regular expression for one value, in the syntax both Python and awatcher (Rust's regex)
    read the same way: (?i), plain escapes, and \\b only on a latin edge."""
    v = clean(value)
    body = re.sub(r"([\\.+*?()|\[\]{}^$])", r"\\\1", v)
    left = r"\b" if LATIN.match(v) else ""
    right = r"\b" if LATIN.match(v[-1:]) else ""
    return f"(?i).*{left}{body}{right}.*"


def found(value: str, text: str) -> bool:
    return re.fullmatch(pattern(value), text or "", flags=re.DOTALL) is not None


@dataclass(frozen=True)
class Rules:
    apps: tuple[str, ...]
    titles: tuple[str, ...]
    words: tuple[str, ...]

    def verdict(self, app: str, title: str) -> str:
        """drop (never kept) · hide (kept, title hidden) · keep."""
        if any(found(v, app) for v in self.apps) or any(found(v, title) for v in self.titles):
            return "drop"
        if any(found(v, title) for v in self.words):
            return "hide"
        return "keep"


def rules() -> Rules:
    with session() as s:
        rows = s.scalars(select(PrivacyRule)).all()
    pick = lambda kind: tuple(sorted({clean(r.value) for r in rows if r.kind == kind and clean(r.value)}))  # noqa: E731
    return Rules(pick("app"), pick("title"), pick("word"))


# ------------------------------------------------------------------ pauses (หยุดบันทึก)
def pauses() -> list[tuple[datetime, datetime]]:
    return [(datetime.fromisoformat(a), datetime.fromisoformat(b)) for a, b in settings.get(PAUSES_KEY, [])]


def add_pause(start: datetime, end: datetime) -> None:
    keep = [(a, b) for a, b in pauses() if b > now() - timedelta(days=8)]  # older ones can't matter any more
    settings.put(PAUSES_KEY, [[a.isoformat(), b.isoformat()] for a, b in [*keep, (start, end)]])


def end_pause(at: datetime) -> None:
    """Resume early: a pause that is still on ends now."""
    settings.put(PAUSES_KEY, [[a.isoformat(), min(b, at).isoformat()] for a, b in pauses()])


def paused_until(at: datetime) -> datetime | None:
    return max((b for a, b in pauses() if a <= at < b), default=None)


def cut_pauses(start: datetime, end: datetime, windows: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """[start, end) without the paused windows: what may be kept of it."""
    pieces = [(start, end)]
    for a, b in windows:
        nxt = []
        for s_, e_ in pieces:
            if b <= s_ or a >= e_:
                nxt.append((s_, e_))
                continue
            if s_ < a:
                nxt.append((s_, a))
            if b < e_:
                nxt.append((b, e_))
        pieces = nxt
    return [(s_, e_) for s_, e_ in pieces if e_ > s_]


# ------------------------------------------------------------------ awatcher's config (the first line)
def awatcher_config_path() -> Path:
    return Path.home() / ".config" / "awatcher" / "config.toml"


def awatcher_config(r: Rules) -> str:
    """awatcher's config.toml: drop filters first (awatcher stops at the first match), then the words."""
    q = lambda s: json.dumps(s, ensure_ascii=False)  # noqa: E731  (a JSON string is a valid TOML basic string)
    out = ["# เขียนโดยเลขา (my_secretary) จากรายชื่อห้ามบันทึกในหน้าการใช้เวลา: แก้ที่หน้านั้น ไฟล์นี้จะถูกเขียนทับ",
           "[server]", "port = 5600", 'host = "127.0.0.1"', "",
           "[awatcher]", "idle-timeout-seconds = 180", "poll-time-idle-seconds = 5", "poll-time-window-seconds = 1", "",
           "# ห้ามบันทึก: ไม่ส่งเข้า ActivityWatch เลย (กติกาที่ไม่มี replace)"]
    for v in r.apps:
        out += ["[[awatcher.filters]]", f"match-app-id = {q(pattern(v))}", ""]
    for v in r.titles:
        out += ["[[awatcher.filters]]", f"match-title = {q(pattern(v))}", ""]
    out.append("# คำในชื่อหน้าต่าง: เก็บเวลาไว้ แต่ซ่อนชื่อหน้าต่าง")
    for v in r.words:
        out += ["[[awatcher.filters]]", f"match-title = {q(pattern(v))}", f"replace-title = {q(HIDDEN)}", ""]
    return "\n".join(out).rstrip() + "\n"


def write_awatcher_config() -> Path:
    path = awatcher_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(awatcher_config(rules()), encoding="utf-8")
    return path


# ------------------------------------------------------------------ changing the list
def reapply(r: Rules | None = None) -> tuple[int, int]:
    """Clean what's kept already with the current rules. -> (rows deleted, titles hidden)."""
    r = r or rules()
    dropped = hidden = 0
    with session() as s:
        for row in s.scalars(select(Activity)):
            v = r.verdict(row.app, row.title)
            if v == "drop":
                s.delete(row)
                dropped += 1
            elif v == "hide" and row.title != HIDDEN:
                row.title = HIDDEN
                hidden += 1
    return dropped, hidden


async def changed() -> None:
    """After any change: clean the log, rewrite awatcher's config, restart the recorder if it runs."""
    import asyncio

    from app.features.time import recorder

    reapply()
    write_awatcher_config()
    await asyncio.to_thread(recorder.restart_if_running)


async def add(kind: str, value: str, note: str = "", *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    if kind not in KINDS:
        raise ValueError(f"ชนิดต้องเป็น {', '.join(KINDS)}")
    value = clean(value)
    if len(value) < 2:
        raise ValueError("สั้นเกินไป · อย่างน้อย 2 ตัวอักษร")
    with session() as s:
        if s.scalar(select(PrivacyRule.id).where(PrivacyRule.kind == kind, PrivacyRule.value == value)):
            raise ValueError("มีอยู่แล้ว")
        row = PrivacyRule(kind=kind, value=value, note=note.strip()[:200])
        s.add(row)
        s.flush()
        rule_id = row.id
    await changed()
    return actions.record("privacy.add", f"ห้ามบันทึก{KINDS[kind]}: {value}", note, source_label=via[0], source_url=via[1],
                          undo={"rule_id": rule_id})


async def remove(rule_id: int, *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    with session() as s:
        row = s.get(PrivacyRule, rule_id)
        if row is None:
            raise ValueError("ไม่พบกติกานี้")
        saved = {"kind": row.kind, "value": row.value, "note": row.note}
        s.delete(row)
    await changed()
    return actions.record("privacy.remove", f"เลิกห้ามบันทึก{KINDS[saved['kind']]}: {saved['value']}", "",
                          source_label=via[0], source_url=via[1], undo=saved)


async def _undo_add(undo: dict) -> None:
    with session() as s:
        s.execute(delete(PrivacyRule).where(PrivacyRule.id == undo["rule_id"]))
    await changed()


async def _undo_remove(undo: dict) -> None:
    with session() as s:
        s.add(PrivacyRule(kind=undo["kind"], value=undo["value"], note=undo["note"]))
    await changed()


actions.register_undo("privacy.add", _undo_add)
actions.register_undo("privacy.remove", _undo_remove)


def listed() -> list[dict]:
    with session() as s:
        return [{"id": r.id, "kind": r.kind, "kind_name": KINDS[r.kind], "value": r.value, "note": r.note}
                for r in s.scalars(select(PrivacyRule).order_by(PrivacyRule.kind, PrivacyRule.id))]
