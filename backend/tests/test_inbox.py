"""B5's gate for other projects: JSON files in ~/.secretary/inbox become news, tasks and statuses;
failures and questions from projects that matter go to #ด่วน at once."""

import asyncio
import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core import db
from app.core.db import now, session
from app.core.tables import Task
from app.features.briefs import day
from app.features.projects import inbox
from app.features.projects.tables import Project, ProjectNews


@pytest.fixture(scope="module", autouse=True)
def database():
    db.migrate()


@pytest.fixture(scope="module")
def projects():
    with session() as s:
        s.add_all([Project(name="news-high", path="/tmp/news-high", potential="A", urgency=2),
                   Project(name="news-low", path="/tmp/news-low", potential="D", urgency=1),
                   Project(name="news-rush", path="/tmp/news-rush", potential="C", urgency=4)])


def drop(project: str, name: str, data) -> None:
    folder = inbox.inbox_dir() / project
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False))


def news(title: str) -> ProjectNews:
    with session() as s:
        row = s.scalar(select(ProjectNews).where(ProjectNews.title == title))
        s.expunge(row)
    return row


@pytest.fixture
def sent(monkeypatch):
    calls: list[int] = []

    async def hook(news_id: int) -> None:
        calls.append(news_id)

    monkeypatch.setattr(inbox, "URGENT", [hook])
    return calls


def test_a_failure_in_a_project_that_matters_is_sent_at_once(projects, sent):
    drop("news-high", "run.json", {"kind": "status", "title": "backtest รอบ 14", "status": "failed", "body": "หน่วยความจำไม่พอ"})
    drop("news-low", "run.json", {"kind": "report", "title": "ล้มแต่ไม่ด่วน", "failed": True})
    drop("news-rush", "ask.json", {"kind": "report", "title": "เลือกชุดข้อมูลไหนดี", "needs_you": True})
    line = asyncio.run(inbox.run())
    assert line == "ข่าวโปรเจค 3 เรื่อง · ด่วน 2"
    high, low, rush = news("backtest รอบ 14"), news("ล้มแต่ไม่ด่วน"), news("เลือกชุดข้อมูลไหนดี")
    assert high.urgent and high.failed and rush.urgent and not low.urgent  # D · 1 waits for the morning
    assert sorted(sent) == sorted([high.id, rush.id])
    assert (inbox.inbox_dir() / "news-high" / "read" / "run.json").is_file()  # read once, moved away
    assert not (inbox.inbox_dir() / "news-high" / "run.json").exists()
    with session() as s:
        assert s.scalar(select(Project.status).where(Project.name == "news-high")) == "auto"  # it reports its runs


def test_a_schedule_becomes_a_task_the_planner_books_time_for(projects, sent):
    drop("news-low", "due.json", {"kind": "schedule", "title": "ตรวจผลรอบใหม่", "due": "2026-11-20T17:00:00+07:00", "minutes": 90})
    asyncio.run(inbox.run())
    with session() as s:
        t = s.scalar(select(Task).where(Task.title == "news-low: ตรวจผลรอบใหม่"))
        assert (t.source, t.est_minutes, t.project) == ("project", 90, "news-low")
        assert t.due_at.isoformat().startswith("2026-11-20T10:00")  # 17:00 in Bangkok


def test_a_file_that_cant_be_read_is_set_aside_and_said(projects, sent):
    drop("news-low", "broken.json", "{not json")
    drop("news-low", "notitle.json", {"kind": "report"})
    drop("news-low", ".writing.json", {"kind": "report", "title": "ยังเขียนไม่เสร็จ"})  # hidden: not read yet
    line = asyncio.run(inbox.run())
    assert line == "ข่าวโปรเจค 0 เรื่อง · อ่านไม่ได้ 2"
    assert (inbox.inbox_dir() / "news-low" / "bad" / "broken.json").is_file()
    assert (inbox.inbox_dir() / "news-low" / ".writing.json").is_file()
    assert news("อ่านไฟล์ notitle.json ไม่ได้").kind == "bad"


def test_a_second_file_of_the_same_name_doesnt_overwrite_the_first(projects, sent):
    drop("news-low", "run.json", {"kind": "report", "title": "รอบสอง"})
    asyncio.run(inbox.run())
    assert (inbox.inbox_dir() / "news-low" / "read" / "run-1.json").is_file()


def test_nothing_new_leaves_no_line(projects, sent):
    assert asyncio.run(inbox.run()) is None


def test_the_morning_brief_lists_the_news_urgent_first(projects):
    rows = day.project_news(now() - timedelta(hours=1), now() + timedelta(minutes=1))
    assert rows[0][2] is True  # urgent ones lead
    assert ("news-low", "รอบสอง", False) in rows


def test_the_inbox_carries_its_guide():
    inbox.ensure()
    assert "~/.secretary/inbox/" in (inbox.inbox_dir() / "CONNECT.md").read_text()
