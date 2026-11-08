"""B4's briefs: what the morning brief (D2) and the evening review (D3) say, and when they go out.

The data sits on its own days in 2027 (Wed 10 Mar for the morning, Thu 11 Mar for the evening),
so other tests' rows can't fall into the windows. Discord isn't configured in tests: nothing
is sent, the briefs are only made and stored.
"""

import asyncio
import itertools
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.core import db, settings
from app.core.db import session
from app.core.tables import Block, Event, LLMUsage, Task
from app.features.briefs import day, morning
from app.features.briefs.tables import Brief
from app.features.mail import rounds
from app.features.mail.tables import Email, Person

BKK = ZoneInfo("Asia/Bangkok")
_ids = itertools.count(1)


def at(d: int, h: int, m: int = 0) -> datetime:
    return datetime(2027, 3, d, h, m, tzinfo=BKK)


@pytest.fixture(scope="module", autouse=True)
def database():
    db.migrate()


def mail(who: Person | None, level: str, stage: str, sent: datetime, summary: str = "", flagged: str = "",
         sender: str = "") -> str:
    eid = f"brief-{next(_ids)}"
    with session() as s:
        s.add(Email(id=eid, account="gmail", thread_id=eid, person_id=who.id if who else None,
                    sender=sender or (f"{who.name}@example.com" if who else "x@example.com"),
                    sender_name=sender or (who.name if who else ""), subject=f"เรื่อง {eid}", sent_at=sent,
                    level=level, stage=stage, summary=summary, flagged=flagged))
    return eid


def person(name: str, level: str) -> Person:
    with session() as s:
        p = Person(name=name, level=level)
        s.add(p)
        s.flush()
        s.expunge(p)
    return p


@pytest.fixture(scope="module")
def night():
    """The night before Wed 10 Mar 07:00, as the mail rounds and the schedule left it."""
    vipa, mind = person("อ.วิภา", "important"), person("มายด์", "interested")
    mail(vipa, "important", "read", at(9, 20), "ขอร่างบทที่ 3 ก่อนวันศุกร์")
    mail(vipa, "important", "read", at(10, 6, 30), "ส่งตัวอย่างสไลด์มาให้ดู")
    mail(None, "ignored", "read", at(10, 1), "เลื่อนสอบกลางภาคเป็นวันจันทร์", flagged="keyword:สอบ", sender="ฝ่ายทะเบียน")
    asked = mail(mind, "interested", "summarized", at(9, 15), "ชวนประชุมกลุ่ม ศ. 14:00")
    mail(mind, "interested", "summarized", at(9, 16), "ชวนประชุมกลุ่ม ศ. 14:00")
    for _ in range(3):
        mail(None, "ignored", "skimmed", at(9, 22), sender="Shop")
    mail(None, "ignored", "skimmed", at(9, 23), sender="News")
    mail(mind, "interested", "seen", at(10, 5))  # after the 00:00 round: waits for 12:00
    mail(vipa, "important", "old", at(9, 21))  # the first run's backlog: never in a brief
    with session() as s:
        s.add(Event(title="ประชุมกลุ่ม", starts_at=at(12, 14), ends_at=at(12, 15), source="email", source_ref=asked,
                    status="proposed"))
        s.add(Event(title="นัด พี่ต้น", starts_at=at(10, 14), ends_at=at(10, 15), location="ออนไลน์", source="calendar",
                    status="placed"))
        work = Task(title="datacom", source="you")
        s.add(work)
        s.flush()
        s.add(Block(task_id=work.id, starts_at=at(10, 9), ends_at=at(10, 10)))
        s.add(Task(title="ส่งการบ้าน", source="classroom", due_at=at(10, 17)))
        s.add(LLMUsage(at=at(10, 0, 5), task="mail", model="Opus", tokens_in=15000, tokens_out=3000))
    asyncio.run(morning.remember_night(rounds.RoundResult(big=True, noteworthy=[("Medium", "Time series 101", "ตรงเรื่องที่สนใจ")])))


# ------------------------------------------------------------------ the morning brief
def test_the_morning_brief_says_what_the_night_brought(night):
    # the 00:00 round's notes were kept at 00:10 that night
    settings.put(day.NIGHT_KEY, {**settings.get(day.NIGHT_KEY), "at": at(10, 0, 10).isoformat()})
    b = morning.compose(at(10, 7))
    waiting = len(day.waiting())
    assert b["title"] == "พุธ 10 มี.ค. · วันนี้มี 1 นัด"
    assert b["headline"] == f"เรื่องสำคัญ 3 · นัดวันนี้ 1 · รอคุณตัดสิน {waiting} · งานส่งวันนี้ 1"
    fields = dict(b["fields"])
    assert "อ.วิภา: ส่งตัวอย่างสไลด์มาให้ดู" in fields["เรื่องสำคัญ"]
    assert "ฝ่ายทะเบียน: เลื่อนสอบกลางภาคเป็นวันจันทร์" in fields["เรื่องสำคัญ"]  # a keyword counts as important
    who = fields["ใครส่งอะไรมา"]
    assert "**สำคัญ** · อ.วิภา 2 ฉบับ · ฝ่ายทะเบียน 1 ฉบับ" in who  # the keyword one counts with the important
    assert "มายด์: ชวนประชุมกลุ่ม ศ. 14:00 (นัดรอคุณรับ)" in who  # and what the secretary did about it
    assert "**ไม่สนใจ** · 4 ฉบับ: Shop 3 · News 1" in who
    assert "น่าดู: Medium: Time series 101" in who  # the 00:00 round's pick, which its card used to carry
    assert "ยังไม่อ่าน 1 ฉบับ · รอรอบ 12:00" in who
    assert fields["นัดวันนี้"] == "09:00 บล็อก datacom · 14:00 นัด พี่ต้น (ออนไลน์) · ส่ง 17:00 ส่งการบ้าน"
    assert b["footer"] == "อ่าน 9 ฉบับตั้งแต่สรุปครั้งก่อน · Opus 18k โทเคน · สรุปนี้ไม่ใช้โทเคน"


def test_a_day_gets_one_morning_brief(night):
    first = morning.make(at(10, 7))
    assert first is not None
    assert morning.make(at(10, 8)) is None  # caught up later, or restarted: not a second one


def test_the_next_brief_starts_where_the_last_one_ended(night):
    morning.make(at(10, 7))
    assert day.since_last("morning", at(11, 7)) == at(10, 7)
    mail(None, "important", "read", at(10, 6, 30), "ก่อนสรุปครั้งก่อน", sender="ก่อน")
    assert all(m.who != "ก่อน" for m in day.important_mail(day.since_last("morning", at(11, 7)), at(11, 7)))


@pytest.mark.parametrize("hm,ok", [((6, 59), False), ((7, 0), True), ((11, 59), True), ((12, 0), False), ((20, 0), False)])
def test_the_morning_brief_goes_out_from_seven_until_noon(hm, ok):
    assert morning.open_now(datetime.combine(at(10, 0).date(), time(*hm), BKK)) is ok


def test_only_the_big_rounds_findings_are_kept_for_the_morning():
    settings.put(day.NIGHT_KEY, {})
    asyncio.run(morning.remember_night(rounds.RoundResult(big=False, noteworthy=[("x", "y", "z")])))
    assert settings.get(day.NIGHT_KEY) == {}
    asyncio.run(morning.remember_night(rounds.RoundResult(big=True, noteworthy=[("a", "b", "c")], skimmed=4)))
    assert settings.get(day.NIGHT_KEY)["noteworthy"] == [["a", "b", "c"]]


def test_mail_from_the_first_runs_backlog_and_your_own_never_counts(night):
    with session() as s:
        s.add(Email(id="brief-mine", account="gmail", thread_id="t", sender="me@example.com", sent_at=at(10, 6),
                    level="important", stage="read", from_me=True))
    names = [m.who for m in day.important_mail(at(9, 7), at(10, 7))]
    assert names.count("อ.วิภา") == 2  # the "old" one isn't there
    assert "me@example.com" not in names
    # the side menu's number is the today page's list: since midnight, the same rules
    assert day.important_today(at(10, 8)) == len(day.important_mail(day.day_start(at(10, 0).date()), at(10, 8))) > 0


def test_an_older_nights_picks_are_not_repeated(night):
    # what the 00:00 round picked five nights ago was in that morning's brief, not this one's
    settings.put(day.NIGHT_KEY, {"at": at(5, 0, 10).isoformat(), "noteworthy": [["Old", "เก่าแล้ว", "เคยบอกแล้ว"]]})
    who = dict(morning.compose(at(10, 7))["fields"]).get("ใครส่งอะไรมา", "")
    assert "น่าดู" not in who


# ------------------------------------------------------------------ the evening review
@pytest.fixture(scope="module")
def thursday():
    """Thu 11 Mar: two blocks, one task closed during the day; Fri 12 Mar: a class and a block."""
    from app.core.tables import Action
    with session() as s:
        work = Task(title="รายงาน OS", source="you")
        s.add(work)
        s.flush()
        s.add_all([Block(task_id=work.id, starts_at=at(11, 9), ends_at=at(11, 11)),
                   Block(task_id=work.id, starts_at=at(11, 14), ends_at=at(11, 15, 30)),
                   Block(task_id=work.id, starts_at=at(12, 13), ends_at=at(12, 14))])
        s.add(Event(title="เรียน OS", starts_at=at(12, 9), ends_at=at(12, 12), location="ห้อง 204", source="calendar",
                    status="placed"))
        s.add(Action(at=at(11, 16), kind="task.done", summary="ทำเสร็จแล้ว: สไลด์ datacom"))
        s.add(Action(at=at(11, 17), kind="task.done", summary="ทำเสร็จแล้ว: กดผิด", undone_at=at(11, 17, 1)))


def test_the_evening_review_reports_the_day_and_tomorrow(thursday, monkeypatch):
    from app.features.briefs import evening
    monkeypatch.setattr(evening, "tonight", lambda at: "00:00 รอบอ่านอีเมล (ใหญ่)")
    b = evening.compose(at(11, 21))
    assert b["title"] == "วันนี้มีบล็อกงาน 2 บล็อก รวม 3 ชม. 30 นาที"
    assert b["headline"] == "ปิดงาน 1 งาน · พรุ่งนี้ 1 นัด · บล็อก 1"
    fields = dict(b["fields"])
    assert fields["บล็อกวันนี้"] == "09:00 บล็อก รายงาน OS · 14:00 บล็อก รายงาน OS"
    assert fields["ปิดงานวันนี้"] == "สไลด์ datacom"  # an undone one isn't counted
    assert fields["พรุ่งนี้"] == "09:00 เรียน OS (ห้อง 204) · 13:00 บล็อก รายงาน OS"
    assert "ยังไม่ได้เปิดบันทึกกิจกรรม" in b["footer"]  # B6: nothing recorded, so it can't say how the plan went


def test_tonight_lists_the_rounds_that_are_on_and_says_how_often_the_frequent_ones_run(monkeypatch):
    from app.core import clock
    from app.features.briefs import evening
    on = {"mail_big", "backup", "morning", "watch"}
    for rid in ("mail_big", "backup", "morning", "watch", "schedule"):
        monkeypatch.setattr(clock.ROUNDS[rid], "handler", lambda: None)
    monkeypatch.setattr(clock, "enabled", lambda rid: rid in on)
    text = evening.tonight(at(11, 21))
    assert text.splitlines()[0] == "00:00 รอบอ่านอีเมล (ใหญ่) · 03:30 สำรองฐานข้อมูล (เก็บ 14 วัน) · 07:00 สรุปเช้า"
    assert "รอบประจำ: เฝ้าคนสำคัญและคีย์เวิร์ด (ทุก 5 นาที)" in text
    assert "ซิงก์ตาราง" not in text  # it would run every 15 minutes tonight, but it's switched off: not promised


@pytest.mark.parametrize("hm,ok", [((20, 59), False), ((21, 0), True), ((23, 59), True), ((0, 30), False), ((7, 0), False)])
def test_the_evening_review_goes_out_from_nine_until_midnight(hm, ok):
    from app.features.briefs import evening
    assert evening.open_now(datetime.combine(at(11, 0).date(), time(*hm), BKK)) is ok


def test_a_day_gets_one_evening_review(thursday, monkeypatch):
    from app.features.briefs import evening
    monkeypatch.setattr(evening, "tonight", lambda at: "")
    assert evening.make(at(11, 21)) is not None
    assert evening.make(at(11, 22)) is None


# ------------------------------------------------------------------ decisions in one place
def test_a_waiting_appointment_says_what_else_is_at_that_time():
    from app.api import settings as settings_api
    from app.core.tables import Decision
    with session() as s:
        busy = Event(title="เรียน DSP", starts_at=at(15, 13), ends_at=at(15, 16), source="calendar", status="placed")
        clash = Event(title="ประชุมโปรเจค", starts_at=at(15, 14), ends_at=at(15, 15), source="email", status="proposed")
        free = Event(title="คุยงาน", starts_at=at(15, 17), ends_at=at(15, 18), source="email", status="proposed")
        s.add_all([busy, clash, free])
        s.flush()
        a = Decision(kind="appointment", title="ประชุมโปรเจค", detail={"event_id": clash.id})
        b = Decision(kind="appointment", title="คุยงาน", detail={"event_id": free.id})
        s.add_all([a, b])
        s.flush()
        ids = (a.id, b.id)
    shown = {d["id"]: d for d in settings_api.decisions()["items"]}
    assert shown[ids[0]]["clash"] == "เรียน DSP"
    assert shown[ids[1]]["clash"] == ""  # nothing else then: "ไม่ชนนัดอื่น"


def test_answering_on_the_web_without_discord_leaves_the_card_alone():
    from app.core.tables import Decision
    from app.features import decisions
    with session() as s:
        d = Decision(kind="course", title="OS", status="approved")
        s.add(d)
        s.flush()
        did = d.id
    asyncio.run(decisions.settle_card(did))  # the bot isn't connected in tests: nothing to do, nothing raised


# ------------------------------------------------------------------ the today page
def test_the_today_page_repeats_the_morning_briefs_numbers(night, monkeypatch):
    from app.api import today as api
    monkeypatch.setattr(api, "now", lambda: at(10, 9))
    monkeypatch.setattr(day, "now", lambda: at(10, 9))
    morning.make(at(10, 7))  # (or the one an earlier test made: one per day)
    page = api.today_page()
    with session() as s:
        b = s.scalar(select(Brief).where(Brief.kind == "morning", Brief.day == "2027-03-10"))
    assert page["headline"] == b.headline and page["brief"]["fields"] == b.fields  # B4's check: the numbers match
    assert page["greeting"] == "สวัสดีตอนเช้าครับ"
    assert [i["kind"] for i in page["plan"]] == ["block", "meet", "dead"]
    assert all(m["who"] for m in page["important"])


def test_a_stored_brief_waits_for_the_bot_then_is_posted_once(monkeypatch):
    """The clock catches up before Discord connects: the brief must wait, not be lost or sent twice."""
    from app.connectors import discord_bot as dc
    from app.features.briefs import post

    sent: list[tuple[str, str]] = []

    class Row:
        id = 4242

    async def fake_send(channel, **kw):
        sent.append((channel, kw["kind"]))
        return Row(), None

    monkeypatch.setattr(dc, "configured", lambda: True)
    monkeypatch.setattr(dc.bot, "send", fake_send)

    async def startup():
        dc.bot.ready_event.clear()
        bid = post.store("morning", at(13, 7), {"title": "t", "headline": "h", "fields": [], "footer": ""})
        assert post.send_soon(bid, "morning", lambda b: (None, None))
        await asyncio.sleep(0.05)
        assert sent == []  # Discord isn't up yet: waiting
        dc.bot.ready_event.set()  # ...now it is
        await asyncio.sleep(0.05)
        post.send_soon(bid, "morning", lambda b: (None, None))  # asked again (a second catch-up): not posted twice
        await asyncio.sleep(0.05)
        dc.bot.ready_event.clear()
        return bid

    bid = asyncio.run(startup())
    assert sent == [("summary", "brief_morning")]
    with session() as s:
        assert s.get(Brief, bid).message_id == 4242
