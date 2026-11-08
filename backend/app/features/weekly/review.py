"""ทบทวนรายสัปดาห์ (D4, P3, B7): Sunday 19:00 in #สรุป, made with templates (no model, no tokens).

1. The overview: the week in numbers (how much of the plan you followed against your target,
   where your time went against last week) and "รับทุกเรื่องตามที่เสนอ".
2. One message per topic (topics.py), each a decision of kind "weekly" with its own buttons, so it
   also waits in the bell and on the today page. Idea groups waiting for you (B6) follow with
   their own buttons.

Answering (`answer`) does what the topic says, through the parts that own it, so every change is
in สิ่งที่เลขาทำ and can be undone there: a level change, a rule in the rule book, a task the
planner books. A topic nobody answers changes nothing; at the next review it's closed as expired.
"รับทุกเรื่องตามที่เสนอ" answers every waiting topic of that review with its default, leaving
the idea groups (you choose) and anything that would spend tokens.

The round runs on Sunday from 19:00; when the machine was off then, the clock's catch-up still
makes it until Monday 12:00. One per week (the briefs table: kind "weekly", day = that Sunday).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from app.core import actions, settings
from app.core.config import get_config
from app.core.db import now, session
from app.core.tables import Decision, Task
from app.core.timefmt import local
from app.features import decisions
from app.features.briefs.tables import Brief
from app.features.time import followed, insights
from app.features.weekly import topics as T

log = logging.getLogger(__name__)

TARGET_KEY = "schedule.follow_target"  # the schedule page's target (api/schedule.py), default 80
SHORT_CAT = {"code": "โค้ด", "study": "เรียน", "meeting": "ประชุม", "chat": "อีเมลและแชท", "web": "เว็บและโซเชียล", "other": "อื่นๆ"}

# Called with the brief id once a review is made: cards.py posts it to #สรุป.
MADE: list[Callable[[int], Awaitable[None]]] = []

Via = tuple[str, str]


def sunday(at: datetime) -> date:
    d = local(at).date()
    return d + timedelta(days=6 - d.weekday())


def open_now(at: datetime) -> bool:
    """Sunday from 19:00, or Monday until 12:00 (a review the machine slept through)."""
    t = local(at)
    return (t.weekday() == 6 and t.time() >= time(19, 0)) or (t.weekday() == 0 and t.time() < time(12, 0))


def week_of(at: datetime) -> tuple[datetime, datetime, str]:
    """The week the review is about: the one that ends this Sunday (or, on Monday morning, yesterday)."""
    t = local(at)
    return insights.span("week", at - timedelta(days=1) if t.weekday() == 0 and t.time() < time(12, 0) else at)


# ------------------------------------------------------------------ the overview
def overview(at: datetime, n: int) -> tuple[str, str, list[str]]:
    """-> (title, headline, bullets)."""
    start, end, label = week_of(at)
    upto = min(end, at)
    bullets = []
    f = followed.followed(start, upto)
    if f["percent"] is not None:
        note = next((p["title"] for p in followed.patterns(at)), "")
        bullets.append(f"ทำตามแผน {f['percent']}% (เป้า {settings.get(TARGET_KEY, 80)}%)" + (f" · {note}" if note else ""))
    this, last = per_category(start, upto), per_category(start - timedelta(days=7), start)
    if this:
        parts = []
        for cat, mins in sorted(this.items(), key=lambda kv: -kv[1]):
            if mins < 30:
                continue
            delta = round((mins - last.get(cat, 0)) / 60)
            parts.append(f"{SHORT_CAT.get(cat, cat)} {T.hours(mins)}" + (" ชม." if not parts else "")
                         + (f" ({delta:+d})" if last and abs(delta) >= 2 else ""))
        bullets.append("เวลา: " + " · ".join(parts))
    else:
        bullets.append("ยังไม่มีเวลาจริงจาก ActivityWatch (เปิดบันทึกกิจกรรมที่หน้าการใช้เวลา)")
    title = f"{label} · {n} เรื่องให้ตัดสิน" if n else f"{label} · ไม่มีเรื่องให้ตัดสิน"
    return title, " · ".join(bullets), bullets


def per_category(start: datetime, end: datetime) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in insights.rows(start, end):
        out[r.category or "other"] = out.get(r.category or "other", 0) + insights.minutes(r)
    return out


# ------------------------------------------------------------------ making it
def expire_old() -> list[int]:
    """Topics of earlier reviews nobody answered: closed, nothing changed. -> their ids."""
    with session() as s:
        old = s.scalars(select(Decision).where(Decision.kind == "weekly", Decision.status == "pending")).all()
        for d in old:
            d.status, d.answered_at = "expired", now()
        return [d.id for d in old]


def make(at: datetime | None = None, *, again: bool = False) -> int | None:
    """Build this week's review: the brief and a decision per topic. -> the brief id, or None when
    this week has one already. again=True (ส่งตอนนี้): the week's review is made again in place,
    the same brief with fresh topics; the old ones still waiting expire."""
    at = at or now()
    day = sunday(at - timedelta(days=1)) if local(at).weekday() == 0 and local(at).time() < time(12, 0) else sunday(at)
    with session() as s:
        if s.scalar(select(Brief.id).where(Brief.kind == "weekly", Brief.day == day.isoformat())) and not again:
            return None
    expire_old()
    found, idea_ids = T.build(at)
    title, headline, bullets = overview(at, len(found) + len(idea_ids))
    with session() as s:
        brief = s.scalar(select(Brief).where(Brief.kind == "weekly", Brief.day == day.isoformat()))
        if brief is None:  # (made again: the same row, so a decision's brief_id can't point at a reused id)
            brief = Brief(kind="weekly", day=day.isoformat())
            s.add(brief)
        brief.made_at, brief.title, brief.headline, brief.message_id = at, title, headline, None
        brief.fields = [["ภาพรวม", "\n".join(f"• {b}" for b in bullets)]]
        brief.footer = ("ทุกเรื่องด้านล่างบอกว่าจะทำอะไร ทำยังไง แค่ไหน · เรื่องที่ไม่ตัดสิน เลขาไม่เปลี่ยนอะไร"
                        " · “รับทุกเรื่อง” ทำตามที่เสนอ ยกเว้นกลุ่มไอเดีย (เลือกเอง) และงานที่ใช้โทเคน")
        s.flush()
        for i, topic in enumerate(found, 1):
            s.add(Decision(kind="weekly", title=topic["title"],
                           detail={**topic, "brief_id": brief.id, "n": i, "of": len(found) + len(idea_ids), "ideas": idea_ids}))
        brief_id = brief.id
    return brief_id


def of_brief(brief_id: int, status: str | None = "pending") -> list[Decision]:
    with session() as s:
        rows = [d for d in s.scalars(select(Decision).where(Decision.kind == "weekly").order_by(Decision.id))
                if (d.detail or {}).get("brief_id") == brief_id and (status is None or d.status == status)]
        s.expunge_all()
    return rows


async def run() -> str | None:
    """The "weekly" round (Sunday 19:00)."""
    at = now()
    if not open_now(at):
        return f"ข้าม: ทบทวนรายสัปดาห์ส่งได้วันอาทิตย์ 19:00 ถึงวันจันทร์ 12:00 · ตอนนี้ {local(at):%a %H:%M}"
    return await send(at)


async def send(at: datetime | None = None, *, again: bool = False) -> str | None:
    brief_id = await asyncio.to_thread(make, at, again=again)
    if brief_id is None:
        return None
    for hook in MADE:
        try:
            await hook(brief_id)
        except Exception:
            log.exception("the weekly review couldn't be posted")
    with session() as s:
        return s.get(Brief, brief_id).title


# ------------------------------------------------------------------ answering (step 3)
class AnswerError(ValueError):
    """Why a topic can't be answered that way, in your words."""


def _waiting(decision_id: int) -> Decision:
    with session() as s:
        d = s.get(Decision, decision_id)
        if d is None or d.kind != "weekly":
            raise AnswerError("ไม่พบเรื่องนี้")
        if d.status != "pending":
            raise AnswerError("เรื่องนี้ตัดสินไปแล้ว" if d.status != "expired" else "เรื่องนี้หมดรอบแล้ว")
        s.expunge(d)
        return d


def _close(decision_id: int, status: str, answer: str) -> None:
    with session() as s:
        d = s.get(Decision, decision_id)
        d.status, d.answer, d.answered_at = status, answer, now()


def _task(title: str, project: str, minutes: int, *, block: int | None = None, due: datetime | None = None,
          not_before: datetime | None = None, details: str = "", via: Via) -> int:
    from app.features.schedule import tasks

    task_id, action_id = tasks.add(title, due_at=due, est_minutes=minutes, block_minutes=block, details=details, via=via)
    with session() as s:
        t = s.get(Task, task_id)
        t.project, t.source, t.not_before = project, "project", not_before
    return action_id


async def _replan() -> str:
    """Plan again now, best effort: when Google can't be reached, the next schedule round does it."""
    from app.features.schedule import sync

    try:
        return await sync.run(force=True) or ""
    except Exception as exc:
        log.warning("couldn't re-plan after the weekly review: %s", exc)
        return "วางตารางใหม่ในรอบถัดไป"


async def answer(decision_id: int, act: str, *, via: Via = ("หน้าเว็บ", "")) -> str:
    """Do what the topic says (act: one of its buttons). -> what was done, in your words."""
    from app.features.mail import review as people_review

    d = _waiting(decision_id)
    detail = d.detail
    if act not in dict(detail["acts"]):
        raise AnswerError("ไม่มีตัวเลือกนี้")
    topic, proposal = detail["topic"], detail["proposal"]
    if act == "reject":
        _close(decision_id, "rejected", "reject")
        await decisions.settle_card(decision_id, where=via[0])
        return "ไม่เอา · เลขาไม่เปลี่ยนอะไร"
    if topic == "people":
        done = await people_review.answer([{"person_id": i["person_id"], "choice": i["choice"]} for i in proposal["items"]],
                                          decision_id, via=via)
        return f"✅ ปรับทะเบียนแล้ว {len(done)} คน · ย้อนกลับได้ที่หน้าสิ่งที่เลขาทำ"
    said = ""
    if topic == "schedule":
        made = []
        if proposal.get("focus"):
            followed.focus_rule(proposal["focus"]["from"], proposal["focus"]["to"], via=via)
            made.append(f"ช่วงโฟกัส {proposal['focus']['from']}–{proposal['focus']['to']} ก่อน")
        for a in proposal.get("avoid", []):
            try:
                followed.avoid_rule(a["weekday"], a["part"], via=via)
                made.append(f"ไม่วางบล็อก{a['part']}{followed.WEEKDAYS[a['weekday']]}")
            except ValueError:
                pass  # added by hand meanwhile
        line = await _replan()
        said = "✅ เพิ่มกติกาแล้ว: " + " · ".join(made) + (f" · วางตารางใหม่: {line}" if line else "")
    elif topic == "time":
        for b in proposal["projects"]:
            _task(f"{b['name']}: เวลาที่ขาดจากสัปดาห์ก่อน (ทบทวนรายสัปดาห์)", b["name"], b["book"],
                  not_before=datetime.fromisoformat(proposal["from"]),
                  details=f"ทำ {T.hours(b['minutes'])} จากแผน {T.hours(b['planned'])} ชม.", via=via)
        await _replan()
        said = "✅ จองเวลาแล้ว: " + " · ".join(f"{b['name']} {T.hours(b['book'])} ชม." for b in proposal["projects"])
    elif topic == "project":
        due = datetime.fromisoformat(proposal["due"]) if proposal.get("due") else None
        _task(f"{proposal['name']}: {proposal['next'] or 'ทำต่อ'} (ทบทวนรายสัปดาห์)", proposal["name"], T.PROJECT_MINUTES,
              block=T.PROJECT_BLOCK, due=due, details=f"ขั้นถัดไปใน PROGRESS.md: {proposal['next']}" if proposal["next"] else "", via=via)
        said = f"✅ จองเวลา {proposal['name']} {T.PROJECT_MINUTES // 60} ชม. แล้ว"
        if act == "both":
            said += " · " + await _summary_job(proposal, via)
        await _replan()
    _close(decision_id, "approved", act)
    await decisions.settle_card(decision_id, where=via[0])
    actions.record("weekly.answer", f"ทบทวนรายสัปดาห์: {d.title}", said, source_label=via[0], source_url=via[1])
    return said


async def _summary_job(proposal: dict, via: Via) -> str:
    """รับทั้งสองอย่าง: a background job that summarises where the project is stuck (B5's queue and
    rules: planned by Opus now, so a plan that has to ask you is in #อนุมัติ at once)."""
    from app.features.jobs import plan as plans
    from app.features.jobs import queue

    try:
        job_id, _ = queue.add(proposal["project_id"], T.SUMMARY_NOTE, via=via)
    except ValueError as exc:
        return f"ให้เลขาสรุปไม่ได้: {exc}"
    try:
        verdict = await plans.make(job_id)
    except Exception as exc:  # the job waits in the queue and is planned at night
        return f"ใส่คิวงานเบื้องหลังแล้ว (วางแผนตอนนี้ไม่สำเร็จ: {exc})"
    return "งานสรุปผ่านกฎแล้ว รอทำตอน 01:00–06:00" if verdict.go else f"งานสรุปรอคุณอนุมัติใน #อนุมัติ ({verdict.why})"


async def accept_all(brief_id: int, *, via: Via = ("#สรุป", "")) -> list[str]:
    """รับทุกเรื่องตามที่เสนอ: every waiting topic of this review, with its default."""
    out = []
    for d in of_brief(brief_id):
        default = d.detail.get("default")
        if default:
            try:
                out.append(await answer(d.id, default, via=via))
            except AnswerError as exc:
                out.append(str(exc))
    return out


def choose_person(decision_id: int, person_id: int, choice: str) -> dict:
    """The people topic's menu: change one person's choice before you press รับ. -> the topic's detail."""
    d = _waiting(decision_id)
    items = d.detail["proposal"]["items"]
    for item in items:
        if item["person_id"] == person_id:
            if choice not in dict(item["choices"]):
                raise AnswerError("ไม่มีตัวเลือกนี้")
            item["choice"] = choice
    detail = {**d.detail, "proposal": {"items": items}, "what": T.people_what(items)}
    with session() as s:
        s.get(Decision, decision_id).detail = detail
    return detail


def setup() -> None:
    from app.core import clock
    clock.attach("weekly", run)

