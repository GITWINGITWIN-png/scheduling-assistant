"""ปรับทะเบียนคนรายสัปดาห์ (1.4, B7): what the weekly review proposes for the people registry, by rules.

Two kinds, as agreed at the B7 plan ("1.ก ... ยกเว้นเลื่อนสนใจ -> ไม่สนใจ ให้ทำการจัดการด้วยมือเท่านั้น"):

- An important person whose end date is within SOON (or has passed): let it end, so they become
  สนใจ (the default), or renew for 1 month, 3 months or with no end. Your note on why they're
  important is shown with it. Whatever you decide, the old note goes ("ตัดสินแล้วลบ"); you can
  write a new one on the people page.
- An ignored sender whose subjects matched one of your interests ("เรื่องที่สนใจช่วงนี้" on the
  people page) at least RAISE_HITS times in WINDOW: raise them to สนใจ. With no interests set,
  there's nothing to match, so nobody is proposed.

Interested people are never proposed for ignored: you do that by hand.

Each item has its choices; "skip" leaves that person as they are this week (they come up again
next week if they still qualify). Nothing here changes anything: `apply` does, one recorded and
undoable level change per person (people.set_level).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.db import now, session
from app.core.timefmt import thai_date
from app.features.mail import people, rounds
from app.features.mail.tables import LEVELS, Email, Person

SOON = timedelta(days=7)
WINDOW = timedelta(days=28)
RAISE_HITS = 2
RENEW = {"renew30": ("ต่ออายุ 1 เดือน", 30), "renew90": ("ต่ออายุ 3 เดือน", 90), "forever": ("ต่อไม่มีกำหนด", None)}
CHOICES = {
    "important": [("expire", "ปล่อยหมดอายุ → สนใจ"), *((k, v[0]) for k, v in RENEW.items()), ("skip", "ยังไม่ตัดสิน")],
    "ignored": [("raise", "ยกเป็นสนใจ"), ("skip", "คงไม่สนใจ")],
}


def _found(word: str, text: str) -> bool:
    """Case-insensitive; a latin word stands alone, a Thai one is found inside words."""
    w, t = word.strip().lower(), text.lower()
    if not w:
        return False
    left = r"(?<![a-z0-9])" if re.match(r"[a-z0-9]", w) else ""
    right = r"(?![a-z0-9])" if re.search(r"[a-z0-9]$", w) else ""
    return re.search(left + re.escape(w) + right, t) is not None


def proposals(at: datetime | None = None) -> list[dict]:
    """This week's proposals: [{person_id, name, level, to, choice, choices, why, note, until}]."""
    at = at or now()
    out: list[dict] = []
    with session() as s:
        for p in s.scalars(select(Person).where(Person.level == "important", Person.level_until.is_not(None),
                                                Person.level_until <= at + SOON).order_by(Person.level_until)):
            ended = p.level_until <= at
            out.append({"person_id": p.id, "name": p.name or "(ไม่มีชื่อ)", "level": "important", "to": "interested",
                        "choice": "expire", "choices": CHOICES["important"], "note": p.note,
                        "until": p.level_until.isoformat(),
                        "why": f"คนสำคัญ{'หมดอายุแล้วเมื่อ' if ended else 'หมดอายุ'} {thai_date(p.level_until)}"})
        topics = rounds.interests()
        if topics:
            rows = s.execute(select(Person, Email.subject).join(Email, Email.person_id == Person.id)
                             .where(Person.level == "ignored", Email.sent_at >= at - WINDOW, Email.from_me.is_(False))).all()
            hits: dict[int, list[str]] = {}
            names: dict[int, Person] = {}
            for p, subject in rows:
                matched = [t for t in topics if _found(t, subject or "")]
                if matched:
                    hits.setdefault(p.id, []).extend(matched)
                    names[p.id] = p
            for pid, matched in hits.items():
                if len(matched) >= RAISE_HITS:
                    p = names[pid]
                    top = max(set(matched), key=matched.count)
                    out.append({"person_id": pid, "name": p.name or "(ไม่มีชื่อ)", "level": "ignored", "to": "interested",
                                "choice": "raise", "choices": CHOICES["ignored"], "note": "", "until": None,
                                "why": f"หัวข้อตรงเรื่องที่สนใจ “{top}” {len(matched)} ครั้งใน 4 สัปดาห์"})
    return out


def words(item: dict) -> str:
    """One line per person, for the review card: "อ.ธนา (สำคัญ) หมดอายุ 20 พ.ย. → ปล่อยหมดอายุ → สนใจ"."""
    label = dict(item["choices"]).get(item["choice"], item["choice"])
    return f"{item['name']} ({LEVELS[item['level']]}): {item['why']} → {label}"


def apply(items: list[dict], *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> list[int]:
    """Do what each item's choice says. -> the action ids (one per person changed)."""
    done = []
    for item in items:
        choice, pid = item["choice"], item["person_id"]
        with session() as s:
            p = s.get(Person, pid)
            if p is None or p.level != item["level"]:
                continue  # changed by hand meanwhile: leave it
        if choice == "expire":
            done.append(people.set_level(pid, "interested", reason=f"หมดอายุ (ทบทวนรายสัปดาห์): {item['note']}".strip(": "),
                                         source="secretary", via=via))
        elif choice in RENEW:
            done.append(people.set_level(pid, "important", days=RENEW[choice][1], source="you", via=via))
        elif choice == "raise":
            done.append(people.set_level(pid, "interested", source="secretary", via=via))
    return done


# ------------------------------------------------------------------ the people page's card and the weekly review
def pending() -> tuple[int, list[dict]] | None:
    """The weekly review's people topic, while it waits for you: (decision id, items)."""
    from app.core.tables import Decision

    with session() as s:
        for d in s.scalars(select(Decision).where(Decision.kind == "weekly", Decision.status == "pending")
                           .order_by(Decision.created_at.desc())):
            if (d.detail or {}).get("topic") == "people":
                return d.id, list(d.detail["proposal"]["items"])
    return None


def current() -> dict:
    """What the people page shows: the review's proposals while they wait, or else as things stand now."""
    waiting = pending()
    if waiting:
        return {"decision_id": waiting[0], "items": waiting[1]}
    return {"decision_id": None, "items": proposals()}


async def answer(choices: list[dict], decision_id: int | None, *, via: tuple[str, str]) -> list[int]:
    """You chose, person by person (from the page or Discord). -> the action ids of what changed."""
    from app.core.tables import Decision
    from app.features import decisions

    picked = {int(c["person_id"]): c["choice"] for c in choices}
    if decision_id is not None:
        with session() as s:
            d = s.get(Decision, decision_id)
            if d is None or d.kind != "weekly" or d.status != "pending":
                raise ValueError("เรื่องนี้ตัดสินไปแล้ว")
            items = list(d.detail["proposal"]["items"])
    else:
        items = proposals()
    for item in items:
        if item["person_id"] in picked:
            if picked[item["person_id"]] not in dict(item["choices"]):
                raise ValueError(f"ไม่มีตัวเลือก {picked[item['person_id']]} สำหรับ {item['name']}")
            item["choice"] = picked[item["person_id"]]
    done = apply(items, via=via)
    if decision_id is not None:
        with session() as s:
            d = s.get(Decision, decision_id)
            d.detail = {**d.detail, "proposal": {**d.detail["proposal"], "items": items}}
            d.status, d.answer, d.answered_at = "approved", "people", now()
        await decisions.settle_card(decision_id, where=via[0])
    return done
