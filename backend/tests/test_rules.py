"""B5's rule book and rule checker: when a background plan may start by itself (the agreed order),
the 7 high-risk kinds, your rules and what reads them, and what the secretary learns from your
answers (never used before you accept it)."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api import rules as api
from app.core import actions, db, llm, settings
from app.core.db import session
from app.core.rules import book, learn, parse
from app.core.rules.check import check
from app.core.tables import Decision, Event, Rule

AT = datetime(2027, 3, 1, 3, 0, tzinfo=timezone.utc)  # Monday 10:00 in Bangkok, far from other tests' rows


@pytest.fixture(scope="module", autouse=True)
def database():
    db.migrate()
    book.seed()


# ------------------------------------------------------------------ the checker, in the agreed order
def test_a_plan_you_approved_starts_for_three_days_whatever_else():
    v = check(risks=["push หรือ deploy"], week_left=None, at=AT, approved_until=AT + timedelta(hours=1))
    assert v.go and v.why.startswith("คุณอนุมัติแผนนี้แล้ว")
    expired = check(risks=[], week_left=90, at=AT, approved_until=AT - timedelta(seconds=1))
    assert expired.go and expired.why.startswith("โควตาเหลือ")  # an old approval is just ignored


def test_no_quota_reading_means_every_plan_asks():
    v = check(risks=[], week_left=None, at=AT, standing="งานของ finance ทำเองได้")
    assert not v.go and v.why == "อ่านโควตาไม่ได้ ทุกแผนถามคุณก่อน"


def test_high_risk_asks_however_much_quota_is_left():
    v = check(risks=["โหลดของจากภายนอก", "ใช้เงิน"], week_left=99, at=AT, standing="งานของ finance ทำเองได้")
    assert not v.go and v.why == "งานเสี่ยงสูง: โหลดของจากภายนอก · ใช้เงิน"


def test_a_standing_rule_lets_a_low_risk_plan_start_below_the_line():
    v = check(risks=[], week_left=40, at=AT, standing="งานของ finance ทำเองได้")
    assert v.go and v.why == "ตามกติกาของคุณ: งานของ finance ทำเองได้"


def test_the_70_percent_line():
    assert check(risks=[], week_left=71, at=AT).go
    assert not check(risks=[], week_left=70, at=AT).go  # "เกิน 70%": exactly 70 asks
    assert check(risks=[], week_left=50, at=AT).why == "โควตาเหลือ 50% ไม่เกินเส้น 70%"
    assert not check(risks=[], week_left=75, at=AT, line=80).go
    off = check(risks=[], week_left=95, at=AT, auto=False)
    assert not off.go and off.why == "คุณปิดการทำเองไว้ ทุกแผนถามคุณก่อน"


# ------------------------------------------------------------------ the 7 high-risk kinds
@pytest.mark.parametrize("text,kind", [
    ("ติดตั้ง pandas ด้วย uv add pandas", "download"),
    ("ดาวน์โหลดชุดข้อมูล MNIST มาเทรน", "download"),
    ("git clone repo ตัวอย่างมาดู", "download"),
    ("ลองซ้ำหลายรอบจนกว่าค่า loss จะลด", "recheck"),
    ("retry the flaky test and compare", "recheck"),
    ("ไล่แก้ทุกไฟล์ทั้ง repo ให้ใช้ชื่อใหม่", "loop"),
    ("grid search hyperparameter ของโมเดล", "loop"),
    ("ลบไฟล์ผลลัพธ์เก่าทิ้ง", "delete"),
    ("git reset --hard แล้วเริ่มใหม่", "delete"),
    ("drop table runs แล้วสร้างใหม่", "delete"),
    ("git push ขึ้น GitHub", "push"),
    ("deploy เว็บขึ้น vercel", "push"),
    ("ส่งอีเมลสรุปให้อาจารย์", "message"),
    ("post to the class discord webhook", "message"),
    ("สมัครบริการ GPU รายเดือน", "money"),
    ("ซื้อโดเมนใหม่ $12", "money"),
])
def test_each_kind_is_spotted_in_a_plan(text, kind):
    assert kind in book.flags(text)


def test_what_a_plan_says_it_wont_do_is_not_a_risk():
    # the steps of the slugify plan at B5's check, which were flagged as a download and a push
    plan = ("เพิ่ม slugify(text: str) -> str ต่อท้ายใน textutil.py โดยใช้แค่ stdlib (re, unicodedata) ห้ามติดตั้งแพ็กเกจเพิ่ม\n"
            "รัน python -m unittest -v test_textutil ให้ผ่านทุกเทสต์\ncommit บน branch ของงานนี้ ห้าม push\n"
            "commit ทุกไฟล์บน branch ของงาน ไม่ push · ห้ามรันซ้ำวนไป · do not deploy · without installing anything")
    assert book.flags(plan) == []
    assert book.flags("ห้าม push แต่ต้อง pip install requests") == ["download"]  # a no covers its own words only
    assert book.flags("ไล่แก้ทุกไฟล์ทั้งโปรเจค") == ["loop"]


def test_ordinary_work_is_not_high_risk():
    plan = ("1. อ่าน PROGRESS.md หาขั้นถัดไป\n2. เขียนเทสต์ให้ฟังก์ชัน parse แล้วแก้บั๊กที่เจอ\n"
            "3. ลบ import ที่ไม่ใช้ · ปรับชื่อตัวแปร\n4. commit บน branch ของงาน")
    assert book.flags(plan) == []


def test_the_seven_are_in_the_book_once_and_fixed():
    book.seed()  # every start seeds again: still once each
    risks = book.risks()
    assert [r["key"] for r in risks[:7]] == [r.key for r in book.RISKS]
    assert [r["text"] for r in risks[:7]] == ["โหลดของจากภายนอก", "งานที่ตรวจซ้ำไปมา", "งานที่อาจวนจนเปลืองโทเคน",
                                              "ลบหรือเขียนทับไฟล์/ข้อมูล", "push หรือ deploy", "ส่งข้อความหาคนอื่น", "ใช้เงิน"]
    seven = risks[0]["id"]
    with pytest.raises(ValueError):
        book.edit(seven, enabled=False)
    with pytest.raises(ValueError):
        book.delete(seven)


def test_a_high_risk_kind_you_add_is_listed_after_the_seven_and_can_go():
    rule_id, _ = book.add("แก้ไฟล์ .env", [], kind="high_risk")
    risks = book.risks()
    assert risks[-1] == {"id": rule_id, "key": f"rule{rule_id}", "text": "แก้ไฟล์ .env", "fixed": False, "hint": ""}
    book.delete(rule_id)
    assert all(r["id"] != rule_id for r in book.risks())


# ------------------------------------------------------------------ your rules and who reads them
def test_a_note_reaches_the_parts_it_names_and_can_be_switched_off_and_undone():
    rule_id, _ = book.add("finance สำคัญกว่า research-lab", ["ask", "jobs"])
    assert "finance สำคัญกว่า research-lab" in book.notes_for("jobs")
    assert "- finance สำคัญกว่า research-lab" in book.prompt_block("ask")
    off = book.edit(rule_id, enabled=False)
    assert "finance สำคัญกว่า research-lab" not in book.notes_for("ask")
    asyncio.run(actions.undo(off["action_id"]))  # switched on again
    assert "finance สำคัญกว่า research-lab" in book.notes_for("ask")
    with pytest.raises(ValueError):
        book.edit(rule_id, used_by=["planner"])  # a note can only reach the parts that read text
    gone = book.delete(rule_id)
    assert "finance สำคัญกว่า research-lab" not in book.notes_for("ask")
    asyncio.run(actions.undo(gone))
    assert "finance สำคัญกว่า research-lab" in book.notes_for("ask")


def test_a_standing_rule_is_found_by_its_project():
    book.add("งานของ finance ทำเองได้", ["jobs"], effect={"type": "job_auto", "project": "finance"})
    assert book.standing_for("finance") == "งานของ finance ทำเองได้"
    assert book.standing_for("research-lab") == ""
    assert "งานของ finance ทำเองได้" not in book.notes_for("jobs")  # the code follows it; it isn't a note


def test_the_line_and_its_switch_are_recorded_and_undoable():
    assert (book.auto(), book.line()) == (True, 70.0)
    changed = book.set_jobs(auto_on=False, line_pct=80)
    assert (book.auto(), book.line()) == (False, 80.0)
    with pytest.raises(ValueError):
        book.set_jobs(line_pct=5)
    asyncio.run(actions.undo(changed))
    assert (book.auto(), book.line()) == (True, 70.0)


# ------------------------------------------------------------------ what the secretary learns
def appointment(day: datetime, answer: str) -> None:
    """An appointment request on `day` (10:00 Bangkok), answered a day before AT."""
    with session() as s:
        ev = Event(title="นัด", starts_at=day, ends_at=day + timedelta(hours=1), source="email", status="proposed")
        s.add(ev)
        s.flush()
        s.add(Decision(kind="appointment", title="นัด", detail={"event_id": ev.id}, status=answer,
                       answered_at=AT - timedelta(days=1)))


SATURDAYS = [datetime(2027, 2, 27, 3, 0, tzinfo=timezone.utc) - timedelta(days=7 * i) for i in range(3)]


def learned(key: str) -> Rule | None:
    with session() as s:
        r = s.scalar(select(Rule).where(Rule.key == key))
        if r is not None:
            s.expunge(r)
    return r


def test_three_saturdays_turned_down_become_a_suggestion_that_waits():
    for day in SATURDAYS[:2]:
        appointment(day, "rejected")
    assert learn.refresh(at=AT) == 0  # twice isn't a pattern yet
    appointment(SATURDAYS[2], "rejected")
    appointment(SATURDAYS[0] + timedelta(days=1), "approved")  # a Sunday you accepted
    assert learn.refresh(at=AT) == 1
    r = learned("learned.appointment_day.5")
    assert (r.text, r.evidence, r.status, r.effect) == ("คุณมักไม่รับนัดวันเสาร์", "ปฏิเสธ 3 ครั้งใน 4 สัปดาห์", "pending",
                                                        {"type": "appointment_days", "weekdays": [5]})
    assert book.appointment_note(SATURDAYS[0]) == ""  # not used before you say so


def test_accepting_it_marks_saturday_requests_and_it_can_be_undone():
    r = learned("learned.appointment_day.5")
    accepted = book.answer_learned(r.id, accept=True)
    assert book.appointment_note(SATURDAYS[0] + timedelta(days=7)) == "คุณมักไม่รับนัดวันเสาร์"
    assert book.appointment_note(SATURDAYS[0] + timedelta(days=2)) == ""  # a Monday
    with pytest.raises(ValueError):
        book.answer_learned(r.id, accept=False)  # answered already
    asyncio.run(actions.undo(accepted["action_id"]))
    assert learned("learned.appointment_day.5").status == "pending"


def test_turning_it_down_keeps_it_from_coming_back():
    r = learned("learned.appointment_day.5")
    book.answer_learned(r.id, accept=False)
    assert learn.refresh(at=AT) == 0
    assert learned("learned.appointment_day.5").status == "dismissed"


def test_a_suggestion_that_no_longer_holds_is_dropped_if_unanswered():
    mondays = [datetime(2027, 2, 22, 3, 0, tzinfo=timezone.utc) - timedelta(days=7 * i) for i in range(3)]
    for day in mondays:
        appointment(day, "rejected")
    assert learn.refresh(at=AT) == 1 and learned("learned.appointment_day.0").status == "pending"
    appointment(mondays[0] + timedelta(days=7), "approved")  # now you accepted a Monday
    assert learn.refresh(at=AT) == 0 and learned("learned.appointment_day.0") is None


# ------------------------------------------------------------------ a rule typed as a sentence
CTX = parse.Context(projects={"finance": True, "research-lab": False}, day_start="09:00", day_end="22:00",
                    keywords=("ด่วน", "สอบ"))


def test_the_models_answer_is_checked_against_what_the_secretary_can_do():
    p = parse.proposal("ไม่นัดวันอาทิตย์", {"type": "appointment_days", "text": "ไม่รับนัดวันอาทิตย์", "weekdays": [6]}, CTX)
    assert (p.ok, p.used_by, p.effect) == (True, ["mail"], {"type": "appointment_days", "weekdays": [6]})
    assert not parse.proposal("x", {"type": "appointment_days", "weekdays": [9]}, CTX).ok
    hours = parse.proposal("เริ่มงาน 8 โมงครึ่ง", {"type": "schedule_hours", "day_start": "8:30"}, CTX)
    assert hours.change == {"day_start": "08:30", "day_end": "22:00"} and "(ตอนนี้ 09:00–22:00)" in hours.why
    assert not parse.proposal("x", {"type": "schedule_hours", "day_start": "23:00"}, CTX).ok  # after the end
    assert not parse.proposal("x", {"type": "mail_keywords", "add": ["สอบ"]}, CTX).ok  # already there
    assert parse.proposal("x", {"type": "mail_keywords", "add": ["ทุน", "สอบ"]}, CTX).change == {"add": ["ทุน"]}
    research = parse.proposal("x", {"type": "job_auto", "project": "Research-Lab"}, CTX)
    assert research.effect == {"type": "job_auto", "project": "research-lab"} and "ต้องเปิด" in research.why
    assert not parse.proposal("x", {"type": "job_auto", "project": "nope"}, CTX).ok
    note = parse.proposal("ตอบสั้นๆ", {"type": "note", "text": "ตอบสั้นๆ", "used_by": ["planner"]}, CTX)
    assert (note.kind, note.used_by) == ("note", ["ask", "jobs"])  # only the parts that read text
    assert not parse.proposal("x", None, CTX).ok and not parse.proposal("x", {"type": "magic"}, CTX).ok
    said = parse.proposal("ส่งเมลแทนฉัน", {"type": "unsupported", "why": "เลขาส่งข้อความหาคนอื่นไม่ได้"}, CTX)
    assert (said.ok, said.why) == (False, "เลขาส่งข้อความหาคนอื่นไม่ได้")


def test_parse_reads_a_fenced_answer(monkeypatch):
    async def fake_run(task, prompt, **kw):
        assert task == "rule" and "[กติกา] ไม่นัดวันอาทิตย์" in prompt and "finance" in prompt
        return llm.Reply(text='```json\n{"type": "appointment_days", "text": "ไม่รับนัดวันอาทิตย์", "weekdays": [6]}\n```',
                         model="claude-sonnet-5-5", effort="low", tokens_in=300, tokens_out=40)
    monkeypatch.setattr(llm, "run", fake_run)
    p, tokens = asyncio.run(parse.parse("ไม่นัดวันอาทิตย์", CTX))
    assert (p.kind, p.text, tokens) == ("appointment_days", "ไม่รับนัดวันอาทิตย์", 340)


def test_a_rule_that_is_really_a_setting_changes_the_setting_and_can_be_undone():
    from app.features.schedule import sync
    out = api.add_rule(api.RuleIn(kind="schedule_hours", text="เริ่มงาน 8 โมงครึ่ง", change={"day_start": "08:30"}))
    assert sync.rules_dict()["day_start"] == "08:30" and "08:30–22:00" in out["why"]
    asyncio.run(actions.undo(out["action_id"]))
    assert sync.rules_dict()["day_start"] == "09:00"
    with pytest.raises(HTTPException):
        api.add_rule(api.RuleIn(kind="schedule_hours", text="x", change={"day_start": "23:30"}))


def test_the_page_has_everything_in_one_place():
    page = api.rules_page()
    assert [r["key"] for r in page["system"]] == ["schedule", "mail", "jobs", "never"]
    assert page["system"][2]["text"] == "งานเบื้องหลังทำเองได้เมื่อโควตาเหลือเกิน 70% และไม่ใช่งานเสี่ยงสูง"
    assert page["counts"]["risks"] == 7 and len(page["risks"]) == 7
    assert any(r["text"] == "งานของ finance ทำเองได้" for r in page["yours"])
    assert settings.get(book.AUTO_KEY, True) is True
