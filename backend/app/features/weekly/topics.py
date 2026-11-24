"""The weekly review's topics (D4, P3, B7): one each for what there is to decide this week, built by
rules from what the other parts know. Nothing here changes anything; review.py stores the topics
as decisions and answers them.

A topic says, as the mockup asks for (D4 ④): why (`why`), what the secretary would do (`what`),
how (`how`), and how far it goes (`extent`: time, tokens, what it won't touch). Its buttons are
`acts`; `default` is what "รับทุกเรื่องตามที่เสนอ" (accept everything as proposed) does with it (None: you choose yourself).

- people: the weekly people proposals (mail/review.py, 1.4);
- schedule: your focus hours first, and a weekday's part that keeps being missed kept free (both
  rules the user chose at the B7 plan: "2.ค");
- time: projects that got well under their plan this week: book the missing time next week;
- project: a stalled project that matters or has a due date: book 3 blocks for you, and, on its
  own button only, a background job that summarises where it's stuck ("3.ก": one press for
  everything never spends tokens);
- ideas aren't built here: the idea groups waiting for you (B6) are shown with their own buttons.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.db import session
from app.core.rules import book
from app.core.tables import Block, Task
from app.core.timefmt import local, thai_date
from app.features.jobs.base import branch_name
from app.features.mail import review as people_review
from app.features.mail.tables import LEVELS
from app.features.time import followed, insights

FOCUS_LOOKBACK = timedelta(days=28)
SHORT_SHARE = 0.7  # a project under this share of its plan this week is a topic
BOOK_CAP = 240  # minutes booked for one project's missing time
STALLED = 2  # at most this many stalled projects a week
PROJECT_MINUTES, PROJECT_BLOCK = 360, 120  # what a stalled project gets: 3 blocks of 2 hours
SUMMARY_NOTE = ("อ่าน PROGRESS.md และงานที่ค้างของโปรเจคนี้ แล้วเขียนสรุปหน้าเดียวว่าค้างตรงไหน ต้องทำอะไรต่อ "
                "และอะไรที่ยังไม่ชัด ลงไฟล์ SUMMARY-<วันนี้>.md · ห้ามแก้โค้ดหรือไฟล์อื่น")


def hours(minutes: float) -> str:
    h = minutes / 60
    return f"{h:.0f}" if abs(h - round(h)) < 0.05 else f"{h:.1f}"


def people(at: datetime) -> dict | None:
    items = people_review.proposals(at)[:5]  # a select menu holds 25 options: 5 people x 5 choices
    if not items:
        return None
    why = "\n".join(f"{i['name']} ({LEVELS[i['level']]}): {i['why']}" + (f"\n> โน้ตที่คุณจดไว้: “{i['note']}”" if i["note"] else "")
                    for i in items)
    return {"topic": "people", "label": "คน", "title": f"ปรับทะเบียน {len(items)} คน", "why": why,
            "what": people_what(items),
            "how": "แก้ทะเบียนคนแล้วจดลงบันทึกสิ่งที่เลขาทำ · โน้ตเดิมลบทิ้งเมื่อตัดสิน · ต่ออายุแล้วจดโน้ตใหม่ได้ที่หน้าคนและอีเมล",
            "extent": "มีผลรอบอ่านอีเมลถัดไป · ย้อนกลับได้ทุกคน · เลือกรายคนได้ในเมนูด้านล่าง หรือที่หน้าคนและอีเมล",
            "acts": [["approve", f"รับทั้ง {len(items)}"], ["reject", "ไม่เอา"]], "default": "approve",
            "proposal": {"items": items}}


def people_what(items: list[dict]) -> str:
    return " · ".join(f"{i['name']} → {dict(i['choices'])[i['choice']]}" for i in items)


def schedule(at: datetime) -> dict | None:
    avoid = [p for p in followed.patterns(at) if not p["avoided"]][:2]
    best = insights.focus(at - FOCUS_LOOKBACK, at)
    have = book.focus_window()
    focus = best if best and (not have or (have["from"], have["to"]) != (best["from"], best["to"])) else None
    if not (avoid or focus):
        return None
    rules, why, moves = [], [], 0
    if focus:
        rules.append(f"“วางบล็อกงานช่วงโฟกัส {focus['from']}–{focus['to']} ก่อน”")
        why.append(f"ช่วงที่คุณโฟกัสดีสุดคือ {focus['from']}–{focus['to']} (สลับแอป {focus['rate']:.0f} ครั้งต่อชั่วโมง)")
    for p in avoid:
        lo, hi = followed.PARTS[p["part"]]
        rules.append(f"“ไม่วางบล็อกงาน{p['part']}{followed.WEEKDAYS[p['weekday']]}”")
        why.append(p["title"])
        moves += sum(1 for b in upcoming(at) if local(b.starts_at).weekday() == p["weekday"]
                     and lo <= local(b.starts_at).strftime("%H:%M") < hi)
    title = (f"วางงานช่วงโฟกัส {focus['from']}–{focus['to']}" if focus else "") + (" · " if focus and avoid else "") + \
            (" · ".join(f"เว้น{p['part']}{followed.WEEKDAYS[p['weekday']]}" for p in avoid))
    how = "วางตารางใหม่ทันทีที่รับ · " + (f"บล็อกในช่วงที่เว้น {moves} บล็อกจะย้าย" if moves else "ไม่มีบล็อกที่ต้องย้ายตอนนี้")
    if focus:
        how += " · บล็อกใหม่ลงช่วงโฟกัสก่อนในแต่ละวัน (ยกเว้นงานตอบอีเมล)"
    return {"topic": "schedule", "label": "ตาราง", "title": title, "why": " · ".join(why),
            "what": "เพิ่มกติกา " + " และ ".join(rules) + " แล้ววางตารางใหม่",
            "how": how,
            "extent": "เฉพาะบล็อกงานของคุณ ไม่แตะนัดและเวลาเรียน · ปิดหรือลบกติกาได้ในสมุดกติกา · ย้อนกลับได้",
            "acts": [["approve", "รับ"], ["reject", "ไม่เอา"]], "default": "approve",
            "proposal": {"avoid": [{"weekday": p["weekday"], "part": p["part"]} for p in avoid],
                         "focus": {"from": focus["from"], "to": focus["to"]} if focus else None}}


def upcoming(at: datetime, days: int = 14) -> list[Block]:
    with session() as s:
        rows = s.scalars(select(Block).where(Block.status == "planned", Block.starts_at >= at,
                                             Block.starts_at < at + timedelta(days=days))).all()
        s.expunge_all()
    return list(rows)


def time_use(at: datetime) -> dict | None:
    start, end, _ = insights.span("week", at)
    rs = insights.rows(start, min(end, at))
    if not rs:
        return None
    per = insights.projects(start, min(end, at), rs)
    short = [p for p in per if p["planned"] >= 120 and p["minutes"] < SHORT_SHARE * p["planned"]][:3]
    if not short:
        return None
    book_for = [{"name": p["name"], "minutes": p["minutes"], "planned": p["planned"],
                 "book": min(BOOK_CAP, int(math.ceil((p["planned"] - p["minutes"]) / 30) * 30))} for p in short]
    first = short[0]
    pct = 100 - round(100 * first["minutes"] / first["planned"])
    title = (f"{first['name']} ได้เวลาน้อยกว่าแผน {pct}%" if len(short) == 1 else f"{len(short)} โปรเจคได้เวลาน้อยกว่าแผน")
    context = [f"{p['name']} {hours(p['minutes'])} จาก {hours(p['planned'])} ชม." for p in per if p["planned"]][:4]
    late = next((b["title"] for b in insights.behaviours("week", rs, per) if b["icon"] == "eye"), "")
    return {"topic": "time", "label": "การใช้เวลา", "title": title, "why": " · ".join(context + ([late] if late else [])),
            "what": "เพิ่มเวลา " + " · ".join(b["name"] for b in book_for) + " สัปดาห์หน้าให้ครบแผน",
            "how": " · ".join(f"จองงาน {b['name']} {hours(b['book'])} ชม." for b in book_for)
                   + " ไม่มีกำหนดส่ง ตัววางตารางหาเวลาว่างตั้งแต่วันจันทร์",
            "extent": " · ".join(f"{b['name']} +{hours(b['book'])} ชม." for b in book_for) + " · ใช้เฉพาะเวลาว่าง ไม่ทับนัด · ย้อนกลับได้",
            "acts": [["approve", "รับ"], ["reject", "ไม่เอา"]], "default": "approve",
            "proposal": {"projects": book_for, "from": end.isoformat()}}  # the Monday after the week: answered later, it's past


def projects(at: datetime) -> list[dict]:
    from app.features.jobs import queue
    from app.features.projects import advice
    from app.features.projects.tables import Project

    out = []
    for a in [a for a in advice.advice(at) if a.kind == "stale"][:STALLED]:
        with session() as s:
            p = s.get(Project, a.project_id)
            blocked = queue.blocked(p)
            booked = s.scalar(select(Task.id).where(Task.status == "open", Task.project == a.project,
                                                    Task.source == "project", Task.title.like("%(ทบทวนรายสัปดาห์)%")))
        if booked:
            continue  # the time from an earlier review still waits in the schedule
        due = f" · ส่ง {thai_date(a.due)}" if a.due else ""
        acts = ([["both", "รับทั้งสองอย่าง"]] if not blocked else []) + [["book", "แค่จองเวลา"], ["reject", "ไม่เอา"]]
        out.append({
            "topic": "project", "label": "โปรเจค", "title": a.title + due, "tone": "warn",
            "why": a.detail or f"ขั้นถัดไป: {a.next}",
            "what": "จองเวลาให้คุณ 3 บล็อก" + ("" if blocked else " และให้เลขาสรุปสิ่งที่ค้างไว้ (เฉพาะปุ่ม “รับทั้งสองอย่าง”)"),
            "how": f"บล็อกละ {PROJECT_BLOCK // 60} ชม. รวม {PROJECT_MINUTES // 60} ชม." + (" ก่อนกำหนดส่ง" if a.due else "")
                   + ("" if blocked else f" · งานเบื้องหลังอ่าน PROGRESS.md แล้วเขียนสรุปหน้าเดียวบน branch {branch_name(a.project)} ไม่แก้โค้ด"),
            "extent": f"เวลาคุณ {PROJECT_MINUTES // 60} ชม." + (
                f" · ให้เลขาสรุปไม่ได้: {blocked}" if blocked else
                " · งานสรุป: Opus วางแผนแล้วผ่านกฎงานเบื้องหลังเหมือนเดิม ใช้โควตา Claude · “รับทุกเรื่อง” จองเวลาอย่างเดียว"),
            "acts": acts, "default": "book",
            "proposal": {"project_id": a.project_id, "name": a.project, "next": a.next,
                         "due": a.due.isoformat() if a.due else None}})
    return out


def ideas() -> list[int]:
    """The idea groups waiting for your answer (B6): their ids."""
    from app.features.ideas.tables import IdeaGroup

    with session() as s:
        return list(s.scalars(select(IdeaGroup.id).where(IdeaGroup.status == "asked").order_by(IdeaGroup.updated_at.desc()).limit(3)))


def build(at: datetime) -> tuple[list[dict], list[int]]:
    """Everything to decide this week: (topics, idea group ids)."""
    topics = [t for t in (people(at), schedule(at), time_use(at)) if t] + projects(at)
    return topics, ideas()
