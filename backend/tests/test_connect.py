"""B10 · เชื่อมโปรเจคกับเลขา: the `secretary-news` command writes what docs/CONNECT.md asks for and
the inbox reads it as news; the note in each project goes in where Claude Code reads it, git never
sees it, and undo takes back exactly what was changed (your own lines stay)."""

import asyncio
import importlib.util
import json
import sqlite3
import subprocess

import pytest
from sqlalchemy import delete

from app.core import actions, db
from app.core.config import REPO_DIR
from app.core.db import session
from app.features.projects import connect, inbox
from app.features.projects.tables import Project, ProjectNews

spec = importlib.util.spec_from_file_location("secretary_news", REPO_DIR / "desktop" / "secretary_news.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


@pytest.fixture(scope="module", autouse=True)
def _db():
    db.migrate()


# ------------------------------------------------------------------ the command
def test_each_kind_has_the_fields_connect_md_asks_for_and_bad_ones_are_refused():
    assert cli.item("report", "เสร็จ:  ตัวแยกคำ\nภาษาไทย", body="ขั้นต่อไป: เทสต์", needs_you=True) == {
        "kind": "report", "title": "เสร็จ: ตัวแยกคำ ภาษาไทย", "body": "ขั้นต่อไป: เทสต์", "needs_you": True}
    assert cli.item("schedule", "ส่งรายงาน", due="2026-11-13T17:00", minutes=90) == {
        "kind": "schedule", "title": "ส่งรายงาน", "due": "2026-11-13T17:00", "minutes": 90}
    assert cli.item("status", "backtest รอบ 14", state="failed")["status"] == "failed"
    for bad in (lambda: cli.item("report", "   "), lambda: cli.item("schedule", "ไม่มีกำหนด"),
                lambda: cli.item("schedule", "x", due="ศุกร์นี้"), lambda: cli.item("status", "x", state="ok")):
        with pytest.raises(cli.Refused):
            bad()


def test_the_project_is_the_folder_under_projects_even_from_a_subfolder(tmp_path):
    root = tmp_path / "Projects"
    (root / "job-search" / "ai-job-search").mkdir(parents=True)
    assert cli.project_of(root / "job-search" / "ai-job-search", root) == "job-search"
    assert cli.project_of(root, root) is None and cli.project_of(tmp_path, root) is None


def test_a_news_file_is_written_whole_and_the_inbox_reads_it_as_news(tmp_path, monkeypatch, capsys):
    root, data = tmp_path / "Projects", tmp_path / "data"
    (root / "research_labs" / "src").mkdir(parents=True)
    monkeypatch.setenv("SECRETARY_PROJECTS_DIR", str(root))
    monkeypatch.setenv("SECRETARY_DATA_DIR", str(data))
    monkeypatch.chdir(root / "research_labs" / "src")
    assert cli.main(["report", "เสร็จ: สแกน feed รอบใหม่", "--body", "ขั้นต่อไป: จด query string", "--needs-you"]) == 0
    assert "ส่งข่าวให้เลขาแล้ว · research_labs · report" in capsys.readouterr().out
    files = list((data / "inbox" / "research_labs").iterdir())
    assert len(files) == 1 and files[0].suffix == ".json" and not files[0].name.startswith(".")  # nothing half-written
    news_id = inbox.read_one(files[0], None)
    with session() as s:
        row = s.get(ProjectNews, news_id)
        assert (row.project, row.kind, row.title, row.body, row.needs_you) == (
            "research_labs", "report", "เสร็จ: สแกน feed รอบใหม่", "ขั้นต่อไป: จด query string", True)
        s.delete(row)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["report", "จากนอกโปรเจค"]) == 2  # outside ~/Projects without --project: refused, nothing sent


def test_it_says_when_the_secretary_isnt_reading_its_inbox_yet(tmp_path):
    assert cli.round_on(tmp_path) is None  # no secretary here: it says nothing
    store = sqlite3.connect(tmp_path / "secretary.db")
    store.execute("create table settings (key text primary key, value text)")
    store.execute("insert into settings values ('clock.enabled', ?)", (json.dumps({"watch": True}),))
    store.commit()
    assert cli.round_on(tmp_path) is False
    store.execute("update settings set value = ?", (json.dumps({"inbox": True}),))
    store.commit()
    store.close()
    assert cli.round_on(tmp_path) is True


def test_install_puts_a_link_and_never_overwrites_someone_elses_file(tmp_path, monkeypatch):
    command = tmp_path / "bin" / "secretary-news"
    monkeypatch.setattr(cli, "COMMAND", command)
    assert cli.install().startswith("ติดตั้งแล้ว") and command.resolve() == cli.HERE
    assert cli.install().startswith("ติดตั้งอยู่แล้ว")
    assert cli.uninstall().startswith("เอาออกแล้ว") and not command.exists()
    command.write_text("ของคนอื่น")
    with pytest.raises(cli.Refused):
        cli.install()
    assert cli.uninstall().startswith("ไม่ได้ติดตั้ง") and command.read_text() == "ของคนอื่น"


# ------------------------------------------------------------------ the note in each project
@pytest.fixture
def projects(tmp_path):
    """A fake ~/Projects: alpha is a git repo, beta has your own CLAUDE.local.md, gamma uses AGENTS.md."""
    root = tmp_path / "Projects"
    for name in ("alpha", "beta", "gamma"):
        (root / name).mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root / "alpha")], check=True)
    (root / "beta" / "CLAUDE.local.md").write_text("# ของผู้ใช้\nใช้ uv\n")
    (root / "gamma" / "AGENTS.md").write_text("use pnpm\n")
    with session() as s:
        rows = [Project(name=n, path=str(root / n), is_git=n == "alpha") for n in ("alpha", "beta", "gamma")]
        s.add_all(rows)
        s.flush()
        ids = {p.name: p.id for p in rows}
    yield root, ids
    with session() as s:
        s.execute(delete(Project).where(Project.id.in_(ids.values())))


def _git_status(path) -> str:
    return subprocess.run(["git", "-C", str(path), "status", "--porcelain"], capture_output=True, text=True).stdout


def test_connecting_all_writes_the_note_where_claude_reads_it_and_git_never_sees_it(projects):
    root, ids = projects
    names, failed, action_id = connect.connect_all(root=root)
    assert names == ["alpha", "beta", "gamma"] and failed == [] and action_id
    alpha = (root / "alpha" / "CLAUDE.local.md").read_text()
    assert "## ส่งข่าวให้เลขา" in alpha and "`alpha`" in alpha and 'secretary-news report "เสร็จ:' in alpha
    assert _git_status(root / "alpha") == ""  # nothing to commit
    beta = (root / "beta" / "CLAUDE.local.md").read_text()
    assert beta.startswith("# ของผู้ใช้\nใช้ uv\n\n" + connect.START)  # yours stays, first
    assert "@AGENTS.md" in (root / "gamma" / "CLAUDE.local.md").read_text()  # so AGENTS.md is still read
    assert connect.connect_all(root=root) == ([], [], None)  # again: nothing to change
    asyncio.run(actions.undo(action_id))
    assert not (root / "alpha" / "CLAUDE.local.md").exists() and not (root / "gamma" / "CLAUDE.local.md").exists()
    assert (root / "beta" / "CLAUDE.local.md").read_text() == "# ของผู้ใช้\nใช้ uv\n"
    assert "CLAUDE.local.md" not in (root / "alpha" / ".git" / "info" / "exclude").read_text()


def test_the_secretary_itself_and_hidden_or_missing_folders_get_no_note(tmp_path):
    assert connect.why_not(Project(name="my_secretary", path=str(REPO_DIR))) == "นี่คือตัวเลขาเอง"
    assert connect.why_not(Project(name="สำรอง", path=str(tmp_path), hidden=True)).startswith("ซ่อนไว้")
    assert connect.why_not(Project(name="หายไป", path=str(tmp_path / "gone"))) == "ไม่พบโฟลเดอร์"


def test_one_project_connects_and_disconnects_and_undo_brings_it_back(projects):
    root, ids = projects
    assert connect.connect_one(ids["alpha"]) and connect.connected(root / "alpha")
    assert connect.connect_one(ids["alpha"]) is None  # connected already
    off = connect.disconnect_one(ids["alpha"])
    assert off and not connect.connected(root / "alpha") and _git_status(root / "alpha") == ""
    asyncio.run(actions.undo(off))
    assert connect.connected(root / "alpha")


def test_a_folder_that_cant_be_written_is_skipped_and_said(projects):
    root, ids = projects
    (root / "gamma").chmod(0o500)
    try:
        names, failed, _ = connect.connect_all(root=root)
    finally:
        (root / "gamma").chmod(0o700)
    assert names == ["alpha", "beta"] and len(failed) == 1 and failed[0].startswith("gamma:")
