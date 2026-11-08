"""ถามเลขาได้ทุกส่วน (P10, B7): read-only tools over every part of the store, for the chat's model.

B1's four tools (ask.py) read the action log, waiting decisions, model usage and the clock. These
read the rest: people and their mail (summaries and a Gmail link, never bodies: bodies aren't
kept), what's waiting for a reply, the schedule and tasks, projects with their news, background
jobs and time, ideas, time use with window titles (allowed at the B7 plan, "4.ข": they're the
titles left after the privacy filter), Classroom, and the rule book.

Each answer lists the tools it used as its sources (ask.SOURCE_NAMES), and the tools hand back
links where a thing has one, so the answer can point at the email or the coursework itself. Rows
are capped, so one question can't send the whole store to the model.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, time, timedelta
from typing import Annotated

from claude_agent_sdk import tool
from sqlalchemy import or_, select

from app.core.config import get_config
from app.core.db import now, session
from app.core.tables import Block, Event, Rule, Task
from app.core.timefmt import local, thai_datetime

SOURCE_NAMES = {
    "people_and_mail": "คนและอีเมล", "waiting_replies": "เรื่องค้าง", "schedule": "ตาราง", "tasks": "งาน",
    "projects": "โปรเจค", "ideas": "ไอเดีย", "time_use": "การใช้เวลา", "classroom": "Classroom", "rule_book": "สมุดกติกา",
}
MAX_ROWS = 40


def _text(value) -> dict:
    return {"content": [{"type": "text", "text": value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)}]}


def _days(args: dict, key: str, default: int, most: int = 120) -> int:
    try:
        return max(0, min(most, int(args.get(key) if args.get(key) is not None else default)))
    except (TypeError, ValueError):
        return default


def _today_start() -> datetime:
    return datetime.combine(local(now()).date(), time(0), get_config().tz)


def _like(text: str) -> str:
    return f"%{text.strip()}%"


# ------------------------------------------------------------------ people and mail
@tool("people_and_mail",
      "คนในทะเบียน (ระดับ วันหมดอายุ โน้ต) และอีเมลที่เขาส่งมาย้อนหลัง พร้อมสรุปและลิงก์เปิดใน Gmail · "
      "ค้นด้วยชื่อหรือที่อยู่อีเมล (บางส่วนก็ได้) หรือค้นจากหัวข้อและสรุปด้วย query",
      {"name": Annotated[str, "ชื่อหรืออีเมล เช่น วิภา · ว่างได้"], "query": Annotated[str, "คำในหัวข้อหรือสรุป · ว่างได้"],
       "days": Annotated[int, "ย้อนหลังกี่วัน (สัปดาห์นี้ = นับจากวันจันทร์)"]})
async def people_and_mail(args: dict) -> dict:
    from app.features.mail.extract import gmail_link
    from app.features.mail.tables import LEVELS, Email, Person, PersonAddress

    name, query = (args.get("name") or "").strip(), (args.get("query") or "").strip()
    since = _today_start() - timedelta(days=_days(args, "days", 7))
    with session() as s:
        people = []
        if name:
            ids = set(s.scalars(select(Person.id).where(Person.name.like(_like(name)))))
            ids |= set(s.scalars(select(PersonAddress.person_id).where(PersonAddress.address.like(_like(name.lower())))))
            people = s.scalars(select(Person).where(Person.id.in_(ids))).all() if ids else []
            if not people:
                return _text(f"ไม่พบคนชื่อหรืออีเมล “{name}” ในทะเบียน")
        q = select(Email).where(Email.sent_at >= since, Email.from_me.is_(False)).order_by(Email.sent_at.desc()).limit(MAX_ROWS)
        if people:
            q = q.where(Email.person_id.in_([p.id for p in people]))
        if query:
            q = q.where(or_(Email.subject.like(_like(query)), Email.summary.like(_like(query))))
        mails = s.scalars(q).all()
        out = {"คน": [{"ชื่อ": p.name, "ระดับ": LEVELS[p.level], "หมดอายุ": thai_datetime(p.level_until) if p.level_until else "",
                       "โน้ต": p.note} for p in people],
               "อีเมล": [{"เมื่อ": thai_datetime(e.sent_at), "จาก": e.sender_name or e.sender, "หัวข้อ": e.subject,
                          "สรุป": e.summary or ("(ยังไม่ได้สรุป)" if e.stage == "seen" else "(อ่านแค่หัวข้อ)"),
                          "ต้องตอบ": e.needs_reply, "ลิงก์": gmail_link(e)} for e in mails]}
    if not out["อีเมล"]:
        out["อีเมล"] = f"ไม่มีอีเมลตั้งแต่ {thai_datetime(since)}"
    return _text(out)


@tool("waiting_replies", "เรื่องค้าง: อีเมลที่รอคุณตอบ และที่คุณรอคำตอบจากคนอื่น ตั้งแต่เมื่อไร", {})
async def waiting_replies(args: dict) -> dict:
    from app.features.mail.tables import Followup, Person

    with session() as s:
        rows = s.execute(select(Followup, Person.name).outerjoin(Person, Person.id == Followup.person_id)
                         .where(Followup.closed_at.is_(None)).order_by(Followup.since).limit(MAX_ROWS)).all()
        return _text([{"กับ": who or "", "หัวข้อ": f.subject, "รอ": "คุณตอบ" if f.waiting_on == "you" else "เขาตอบ",
                       "ตั้งแต่": thai_datetime(f.since)} for f, who in rows] or "ไม่มีเรื่องค้าง")


# ------------------------------------------------------------------ schedule and tasks
@tool("schedule", "ตารางช่วงหนึ่ง: นัดในปฏิทิน บล็อกงานที่เลขาจอง (พร้อมผลว่าทำแล้วหรือหลุด) และงานที่ถึงกำหนดส่ง",
      {"days_back": Annotated[int, "ย้อนหลังกี่วันจากวันนี้ (0 = เริ่มวันนี้)"], "days_ahead": Annotated[int, "ล่วงหน้ากี่วัน"]})
async def schedule(args: dict) -> dict:
    lo = _today_start() - timedelta(days=_days(args, "days_back", 0, 60))
    hi = _today_start() + timedelta(days=_days(args, "days_ahead", 7, 60) + 1)
    with session() as s:
        events = s.scalars(select(Event).where(Event.status == "placed", Event.starts_at < hi, Event.ends_at > lo)
                           .order_by(Event.starts_at).limit(MAX_ROWS)).all()
        blocks = s.execute(select(Block, Task.title).join(Task, Task.id == Block.task_id)
                           .where(Block.status.in_(("planned", "pinned")), Block.starts_at < hi, Block.ends_at > lo)
                           .order_by(Block.starts_at).limit(MAX_ROWS)).all()
        due = s.scalars(select(Task).where(Task.due_at >= lo, Task.due_at < hi).order_by(Task.due_at).limit(MAX_ROWS)).all()
        outcome = {"done": "ทำแล้ว", "missed": "หลุด", "away": "ไม่ได้ใช้คอม", "unknown": "ไม่มีข้อมูล", "": ""}
        return _text({
            "นัด": [{"เมื่อ": thai_datetime(e.starts_at), "ถึง": f"{local(e.ends_at):%H:%M}", "เรื่อง": e.title, "ที่": e.location,
                     "ลิงก์": e.link} for e in events],
            "บล็อกงาน": [{"เมื่อ": thai_datetime(b.starts_at), "ถึง": f"{local(b.ends_at):%H:%M}", "งาน": title,
                          "ผล": outcome.get(b.outcome, b.outcome) + (f" (ทำ {b.worked_minutes} นาที)" if b.worked_minutes else ""),
                          "ทำแทน": b.instead} for b, title in blocks],
            "กำหนดส่ง": [{"เมื่อ": thai_datetime(t.due_at), "งาน": t.title, "สถานะ": t.status} for t in due]})


@tool("tasks", "รายการงาน: ชื่อ กำหนดส่ง มาจากไหน โปรเจค รายละเอียด · status: open (ค้าง) · done (เสร็จ) · all",
      {"status": Annotated[str, "open · done · all"], "query": Annotated[str, "คำในชื่องาน · ว่างได้"]})
async def tasks(args: dict) -> dict:
    from app.features.schedule.tasks import SOURCE_NAMES as TASK_SOURCES

    status, query = (args.get("status") or "open").strip(), (args.get("query") or "").strip()
    with session() as s:
        q = select(Task).order_by(Task.due_at.is_(None), Task.due_at, Task.id.desc()).limit(MAX_ROWS)
        if status in ("open", "done"):
            q = q.where(Task.status == status)
        if query:
            q = q.where(Task.title.like(_like(query)))
        return _text([{"งาน": t.title, "ส่ง": thai_datetime(t.due_at) if t.due_at else "ไม่มีกำหนด", "ที่มา": TASK_SOURCES.get(t.source, t.source),
                       "โปรเจค": t.project, "สถานะ": t.status, "รายละเอียด": t.details[:300]} for t in s.scalars(q)] or "ไม่มีงาน")


# ------------------------------------------------------------------ projects, ideas, time
@tool("projects", "โปรเจคใน ~/Projects: สถานะ ระดับ ขั้นถัดไปใน PROGRESS.md ความเคลื่อนไหวล่าสุด · ใส่ name เพื่อดูละเอียด "
      "(ข่าวจากโปรเจค งานเบื้องหลัง เวลาที่ทำจริง 7 วัน)",
      {"name": Annotated[str, "ชื่อโปรเจค (บางส่วนก็ได้) · ว่าง = ทุกโปรเจค"]})
async def projects(args: dict) -> dict:
    from app.features.jobs.tables import Job
    from app.features.projects.tables import STATUSES, Project, ProjectNews
    from app.features.time.tables import Activity

    name = (args.get("name") or "").strip()
    with session() as s:
        q = select(Project).where(Project.hidden.is_(False), Project.missing.is_(False)).order_by(Project.last_activity.desc())
        if name:
            q = q.where(Project.name.like(_like(name)))
        rows = s.scalars(q.limit(MAX_ROWS)).all()
        if not rows:
            return _text(f"ไม่พบโปรเจค “{name}”" if name else "ยังไม่มีโปรเจคในทะเบียน")
        out = [{"โปรเจค": p.name, "สถานะ": STATUSES.get(p.status, p.status), "ระดับ": f"{p.potential} · เร่งด่วน {p.urgency}",
                "ขั้นถัดไป": (p.progress or {}).get("next", ""), "ทำแล้ว/ค้าง": f"{(p.progress or {}).get('done', 0)}/{(p.progress or {}).get('todo', 0)}",
                "ล่าสุด": thai_datetime(p.last_activity) if p.last_activity else ""} for p in rows]
        if name and len(rows) <= 3:
            week = now() - timedelta(days=7)
            for row, p in zip(out, rows):
                row["ข่าว"] = [{"เมื่อ": thai_datetime(n.at), "เรื่อง": n.title, "ลิงก์": n.link}
                               for n in s.scalars(select(ProjectNews).where(ProjectNews.project == p.name)
                                                  .order_by(ProjectNews.at.desc()).limit(5))]
                row["งานเบื้องหลัง"] = [{"งาน": j.title or j.stuck_at, "สถานะ": j.status, "ผล": j.result[:200]}
                                        for j in s.scalars(select(Job).where(Job.project_id == p.id).order_by(Job.id.desc()).limit(3))]
                mins = sum((min(a.end, now()) - max(a.start, week)).total_seconds() / 60
                           for a in s.scalars(select(Activity).where(Activity.project == p.name, Activity.end > week)))
                row["เวลาที่ทำจริง 7 วัน"] = f"{mins / 60:.1f} ชม."
    return _text(out)


@tool("ideas", "ไอเดียที่จดไว้และกลุ่มไอเดีย · ค้นด้วยคำหรือแท็ก", {"query": Annotated[str, "คำหรือแท็ก · ว่าง = ล่าสุด"]})
async def ideas(args: dict) -> dict:
    from app.features.ideas.tables import GROUP_STATUSES, SOURCES, Idea, IdeaGroup

    query = (args.get("query") or "").strip().lstrip("#")
    with session() as s:
        groups = {g.id: g for g in s.scalars(select(IdeaGroup))}
        # (filtered here, not with LIKE: the JSON column keeps Thai tags as \uXXXX escapes)
        recent = s.scalars(select(Idea).order_by(Idea.created_at.desc()).limit(500)).all()
        needle = query.lower()
        rows = [i for i in recent if not needle or needle in i.text.lower() or any(needle in tag for tag in i.tags or [])][:MAX_ROWS]
        return _text({"ไอเดีย": [{"เมื่อ": thai_datetime(i.created_at), "ไอเดีย": i.text, "แท็ก": i.tags, "จาก": SOURCES.get(i.source, i.source),
                                   "กลุ่ม": groups[i.group_id].name if i.group_id in groups else ""} for i in rows] or "ไม่พบ",
                      "กลุ่ม": [{"กลุ่ม": g.name, "สถานะ": GROUP_STATUSES.get(g.status, g.status)} for g in groups.values()
                                if not query or query.lower() in (g.name + g.tag).lower()][:MAX_ROWS]})


@tool("time_use", "การใช้เวลาบนคอมจาก ActivityWatch (ผ่านตัวกรองความเป็นส่วนตัวแล้ว): รวมต่อวัน ต่อหมวด ต่อโปรเจค "
      "และชื่อหน้าต่างที่ใช้นานสุด · ใส่ project เพื่อดูเฉพาะโปรเจคนั้น",
      {"days": Annotated[int, "ย้อนหลังกี่วัน (0 = วันนี้)"], "project": Annotated[str, "ชื่อโปรเจค · ว่างได้"]})
async def time_use(args: dict) -> dict:
    from app.features.time import insights
    from app.features.time.categorize import CATEGORIES

    start = _today_start() - timedelta(days=_days(args, "days", 0, 60))
    rows = insights.rows(start, now())
    project = (args.get("project") or "").strip().lower()
    if project:
        rows = [r for r in rows if project in (r.project or "").lower()]
    if not rows:
        return _text("ไม่มีเวลาที่บันทึกในช่วงนี้ (ActivityWatch อาจยังไม่ได้เปิด)")
    per_day, per_cat, per_project, titles = defaultdict(float), defaultdict(float), defaultdict(float), defaultdict(float)
    for r in rows:
        m = insights.minutes(r)
        per_day[f"{insights.DAYS[local(r.start).weekday()]} {local(r.start).day}"] += m
        per_cat[CATEGORIES.get(r.category or "other", "อื่นๆ")] += m
        if r.project:
            per_project[r.project] += m
        titles[(r.app, r.title)] += m
    h = lambda m: f"{m / 60:.1f} ชม."  # noqa: E731
    return _text({"ต่อวัน": {k: h(v) for k, v in per_day.items()}, "ต่อหมวด": {k: h(v) for k, v in sorted(per_cat.items(), key=lambda x: -x[1])},
                  "ต่อโปรเจค": {k: h(v) for k, v in sorted(per_project.items(), key=lambda x: -x[1])},
                  "หน้าต่างที่ใช้นานสุด": [{"แอป": a, "ชื่อหน้าต่าง": t, "เวลา": h(m)}
                                          for (a, t), m in sorted(titles.items(), key=lambda x: -x[1])[:15]]})


# ------------------------------------------------------------------ Classroom, the rule book
@tool("classroom", "Classroom: วิชาที่ติดตาม งานที่มอบหมาย (กำหนดส่ง ส่งแล้วหรือยัง) และสื่อการเรียนใหม่ พร้อมลิงก์",
      {"days_ahead": Annotated[int, "งานที่ส่งภายในกี่วัน"]})
async def classroom(args: dict) -> dict:
    from app.features.classroom.tables import STATES, Course, CourseItem

    hi = _today_start() + timedelta(days=_days(args, "days_ahead", 14, 120) + 1)
    with session() as s:
        courses = {c.id: c for c in s.scalars(select(Course))}
        work = s.scalars(select(CourseItem).where(CourseItem.kind == "work", CourseItem.due_at.is_not(None),
                                                  CourseItem.due_at >= _today_start() - timedelta(days=7), CourseItem.due_at < hi)
                         .order_by(CourseItem.due_at).limit(MAX_ROWS)).all()
        new = s.scalars(select(CourseItem).where(CourseItem.kind == "material").order_by(CourseItem.synced_at.desc()).limit(10)).all()
        return _text({"วิชา": [{"วิชา": c.name, "สถานะ": STATES.get(c.state, c.state)} for c in courses.values()],
                      "งาน": [{"วิชา": courses[i.course_id].name if i.course_id in courses else "", "งาน": i.title,
                               "ส่ง": thai_datetime(i.due_at), "ส่งแล้ว": i.turned_in, "ลิงก์": i.link} for i in work],
                      "สื่อใหม่": [{"วิชา": courses[i.course_id].name if i.course_id in courses else "", "เรื่อง": i.title,
                                    "ไฟล์": [f.get("name") for f in i.files][:5], "ลิงก์": i.link} for i in new]})


@tool("rule_book", "สมุดกติกา: กติกาที่ผู้ใช้ตั้ง ที่เลขาเรียนรู้ และงานเสี่ยงสูงที่ต้องถามก่อน", {})
async def rule_book(args: dict) -> dict:
    with session() as s:
        return _text([{"ชนิด": r.kind, "กติกา": r.text, "เปิดอยู่": r.enabled, "สถานะ": r.status}
                      for r in s.scalars(select(Rule).where(Rule.status != "dismissed").order_by(Rule.kind, Rule.id))] or "ยังไม่มีกติกา")


TOOLS = [people_and_mail, waiting_replies, schedule, tasks, projects, ideas, time_use, classroom, rule_book]
