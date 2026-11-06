"""B5's runner, with a scripted Claude: a job works in a worktree on its own branch and never on
yours, what it left is committed, the worktree goes away, a job cut off at a restart is kept,
and the night round only starts work in its window."""

import asyncio
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core import db
from app.core.db import now, session
from app.core.rules import book
from app.features.jobs import plan, queue, quota, runner
from app.features.jobs.tables import Job, QuotaReading
from app.features.projects.tables import Project
from tests.fake_claude import FakeClient

GIT = ["-c", "user.email=t@example.com", "-c", "user.name=t"]


@pytest.fixture(scope="module", autouse=True)
def database():
    db.migrate()
    book.seed()


def git(path: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "run-demo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "PROGRESS.md").write_text("- [x] เริ่ม\n- [ ] เขียน hello\n")
    (root / "notes.txt").write_text("ของคุณ\n")
    git(root, "add", "-A")
    git(root, *GIT, "commit", "-q", "-m", "start")
    (root / "notes.txt").write_text("ของคุณ ยังไม่ commit\n")  # your work in progress: the job must not see or touch it
    with session() as s:
        p = Project(name=f"run-demo-{tmp_path.name[-6:]}", path=str(root), potential="A", urgency=3, allow_jobs=True, is_git=True,
                    progress={"next": "เขียน hello", "todo": 1, "done": 1})
        s.add(p)
        s.flush()
        project_id = p.id
    yield root, project_id
    with session() as s:  # one job at a time: never leave one running for the next test
        for j in s.scalars(select(Job).where(Job.status == "running")):
            j.status = "stopped"
        s.get(Project, project_id).allow_jobs = False


def ready_job(project_id: int, *, budget: int = 100_000, risks: list[str] | None = None, approved: bool = True) -> int:
    with session() as s:
        p = s.get(Project, project_id)
        job = Job(project_id=p.id, project=p.name, stuck_at="เขียน hello", status="ready", title="เขียน hello",
                  steps=["เขียน hello.py", "commit"], model="sonnet", effort="low", estimate=budget, budget=budget,
                  risks=risks or [], planned_at=now(), approved_until=now() + timedelta(days=3) if approved else None)
        s.add(job)
        s.flush()
        return job.id


def run_job(job_id: int, monkeypatch, script: list, **start) -> Job:
    FakeClient.script = script
    monkeypatch.setattr(runner, "Client", FakeClient)

    async def go():
        await runner.start(job_id, **start)
        await runner.RUNNING[job_id].task
    asyncio.run(go())
    with session() as s:
        j = s.get(Job, job_id)
        s.expunge(j)
    return j


@pytest.fixture(autouse=True)
def quota_ok(monkeypatch):
    async def fake(max_age=None):
        return 85.0
    monkeypatch.setattr(quota, "week_left", fake)


HELLO = [("tool", "Write", {"file_path": "hello.py", "content": "def hello():\n    return 'hi'\n"}, 20_000),
         ("tool", "Bash", {"command": "git add hello.py && git -c user.email=t@example.com -c user.name=t commit -q -m 'เพิ่ม hello'"}, 5_000),
         ("tool", "Write", {"file_path": "PROGRESS.md", "content": "- [x] เริ่ม\n- [x] เขียน hello\n"}, 5_000),
         ("text", "เพิ่ม hello.py แล้ว commit · ติ๊ก PROGRESS.md (ยังไม่ commit)", 2_000)]


def test_a_job_works_on_its_own_branch_and_never_on_yours(project, monkeypatch):
    root, project_id = project
    yours = git(root, "rev-parse", "HEAD")
    job = run_job(ready_job(project_id), monkeypatch, HELLO)
    assert job.status == "done" and job.branch.startswith("secretary/") and job.used == 32_000
    assert git(root, "rev-parse", "HEAD") == yours and git(root, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert (root / "notes.txt").read_text() == "ของคุณ ยังไม่ commit\n"  # your uncommitted change is untouched
    assert not (root / "hello.py").exists()  # nothing appeared in your folder
    log = git(root, "log", "--format=%s", f"main..{job.branch}").splitlines()
    assert log == ["เลขา: งานค้างของงาน #%d" % job.id, "เพิ่ม hello"]  # its commit, then what it left (the PROGRESS tick)
    assert git(root, "show", f"{job.branch}:PROGRESS.md").endswith("- [x] เขียน hello")
    assert git(root, "show", f"{job.branch}:notes.txt") == "ของคุณ"  # it started from your last commit
    assert git(root, "worktree", "list").count("\n") == 0  # its worktree is gone; the branch stays
    assert "ทำเสร็จ · 2 commit บน " in job.result and "เริ่มจาก main" in job.result
    assert "ขั้นที่ค้างใน PROGRESS.md: เขียน hello" in FakeClient.last.prompt


def test_the_project_moving_on_means_planning_again(project, monkeypatch):
    root, project_id = project
    job_id = ready_job(project_id)
    (root / "PROGRESS.md").write_text("- [x] เริ่ม\n- [x] เขียน hello\n- [ ] เขียนเทสต์\n")  # you did it meanwhile
    with pytest.raises(runner.RunError) as exc:
        asyncio.run(runner.start(job_id))
    assert "ไปต่อแล้ว (ขั้นถัดไป: เขียนเทสต์)" in str(exc.value)
    with session() as s:
        j = s.get(Job, job_id)
        assert (j.status, j.stuck_at, j.steps) == ("queued", "เขียนเทสต์", [])


def test_one_job_at_a_time_and_only_ready_ones(project, monkeypatch):
    _, project_id = project
    job_id = ready_job(project_id)
    with session() as s:
        s.get(Job, job_id).status = "asking"
    with pytest.raises(runner.RunError):
        asyncio.run(runner.start(job_id))
    with session() as s:
        s.get(Job, job_id).status = "running"  # as if another copy of the secretary were running it
    other = ready_job(project_id)
    with pytest.raises(runner.RunError) as exc:
        asyncio.run(runner.start(other))
    assert "ทำทีละงาน" in str(exc.value)


def test_the_five_hour_window_nearly_spent_waits(project, monkeypatch):
    _, project_id = project
    job_id = ready_job(project_id)
    with session() as s:
        s.add(QuotaReading(at=now(), week_left=85.0, five_left=12.0, source="sdk", raw={}))
    with pytest.raises(runner.RunError) as exc:
        asyncio.run(runner.start(job_id))
    assert "โควตา 5 ชั่วโมงเหลือ 12%" in str(exc.value)
    with session() as s:
        s.add(QuotaReading(at=now() + timedelta(seconds=1), week_left=85.0, five_left=90.0, source="sdk", raw={}))


def test_a_job_cut_off_by_a_restart_is_kept_on_its_branch(project):
    root, project_id = project
    job_id = ready_job(project_id)
    with session() as s:
        j = s.get(Job, job_id)
        j.status, j.branch = "running", f"secretary/{job_id}-run-demo"
        name = j.project
    wt = runner.worktrees() / f"{runner.slug(name)}-{job_id}"
    runner.worktrees().mkdir(parents=True, exist_ok=True)
    git(root, "worktree", "add", "-q", "-b", f"secretary/{job_id}-run-demo", str(wt))
    (wt / "half.py").write_text("x = 1\n")
    assert job_id in runner.recover()
    with session() as s:
        j = s.get(Job, job_id)
        assert j.status == "stopped" and j.result.startswith("หยุด: เลขาปิดระหว่างทำ")
    assert git(root, "show", f"secretary/{job_id}-run-demo:half.py") == "x = 1" and not wt.exists()


def test_the_night_round_starts_work_only_in_its_window(project, monkeypatch):
    _, project_id = project
    monkeypatch.setattr(runner, "now", lambda: datetime(2026, 11, 7, 3, 0, tzinfo=timezone.utc))  # 10:00 in Bangkok
    assert asyncio.run(runner.round_tick()) == "นอกช่วง 01:00–06:00 · ไม่เริ่มงานใหม่"
    job_id = ready_job(project_id)
    night = datetime(2026, 11, 6, 19, 30, tzinfo=timezone.utc)  # 02:30 in Bangkok
    monkeypatch.setattr(runner, "now", lambda: night)
    monkeypatch.setattr(queue, "now", lambda: night)
    FakeClient.script = HELLO
    monkeypatch.setattr(runner, "Client", FakeClient)

    async def go():
        line = await runner.round_tick()
        started = [j for j in runner.RUNNING]
        if started:
            await runner.RUNNING[started[0]].task
        return line, started
    line, started = asyncio.run(go())
    assert started == [job_id] and line.startswith("เริ่ม ")
