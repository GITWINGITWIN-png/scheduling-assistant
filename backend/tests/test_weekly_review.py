"""B7's weekly review (D4) and doing what was decided (agreed at the plan): which topics a week
brings, what each answer changes, what "รับทุกเรื่อง" leaves alone, and that unanswered topics
change nothing."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.core import db
from app.core.config import get_config
from app.core.db import session
from app.core.rules import book
from app.core.tables import Block, Decision, Rule, Task
from app.features.briefs.tables import Brief
from app.features.mail.tables import Person
from app.features.projects.tables import Project
from app.features.schedule import sync
from app.features.time.tables import Activity
from app.features.weekly import review
from app.features.weekly import topics as T

TZ = get_config().tz
SUNDAY = datetime(2026, 11, 15, 19, 30, tzinfo=TZ)  # the review's time; its week is Mon 9 – Sun 15 Nov


def day(d: int, h: int, mi: int = 0) -> datetime:
    return datetime(2026, 11, d, h, mi, tzinfo=TZ)


@pytest.fixture(scope="module", autouse=True)
def _db():
    db.migrate()


@pytest.fixture
def week(tmp_path, monkeypatch):
    """A week with something in every topic, and no Google: re-planning is counted, not done."""
    replans = []

    async def fake_run(force=False):
        replans.append(force)
        return "บล็อกใหม่ 2"
    monkeypatch.setattr(sync, "run", fake_run)
    with session() as s:
        s.execute(delete(Activity))
        person = Person(name="wr-อ.ธนา", level="important", level_until=SUNDAY + timedelta(days=5), note="สอนวิชา datacom ถึงสอบ")
        s.add(person)
        lab = Project(name="wr-lab", path=str(tmp_path / "wr-lab"), status="active", potential="S", urgency=4,
                      progress={"todo": 3, "done": 1, "next": "ขั้น 2: feature selection"}, last_activity=SUNDAY - timedelta(days=9),
                      is_git=False)
        s.add(lab)
        t = Task(title="wr-lab: ทำต่อ", source="project", project="wr-lab", source_ref="weekly-test")
        s.add(t)
        s.flush()
        for d in (3, 10):  # Tuesday afternoons, two weeks running, missed
            s.add(Block(task_id=t.id, starts_at=day(d, 13), ends_at=day(d, 15), status="planned", outcome="missed"))
        for d in (9, 11, 12):  # three mornings of the plan for wr-lab; you worked on it half an hour in all
            s.add(Block(task_id=t.id, starts_at=day(d, 14), ends_at=day(d, 15), status="planned", outcome=""))
        ok = Task(title="wr-ok: ทำต่อ", source="project", project="wr-ok", source_ref="weekly-test")  # kept to its plan
        s.add(ok)
        s.flush()
        s.add(Block(task_id=ok.id, starts_at=day(13, 16), ends_at=day(13, 18), status="planned"))
        s.add(Activity(start=day(13, 16), end=day(13, 18), app="code", title="ok.py - wr-ok - VS Code", category="code",
                       project="wr-ok"))
        for d in (9, 10, 11, 12, 13):  # mornings of steady code: the focus hours
            s.add(Activity(start=day(d, 9), end=day(d, 11), app="code", title="x.py - other - VS Code", category="code"))
        s.add(Activity(start=day(9, 14), end=day(9, 14, 30), app="code", title="lab.py - wr-lab - VS Code", category="code",
                       project="wr-lab"))
        ids = {"person": person.id, "lab": lab.id, "task": t.id}
    yield ids, replans
    with session() as s:
        s.execute(delete(Activity))
        for model, where in ((Block, Block.task_id.in_(select(Task.id).where(Task.project == "wr-lab"))),
                             (Block, Block.task_id.in_(select(Task.id).where(Task.project == "wr-ok"))),
                             (Task, Task.project.in_(("wr-lab", "wr-ok"))), (Project, Project.name == "wr-lab"),
                             (Person, Person.name.like("wr-%")), (Brief, Brief.kind == "weekly"),
                             (Decision, Decision.kind == "weekly")):
            s.execute(delete(model).where(where))
        for r in s.scalars(select(Rule)):  # the schedule rules the answers made
            if (r.effect or {}).get("type") in ("block_avoid", "focus_first"):
                s.delete(r)


def mine(topics):
    return {t["topic"]: t for t in topics if t["topic"] != "project" or t["proposal"]["name"] == "wr-lab"}


def test_a_week_brings_a_topic_for_each_thing_to_decide(week):
    found = mine(T.build(SUNDAY)[0])
    assert set(found) == {"people", "schedule", "time", "project"}
    people = found["people"]
    assert "โน้ตที่คุณจดไว้: “สอนวิชา datacom ถึงสอบ”" in people["why"] and people["default"] == "approve"
    sched = found["schedule"]["proposal"]
    assert sched["focus"] == {"from": "09:00", "to": "11:00"} and sched["avoid"] == [{"weekday": 1, "part": "บ่าย"}]
    # the plan: three 1-hour blocks and Tuesday's missed 2 hours; 4.5 hours short, booked up to the 4-hour cap
    assert "wr-ok" not in [b["name"] for b in found["time"]["proposal"]["projects"]]  # it got its plan: nothing to book
    ours = [b for b in found["time"]["proposal"]["projects"] if b["name"] == "wr-lab"]  # (other files share this week)
    assert ours == [{"name": "wr-lab", "minutes": 30, "planned": 300, "book": 240}]
    project = found["project"]
    assert project["default"] == "book" and [a for a, _ in project["acts"]] == ["book", "reject"]  # no git: no summary job
    assert "ให้เลขาสรุปไม่ได้" in project["extent"]


def test_the_review_is_stored_once_a_week_and_an_old_topic_expires_unchanged(week):
    brief_id = review.make(SUNDAY)
    assert review.make(SUNDAY) is None  # one a week
    with session() as s:
        b = s.get(Brief, brief_id)
        assert b.title.startswith("9–15 พ.ย. · ") and "เรื่องให้ตัดสิน" in b.title and b.day == "2026-11-15"
        assert "เวลา: โค้ด" in b.headline
    waiting = review.of_brief(brief_id)
    assert waiting and all(d.status == "pending" for d in waiting)
    again = review.make(SUNDAY, again=True)  # ส่งตอนนี้ again: the same review, fresh topics; the old ones expire
    assert again == brief_id
    fresh = review.of_brief(brief_id)
    assert fresh and not {d.id for d in fresh} & {d.id for d in waiting}
    with session() as s:
        assert {d.status for d in s.scalars(select(Decision).where(Decision.id.in_([d.id for d in waiting])))} == {"expired"}
        assert s.get(Person, week[0]["person"]).level == "important"  # nothing changed
    with pytest.raises(review.AnswerError):
        asyncio.run(review.answer(waiting[0].id, "approve"))


def test_each_answer_does_what_its_topic_says(week):
    ids, replans = week
    brief_id = review.make(SUNDAY)
    topics = {d.detail["topic"]: d for d in review.of_brief(brief_id) if d.detail["topic"] != "project"
              or d.detail["proposal"]["name"] == "wr-lab"}
    said = asyncio.run(review.answer(topics["schedule"].id, "approve"))
    assert said.startswith("✅ เพิ่มกติกาแล้ว: ช่วงโฟกัส 09:00–11:00 ก่อน · ไม่วางบล็อกบ่ายวันอังคาร") and replans
    assert book.focus_window() == {"type": "focus_first", "from": "09:00", "to": "11:00"}
    assert book.block_avoid() == [{"type": "block_avoid", "weekday": 1, "from": "12:00", "to": "17:00"}]
    asyncio.run(review.answer(topics["time"].id, "approve"))
    asyncio.run(review.answer(topics["project"].id, "book"))
    with session() as s:
        booked = {t.title: t for t in s.scalars(select(Task).where(Task.project == "wr-lab", Task.title.like("%ทบทวนรายสัปดาห์%")))}
    time_task = booked["wr-lab: เวลาที่ขาดจากสัปดาห์ก่อน (ทบทวนรายสัปดาห์)"]
    assert time_task.est_minutes == 240 and time_task.not_before == day(16, 0)  # from Monday
    lab_task = booked["wr-lab: ขั้น 2: feature selection (ทบทวนรายสัปดาห์)"]
    assert (lab_task.est_minutes, lab_task.block_minutes) == (360, 120)
    asyncio.run(review.answer(topics["people"].id, "reject"))
    with session() as s:
        assert s.get(Person, ids["person"]).level == "important"  # ไม่เอา: nothing changed
        assert s.get(Decision, topics["people"].id).status == "rejected"
    assert T.projects(SUNDAY) == [] or all(p["proposal"]["name"] != "wr-lab" for p in T.projects(SUNDAY))  # booked: not again


def test_accept_all_takes_the_defaults_and_never_the_token_spending_choice(week, monkeypatch):
    ids, _ = week
    calls = []
    from app.features.jobs import queue

    monkeypatch.setattr(queue, "add", lambda *a, **k: calls.append(a) or (1, 1))
    with session() as s:  # the project may have a summary job now
        p = s.get(Project, ids["lab"])
        p.is_git, p.allow_jobs = True, True
    monkeypatch.setattr(queue, "blocked", lambda p: "")
    brief_id = review.make(SUNDAY)
    lab = next(d for d in review.of_brief(brief_id) if d.detail["topic"] == "project" and d.detail["proposal"]["name"] == "wr-lab")
    assert [a for a, _ in lab.detail["acts"]] == ["both", "book", "reject"]
    done = asyncio.run(review.accept_all(brief_id))
    assert len(done) == len(review.of_brief(brief_id, status=None)) and calls == []  # booked only: no job, no tokens
    with session() as s:
        assert s.get(Person, ids["person"]).level == "interested"  # the person's default: let it end
        assert {d.status for d in s.scalars(select(Decision).where(Decision.kind == "weekly"))
                if d.detail.get("brief_id") == brief_id} == {"approved"}


def test_the_people_menu_changes_one_choice_before_you_accept(week):
    ids, _ = week
    brief_id = review.make(SUNDAY)
    people = next(d for d in review.of_brief(brief_id) if d.detail["topic"] == "people")
    detail = review.choose_person(people.id, ids["person"], "renew30")
    assert "wr-อ.ธนา → ต่ออายุ 1 เดือน" in detail["what"]
    asyncio.run(review.answer(people.id, "approve"))
    with session() as s:
        p = s.get(Person, ids["person"])
        assert p.level == "important" and p.note == "" and p.level_until > SUNDAY + timedelta(days=20)


def test_the_review_goes_out_on_sunday_evening_or_monday_morning_only():
    assert review.open_now(SUNDAY) and review.open_now(day(16, 11, 59))
    assert not review.open_now(day(15, 18, 59)) and not review.open_now(day(16, 12)) and not review.open_now(day(12, 20))


def test_the_cards_say_what_how_and_how_far_with_each_topics_own_buttons(week):
    from app.features.weekly import cards

    brief_id = review.make(SUNDAY)
    with session() as s:
        b = s.get(Brief, brief_id)
        s.expunge(b)
    embed, view = cards.overview_card(b, True)
    assert embed.title == b.title and view.children[0].item.label == "รับทุกเรื่องตามที่เสนอ"
    by_topic = {d.detail["topic"]: d for d in review.of_brief(brief_id) if d.detail["topic"] != "project"
                or d.detail["proposal"]["name"] == "wr-lab"}
    embed, view = cards.topic_card(by_topic["people"])
    assert [f.name for f in embed.fields] == ["จะทำอะไร", "ทำยังไง", "แค่ไหน"] and embed.author.name.endswith("· คน")
    menu, *buttons = view.children
    assert [o.label for o in menu.item.options] == ["wr-อ.ธนา: ต่ออายุ 1 เดือน", "wr-อ.ธนา: ต่ออายุ 3 เดือน",
                                                    "wr-อ.ธนา: ต่อไม่มีกำหนด", "wr-อ.ธนา: ยังไม่ตัดสิน"]
    assert [x.item.label for x in buttons] == ["รับทั้ง 1", "ไม่เอา"]
    _, view = cards.topic_card(by_topic["project"])
    assert [x.item.custom_id for x in view.children] == [f"weekly:{by_topic['project'].id}:book", f"weekly:{by_topic['project'].id}:reject"]
