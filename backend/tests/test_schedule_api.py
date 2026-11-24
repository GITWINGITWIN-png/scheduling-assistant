"""The schedule page's API: adding activities and tasks with their own block sizes.

Google Calendar is replaced by a fake that remembers what was written, so nothing here
reaches your real calendar. The schedule round is treated as off, so nothing re-plans
(re-planning would read the real calendar).
"""

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api import schedule as api
from app.connectors import gcal, google
from app.core import actions, clock, db
from app.core.db import now, session
from app.core.tables import Block, Event, Task
from app.features.classroom.sync import details_of

BKK = ZoneInfo("Asia/Bangkok")


@pytest.fixture(scope="module", autouse=True)
def database():
    db.migrate()


@pytest.fixture
def calendar(monkeypatch):
    """A fake main calendar: {event id: what was written}."""
    written: dict[str, dict] = {}

    def insert(title, start, end, *, all_day=False, location="", description="", calendar="primary", mark="appointment"):
        gid = f"g{len(written) + 1}"
        written[gid] = {"title": title, "start": start, "end": end, "all_day": all_day, "location": location,
                        "description": description, "calendar": calendar}
        return gid, f"https://calendar.google.com/event?eid={gid}"

    def delete(event_id, *, calendar="primary"):
        written.pop(event_id, None)

    def retext(event_id, title, description, *, calendar="primary"):
        written[event_id] = {"title": title, "description": description, "calendar": calendar}
        return True

    monkeypatch.setattr(gcal, "insert", insert)
    monkeypatch.setattr(gcal, "delete", delete)
    monkeypatch.setattr(gcal, "retext", retext)
    monkeypatch.setattr(gcal, "blocks_calendar", lambda *, create=True: "blocks")
    monkeypatch.setattr(clock, "enabled", lambda name: False)
    return written


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------ activity
def test_an_event_goes_into_the_main_calendar_and_undo_takes_it_out(calendar):
    r = run(api.add_event(api.EventIn(title=" ประชุมแล็บ ", start="2026-11-12T10:00", end="2026-11-12T11:30",
                                      location="ห้อง 204", description="เอาสไลด์ไปด้วย")))
    [(gid, w)] = calendar.items()
    assert w["title"] == "ประชุมแล็บ" and w["calendar"] == "primary" and w["location"] == "ห้อง 204"
    assert w["start"] == datetime(2026, 11, 12, 10, 0, tzinfo=BKK) and w["end"] == datetime(2026, 11, 12, 11, 30, tzinfo=BKK)
    assert "เอาสไลด์ไปด้วย" in w["description"] and "ลงโดยเลขา" in w["description"]
    with session() as s:
        ev = s.get(Event, r["id"])
        assert (ev.source, ev.status, ev.gcal_id) == ("you", "placed", gid)
        assert ev.link.endswith(gid)  # the page can open it in Google Calendar right away
    run(actions.undo(r["action_id"]))
    assert calendar == {}
    with session() as s:
        assert s.get(Event, r["id"]).status == "removed"


def test_an_all_day_event_covers_its_last_day(calendar):
    run(api.add_event(api.EventIn(title="ไปต่างจังหวัด", start="2026-11-14", end="2026-11-15", all_day=True)))
    [w] = calendar.values()
    assert w["all_day"]
    assert w["start"] == datetime(2026, 11, 14, tzinfo=BKK) and w["end"] == datetime(2026, 11, 16, tzinfo=BKK)


@pytest.mark.parametrize("start,end", [("2026-11-12T11:00", "2026-11-12T10:00"), ("2026-11-12T10:00", "2026-11-12T10:00")])
def test_an_event_that_does_not_end_after_it_starts_is_refused(calendar, start, end):
    with pytest.raises(HTTPException) as exc:
        run(api.add_event(api.EventIn(title="ผิด", start=start, end=end)))
    assert exc.value.status_code == 400 and calendar == {}


def test_a_failed_write_leaves_nothing_behind(calendar, monkeypatch):
    def refuse(*a, **k):
        raise google.NeedsConsent("gmail", "ยังไม่ได้อนุญาต Calendar")

    monkeypatch.setattr(gcal, "insert", refuse)
    with pytest.raises(HTTPException) as exc:
        run(api.add_event(api.EventIn(title="ลงไม่ได้", start="2026-11-12T10:00", end="2026-11-12T11:00")))
    assert exc.value.status_code == 409 and "connect gmail" in exc.value.detail
    with session() as s:
        assert s.scalar(select(Event).where(Event.title == "ลงไม่ได้")) is None


# ------------------------------------------------------------------ task
def test_a_task_keeps_its_own_block_sizes_and_null_puts_one_back_to_the_rules(calendar):
    r = run(api.add_task(api.TaskIn(title="รายงาน datacom", due="2026-11-13T17:00", est_minutes=20 * 60,
                                    block_minutes=60, daily_minutes=120)))
    with session() as s:
        t = s.get(Task, r["id"])
        assert (t.est_minutes, t.block_minutes, t.daily_minutes) == (1200, 60, 120)  # no 8-hour ceiling any more
    edit = run(api.edit_task(r["id"], api.TaskEdit(block_minutes=None)))
    with session() as s:
        t = s.get(Task, r["id"])
        assert (t.block_minutes, t.daily_minutes) == (None, 120)  # only the field sent changed
    run(actions.undo(edit["action_id"]))
    with session() as s:
        assert s.get(Task, r["id"]).block_minutes == 60


@pytest.mark.parametrize("field,value", [("est_minutes", 0), ("est_minutes", 200 * 60 + 15), ("block_minutes", 10),
                                         ("block_minutes", 9 * 60), ("daily_minutes", 17 * 60)])
def test_minutes_outside_the_sensible_range_are_refused(calendar, field, value):
    with pytest.raises(HTTPException) as exc:
        run(api.add_task(api.TaskIn(title="ผิด", **{field: value})))
    assert exc.value.status_code == 400


def test_an_edit_cannot_blank_the_title(calendar):
    r = run(api.add_task(api.TaskIn(title="งานหนึ่ง")))
    for body in (api.TaskEdit(title=None), api.TaskEdit(title="  ")):
        with pytest.raises(HTTPException):
            run(api.edit_task(r["id"], body))


# ------------------------------------------------------------------ task details
def test_details_are_kept_cleared_with_null_and_limited(calendar):
    r = run(api.add_task(api.TaskIn(title="แล็บ 3", details="  ทำข้อ 1-4 ส่งเป็น PDF\nhttps://example.com/hand-in  ")))
    with session() as s:
        assert s.get(Task, r["id"]).details == "ทำข้อ 1-4 ส่งเป็น PDF\nhttps://example.com/hand-in"
    run(api.edit_task(r["id"], api.TaskEdit(details=None)))
    with session() as s:
        assert s.get(Task, r["id"]).details == ""
    with pytest.raises(HTTPException):
        run(api.add_task(api.TaskIn(title="ยาวไป", details="ก" * 5001)))


def test_changing_details_rewrites_the_blocks_already_in_the_calendar(calendar):
    r = run(api.add_task(api.TaskIn(title="รายงาน", due="2026-11-20T17:00")))
    with session() as s:
        s.add(Block(task_id=r["id"], starts_at=now() + timedelta(hours=2), ends_at=now() + timedelta(hours=3), gcal_id="b-up"))
        s.add(Block(task_id=r["id"], starts_at=now() - timedelta(hours=3), ends_at=now() - timedelta(hours=2), gcal_id="b-past"))
    edit = run(api.edit_task(r["id"], api.TaskEdit(details="ส่งในกลุ่ม LINE ของแล็บ")))
    assert set(calendar) == {"b-up"}  # a block that's over is left as it was
    assert calendar["b-up"]["calendar"] == "blocks" and calendar["b-up"]["title"] == "รายงาน"
    assert calendar["b-up"]["description"].startswith("ส่งในกลุ่ม LINE ของแล็บ") and "ส่ง " in calendar["b-up"]["description"]
    run(actions.undo(edit["action_id"]))  # undoing puts the calendar's text back too
    assert "ส่งในกลุ่ม LINE" not in calendar["b-up"]["description"]


def test_a_classroom_task_starts_with_the_instructions_and_the_hand_in_link():
    cw = {"description": "อ่านบทที่ 3 แล้วตอบคำถามท้ายบท", "alternateLink": "https://classroom.google.com/c/1/a/2/details"}
    assert details_of(cw) == "อ่านบทที่ 3 แล้วตอบคำถามท้ายบท\n\nส่งงานที่: https://classroom.google.com/c/1/a/2/details"
    assert details_of({"alternateLink": "https://classroom.google.com/x"}) == "ส่งงานที่: https://classroom.google.com/x"
    long = details_of({"description": "ก" * 3000, "alternateLink": "https://classroom.google.com/x"})
    assert len(long) < 1600 and long.endswith("ส่งงานที่: https://classroom.google.com/x")  # the link is never cut off


def test_an_events_details_are_kept_and_shown(calendar):
    r = run(api.add_event(api.EventIn(title="สอบย่อย", start="2026-11-18T13:00", end="2026-11-18T14:00",
                                      description="เอาบัตรนักศึกษาไป\nห้องสอบ: https://example.com/rooms")))
    [w] = calendar.values()
    assert w["description"].startswith("เอาบัตรนักศึกษาไป")  # Google Calendar gets it too
    shown = api.week("2026-11-16T00:00", "2026-11-23T00:00")["events"]
    assert [e["description"] for e in shown if e["id"] == r["id"]] == ["เอาบัตรนักศึกษาไป\nห้องสอบ: https://example.com/rooms"]


def test_a_calendar_description_becomes_plain_text_and_keeps_its_links():
    assert gcal.plain_text('ส่งที่ <a href="https://x.com/a">โฟลเดอร์</a><br>ห้อง 405<br><br><br>ลงโดยเลขา') \
        == "ส่งที่ โฟลเดอร์ (https://x.com/a)\nห้อง 405"
    assert gcal.plain_text("a < b &amp; c") == "a < b & c"  # not HTML: left as it is, entities read


def test_the_week_shows_appointments_waiting_for_you_and_whether_a_blocks_task_is_done(calendar):
    from app.core.tables import Decision
    start = datetime(2026, 11, 25, 14, 0, tzinfo=BKK)
    with session() as s:
        waiting = Event(title="ประชุมกลุ่ม", starts_at=start, ends_at=start + timedelta(hours=1), source="email", status="proposed")
        ignored = Event(title="นัดที่ไม่ได้ถาม", starts_at=start, ends_at=start + timedelta(hours=1), source="email", status="proposed")
        s.add_all([waiting, ignored])
        s.flush()
        s.add(Decision(kind="appointment", title="ประชุมกลุ่ม", detail={"event_id": waiting.id, "from": "มายด์"}))
        task = Task(title="งานที่เสร็จแล้ว", source="you", status="done")
        s.add(task)
        s.flush()
        s.add(Block(task_id=task.id, starts_at=start - timedelta(hours=3), ends_at=start - timedelta(hours=2)))
        waiting_id = waiting.id
    w = api.week("2026-11-23T00:00", "2026-11-30T00:00")
    shown = {e["title"]: e for e in w["events"]}
    assert "นัดที่ไม่ได้ถาม" not in shown  # proposed but not waiting for you: not drawn
    assert shown["ประชุมกลุ่ม"]["status"] == "proposed" and shown["ประชุมกลุ่ม"]["from"] == "มายด์"
    assert shown["ประชุมกลุ่ม"]["decision_id"] is not None and shown["ประชุมกลุ่ม"]["id"] == waiting_id
    [b] = [b for b in w["blocks"] if b["title"] == "งานที่เสร็จแล้ว"]
    assert b["task_status"] == "done" and not b["running"]
