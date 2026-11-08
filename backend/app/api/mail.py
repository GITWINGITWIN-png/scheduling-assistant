"""B2's web API: the people and email page (W2), appointment requests, mail settings."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from app.connectors import google
from app.core.db import now, session
from app.core.tables import Action
from app.features import decisions
from app.features.mail import extract, followups, people, rounds, watch
from app.features.mail import review as review_people
from app.features.mail.tables import LEVELS, SOURCES, Email, Followup, Person

router = APIRouter(prefix="/api")


# ------------------------------------------------------------------ people
def _person(s, p: Person, awaiting: set[int]) -> dict:
    left = (p.level_until - now()).days if p.level_until else None
    return {"id": p.id, "name": p.name, "level": p.level, "level_name": LEVELS[p.level],
            "source": SOURCES.get(p.level_source, p.level_source),
            "until": p.level_until.isoformat() if p.level_until else None, "days_left": left,
            "expired": people.expired(p), "note": p.note, "demote_reason": p.demote_reason,
            "last_mail_at": p.last_mail_at.isoformat() if p.last_mail_at else None,
            "addresses": people.addresses(s, p.id), "awaiting": p.id in awaiting}


@router.get("/people")
def list_people(level: str = "important") -> dict:
    """One tab of W2: the people at a level, latest mail first, plus the count of every tab."""
    with session() as s:
        counts = dict(s.execute(select(Person.level, func.count()).group_by(Person.level)).all())
        open_fu = s.scalars(select(Followup).where(Followup.closed_at.is_(None))).all()
        awaiting = {f.person_id for f in open_fu if f.waiting_on == "them" and f.person_id}
        rows = s.scalars(select(Person).where(Person.level == level)
                         .order_by(Person.last_mail_at.desc().nulls_last(), Person.name)).all() if level in LEVELS else []
        items = [_person(s, p, awaiting) for p in rows]
    return {"counts": {**{k: counts.get(k, 0) for k in LEVELS}, "followups": len(open_fu)}, "items": items}


@router.get("/people/{person_id}")
def get_person(person_id: int) -> dict:
    """W2's right side: the person, what they sent recently (one line each, and what was done), open follow-ups."""
    with session() as s:
        p = s.get(Person, person_id)
        if p is None:
            raise HTTPException(404, "ไม่พบคนนี้")
        open_fu = s.scalars(select(Followup).where(Followup.person_id == person_id, Followup.closed_at.is_(None))).all()
        mails = s.scalars(select(Email).where(Email.person_id == person_id)
                          .order_by(Email.sent_at.desc()).limit(20)).all()
        done = extract.done_for(s, [e.id for e in mails])
        out = _person(s, p, {person_id} if any(f.waiting_on == "them" for f in open_fu) else set())
        out["emails"] = [{
            "id": e.id, "sent_at": e.sent_at.isoformat(), "subject": e.subject, "from_me": e.from_me,
            "summary": e.summary, "stage": e.stage, "link": extract.gmail_link(e), "needs_reply": e.needs_reply,
            "done": done[e.id],
        } for e in mails]
        out["followups"] = [_followup(f, p.name) for f in open_fu]
    return out


class LevelIn(BaseModel):
    level: str
    days: int | None = None
    note: str | None = None
    reason: str = ""


@router.post("/people/{person_id}/level")
def set_level(person_id: int, body: LevelIn) -> dict:
    """ต่ออายุ · ลด · ยกระดับ (recorded, undoable)."""
    try:
        action_id = people.set_level(person_id, body.level, days=body.days, note=body.note, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"action_id": action_id}


class NoteIn(BaseModel):
    note: str


@router.put("/people/{person_id}/note")
def set_note(person_id: int, body: NoteIn) -> dict:
    """แก้โน้ต: your reason for keeping them important. Only you read it; the secretary doesn't decide on it."""
    with session() as s:
        p = s.get(Person, person_id)
        if p is None:
            raise HTTPException(404, "ไม่พบคนนี้")
        p.note = body.note.strip()
    return {"ok": True}


class NewPersonIn(BaseModel):
    address: str
    name: str = ""
    days: int | None = 90
    note: str = ""


@router.post("/people")
def add_person(body: NewPersonIn) -> dict:
    """Make someone important before they write ("อีเมลนี้สำคัญ รอเลย 3 เดือน")."""
    if "@" not in body.address:
        raise HTTPException(400, "ใส่อีเมลให้ถูกต้อง")
    person_id, action_id = people.add(body.address, body.name, days=body.days or None, note=body.note)
    return {"id": person_id, "action_id": action_id}


# ------------------------------------------------------------------ follow-ups
def _followup(f: Followup, name: str) -> dict:
    return {"id": f.id, "person_id": f.person_id, "name": name, "subject": f.subject, "waiting_on": f.waiting_on,
            "since": f.since.isoformat(), "days": (now() - f.since).days, "remind_after_days": f.remind_after_days}


@router.get("/followups")
def list_followups() -> dict:
    with session() as s:
        rows = s.scalars(select(Followup).where(Followup.closed_at.is_(None)).order_by(Followup.since)).all()
        names = {p.id: p.name for p in s.scalars(select(Person).where(Person.id.in_({f.person_id for f in rows})))}
        return {"items": [_followup(f, names.get(f.person_id, "ไม่ทราบชื่อ")) for f in rows]}


class FollowupIn(BaseModel):
    act: str  # done · later


@router.post("/followups/{followup_id}")
def answer_followup(followup_id: int, body: FollowupIn) -> dict:
    if body.act == "done":
        try:
            followups.done(followup_id, via=("หน้าเว็บ", ""))  # recorded: ย้อนกลับ opens it again
        except ValueError:
            pass  # already closed, or gone: nothing left to do
    elif body.act == "later":
        followups.snooze(followup_id)
    else:
        raise HTTPException(400, "act: done | later")
    return {"ok": True}


# ------------------------------------------------------------------ appointments
class AppointmentIn(BaseModel):
    accept: bool


@router.post("/appointments/{decision_id}")
async def answer_appointment(decision_id: int, body: AppointmentIn) -> dict:
    """รับนัด (into the calendar, undoable) or ไม่ไป, for an appointment waiting in the bell / #อนุมัติ."""
    try:
        d, action_id = await extract.decide(decision_id, body.accept, via=("หน้าเว็บ", ""))
        await decisions.settle_card(decision_id)  # its #อนุมัติ card says so too
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {"id": d.id, "status": d.status, "action_id": action_id}


# ------------------------------------------------------------------ mail settings
@router.get("/mail/settings")
def mail_settings() -> dict:
    state = watch._get(watch.STATE_KEY, {})
    with session() as s:
        week = s.scalar(select(func.count()).select_from(Email).where(Email.seen_at >= now() - timedelta(days=7))) or 0
        last_watch = s.scalar(select(Action.at).where(Action.kind == "round.watch").order_by(Action.at.desc()).limit(1))
    return {"keywords": watch.keywords(), "interests": rounds.interests(), "followup_days": followups.days(),
            "accounts": [{**a, "address": state.get(a["id"], {}).get("me", "")} for a in google.status()],
            "emails_week": week, "last_watch": last_watch.isoformat() if last_watch else None}


class MailSettingsIn(BaseModel):
    keywords: list[str] | None = None
    interests: list[str] | None = None
    followup_days: int | None = None


@router.put("/mail/settings")
def put_mail_settings(body: MailSettingsIn) -> dict:
    if body.keywords is not None:
        watch.set_keywords(body.keywords)
    if body.interests is not None:
        rounds.set_interests(body.interests)
    if body.followup_days is not None:
        watch._put(followups.DAYS_KEY, max(1, min(body.followup_days, 30)))
    return mail_settings()


# ------------------------------------------------------------------ ข้อเสนอปรับระดับรายสัปดาห์ (1.4, B7)
# (not under /people/...: that would be read as /people/{person_id})
@router.get("/proposals/people")
def people_proposals() -> dict:
    """This week's proposals: the weekly review's, while it waits for you, or else as they stand now."""
    return review_people.current()


class ProposalChoice(BaseModel):
    person_id: int
    choice: str


class ProposalsIn(BaseModel):
    items: list[ProposalChoice]
    decision_id: int | None = None  # the weekly review's, when answering it


@router.post("/proposals/people")
async def answer_proposals(body: ProposalsIn) -> dict:
    try:
        ids = await review_people.answer([i.model_dump() for i in body.items], body.decision_id, via=("หน้าคนและอีเมล", ""))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"action_ids": ids}
