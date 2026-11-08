"""B6's time page: the category rules (no model) and what the page counts from them (agreed at the plan)."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.core import actions, db, settings
from app.core.db import session
from app.core.tables import Block, Task
from app.features.classroom.tables import Course
from app.features.projects.tables import Project
from app.features.time import categorize, insights
from app.features.time.tables import Activity

T0 = datetime(2026, 11, 2, 2, 0, tzinfo=timezone.utc)  # Monday 09:00 in Bangkok


@pytest.fixture(scope="module", autouse=True)
def _db():
    db.migrate()


@pytest.fixture(autouse=True)
def world(tmp_path):
    # Only tables nothing points at are emptied (other test files share this database); the
    # course and the tasks are this file's own and are taken out again afterwards.
    with session() as s:
        s.execute(delete(Activity))
        for name in ("my_secretary", "datacom", "datacom-report", "Finance", "ai"):
            s.add(Project(name=name, path=str(tmp_path / name), progress={}))
        s.merge(Course(id="time-c1", name="Data Communication", state="followed", folder=str(tmp_path / "datacom" / "สื่อ")))
    settings.put(categorize.RULES_KEY, [])
    yield
    with session() as s:
        mine = select(Task.id).where(Task.source_ref == "test_time")
        s.execute(delete(Block).where(Block.task_id.in_(mine)))
        s.execute(delete(Task).where(Task.source_ref == "test_time"))
        s.execute(delete(Course).where(Course.id == "time-c1"))
        s.execute(delete(Project).where(Project.path.startswith(str(tmp_path))))


@pytest.mark.parametrize(("app", "title", "want"), [
    ("code", "pull.py - my_secretary - Visual Studio Code", ("code", "my_secretary")),
    ("org.gnome.Ptyxis", "user@pc: ~/Projects/my_secretary/backend", ("code", "my_secretary")),
    ("firefox", "my-secretary · GitHub — Mozilla Firefox", ("code", "my_secretary")),  # - and _ are the same
    ("code", "report.tex - datacom-report - Visual Studio Code", ("code", "datacom-report")),  # the longest name wins
    ("code", "lab2.py - datacom - Visual Studio Code", ("study", "datacom")),  # it holds a Classroom course's folder
    ("org.gnome.Ptyxis", "user@pc: ~/.secretary/inbox", ("code", "")),  # a terminal, not mail
    ("google-chrome", "Meet - abc-defg-hij - Google Chrome", ("meeting", "")),
    ("firefox", "Google Classroom — Mozilla Firefox", ("study", "")),
    ("firefox", "Data Communication: งานที่ 3 — Mozilla Firefox", ("study", "")),  # a course's name
    ("firefox", "Inbox (3) - Gmail — Mozilla Firefox", ("chat", "")),
    ("discord", "Discord | #general", ("chat", "")),
    ("firefox", "YouTube — Mozilla Firefox", ("web", "")),
    ("org.gnome.Nautilus", "Downloads", ("other", "")),
    ("firefox", "AI news — Mozilla Firefox", ("web", "")),  # "ai" is too short to be looked for
])
def test_the_rules_sort_a_window(app, title, want):
    category, project_id, project = categorize.Sorter().sort(app, title)
    assert (category, project) == want
    assert (project_id is None) == (project == "")


def test_a_rule_of_yours_comes_first_sorts_whats_kept_again_and_undoes():
    with session() as s:
        s.add(Activity(start=T0, end=T0 + timedelta(minutes=30), app="obsidian", title="notes", category="other"))
        s.add(Activity(start=T0 + timedelta(hours=1), end=T0 + timedelta(hours=2), app="firefox", title="Overleaf", category="web"))
    action_id = categorize.add_rule("app", "Obsidian", "study")
    categorize.add_rule("title", "overleaf", "code", "datacom-report")
    with session() as s:
        got = {r.app: (r.category, r.project) for r in s.scalars(select(Activity))}
    assert got == {"obsidian": ("study", ""), "firefox": ("code", "datacom-report")}
    asyncio.run(actions.undo(action_id))  # the first rule (and only it) goes; the second stays
    assert [r["match"] for r in categorize.yours()] == ["overleaf"]
    again = categorize.add_rule("title", "overleaf", "study")  # the same match again replaces it
    assert [(r["match"], r["category"]) for r in categorize.yours()] == [("overleaf", "study")]
    asyncio.run(actions.undo(again))  # and undo brings the one it replaced back
    assert [(r["match"], r["category"], r["project"]) for r in categorize.yours()] == [("overleaf", "code", "datacom-report")]
    with pytest.raises(ValueError):
        categorize.add_rule("app", "x", "nonsense")


# ------------------------------------------------------------------ what the page counts
def win(minute: int, length: int, app: str, title: str = "", category: str = "code", project: str = "") -> Activity:
    return Activity(start=T0 + timedelta(minutes=minute), end=T0 + timedelta(minutes=minute + length), app=app, title=title,
                    category=category, project=project)


def test_per_day_and_per_project_against_the_plan():
    with session() as s:
        s.add_all([win(0, 90, "code", project="Finance"), win(90, 30, "firefox", category="web"),
                   win(24 * 60, 60, "code", project="my_secretary")])
        t = Task(title="Finance: backtest", source="project", project="Finance", source_ref="test_time")
        done = Task(title="my_secretary: B6", source="project", project="my_secretary", source_ref="test_time")
        s.add_all([t, done])
        s.flush()
        s.add(Block(task_id=t.id, starts_at=T0, ends_at=T0 + timedelta(hours=3), status="planned"))
        s.add(Block(task_id=done.id, starts_at=T0 + timedelta(days=1), ends_at=T0 + timedelta(days=1, hours=1), status="planned"))
        s.add(Block(task_id=t.id, starts_at=T0 + timedelta(days=3), ends_at=T0 + timedelta(days=3, hours=2), status="removed"))
    start, end, label = insights.span("week", T0)
    assert label == "2–8 พ.ย." and (end - start) == timedelta(days=7)
    rs = insights.rows(start, end)
    bars = insights.buckets("week", start, end, rs)
    assert [b["label"] for b in bars] == ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."]
    assert bars[0]["minutes"] == {"code": 90, "web": 30} and bars[1]["minutes"] == {"code": 60}
    per = {p["name"]: p for p in insights.projects(start, end, rs)}
    assert per["Finance"] == {"name": "Finance", "minutes": 90, "planned": 180, "short": 90}  # a removed block isn't plan
    assert per["my_secretary"] == {"name": "my_secretary", "minutes": 60, "planned": 60, "short": 0}
    per["my_secretary"].update(planned=120, minutes=120)  # a big plan, kept: nothing to say about it
    notes = [n["title"] for n in insights.behaviours("week", rs, list(per.values()))]
    assert "Finance ได้เวลาน้อยกว่าแผน 50%" in notes and not any(n.startswith("my_secretary ได้เวลาน้อยกว่าแผน") for n in notes)


def test_switching_focus_and_late_nights():
    rs = []
    for day in range(3):  # three mornings of steady code, then switching between apps every 5 minutes after 22:00
        base = day * 24 * 60
        rs += [win(base, 60, "code", project="my_secretary"), win(base + 60, 10, "org.gnome.Ptyxis", project="my_secretary"),
               win(base + 70, 50, "code", project="my_secretary"),  # two switches a morning
               win(base + 120, 10, "code", "another file", project="my_secretary")]  # the same app again: no switch
        rs += [win(base + 5 * 60, 120, "zoom", category="meeting")]  # 14:00–16:00, one window: still not focus
        if day == 0:
            rs.append(win(base + 4 * 60, 30, "code", project="my_secretary"))  # 13:00, after an hour away: a new stretch
        rs += [win(base + 13 * 60 + 5 * k, 5, ("firefox", "discord")[k % 2], category=("web", "chat")[k % 2]) for k in range(12)]
    rs.sort(key=lambda r: r.start)  # as rows() gives them
    assert len(insights.switches(rs)) == 3 * (2 + 11)  # the same app twice in a row isn't a switch
    notes = {n["icon"]: n for n in insights.behaviours("week", rs, [])}
    assert notes["bolt"]["title"] == "โฟกัสดีสุด 09:00–11:00"  # the work, not the evening's browsing
    assert notes["eye"]["title"] == "หลัง 22:00 สลับแอปบ่อยขึ้น 24 เท่า"  # 33 in 3 h, against 6 in 13 h before 22:00
    assert notes["eye"]["sub"] in ("ส่วนใหญ่เป็นเว็บและโซเชียล", "ส่วนใหญ่เป็นอีเมลและแชท")
    assert notes["clock"]["title"] == "ทำ my_secretary ต่อเนื่องนานสุด 2 ชม. 10 นาที"


def test_what_the_rules_couldnt_sort_comes_biggest_first():
    rs = [win(0, 10, "obsidian", "a", "other"), win(10, 40, "obsidian", "b", "other"), win(50, 5, "gimp", "x", "other"),
          win(55, 60, "code", "y")]
    assert insights.unsorted(rs) == [{"app": "obsidian", "title": "b", "minutes": 50}, {"app": "gimp", "title": "x", "minutes": 5}]


def test_the_settings_page_says_whether_activitywatch_records(monkeypatch):
    from app.api import settings as settings_api
    from app.features.time import recorder

    monkeypatch.setattr(recorder, "installed", lambda: False)
    services = {x["name"]: x for x in settings_api.get_settings()["services"]}
    assert services["ActivityWatch"]["state"] == "ยังไม่ติดตั้ง" and services["OmniRoute"]["state"] == "ยังไม่ต่อ"
