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


def ready_job(project_id: int, *, budget: int = 100_000, risks: list[str] | None = None, approved: bool = True,
              stuck: str = "เขียน hello") -> int:
    with session() as s:
        p = s.get(Project, project_id)
        job = Job(project_id=p.id, project=p.name, stuck_at=stuck, status="ready", title=stuck,
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
    assert "ใช้ 32,000 / งบ 100,000 โทเคน (อ่าน cache ซ้ำ 31,850)" in job.result  # why the quota hardly moves
    assert job.result.split("\n")[2:4] == ["", "ทำครบตามแผน"]  # Claude's own words in a paragraph of their own (Markdown)
    assert "ขั้นที่ค้างใน PROGRESS.md: เขียน hello" in FakeClient.last.prompt


def test_the_project_moving_on_means_planning_again(project, monkeypatch):
    root, project_id = project
    job_id = ready_job(project_id)
    (root / "PROGRESS.md").write_text("- [x] เริ่ม\n- [x] เขียน hello\n- [ ] เขียนเทสต์\n")  # you did it meanwhile
    git(root, "add", "PROGRESS.md")
    git(root, *GIT, "commit", "-q", "-m", "did hello myself")
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
    with session() as s:  # other test files' ready jobs share this database: only ours may be first
        for j in s.scalars(select(Job).where(Job.status.in_(("ready", "queued")))):
            j.status = "dropped"
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


# ------------------------------------------------------------------ stopping for real (B5.8)
def branch_files(root: Path, job: Job) -> list[str]:
    return sorted(git(root, "ls-tree", "-r", "--name-only", job.branch).splitlines())


def test_over_budget_it_really_stops_and_keeps_what_it_did(project, monkeypatch):
    root, project_id = project
    script = [("tool", "Write", {"file_path": "a.py", "content": "a = 1\n"}, 8_000),
              ("tool", "Write", {"file_path": "b.py", "content": "b = 2\n"}, 9_000),  # 17k: past the 15k budget
              ("tool", "Bash", {"command": "git add -A && git -c user.email=t@e.x -c user.name=t commit -q -m all"}, 1_000)]
    job = run_job(ready_job(project_id, budget=15_000), monkeypatch, script)
    assert job.status == "stopped" and job.result.startswith("หยุด: เกินงบ")
    assert job.used == 17_000 and "ใช้ 17,000 / งบ 15,000" in job.result
    assert FakeClient.last.interrupted and FakeClient.last.ran == []  # nothing after the stop ran
    assert "a.py" in branch_files(root, job) and "b.py" not in branch_files(root, job)  # kept: what it did before
    assert git(root, "log", "-1", "--format=%s", job.branch) == f"เลขา: งานค้างของงาน #{job.id} (หยุดเพราะเกินงบ)"


def test_going_round_in_circles_stops_it(project, monkeypatch):
    _, project_id = project
    again = ("tool", "Bash", {"command": "python -c 'print(1)'"}, 1_000)
    job = run_job(ready_job(project_id), monkeypatch, [again, again, again, again, again])
    assert job.status == "stopped" and job.result.startswith("หยุด: วนซ้ำ")
    assert len(FakeClient.last.ran) == 2  # the third time was stopped before it ran


def test_you_can_stop_it(project, monkeypatch):
    root, project_id = project
    monkeypatch.setattr(runner, "WATCH_EVERY", 0.05)
    script = [("tool", "Write", {"file_path": "a.py", "content": "a = 1\n"}, 1_000), ("wait", 5),
              ("tool", "Write", {"file_path": "late.py", "content": "x\n"}, 1_000)]
    job_id = ready_job(project_id)
    FakeClient.script = script
    monkeypatch.setattr(runner, "Client", FakeClient)

    async def go():
        await runner.start(job_id)
        await asyncio.sleep(0.2)
        runner.stop(job_id)
        await runner.RUNNING[job_id].task
    asyncio.run(go())
    with session() as s:
        job = s.get(Job, job_id)
        s.expunge(job)
    assert job.status == "stopped" and job.result.startswith("หยุด: คุณสั่งหยุด")
    assert "late.py" not in branch_files(root, job) and "a.py" in branch_files(root, job)


def test_out_of_time_it_stops(project, monkeypatch):
    _, project_id = project
    monkeypatch.setattr(runner, "WATCH_EVERY", 0.05)
    monkeypatch.setattr(runner, "MAX_MINUTES", 0)
    job = run_job(ready_job(project_id), monkeypatch, [("wait", 5), ("tool", "Write", {"file_path": "x.py", "content": "x\n"}, 1)])
    assert job.status == "stopped" and job.result.startswith("หยุด: ครบ 0 นาที")


def test_refused_calls_dont_happen_and_are_counted(project, monkeypatch):
    root, project_id = project
    outside = root.parent / "outside.txt"
    script = [("tool", "Bash", {"command": "git push origin HEAD"}, 1_000),
              ("tool", "Bash", {"command": "curl --version"}, 1_000),  # download: not approved for this job
              ("tool", "Write", {"file_path": str(outside), "content": "x\n"}, 1_000),
              ("tool", "Write", {"file_path": "ok.py", "content": "ok = True\n"}, 1_000)]
    job = run_job(ready_job(project_id, approved=False), monkeypatch, script)  # ready by the rules, not by you
    assert job.status == "done" and "ถูกห้าม 3 ครั้ง" in job.result
    assert [n for n, _ in FakeClient.last.denied] == ["Bash", "Bash", "Write"] and FakeClient.last.ran == []
    assert not outside.exists() and "ok.py" in branch_files(root, job)


def test_an_approved_kind_is_allowed_but_only_that_kind(project, monkeypatch):
    _, project_id = project
    script = [("tool", "Bash", {"command": "curl --version > /dev/null"}, 1_000),  # download: approved
              ("tool", "Bash", {"command": "rm -rf build"}, 1_000)]  # delete: not in the plan
    job = run_job(ready_job(project_id, risks=["download"]), monkeypatch, script)
    assert FakeClient.last.ran == ["curl --version > /dev/null"] and [n for n, _ in FakeClient.last.denied] == ["Bash"]
    assert "WebFetch" in FakeClient.last.options.tools  # the web too, with download approved
    assert job.status == "done"



# ------------------------------------------------------------------ one branch per project: jobs go on from each other
def commit_on_main(root: Path, name: str, text: str, message: str) -> None:
    (root / name).write_text(text)
    git(root, "add", name)
    git(root, *GIT, "commit", "-q", "-m", message)


STEP_ONE = [("tool", "Write", {"file_path": "hello.py", "content": "def hello():\n    return 'hi'\n"}, 2_000),
            ("tool", "Write", {"file_path": "PROGRESS.md", "content": "- [x] เริ่ม\n- [x] เขียน hello\n- [ ] เขียนเทสต์\n"}, 1_000)]


def test_the_next_job_goes_on_from_the_last_one_instead_of_doing_it_again(project, monkeypatch):
    from app.features.jobs import base
    root, project_id = project
    with session() as s:
        name = s.get(Project, project_id).name
    first = run_job(ready_job(project_id), monkeypatch, STEP_ONE)
    assert first.status == "done" and first.branch == f"secretary/{base.slug(name)}"
    assert base.next_step(root, name)[0] == "เขียนเทสต์"  # read where the next job starts: the step it did is ticked there
    assert git(root, "show", "main:PROGRESS.md").count("[x]") == 1  # main is untouched
    second = run_job(ready_job(project_id, stuck="เขียนเทสต์"), monkeypatch,
                     [("tool", "Bash", {"command": "test -f hello.py && echo yes > saw-hello.txt"}, 1_000)])
    assert second.status == "done" and second.branch == first.branch and "ต่อจากงานเดิมบน" in second.result
    assert git(root, "show", f"{first.branch}:saw-hello.txt") == "yes"  # it had the first job's work
    assert git(root, "log", "--format=%s", f"main..{first.branch}").count("งานค้างของงาน") == 2  # both jobs, one branch


def test_your_new_commits_come_into_the_secretarys_branch_first(project, monkeypatch):
    root, project_id = project
    first = run_job(ready_job(project_id), monkeypatch, STEP_ONE)
    commit_on_main(root, "mine.txt", "ของคุณ\n", "my own work")
    mine = git(root, "rev-parse", "main")
    second = run_job(ready_job(project_id, stuck="เขียนเทสต์"), monkeypatch,
                     [("tool", "Bash", {"command": "test -f mine.txt && test -f hello.py && echo both > saw.txt"}, 1_000)])
    assert second.status == "done" and "รวม commit ใหม่ของคุณจาก main 1 อันเข้ามาก่อน" in second.result
    assert git(root, "show", f"{first.branch}:saw.txt") == "both"
    assert git(root, "rev-parse", "main") == mine  # main only ever moves when you move it


def test_a_clash_with_your_work_stops_the_job_and_asks_you_to_merge(project, monkeypatch):
    root, project_id = project
    first = run_job(ready_job(project_id), monkeypatch,
                    [("tool", "Write", {"file_path": "notes.txt", "content": "ของเลขา\n"}, 1_000)])
    tip = git(root, "rev-parse", first.branch)
    git(root, "checkout", "-q", "--", "notes.txt")
    commit_on_main(root, "notes.txt", "ของคุณ แก้บรรทัดเดียวกัน\n", "my edit")
    job = run_job(ready_job(project_id), monkeypatch, [("tool", "Bash", {"command": "echo should-not-run > x.txt"}, 1_000)])
    assert job.status == "stopped" and "ชนกับงานของเลขา" in job.result and "รวม" in job.result
    assert git(root, "rev-parse", first.branch) == tip  # the secretary's branch as it was, the half merge undone (nothing ran)
    assert git(root, "worktree", "list").count("\n") == 0


def test_once_you_merge_the_next_job_starts_from_your_head(project, monkeypatch):
    from app.features.jobs import base
    root, project_id = project
    first = run_job(ready_job(project_id), monkeypatch, STEP_ONE)
    git(root, "stash", "-q")  # your uncommitted note aside, to merge
    git(root, *GIT, "merge", "-q", "--no-edit", first.branch)
    git(root, "stash", "pop", "-q")
    with session() as s:
        name = s.get(Project, project_id).name
    assert not base.find(root, name).on_branch  # merged: nothing of the secretary's is waiting
    second = run_job(ready_job(project_id, stuck="เขียนเทสต์"), monkeypatch, [("tool", "Bash", {"command": "echo x > y.txt"}, 1_000)])
    assert second.status == "done" and "เริ่มจาก main" in second.result


def test_the_secretarys_branch_open_in_your_folder_stops_the_job_before_it_starts(project, monkeypatch):
    root, project_id = project
    first = run_job(ready_job(project_id), monkeypatch, STEP_ONE)
    git(root, "stash", "-q")
    git(root, "checkout", "-q", first.branch)
    with pytest.raises(runner.RunError) as exc:
        asyncio.run(runner.start(ready_job(project_id, stuck="เขียนเทสต์")))
    assert "สลับกลับไป branch ของคุณก่อน" in str(exc.value)
    git(root, "checkout", "-q", "main")
    git(root, "stash", "pop", "-q")


# ------------------------------------------------------------------ the budget counts what Claude writes as it writes
def test_writing_counted_as_it_streams_stops_it_over_budget(project, monkeypatch):
    _, project_id = project
    script = [("stream", "msg_1", 6_000, 100), ("stream", "msg_1", 6_000, 5_000),  # the same call: 11k once it has written 5k
              ("tool", "Write", {"file_path": "late.py", "content": "x\n"}, 1)]
    job = run_job(ready_job(project_id, budget=10_000), monkeypatch, script)
    assert job.status == "stopped" and job.result.startswith("หยุด: เกินงบ") and job.used == 11_000


def test_a_job_that_ends_a_little_over_budget_says_so(project, monkeypatch):
    _, project_id = project
    monkeypatch.setattr(FakeClient, "extra", 300)  # the final report counts the last call's words in full
    job = run_job(ready_job(project_id, budget=4_000), monkeypatch,
                  [("tool", "Write", {"file_path": "a.py", "content": "a = 1\n"}, 3_900)])
    assert job.status == "done" and job.result.startswith("ทำเสร็จ (เกินงบ +200 ตอนจบ)")


def test_the_job_is_told_this_machine_has_python3(project, monkeypatch):
    _, project_id = project
    monkeypatch.setattr(runner.shutil, "which", lambda name: None if name == "python" else f"/usr/bin/{name}")
    run_job(ready_job(project_id), monkeypatch, [("tool", "Write", {"file_path": "a.py", "content": "a\n"}, 100)])
    assert "เครื่องนี้มีคำสั่ง python3 ไม่มีคำสั่ง python" in FakeClient.last.options.system_prompt["append"]
