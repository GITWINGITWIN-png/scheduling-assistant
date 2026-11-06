"""B5's background work queue and plans: which projects get a job, the planner's read-only view of
a project, the plan checked and budgeted, the rule check after planning, and your answers."""

import asyncio
import os
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core import actions, db, llm
from app.core.config import REPO_DIR
from app.core.db import now, session
from app.core.rules import book, learn
from app.core.tables import Decision, Rule
from app.features import ask
from app.features.jobs import plan, queue, quota, tools
from app.features.jobs.tables import Job
from app.features.projects.tables import Project


@pytest.fixture(scope="module", autouse=True)
def database():
    db.migrate()
    book.seed()


def git_repo(path: Path, files: dict[str, str]) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text)
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "start"],
                   check=True)
    return path


@pytest.fixture(scope="module")
def projects(tmp_path_factory):
    root = tmp_path_factory.mktemp("jobs-projects")
    alpha = git_repo(root / "jobs-alpha", {"PROGRESS.md": "- [x] เริ่ม\n- [ ] ทำกราฟ\n", "src/plot.py": "def plot():\n    return 1\n",
                                           ".gitignore": "out/\n", ".env": "SECRET=1\n"})
    (alpha / "out").mkdir()
    (alpha / "out" / "big.csv").write_text("ignored\n")
    beta = git_repo(root / "jobs-beta", {"PROGRESS.md": "- [ ] เขียนบท\n"})
    off = git_repo(root / "jobs-off", {"PROGRESS.md": "- [ ] รอ\n"})
    me = root / "jobs-self"
    os.symlink(REPO_DIR, me)  # my_secretary by another path: still itself
    rows = [Project(name="jobs-alpha", path=str(alpha), potential="A", urgency=3, allow_jobs=True, is_git=True,
                    progress={"next": "ทำกราฟ", "todo": 1, "done": 1}),
            Project(name="jobs-beta", path=str(beta), potential="S", urgency=1, allow_jobs=True, is_git=True,
                    progress={"next": "เขียนบท", "todo": 1, "done": 0}),
            Project(name="jobs-off", path=str(off), potential="S", urgency=5, allow_jobs=False, is_git=True,
                    progress={"next": "รอ", "todo": 1, "done": 0}),
            Project(name="jobs-self", path=str(me), potential="S", urgency=5, allow_jobs=True, is_git=True,
                    progress={"next": "B5", "todo": 1, "done": 0}),
            Project(name="jobs-plain", path=str(root), potential="S", urgency=5, allow_jobs=True, is_git=False,
                    progress={"next": "x", "todo": 1, "done": 0})]
    with session() as s:
        s.add_all(rows)
        s.flush()
        ids = {p.name: p.id for p in rows}
    return ids


def job_of(name: str) -> Job | None:
    with session() as s:
        j = s.scalar(select(Job).where(Job.project == name).order_by(Job.id.desc()))
        if j is not None:
            s.expunge(j)
    return j


def set_week(monkeypatch, value):
    async def fake(max_age=None):
        return value
    monkeypatch.setattr(quota, "week_left", fake)


def fake_planner(monkeypatch, answer: str, seen: list | None = None):
    async def fake_run(task, prompt, **kw):
        if seen is not None:
            seen.append((task, prompt, kw))
        return llm.Reply(text=answer, model="claude-opus-5-5", effort="high", tokens_in=9000, tokens_out=1000)
    monkeypatch.setattr(llm, "run", fake_run)


PLAN = ('```json\n{"title": "ทำกราฟรายงาน", "steps": ["อ่าน src/plot.py", "เพิ่มกราฟแท่ง", "รันเทสต์"], "model": "sonnet",'
        ' "effort": "medium", "estimate": 50000, "risks": [], "why": "งานตรงไปตรงมา"}\n```')


# ------------------------------------------------------------------ the queue
def test_only_projects_you_opened_get_a_job_and_only_one(projects):
    new = queue.refresh()
    names = {job_of(n).project for n in ("jobs-alpha", "jobs-beta") if job_of(n)}
    assert names == {"jobs-alpha", "jobs-beta"} and len(new) == 2
    assert all(job_of(n) is None for n in ("jobs-off", "jobs-self", "jobs-plain"))
    assert queue.refresh() == []  # one open job per project
    assert job_of("jobs-alpha").stuck_at == "ทำกราฟ" and job_of("jobs-alpha").source == "progress"
    order = [j.project for j in queue.ordered() if j.project.startswith("jobs-")]
    assert order == ["jobs-beta", "jobs-alpha"]  # potential S before A


def test_the_secretary_never_queues_work_on_itself(projects):
    assert queue.blocked(Project(name="x", path=str(REPO_DIR), is_git=True, allow_jobs=True)) == "เลขาไม่แก้โค้ดของตัวเองขณะทำงาน"
    with pytest.raises(ValueError):
        queue.add(projects["jobs-self"])
    with pytest.raises(ValueError):
        queue.add(projects["jobs-off"], "ทำเถอะ")  # the switch is the gate, for ทำต่อ too


def test_tamtor_needs_a_step_or_a_note_and_one_job_at_a_time(projects):
    with pytest.raises(ValueError):
        queue.add(projects["jobs-alpha"])  # it has a job already
    with session() as s:
        s.get(Project, projects["jobs-off"]).allow_jobs = True
        s.get(Project, projects["jobs-off"]).progress = {}
    with pytest.raises(ValueError):
        queue.add(projects["jobs-off"])  # nothing in PROGRESS.md and no note
    job_id, action_id = queue.add(projects["jobs-off"], "เขียน README")
    assert job_of("jobs-off").note == "เขียน README" and job_of("jobs-off").source == "you"
    asyncio.run(actions.undo(action_id))
    assert job_of("jobs-off").status == "dropped"
    with session() as s:
        s.get(Project, projects["jobs-off"]).allow_jobs = False


# ------------------------------------------------------------------ what the planner may read
def test_the_planner_sees_only_the_project_and_no_secrets(projects):
    with session() as s:
        root = Path(s.get(Project, projects["jobs-alpha"]).path)
    files = tools.list_files(root).splitlines()
    assert "src/plot.py" in files and "PROGRESS.md" in files
    assert ".env" not in files and not any(f.startswith("out/") for f in files)  # secrets and ignored files
    assert tools.read_file(root, "src/plot.py") == "1: def plot():\n2:     return 1"
    assert tools.read_file(root, "src/plot.py", start=2) == "2:     return 1"
    for bad in ("../jobs-beta/PROGRESS.md", "/etc/passwd", ".env", str(Path.home() / ".ssh/id_rsa")):
        assert tools.read_file(root, bad).startswith("อ่านไม่ได้")
    os.symlink("/etc", root / "etc-link")
    assert tools.read_file(root, "etc-link/hostname").startswith("อ่านไม่ได้: อยู่นอกโฟลเดอร์โปรเจค")
    assert tools.search(root, "return 1") == "src/plot.py:2:    return 1"
    assert tools.search(root, "SECRET") == "(ไม่พบ)"


# ------------------------------------------------------------------ the plan, checked and budgeted
def test_a_plan_is_checked_before_it_is_used():
    known = {"download", "push"}
    p = plan.read_plan('{"steps": ["a", "b"], "model": "gpt", "effort": "turbo", "estimate": 100, "risks": ["push", "magic"]}', known)
    assert (p.model, p.effort, p.estimate, p.risks, p.title) == ("opus", "high", 5000, ["push"], "a")
    for bad in ("ไม่ใช่ JSON", '{"steps": [], "estimate": 9000}', '{"steps": ["a"], "estimate": "lots"}'):
        with pytest.raises(plan.PlanError):
            plan.read_plan(bad, known)
    assert plan.budget_for(50_000) == 60_000
    assert plan.rescale(150_000, "high", "medium") == 90_000 and plan.rescale(150_000, "high", "xhigh") == 225_000


def test_a_low_risk_plan_above_the_line_is_ready(projects, monkeypatch):
    seen = []
    fake_planner(monkeypatch, PLAN, seen)
    set_week(monkeypatch, 82.0)
    job = job_of("jobs-alpha")
    verdict = asyncio.run(plan.make(job.id))
    after = job_of("jobs-alpha")
    assert verdict.go and after.status == "ready" and after.rule_why == "โควตาเหลือ 82% เกินเส้น 70%"
    assert (after.title, after.model, after.effort, after.estimate, after.budget) == ("ทำกราฟรายงาน", "sonnet", "medium", 50_000, 60_000)
    assert after.plan_tokens == 10_000 and after.decision_id is None
    task, prompt, kw = seen[0]
    assert task == "job_plan" and "[ขั้นที่ค้างใน PROGRESS.md] ทำกราฟ" in prompt and "- download: โหลดของจากภายนอก" in prompt
    assert [t.name for t in kw["tools"]] == ["list_files", "read_file", "search"]


def test_words_in_the_plan_flag_a_risk_the_planner_left_out(projects, monkeypatch):
    fake_planner(monkeypatch, PLAN.replace('"เพิ่มกราฟแท่ง"', '"pip install matplotlib แล้วเพิ่มกราฟแท่ง"'))
    set_week(monkeypatch, 95.0)
    asked = []

    async def hook(job_id, decision_id):
        asked.append((job_id, decision_id))
    monkeypatch.setattr(plan, "ASKED", [hook])
    job = job_of("jobs-beta")
    verdict = asyncio.run(plan.make(job.id))
    after = job_of("jobs-beta")
    assert not verdict.go and verdict.why == "งานเสี่ยงสูง: โหลดของจากภายนอก"
    assert after.status == "asking" and after.risks == ["download"] and asked == [(after.id, after.decision_id)]
    with session() as s:
        d = s.get(Decision, after.decision_id)
        assert (d.kind, d.status, d.title, d.detail["budget"], d.detail["risks"]) == ("job", "pending", "jobs-beta: ทำกราฟรายงาน",
                                                                                    60_000, ["โหลดของจากภายนอก"])


def test_no_quota_reading_asks_even_for_low_risk(projects, monkeypatch):
    fake_planner(monkeypatch, PLAN)
    set_week(monkeypatch, None)
    job = job_of("jobs-alpha")
    assert asyncio.run(plan.make(job.id)).why == "อ่านโควตาไม่ได้ ทุกแผนถามคุณก่อน"
    assert job_of("jobs-alpha").status == "asking"


# ------------------------------------------------------------------ your answers
def test_changing_the_effort_before_approving_scales_the_budget(projects):
    job = job_of("jobs-beta")
    plan.set_effort(job.id, "opus", "high")
    after = job_of("jobs-beta")
    assert (after.model, after.effort, after.estimate, after.budget) == ("opus", "high", 83_333, 100_000)
    with session() as s:
        assert s.get(Decision, after.decision_id).detail["effort"] == "high"
    with pytest.raises(plan.PlanError):
        plan.set_effort(job_of("jobs-alpha").id + 999, "opus", "low")


def test_you_can_set_a_budget_of_your_own_before_approving(projects):
    job = job_of("jobs-beta")
    with pytest.raises(plan.PlanError):
        plan.set_budget(job.id, 500)  # too small to be a budget
    plan.set_budget(job.id, 8_000)
    assert job_of("jobs-beta").budget == 8_000
    plan.set_effort(job.id, "opus", "high")  # the effort's budget again
    assert job_of("jobs-beta").budget == 100_000


def test_approving_makes_the_plan_good_for_three_days_then_it_can_be_undone(projects, monkeypatch):
    job = job_of("jobs-beta")
    with pytest.raises(ask.DecisionError):
        ask.decide(job.decision_id, "approve")  # the chat plan's buttons don't answer background plans
    done, action_id = plan.answer(job.decision_id, approve=True)
    after = job_of("jobs-beta")
    assert after.status == "ready" and abs((after.approved_until - now()) - timedelta(days=3)) < timedelta(minutes=1)
    set_week(monkeypatch, None)
    assert asyncio.run(plan.decide(after.id)).go  # approved: no quota reading needed (checked again before it starts)
    with pytest.raises(plan.PlanError):
        plan.answer(job.decision_id, approve=False)  # answered already
    asyncio.run(actions.undo(action_id))
    back = job_of("jobs-beta")
    assert back.status == "asking" and back.approved_until is None
    with session() as s:
        assert s.get(Decision, back.decision_id).status == "pending"


def test_revising_asks_the_planner_again_with_your_change(projects, monkeypatch):
    seen = []
    fake_planner(monkeypatch, PLAN, seen)
    set_week(monkeypatch, 50.0)
    job = job_of("jobs-beta")
    old_decision = job.decision_id
    verdict = asyncio.run(plan.revise(old_decision, "ไม่ต้องลง matplotlib ใช้ของที่มี"))
    assert not verdict.go and verdict.why == "โควตาเหลือ 50% ไม่เกินเส้น 70%"
    assert "[ผู้ใช้ขอแก้] ไม่ต้องลง matplotlib ใช้ของที่มี" in seen[0][1] and "[แผนเดิม]" in seen[0][1]
    after = job_of("jobs-beta")
    assert after.decision_id != old_decision and after.risks == []
    with session() as s:
        assert s.get(Decision, old_decision).status == "revised"


def test_an_approval_covers_that_plan_only(projects, monkeypatch):
    job = job_of("jobs-beta")
    plan.answer(job.decision_id, approve=True)
    assert job_of("jobs-beta").status == "ready"
    fake_planner(monkeypatch, PLAN)
    set_week(monkeypatch, 50.0)
    assert not asyncio.run(plan.make(job.id)).go  # planned again: the new plan needs its own yes
    assert job_of("jobs-beta").status == "asking" and job_of("jobs-beta").approved_until is None


def test_rejecting_takes_the_job_out(projects):
    job = job_of("jobs-beta")
    plan.answer(job.decision_id, approve=False)
    assert job_of("jobs-beta").status == "rejected"
    assert queue.refresh() == [] and job_of("jobs-beta").status == "rejected"  # the same step doesn't come back each night
    job_id, _ = queue.add(job.project_id, "ลองใหม่ แบบไม่ลงแพ็กเกจ")  # ทำต่อ always can
    assert job_of("jobs-beta").id == job_id and job_of("jobs-beta").status == "queued"
    queue.drop(job_id)
    assert queue.refresh() == []  # taken out: not back by itself either
    with session() as s:
        s.get(Project, job.project_id).progress = {"next": "บทที่ 2", "todo": 1, "done": 1}
    assert len(queue.refresh()) == 1  # the project moved on: its new step is taken up
    assert job_of("jobs-beta").stuck_at == "บทที่ 2" and job_of("jobs-beta").status == "queued"


def test_switching_a_project_off_drops_its_job_and_withdraws_the_request(projects):
    job = job_of("jobs-alpha")
    assert job.status == "asking"
    with session() as s:
        s.get(Project, projects["jobs-alpha"]).allow_jobs = False
    queue.refresh()
    assert job_of("jobs-alpha").status == "paused"
    with session() as s:
        assert s.get(Decision, job.decision_id).status == "cancelled"
        s.get(Project, projects["jobs-alpha"]).allow_jobs = True
    assert queue.refresh() == [] and job_of("jobs-alpha").id == job.id  # back with the project, the same job
    back = job_of("jobs-alpha")
    assert back.status == "queued" and back.title == "" and back.decision_id is None  # to be planned again


def test_a_job_whose_project_was_switched_off_is_paused_when_its_turn_comes(projects, monkeypatch):
    fake_planner(monkeypatch, PLAN)
    queue.refresh()
    job = job_of("jobs-alpha")
    assert job.status == "queued"
    with session() as s:
        s.get(Project, projects["jobs-alpha"]).allow_jobs = False
    with pytest.raises(plan.PlanError):
        asyncio.run(plan.make(job.id))
    assert job_of("jobs-alpha").status == "paused"  # and it stays so
    with session() as s:
        s.get(Project, projects["jobs-alpha"]).allow_jobs = True


def test_five_approvals_in_a_row_are_offered_as_a_standing_rule(projects):
    at = now() + timedelta(days=200)  # far from the other rows
    with session() as s:
        for i in range(5):
            s.add(Decision(kind="job", title="x", detail={"project": "jobs-learn"}, status="approved", answered_at=at - timedelta(days=i)))
    learn.refresh(at=at)
    with session() as s:
        r = s.scalar(select(Rule).where(Rule.key == "learned.job_auto.jobs-learn"))
        assert (r.status, r.evidence, r.effect) == ("pending", "อนุมัติ 5 จาก 5 ใน 4 สัปดาห์", {"type": "job_auto", "project": "jobs-learn"})
        s.add(Decision(kind="job", title="x", detail={"project": "jobs-learn"}, status="rejected", answered_at=at))
    learn.refresh(at=at)
    with session() as s:
        assert s.scalar(select(Rule).where(Rule.key == "learned.job_auto.jobs-learn")) is None  # one no: not a pattern
