"""B6's plan against what you did (agreed at the plan): which blocks count as done or missed, and what
that changes for the planner."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.core import actions, db
from app.core.db import session
from app.core.tables import Block, Task
from app.features.schedule import sync
from app.features.schedule.planner import Rules, Work, plan
from app.features.time import followed
from app.features.time.tables import Activity

T0 = datetime(2026, 11, 2, 2, 0, tzinfo=timezone.utc)  # Monday 09:00 in Bangkok


def m(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


@pytest.fixture(scope="module", autouse=True)
def _db():
    db.migrate()


@pytest.fixture(autouse=True)
def _clean():
    yield
    with session() as s:
        s.execute(delete(Activity))
        mine = select(Task.id).where(Task.source_ref == "followed")
        s.execute(delete(Block).where(Block.task_id.in_(mine)))
        s.execute(delete(Task).where(Task.source_ref == "followed"))


def task(title: str, project: str = "", source: str = "project") -> Task:
    with session() as s:
        t = Task(title=title, project=project, source=source, source_ref="followed", est_minutes=240)
        s.add(t)
        s.flush()
        s.expunge(t)
        return t


def block(t: Task, start: int, end: int) -> int:
    with session() as s:
        b = Block(task_id=t.id, starts_at=m(start), ends_at=m(end), status="planned")
        s.add(b)
        s.flush()
        return b.id


def kept(start: int, end: int, app: str, title: str = "", category: str = "code", project: str = "") -> None:
    with session() as s:
        s.add(Activity(start=m(start), end=m(end), app=app, title=title, category=category, project=project))


def spans(*pairs):
    return lambda a, b: [(max(m(x), a), min(m(y), b)) for x, y in pairs if min(m(y), b) > max(m(x), a)]


def outcome(block_id: int) -> tuple:
    with session() as s:
        b = s.get(Block, block_id)
        return b.outcome, b.worked_minutes, b.instead


def test_done_missed_away_and_unknown():
    t = task("Finance: backtest", project="Finance")
    done, missed, away, unknown = block(t, 0, 60), block(t, 120, 180), block(t, 240, 300), block(t, 360, 420)
    kept(0, 40, "code", project="Finance")  # 40 of 60: done
    kept(40, 60, "firefox", category="web")
    kept(120, 135, "code", project="Finance")  # 15 of 60 on it, the rest on my_secretary: missed
    kept(135, 180, "code", project="my_secretary")
    kept(240, 250, "firefox", category="web")  # at the computer 10 of 60: away
    present = spans((0, 60), (120, 180), (240, 250))
    covered = spans((0, 330))  # the recorder was off from 05:30 on: the last block is unknown
    assert followed.check(m(500), present, covered) == [missed]
    assert outcome(done) == ("done", 40, "")
    assert outcome(missed) == ("missed", 15, "my_secretary")
    assert outcome(away) == ("away", 0, "")
    assert outcome(unknown) == ("unknown", 0, "")
    assert followed.check(m(500), present, covered) == []  # once only
    day = followed.followed(m(-60), m(600))
    assert (day["checked"], day["percent"]) == (3, 50)  # 1 of done + missed; away isn't in the share, unknown isn't checked


def test_a_block_is_checked_only_once_it_has_ended_for_a_moment():
    t = task("datacom report", project="datacom-report")
    b = block(t, 0, 60)
    assert followed.check(m(61), spans((0, 60)), spans((0, 60))) == [] and outcome(b)[0] == ""  # 1 minute: not yet
    followed.check(m(65), spans((0, 60)), spans((0, 60)))
    assert outcome(b)[0] == "missed"  # nothing on it, at the computer the whole hour


@pytest.mark.parametrize(("t", "row", "want"), [
    (dict(title="HW3 (Data Mining)", source="classroom"), dict(app="firefox", title="anything", category="study"), True),
    (dict(title="ตอบอีเมล อ.วิภา", source="email"), dict(app="firefox", title="Inbox - Gmail", category="chat"), True),
    (dict(title="เขียน report บทที่ 2", source="you"), dict(app="code", title="report.tex - x - VS Code", category="code"), True),
    (dict(title="เขียน report บทที่ 2", source="you"), dict(app="code", title="reports.tex - x", category="code"), False),
    (dict(title="อ่านเปเปอร์ forecasting", source="you"), dict(app="evince", title="ฟอร์มอ่านเปเปอร์ forecasting.pdf", category="other"), True),
    (dict(title="งาน", source="you"), dict(app="code", title="งานบ้าน", category="other"), False),  # too general to look for
])
def test_what_counts_as_working_on_a_task(t, row, want):
    assert followed.matches(Task(project="", **t), Activity(project="", **row), followed.words(t["title"])) is want


def test_the_planner_counts_only_what_was_worked_of_a_missed_block():
    t = task("Finance: backtest", project="Finance")
    b = block(t, 0, 120)
    with session() as s:
        row = s.get(Block, b)
        row.outcome, row.worked_minutes = "missed", 30
    mail = task("ตอบอีเมล อ.วิภา", source="email")
    work, _, kept_blocks, _, fp_missed = sync._inputs(m(180), [])
    mine = next(w for w in work if w.task_id == t.id)
    assert mine.minutes == 240 - 30  # the other 90 minutes went back to the task
    assert mine.focus and not next(w for w in work if w.task_id == mail.id).focus  # email replies never take focus hours
    with session() as s:
        s.get(Block, b).outcome = "done"
    work, _, _, _, fp_done = sync._inputs(m(180), [])
    assert next(w for w in work if w.task_id == t.id).minutes == 240 - 120 and fp_done != fp_missed  # it re-plans


def test_move_to_tomorrow_then_the_planner_waits_and_undo():
    t = task("Finance: backtest", project="Finance")
    action_id = followed.move_to_tomorrow(t.id)
    with session() as s:
        nb = s.get(Task, t.id).not_before
    assert nb is not None and nb > datetime.now(timezone.utc)
    asyncio.run(actions.undo(action_id))
    with session() as s:
        assert s.get(Task, t.id).not_before is None


def test_not_before_in_the_planner():
    now = datetime(2026, 11, 2, 10, 0, tzinfo=timezone(timedelta(hours=7)))
    tomorrow = datetime(2026, 11, 3, 0, 0, tzinfo=timezone(timedelta(hours=7)))
    out = plan([Work(1, 60, not_before=tomorrow)], [], now=now, rules=Rules())
    assert out.blocks[0].start == datetime(2026, 11, 3, 9, 0, tzinfo=timezone(timedelta(hours=7)))  # the day window's start
    assert plan([Work(1, 60)], [], now=now, rules=Rules()).blocks[0].start == now  # without it: right away


def test_mark_done_and_the_days_numbers():
    t = task("Finance: backtest", project="Finance")
    a, b = block(t, 0, 60), block(t, 120, 180)
    followed.check(m(300), spans((0, 180)), spans((0, 180)))  # nothing kept on it: both missed
    assert followed.followed(m(-60), m(600))["percent"] == 0
    action_id = followed.mark_done(a)
    got = followed.followed(m(-60), m(600))
    assert (got["percent"], len(got["done"]), len(got["missed"])) == (50, 1, 1)
    asyncio.run(actions.undo(action_id))
    assert outcome(a)[0] == "missed" and outcome(b)[0] == "missed"


def test_the_evening_review_says_how_the_plan_went(monkeypatch):
    from app.features.briefs import evening

    t = task("Finance: backtest", project="Finance")
    done, missed = block(t, 0, 60), block(t, 120, 180)
    kept(0, 50, "code", project="Finance")
    kept(120, 180, "code", project="my_secretary")
    followed.check(m(300), spans((0, 60), (120, 180)), spans((0, 200)))
    later = block(t, 600, 660)  # the planner booked its time again tonight (19:00)
    other = task("datacom report", project="datacom-report")
    block(other, 180, 240)  # 12:00–13:00, missed too, but its time went to tomorrow: nothing to move
    kept(180, 240, "firefox", "YouTube", category="web")
    followed.check(m(300), spans((180, 240)), spans((0, 300)))
    block(other, 24 * 60, 24 * 60 + 60)
    b = evening.compose(m(540))  # 18:00
    assert b["title"] == "วันนี้ทำตามตารางได้ 1 จาก 3 บล็อก (33%)"
    fields = dict(b["fields"])
    assert fields["หลุดแผน"] == ("Finance: backtest 11:00 · คุณทำ my_secretary แทน · เลขาหาเวลาใหม่: คืนนี้ 19:00\n"
                                 "datacom report 12:00 · ช่วงนั้นเป็นเว็บและโซเชียล · เลขาหาเวลาใหม่: พรุ่งนี้ 09:00")
    assert fields["เวลาจริงวันนี้"] == "โค้ด 1.8 ชม. · เว็บ 1"
    assert evening.to_move(m(540)) == [(t.id, "Finance: backtest")]  # offered: move to tomorrow
    assert later and done


def test_a_repeated_miss_becomes_a_rule_the_planner_follows():
    from app.core import settings as core_settings
    from app.core.rules import book
    from app.core.tables import Rule

    t = task("datacom", project="datacom")
    for week in (0, 1):  # Tuesday 13:00 two weeks running
        b = block(t, week * 7 * 24 * 60 + 24 * 60 + 240, week * 7 * 24 * 60 + 24 * 60 + 300)
        with session() as s:
            s.get(Block, b).outcome = "missed"
    found = [n for n in followed.patterns(m(15 * 24 * 60)) if n["weekday"] == 1]
    assert found and found[0]["part"] == "บ่าย" and found[0]["weeks"] == 2 and not found[0]["avoided"]
    rule_id, action_id = followed.avoid_rule(1, "บ่าย")
    focus_id, _ = followed.focus_rule("09:00", "11:30")
    try:
        r = sync.rules()
        assert (1, r.avoid[0][1].isoformat("minutes"), r.avoid[0][2].isoformat("minutes")) == (1, "12:00", "17:00")
        assert tuple(x.isoformat("minutes") for x in r.focus) == ("09:00", "11:30")
        assert sync.rules_dict()["focus"] == ["09:00", "11:30"]  # it's in the plan's fingerprint too
        assert [n for n in followed.patterns(m(15 * 24 * 60)) if n["weekday"] == 1][0]["avoided"]
        with pytest.raises(ValueError):
            followed.avoid_rule(1, "บ่าย")  # not twice
        asyncio.run(actions.undo(action_id))
        assert sync.rules().avoid == ()
    finally:
        with session() as s:
            for rid in (rule_id, focus_id):
                if (row := s.get(Rule, rid)) is not None:
                    s.delete(row)
    assert book.focus_window() is None and core_settings
