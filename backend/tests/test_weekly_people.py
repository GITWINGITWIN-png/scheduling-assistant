"""B7's weekly people proposals (1.4), agreed at the plan: what gets proposed, what never does, and
what a choice changes."""

import asyncio
import itertools
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core import db
from app.core.db import now, session
from app.core.tables import Decision
from app.features.mail import review, rounds
from app.features.mail.tables import Email, Person

_ids = itertools.count(1)


@pytest.fixture(scope="module", autouse=True)
def database():
    db.migrate()


@pytest.fixture(autouse=True)
def fresh():
    with session() as s:  # only the people and mail this file made (other files share the database)
        for p in s.scalars(select(Person).where(Person.name.like("wk-%"))):
            for e in s.scalars(select(Email).where(Email.person_id == p.id)):
                s.delete(e)
            s.delete(p)
    rounds.set_interests([])
    yield
    rounds.set_interests([])


def person(name: str, level: str, *, until_days: float | None = None, note: str = "") -> int:
    with session() as s:
        p = Person(name=f"wk-{name}", level=level, note=note,
                   level_until=now() + timedelta(days=until_days) if until_days is not None else None)
        s.add(p)
        s.flush()
        return p.id


def mail(pid: int, subject: str, days_ago: float = 1) -> None:
    i = next(_ids)
    with session() as s:
        s.add(Email(id=f"wk{i}", account="you", thread_id=f"wkt{i}", person_id=pid, sender="x@example.com",
                    subject=subject, sent_at=now() - timedelta(days=days_ago), level="ignored"))


def mine(items):
    return {i["name"]: i for i in items if i["name"].startswith("wk-")}


def test_an_important_person_near_the_end_date_comes_with_your_note():
    person("soon", "important", until_days=3, note="อาจารย์วิชา datacom ถึงสอบปลายภาค")
    person("past", "important", until_days=-2)
    person("later", "important", until_days=30)
    person("no-end", "important")
    got = mine(review.proposals())
    assert set(got) == {"wk-soon", "wk-past"}
    soon = got["wk-soon"]
    assert (soon["choice"], soon["to"], soon["note"]) == ("expire", "interested", "อาจารย์วิชา datacom ถึงสอบปลายภาค")
    assert [k for k, _ in soon["choices"]] == ["expire", "renew30", "renew90", "forever", "skip"]
    assert got["wk-past"]["why"].startswith("คนสำคัญหมดอายุแล้วเมื่อ")


def test_an_ignored_sender_is_raised_only_on_your_interests_and_interested_is_never_lowered():
    kaggle = person("kaggle", "ignored")
    mail(kaggle, "Time-series forecasting competition")
    mail(kaggle, "New time-series dataset")
    once = person("once", "ignored")
    mail(once, "time-series tips")
    noisy = person("noisy", "interested")
    for n in range(9):
        mail(noisy, f"ข่าวชมรม {n}")  # 9 mails, nothing useful: still never proposed (you do it by hand)
    assert mine(review.proposals()) == {}  # no interests set: nothing to match
    rounds.set_interests(["time-series"])
    got = mine(review.proposals())
    assert set(got) == {"wk-kaggle"} and got["wk-kaggle"]["choice"] == "raise"
    assert got["wk-kaggle"]["why"] == "หัวข้อตรงเรื่องที่สนใจ “time-series” 2 ครั้งใน 4 สัปดาห์"
    mail(once, "time-series again", days_ago=40)  # too long ago to count
    assert "wk-once" not in mine(review.proposals())


def test_what_each_choice_changes():
    a = person("expire", "important", until_days=1, note="เหตุผลเดิม")
    b = person("renew", "important", until_days=1, note="เหตุผลเดิม")
    c = person("skip", "important", until_days=1, note="เหตุผลเดิม")
    items = mine(review.proposals())
    items["wk-renew"]["choice"], items["wk-skip"]["choice"] = "renew30", "skip"
    assert len(review.apply(list(items.values()))) == 2  # skip changes nothing
    with session() as s:
        pa, pb, pc = s.get(Person, a), s.get(Person, b), s.get(Person, c)
        assert (pa.level, pa.note, pa.level_until) == ("interested", "", None)  # the note goes once decided
        assert pa.demote_reason.startswith("หมดอายุ (ทบทวนรายสัปดาห์): เหตุผลเดิม")
        assert pb.level == "important" and pb.note == "" and timedelta(days=29) < pb.level_until - now() < timedelta(days=31)
        assert (pc.level, pc.note) == ("important", "เหตุผลเดิม")


def test_a_person_changed_by_hand_meanwhile_is_left_alone():
    pid = person("moved", "important", until_days=1)
    items = list(mine(review.proposals()).values())
    with session() as s:
        s.get(Person, pid).level = "ignored"
    assert review.apply(items) == []


def test_answering_the_weekly_reviews_people_topic_settles_it():
    pid = person("weekly", "important", until_days=2)
    items = list(mine(review.proposals()).values())
    with session() as s:
        d = Decision(kind="weekly", title="ปรับทะเบียน 1 คน", detail={"topic": "people", "proposal": {"items": items}})
        s.add(d)
        s.flush()
        decision_id = d.id
    assert review.current()["decision_id"] == decision_id
    asyncio.run(review.answer([{"person_id": pid, "choice": "renew90"}], decision_id, via=("test", "")))
    with session() as s:
        d = s.get(Decision, decision_id)
        assert (d.status, d.answer) == ("approved", "people")
        assert d.detail["proposal"]["items"][0]["choice"] == "renew90"
        assert s.get(Person, pid).level_until - now() > timedelta(days=89)
    assert review.current()["decision_id"] is None
    with pytest.raises(ValueError):
        asyncio.run(review.answer([], decision_id, via=("test", "")))  # once only
