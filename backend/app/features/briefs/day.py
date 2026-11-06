"""What a day holds, for the morning brief (D2), the evening review (D3) and the today page (W1).

Everything here only reads what other features already stored: the mail the watch and the
rounds read (with their summaries), the schedule (appointments, work blocks, due dates), the
decisions waiting for you, Classroom's new files, and the tokens the reading used. One set of
functions for all three places, so the today page's numbers are the morning brief's numbers
(B4's check).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select

from app.core import settings
from app.core.config import get_config
from app.core.db import now, session
from app.core.tables import Action, Block, Decision, Event, LLMUsage, Task
from app.core.timefmt import local
from app.features.briefs.tables import Brief
from app.features.mail.extract import done_for, gmail_link
from app.features.mail.tables import Email, Person

NIGHT_KEY = "state.briefs.night"  # what the 00:00 round found that only its card used to say (noteworthy subjects)
CUT = 90  # characters of a summary in a brief line


def short(text: str, limit: int = CUT) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def day_start(d: date) -> datetime:
    return datetime.combine(d, time(0), get_config().tz)


def today(at: datetime | None = None) -> date:
    return local(at or now()).date()


def since_last(kind: str, at: datetime) -> datetime:
    """Where a brief's window starts: the previous brief of the same kind, or a day back."""
    with session() as s:
        last = s.scalar(select(Brief.made_at).where(Brief.kind == kind, Brief.made_at < at).order_by(Brief.made_at.desc()))
    return last or at - timedelta(days=1)


# ------------------------------------------------------------------ mail
@dataclass
class Mail:
    id: str
    who: str
    summary: str  # the reading's one or two sentences, or the subject
    sent_at: datetime
    done: list[str] = field(default_factory=list)  # what the secretary did (done_for)
    link: str = ""

    def line(self) -> str:
        return f"{self.who}: {short(self.summary)}" + (f" ({' · '.join(self.done)})" if self.done else "")


def _important(s, since: datetime, until: datetime):
    """เรื่องสำคัญ: from important people, or matching a keyword, or someone you were waiting on."""
    return s.scalars(select(Email).where(
        Email.from_me.is_(False), Email.sent_at >= since, Email.sent_at < until, Email.stage != "old",
        (Email.level == "important") | (Email.flagged != "")).order_by(Email.sent_at.desc())).all()


def important_mail(since: datetime, until: datetime | None = None) -> list[Mail]:
    with session() as s:
        rows = _important(s, since, until or now())
        done = done_for(s, [e.id for e in rows])
        names = _names(s, rows)
        return [Mail(e.id, names.get(e.person_id) or e.sender_name or e.sender, e.summary or e.subject, e.sent_at,
                     done[e.id], gmail_link(e)) for e in rows]


def important_today(at: datetime | None = None) -> int:
    """The side menu's red number next to คนและอีเมล, and the today page's เรื่องสำคัญ."""
    at = at or now()
    with session() as s:
        return len(_important(s, day_start(today(at)), at))


def _names(s, rows) -> dict[int, str]:
    ids = {e.person_id for e in rows if e.person_id}
    return {p.id: p.name for p in s.scalars(select(Person).where(Person.id.in_(ids)))} if ids else {}


@dataclass
class WhoSent:
    important: list[tuple[str, int]]  # (name, how many)
    interested: list[tuple[str, str, list[str]]]  # (name, the round's summary of everything they sent, done)
    ignored: int
    ignored_top: list[tuple[str, int]]  # the senders with the most
    noteworthy: list[tuple[str, str, str]]  # (who, subject, why) the 00:00 round picked out of the ignored
    unread: int  # still waiting for the next round (stage "seen")
    read: int  # read, summarized or skimmed in the window


def who_sent(since: datetime, until: datetime) -> WhoSent:
    """ใครส่งอะไรมา ตาม 3 ระดับ (D2 ③): important per person, interested per person with the
    round's summary, ignored only as numbers per sender (the subjects were skimmed by the round)."""
    with session() as s:
        rows = s.scalars(select(Email).where(Email.from_me.is_(False), Email.sent_at >= since, Email.sent_at < until,
                                             Email.stage != "old").order_by(Email.sent_at)).all()
        names = _names(s, rows)
        done = done_for(s, [e.id for e in rows])
    imp: dict[str, int] = {}
    interested: dict[str, tuple[str, list[str]]] = {}
    ign: dict[str, int] = {}
    unread = read = 0
    for e in rows:
        who = names.get(e.person_id) or e.sender_name or e.sender
        if e.stage == "seen":
            unread += 1
            continue
        read += 1
        if e.level == "important" or e.flagged:  # a keyword match is in เรื่องสำคัญ: counted with it
            imp[who] = imp.get(who, 0) + 1
        elif e.level == "interested":
            summary, did = interested.get(who, ("", []))
            interested[who] = (e.summary or summary or e.subject, sorted(set(did + done[e.id])))
        else:
            ign[who] = ign.get(who, 0) + 1
    night = settings.get(NIGHT_KEY, {}) or {}
    kept = datetime.fromisoformat(night["at"]) if night.get("at") else None
    noteworthy = [tuple(x) for x in night.get("noteworthy", [])] if kept and since <= kept < until else []
    return WhoSent(sorted(imp.items(), key=lambda x: -x[1]), [(k, v[0], v[1]) for k, v in interested.items()],
                   sum(ign.values()), sorted(ign.items(), key=lambda x: -x[1])[:3], noteworthy, unread, read)


def who_sent_text(w: WhoSent, next_round: str) -> str:
    lines = []
    if w.important:
        lines.append("**สำคัญ** · " + " · ".join(f"{n} {c} ฉบับ" for n, c in w.important))
    if w.interested:
        lines.append("**สนใจ** · " + " · ".join(
            f"{n}: {short(summary, 70)}" + (f" ({' · '.join(did)})" if did else "") for n, summary, did in w.interested))
    if w.ignored:
        top = " · ".join(f"{n} {c}" for n, c in w.ignored_top)
        rest = w.ignored - sum(c for _, c in w.ignored_top)
        lines.append(f"**ไม่สนใจ** · {w.ignored} ฉบับ: {top}" + (f" · อื่นๆ {rest}" if rest > 0 else ""))
    for who, subject, why in w.noteworthy[:5]:
        lines.append(f"↳ น่าดู: {who}: {short(subject, 60)} ({short(why, 50)})")
    if w.unread:
        lines.append(f"ยังไม่อ่าน {w.unread} ฉบับ · รอรอบ {next_round}")
    return "\n".join(lines)


# ------------------------------------------------------------------ the schedule
@dataclass
class Item:
    start: datetime
    end: datetime
    title: str
    kind: str  # meet · block · dead · allday
    sub: str = ""

    def words(self) -> str:
        at = f"{local(self.start):%H:%M}"
        if self.kind == "allday":
            return f"ทั้งวัน {self.title}"
        if self.kind == "dead":
            return f"ส่ง {local(self.end):%H:%M} {self.title}"
        if self.kind == "block":
            return f"{at} บล็อก {self.title}"
        return f"{at} {self.title}" + (f" ({self.sub})" if self.sub else "")


def agenda(d: date) -> list[Item]:
    """One day: appointments, work blocks and due dates, in time order (all-day ones first)."""
    lo, hi = day_start(d), day_start(d + timedelta(days=1))
    with session() as s:
        events = s.scalars(select(Event).where(Event.status == "placed", Event.starts_at < hi, Event.ends_at > lo)).all()
        blocks = s.execute(select(Block, Task.title).join(Task, Task.id == Block.task_id).where(
            Block.status.in_(("planned", "pinned")), Block.starts_at >= lo, Block.starts_at < hi)).all()
        due = s.scalars(select(Task).where(Task.status == "open", Task.due_at >= lo, Task.due_at < hi)).all()
        items = [Item(e.starts_at, e.ends_at, e.title, "allday" if e.all_day else "meet", e.location) for e in events]
        items += [Item(b.starts_at, b.ends_at, title, "block") for b, title in blocks]
        items += [Item(t.due_at, t.due_at, t.title, "dead") for t in due]
    return sorted(items, key=lambda i: (i.kind != "allday", i.start if i.kind != "dead" else i.end))


def appointments(items: list[Item]) -> int:
    return sum(1 for i in items if i.kind in ("meet", "allday"))


# ------------------------------------------------------------------ the rest of the day's numbers
def waiting() -> list[Decision]:
    """เรื่องที่รอคุณตัดสิน: every pending decision (plans, appointments, courses), newest first."""
    with session() as s:
        rows = s.scalars(select(Decision).where(Decision.status == "pending").order_by(Decision.created_at.desc())).all()
        s.expunge_all()
    return rows


KIND_WORDS = {"appointment": "นัด", "plan": "แผน", "course": "วิชา"}


def waiting_text(rows: list[Decision]) -> str:
    def one(d: Decision) -> str:
        who = d.detail.get("from", "")
        return f"{KIND_WORDS.get(d.kind, d.kind)}{'จาก' + who if who else ''}: {short(d.title, 50)}"
    return " · ".join(one(d) for d in rows[:6]) + (f" · และอีก {len(rows) - 6}" if len(rows) > 6 else "")


def project_news(since: datetime, until: datetime, limit: int = 8) -> list[tuple[str, str, bool]]:
    """ข่าวโปรเจค (2.3, D2 ⑤): what projects dropped in the inbox, the ones that matter most first.
    -> [(project, title, urgent)]"""
    from app.features.projects.tables import Project, ProjectNews

    order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "F": 5}
    with session() as s:
        rows = s.execute(select(ProjectNews, Project.potential, Project.urgency)
                         .outerjoin(Project, Project.id == ProjectNews.project_id)
                         .where(ProjectNews.at >= since, ProjectNews.at < until, ProjectNews.kind != "bad")).all()
    rows.sort(key=lambda r: (not r[0].urgent, order.get(r[1] or "C", 3), -(r[2] if r[2] is not None else 2), -r[0].at.timestamp()))
    return [(n.project, n.title, n.urgent) for n, _, _ in rows[:limit]]


def new_materials(since: datetime, until: datetime) -> list[str]:
    """สื่อการเรียนใหม่ (U1: "บอกในสรุปเช้า"): what Classroom's round downloaded, per course."""
    with session() as s:
        rows = s.scalars(select(Action).where(Action.kind == "classroom.files", Action.at >= since, Action.at < until,
                                              Action.undone_at.is_(None))).all()
    return [r.summary.removeprefix("ดาวน์โหลดสื่อ ") for r in rows]


def tokens_used(since: datetime, until: datetime) -> list[tuple[str, int]]:
    """What reading the mail cost in the window, per model ([("Opus", 18000)])."""
    with session() as s:
        rows = s.execute(select(LLMUsage.model, func.sum(LLMUsage.tokens_in + LLMUsage.tokens_out))
                         .where(LLMUsage.at >= since, LLMUsage.at < until).group_by(LLMUsage.model)).all()
    return [(model, int(n or 0)) for model, n in rows if n]


def tokens_words(used: list[tuple[str, int]]) -> str:
    def k(n: int) -> str:
        return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)
    return " · ".join(f"{model} {k(n)} โทเคน" for model, n in used) or "ไม่ใช้โทเคน"
