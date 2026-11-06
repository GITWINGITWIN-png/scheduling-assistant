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
from app.core.tables import Decision
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
    found = rows()
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
