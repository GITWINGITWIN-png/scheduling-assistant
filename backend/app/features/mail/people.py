"""The people registry (feature 1.2): who someone is and which of the 3 levels they're at.

Rules agreed in stage 1:
- someone writing for the first time starts as interested (interested)
- you make someone important (important), usually for a while ("3 months for project A"),
  even before they ever write; when the time is up you decide again (W2 now, the
  weekly review from B7)
- a level change is always recorded in the action log with undo
"""

from datetime import datetime, timedelta
from email.utils import parseaddr

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import actions
from app.core.db import now, session
from app.features.mail.tables import LEVELS, Person, PersonAddress


def normalize(address: str) -> str:
    """'Somchai <Somchai@Example.com>' -> 'somchai@example.com'."""
    return parseaddr(address)[1].strip().lower()


def find(s: Session, address: str) -> Person | None:
    row = s.get(PersonAddress, normalize(address))
    return s.get(Person, row.person_id) if row else None


def ensure(s: Session, address: str, name: str = "", *, level: str = "interested", source: str = "first_mail") -> Person:
    """The person behind an address (inside your session). Someone new starts at `level`;
    someone already known keeps theirs, so a person you set in advance stays as you set them."""
    address = normalize(address)
    person = find(s, address)
    if person is None:
        person = Person(name=name or address.split("@")[0], level=level, level_source=source)
        s.add(person)
        s.flush()  # get the id
        s.add(PersonAddress(address=address, person_id=person.id))
    elif name and (not person.name or person.name == address.split("@")[0]):
        person.name = name  # a real display name beats the address prefix
    return person


def expired(p: Person, at: datetime | None = None) -> bool:
    return p.level == "important" and p.level_until is not None and p.level_until <= (at or now())


def _snapshot(p: Person) -> dict:
    return {"level": p.level, "level_source": p.level_source, "note": p.note, "demote_reason": p.demote_reason,
            "level_until": p.level_until.isoformat() if p.level_until else None}


def set_level(person_id: int, level: str, *, days: int | None = None, note: str | None = None,
              reason: str = "", source: str = "you", via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    """Move someone to a level and record it (undoable). Returns the action id.

    days: how long an important level lasts (None = no end date). note: your reason for
    making them important. reason: why they were demoted (kept for the weekly review).
    Deciding again clears the old note, as agreed ("decided, so delete").
    """
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}")
    with session() as s:
        p = s.get(Person, person_id)
        if p is None:
            raise ValueError(f"no person {person_id}")
        before = _snapshot(p)
        renewing = level == p.level == "important"
        p.level, p.level_source = level, source
        p.level_until = now() + timedelta(days=days) if level == "important" and days else None
        p.note = (note or "") if level == "important" else ""
        p.demote_reason = reason if level != "important" and before["level"] == "important" else ""
        name = p.name
    what = (f"ต่ออายุคนสำคัญ {days} วัน" if renewing and days else
            f"{LEVELS[before['level']]} → {LEVELS[level]}" + (f" · {days} วัน" if level == "important" and days else ""))
    return actions.record("person.level", what, name, source_label=via[0], source_url=via[1],
                          undo={"person_id": person_id, "old": before})


def add(address: str, name: str = "", *, level: str = "important", days: int | None = 90, note: str = "",
        via: tuple[str, str] = ("หน้าเว็บ", "")) -> tuple[int, int]:
    """Put someone in the registry before they write (e.g. "important for 3 months"). -> (person id, action id)."""
    with session() as s:
        person_id = ensure(s, address, name).id
    return person_id, set_level(person_id, level, days=days, note=note, via=via)


def add_address(person_id: int, address: str) -> None:
    """Another address for the same person (their work and personal mail, say)."""
    with session() as s:
        if s.get(PersonAddress, normalize(address)) is None:
            s.add(PersonAddress(address=normalize(address), person_id=person_id))


def addresses(s: Session, person_id: int) -> list[str]:
    return list(s.scalars(select(PersonAddress.address).where(PersonAddress.person_id == person_id)))


async def _undo_level(undo: dict) -> None:
    old = undo["old"]
    with session() as s:
        p = s.get(Person, undo["person_id"])
        if p is None:
            raise actions.UndoError("คนนี้ถูกลบไปแล้ว")
        p.level, p.level_source, p.note, p.demote_reason = old["level"], old["level_source"], old["note"], old["demote_reason"]
        p.level_until = datetime.fromisoformat(old["level_until"]) if old["level_until"] else None


actions.register_undo("person.level", _undo_level)
