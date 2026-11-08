"""B7's ถามเลขาได้ทุกส่วน: the chat's read-only tools find the right rows, with links, and nothing
they shouldn't (called directly: no model here)."""

import asyncio
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.core import db
from app.core.config import get_config
from app.core.db import now, session
from app.core.tables import Block, Task
from app.features import ask, ask_tools
from app.features.ideas.tables import Idea
from app.features.mail.tables import Email, Person, PersonAddress
from app.features.time.tables import Activity


@pytest.fixture(scope="module", autouse=True)
def _db():
    db.migrate()


def call(tool, **args):
    out = asyncio.run(tool.handler(args))
    text = out["content"][0]["text"]
    try:
        return json.loads(text)
    except ValueError:
        return text


@pytest.fixture
def vipa():
    start = datetime.combine(now().astimezone(get_config().tz).date(), datetime.min.time(), get_config().tz)
    with session() as s:
        p = Person(name="at-อ.วิภา", level="important", note="ที่ปรึกษาโปรเจคจบ")
        s.add(p)
        s.flush()
        s.add(PersonAddress(address="at-vipa@uni.ac.th", person_id=p.id))
        for i, (subject, summary, days) in enumerate([("ร่างบทที่ 3", "ขอร่างบทที่ 3 ก่อนศุกร์", 0),
                                                      ("นัดคุยความคืบหน้า", "นัดศุกร์ 10:00", 1),
                                                      ("ลิงก์ paper", "ส่ง paper time-series 2 อัน", 20)]):
            s.add(Email(id=f"at-m{i}", account="ku", thread_id=f"at-t{i}", person_id=p.id, sender="at-vipa@uni.ac.th",
                        sender_name="อ.วิภา", subject=subject, summary=summary, stage="summarized",
                        sent_at=start + timedelta(hours=9) - timedelta(days=days)))
        pid = p.id
    yield pid
    with session() as s:
        s.execute(delete(Email).where(Email.id.like("at-%")))
        s.execute(delete(PersonAddress).where(PersonAddress.person_id == pid))
        s.execute(delete(Person).where(Person.id == pid))


def test_what_someone_sent_this_week_comes_with_gmail_links(vipa):
    got = call(ask_tools.people_and_mail, name="วิภา", days=2)
    assert [p["ชื่อ"] for p in got["คน"]] == ["at-อ.วิภา"] and got["คน"][0]["โน้ต"] == "ที่ปรึกษาโปรเจคจบ"
    assert [m["หัวข้อ"] for m in got["อีเมล"]] == ["ร่างบทที่ 3", "นัดคุยความคืบหน้า"]  # the 20-day-old one is out of range
    assert all(m["ลิงก์"].startswith("https://mail.google.com/mail/") and m["ลิงก์"].endswith(f"#all/at-m{i}")
               for i, m in enumerate(got["อีเมล"]))
    assert call(ask_tools.people_and_mail, name="at-vipa@uni", days=30)["อีเมล"][-1]["หัวข้อ"] == "ลิงก์ paper"  # by address
    assert call(ask_tools.people_and_mail, name="", query="time-series", days=30)["อีเมล"][0]["หัวข้อ"] == "ลิงก์ paper"
    assert call(ask_tools.people_and_mail, name="ไม่มีคนนี้", days=7) == "ไม่พบคนชื่อหรืออีเมล “ไม่มีคนนี้” ในทะเบียน"


def test_the_schedule_shows_appointments_blocks_with_outcomes_and_due_dates():
    at = now()
    with session() as s:
        t = Task(title="at-รายงาน datacom", source="you", due_at=at + timedelta(days=2), source_ref="ask-tools")
        s.add(t)
        s.flush()
        s.add(Block(task_id=t.id, starts_at=at - timedelta(hours=3), ends_at=at - timedelta(hours=2), status="planned",
                    outcome="missed", worked_minutes=10, instead="my_secretary"))
        tid = t.id
    try:
        got = call(ask_tools.schedule, days_back=1, days_ahead=3)
        block = next(b for b in got["บล็อกงาน"] if b["งาน"] == "at-รายงาน datacom")
        assert block["ผล"] == "หลุด (ทำ 10 นาที)" and block["ทำแทน"] == "my_secretary"
        assert any(d["งาน"] == "at-รายงาน datacom" for d in got["กำหนดส่ง"])
    finally:
        with session() as s:
            s.execute(delete(Block).where(Block.task_id == tid))
            s.execute(delete(Task).where(Task.id == tid))


def test_time_use_gives_totals_and_window_titles_and_ideas_are_found_by_tag():
    at = now()
    with session() as s:
        s.execute(delete(Activity))
        s.add(Activity(start=at - timedelta(minutes=90), end=at - timedelta(minutes=30), app="code",
                       title="ask.py - my_secretary - VS Code", category="code", project="my_secretary"))
        s.add(Idea(text="at-ให้เลขาพูดสรุปเช้า", source="key", tags=["เสียง"], tagged="you"))
    try:
        got = call(ask_tools.time_use, days=0)
        assert got["ต่อโปรเจค"] == {"my_secretary": "1.0 ชม."} and got["หน้าต่างที่ใช้นานสุด"][0]["ชื่อหน้าต่าง"].startswith("ask.py")
        assert call(ask_tools.time_use, days=0, project="finance") == "ไม่มีเวลาที่บันทึกในช่วงนี้ (ActivityWatch อาจยังไม่ได้เปิด)"
        found = call(ask_tools.ideas, query="#เสียง")["ไอเดีย"]
        assert [i["ไอเดีย"] for i in found if i["ไอเดีย"].startswith("at-")] == ["at-ให้เลขาพูดสรุปเช้า"]
    finally:
        with session() as s:
            s.execute(delete(Activity))
            s.execute(delete(Idea).where(Idea.text.like("at-%")))


def test_every_tool_is_given_to_the_chat_with_a_source_name():
    names = {t.name for t in ask.TOOLS}
    assert set(ask_tools.SOURCE_NAMES) <= names and all(n in ask.SOURCE_NAMES for n in names)
    assert len(names) == len(ask.TOOLS)  # no tool twice
    with session() as s:
        assert s.scalar(select(Email.id).where(Email.id.like("at-%"))) is None  # nothing left behind
