"""B5's jobs page, the briefs' lines about background work, and the menu's counts."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.api import jobs as api
from app.api import settings as settings_api
from app.core import db
from app.core.db import now, session
from app.core.rules import book
from app.core.tables import Decision
from app.features.briefs import day
from app.features.jobs.tables import Job
from app.features.projects.tables import Project


@pytest.fixture(scope="module", autouse=True)
def rows(tmp_path_factory):
    db.migrate()
    book.seed()
    folder = tmp_path_factory.mktemp("page-proj")
    (folder / ".git").mkdir()  # enough for the gate (it checks is_git, not the folder)
    with session() as s:
        p = Project(name="page-proj", path=str(folder), potential="S", urgency=4, allow_jobs=True, is_git=True, status="active",
                    progress={})
        s.add(p)
        s.flush()
        d = Decision(kind="job", title="page-proj: กราฟ", detail={"job_id": None, "project": "page-proj", "budget": 60_000,
                                                                "risks": ["โหลดของจากภายนอก"], "why": "งานเสี่ยงสูง: โหลดของจากภายนอก"})
        s.add(d)
        s.flush()
        asking = Job(project_id=p.id, project=p.name, status="asking", title="กราฟ", steps=["a"], model="opus", effort="high",
                     estimate=50_000, budget=60_000, risks=["download"], decision_id=d.id, rule_ok=False,
                     rule_why="งานเสี่ยงสูง: โหลดของจากภายนอก")
        s.add(asking)
        s.flush()
        d.detail = {**d.detail, "job_id": asking.id}
        s.add(Job(project_id=p.id, project=p.name, status="done", title="บทที่ 1", finished_at=now() - timedelta(hours=3),
                  started_at=now() - timedelta(hours=4), result="ทำเสร็จ · 2 commit บน secretary/9-page-proj · ใช้ 80,000 / งบ 90,000 โทเคน\nสรุป"))
        s.add(Job(project_id=p.id, project=p.name, status="stopped", title="บทที่ 2", finished_at=now() - timedelta(hours=2),
                  result="หยุด: เกินงบ · 0 commit บน secretary/10-page-proj · ใช้ 20,000 / งบ 15,000 โทเคน"))
        return {"decision": d.id, "job": asking.id}


def test_the_page_has_the_queue_the_kpis_and_what_was_done(rows):
    page = api.jobs_page()
    mine = [j for j in page["queue"] if j["project"] == "page-proj"]
    assert [j["status"] for j in mine] == ["asking"] and mine[0]["high_risk"] and mine[0]["risks"] == ["โหลดของจากภายนอก"]
    assert mine[0]["efforts"]["medium"] == 36_000 and mine[0]["efforts"]["xhigh"] == 90_000  # what the effort stepper says
    assert page["kpi"]["asking"] >= 1 and page["kpi"]["over_budget"] >= 1
    ends = [j["finished_at"] for j in page["recent"]]
    assert ends == sorted(ends, reverse=True)  # newest first (other files' jobs share this list of 10)
    assert "บทที่ 2" in [j["title"] for j in page["recent"] if j["project"] == "page-proj"]
    assert page["approval_days"] == 3 and page["window"] == "01:00–06:00"


def test_the_briefs_say_what_ran_and_what_waits(rows):
    lines = day.jobs_finished(now() - timedelta(hours=12), now())
    assert "page-proj: บทที่ 1 · ทำเสร็จ · 2 commit บน secretary/9-page-proj" in lines
    assert "page-proj: บทที่ 2 · หยุด: เกินงบ · 0 commit บน secretary/10-page-proj" in lines
    assert "รอคุณอนุมัติ: " in day.jobs_waiting() and "page-proj" in day.jobs_waiting()


def test_the_menu_counts_plans_waiting_and_projects_on_the_go(rows):
    counts = settings_api.work_counts()
    assert counts["jobs"] >= 1 and counts["projects"] >= 1


def test_approving_on_the_web(rows):
    out = asyncio.run(api.answer(rows["decision"], api.AnswerIn(approve=True)))
    assert out["job"]["status"] == "ready" and out["job"]["approved_until"]
    with session() as s:
        assert s.get(Decision, rows["decision"]).status == "approved"
        assert s.scalar(select(Job.status).where(Job.id == rows["job"])) == "ready"


def test_tamtor_plans_at_once_so_a_plan_that_asks_is_in_the_bell_straight_away(rows, tmp_path, monkeypatch):
    from app.core import llm
    from app.features.jobs import quota

    folder = tmp_path / "now-proj"
    (folder / ".git").mkdir(parents=True)
    with session() as s:
        p = Project(name="now-proj", path=str(folder), potential="B", urgency=2, allow_jobs=True, is_git=True, progress={})
        s.add(p)
        s.flush()
        project_id = p.id

    async def planner(task, prompt, **kw):
        assert task == "job_plan" and "[ผู้ใช้สั่ง] ติดตั้ง requests แล้วดึงเว็บ" in prompt
        return llm.Reply(text='{"title": "ดึงเว็บ", "steps": ["pip install requests", "เขียน fetch.py"], "model": "sonnet",'
                              ' "effort": "low", "estimate": 40000, "risks": ["download"]}', model="claude-opus-5-5", effort="high")

    async def week(max_age=None):
        return 90.0
    monkeypatch.setattr(llm, "run", planner)
    monkeypatch.setattr(quota, "week_left", week)
    out = asyncio.run(api.add_job(api.NewJob(project_id=project_id, note="ติดตั้ง requests แล้วดึงเว็บ")))
    assert out["go"] is False and out["why"] == "งานเสี่ยงสูง: โหลดของจากภายนอก"
    with session() as s:
        job = s.get(Job, out["id"])
        assert job.status == "asking" and s.get(Decision, job.decision_id).status == "pending"
