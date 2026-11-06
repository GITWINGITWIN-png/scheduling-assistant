"""B5's project registry: the scan of ~/Projects, the first scan's quiet registration, new folders
asked about, levels, and the switch that lets the secretary work on a project."""

import asyncio
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api import projects as api
from app.core import actions, db
from app.core.config import REPO_DIR
from app.core.db import session
from app.core.tables import Decision, Task
from app.features.projects import progress, scan
from app.features.projects.tables import Project

NOW = datetime(2026, 11, 9, 1, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def database():
    db.migrate()


def repo(root: Path, name: str, days_ago: int, progress_md: str = "") -> Path:
    path = root / name
    path.mkdir()
    when = (NOW - timedelta(days=days_ago)).isoformat()
    env = {**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if progress_md:
        (path / "PROGRESS.md").write_text(progress_md)
    subprocess.run(["git", "-C", str(path), "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q",
                    "--allow-empty", "-m", "start"], check=True, env=env)
    return path


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    r = tmp_path_factory.mktemp("Projects")
    repo(r, "alpha", 5, "- [x] วางแผน\n- [ ] **ทำหน้าเว็บ**\n  - [x] หน้าแรก\n  - [ ] หน้าตั้งค่า\n")
    repo(r, "beta", 60)
    plain = r / "gamma"
    plain.mkdir()
    old = (NOW - timedelta(days=90)).timestamp()
    os.utime(plain, (old, old))
    (r / ".cache").mkdir()  # hidden folders aren't projects
    return r


def rows() -> dict[str, Project]:
    with session() as s:
        out = {p.name: p for p in s.scalars(select(Project))}
        s.expunge_all()
    return out


def test_the_first_scan_records_everything_quietly(root):
    result = scan.scan(root, at=NOW)
    assert result.first and result.total == 3 and result.new == []  # nothing asked: 3 folders, no questions
    found = {n: p for n, p in rows().items() if p.path.startswith(str(root))}  # (other tests' rows aside)
    assert set(found) == {"alpha", "beta", "gamma"}
    assert found["alpha"].status == "active" and found["beta"].status == "paused" and found["gamma"].status == "paused"
    assert all((p.potential, p.urgency, p.level_set, p.allow_jobs) == ("C", 2, False, False) for p in found.values())
    assert found["alpha"].is_git and not found["gamma"].is_git
    assert found["alpha"].progress["next"] == "ทำหน้าเว็บ › หน้าตั้งค่า"
    assert found["alpha"].progress["done"] == 2 and found["alpha"].progress["todo"] == 2
    assert "จดโปรเจคที่มีอยู่ 3 โฟลเดอร์" in result.line()


def test_a_folder_that_appears_later_is_asked_about(root):
    repo(root, "delta", 1)
    result = scan.scan(root, at=NOW)
    assert not result.first and len(result.new) == 1
    project_id, decision_id = result.new[0]
    with session() as s:
        d = s.get(Decision, decision_id)
        assert (d.kind, d.status, d.title, d.detail["project_id"]) == ("project_level", "pending", "delta", project_id)
    assert scan.scan(root, at=NOW).new == []  # asked once


def test_setting_the_levels_answers_the_question_and_can_be_undone(root):
    with session() as s:
        d = s.scalar(select(Decision).where(Decision.kind == "project_level", Decision.title == "delta"))
        decision_id = d.id
    with pytest.raises(ValueError):
        scan.set_levels(decision_id, "Z", 3)
    scan.set_levels(decision_id, "A", 5)
    assert (rows()["delta"].potential, rows()["delta"].urgency, rows()["delta"].level_set) == ("A", 5, True)
    with session() as s:
        action_id = s.scalar(select(actions.Action.id).where(actions.Action.kind == "project.level").order_by(actions.Action.id.desc()))
    scan.setup()  # registers the undo
    asyncio.run(actions.undo(action_id))
    assert (rows()["delta"].potential, rows()["delta"].urgency) == ("C", 2)
    with session() as s:
        assert s.get(Decision, decision_id).status == "pending"  # asked again


def test_a_folder_that_went_away_is_kept_but_marked(root):
    subprocess.run(["rm", "-rf", str(root / "beta")], check=True)
    result = scan.scan(root, at=NOW)
    assert result.gone == ["beta"] and rows()["beta"].missing


def test_the_secretary_never_works_on_itself_or_without_git(root):
    assert scan.is_self(REPO_DIR) and not scan.is_self(root / "alpha")
    with session() as s:
        me = Project(name="my_secretary", path=str(REPO_DIR), is_git=True)
        s.add(me)
        s.flush()
        me_id = me.id
    found = rows()
    with pytest.raises(HTTPException) as exc:
        api.edit_project(me_id, api.ProjectEdit(allow_jobs=True))
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException):
        api.edit_project(found["gamma"].id, api.ProjectEdit(allow_jobs=True))  # no git: no branch to work on
    api.edit_project(found["alpha"].id, api.ProjectEdit(allow_jobs=True, urgency=4))
    assert rows()["alpha"].allow_jobs and rows()["alpha"].urgency == 4 and rows()["alpha"].level_set


def test_urgency_five_comes_first_and_hidden_last(root):
    found = rows()
    api.edit_project(found["gamma"].id, api.ProjectEdit(hidden=True))
    order = [p["name"] for p in api.projects()["items"]]
    assert order.index("alpha") < order.index("delta")  # both C; alpha is urgency 4, delta 2
    assert order[-1] in ("gamma", "beta")  # hidden and missing go to the end


def test_progress_reading_skips_checks_left_under_finished_items():
    text = "- [x] **B1 · พื้นฐาน**\n  - [ ] เช็กว่าเสร็จ (deferred)\n- [ ] **B2 · อีเมล**\n  - [ ] 1. ทะเบียนคน\n"
    assert progress.parse(text)["next"] == "B2 · อีเมล › 1. ทะเบียนคน"


# ------------------------------------------------------------------ advice from PROGRESS.md
def test_advice_says_which_projects_stood_still_and_which_matter_but_got_nothing(root):
    from app.features.projects import advice
    from app.features.schedule import tasks
    found = rows()
    with session() as s:
        alpha = s.get(Project, found["alpha"].id)  # 5 days ago, still has steps: not stale yet
        alpha.last_activity = NOW - timedelta(days=9)  # now it stood still for 9 days
        delta = s.get(Project, found["delta"].id)
        delta.potential, delta.commits_14d = "S", 0  # matters, but no commit in two weeks
    tasks.add("ส่ง alpha", due_at=NOW + timedelta(days=11))
    with session() as s:
        s.scalar(select(Task).where(Task.title == "ส่ง alpha")).project = "alpha"
    tips = advice.advice(at=NOW)
    by = {a.project: a for a in tips}
    assert by["alpha"].kind == "stale" and by["alpha"].title == "alpha นิ่ง 9 วัน"
    assert "ขั้นถัดไป: ทำหน้าเว็บ › หน้าตั้งค่า" in by["alpha"].detail and "แต่ส่ง 20 พ.ย." in by["alpha"].detail
    assert by["delta"].kind == "short"
    assert by["delta"].detail == "สัปดาห์นี้ได้เวลาในตาราง 0 ชม. ต่ำกว่าเป้า 10 ชม. · 2 สัปดาห์ไม่มี commit"
    assert [a.project for a in tips].index("delta") < [a.project for a in tips].index("alpha")  # S before C
    assert "gamma" not in by  # hidden: no advice


def test_time_booked_in_the_schedule_this_week_counts_toward_the_target(root):
    from app.core.tables import Block
    from app.features.projects import advice
    with session() as s:
        t = Task(title="delta: งานหลัก", source="project", project="delta", est_minutes=600)
        s.add(t)
        s.flush()
        monday = datetime(2026, 11, 9, 2, 0, tzinfo=timezone.utc)  # NOW is Monday 08:00 in Bangkok
        s.add_all([Block(task_id=t.id, starts_at=monday + timedelta(days=d), ends_at=monday + timedelta(days=d, hours=2),
                         status="planned") for d in range(4)])  # 8 hours this week
        s.add(Block(task_id=t.id, starts_at=monday - timedelta(days=3), ends_at=monday - timedelta(days=3, hours=-4)))  # last week
    assert {a.project: a for a in advice.advice(at=NOW)}["delta"].detail.startswith("สัปดาห์นี้ได้เวลาในตาราง 8 ชม.")
    with session() as s:
        s.add(Block(task_id=t.id, starts_at=monday + timedelta(days=5), ends_at=monday + timedelta(days=5, hours=2), status="pinned"))
    assert "delta" not in {a.project for a in advice.advice(at=NOW)}  # 10 hours: the target is met


def test_booking_time_makes_a_task_for_the_next_step(root):
    from app.features.projects import advice
    task_id = advice.book(rows()["alpha"].id, 120)
    with session() as s:
        t = s.get(Task, task_id)
        assert (t.title, t.est_minutes, t.project, t.source, t.due_at) == ("alpha: ทำหน้าเว็บ › หน้าตั้งค่า", 120, "alpha", "project", None)
