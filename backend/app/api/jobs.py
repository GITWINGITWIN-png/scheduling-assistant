"""B5's web API for the background work (W4): the quota and the line, what's running, the queue
and its plans (with the model and effort to change before you approve), what was done, and
the buttons: ทำต่อ, วางแผนเลย, อนุมัติ · แก้แผน · ไม่เอา, ทำเลย, หยุด. The rule book (W8) has its
own, api/rules.py."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.core import clock as clock_mod
from app.core.db import now, session
from app.core.rules import book
from app.core.rules.check import APPROVAL_DAYS
from app.features import decisions
from app.features.jobs import plan as plans
from app.features.jobs import queue, quota, runner
from app.features.jobs.tables import Job
from app.features.projects.tables import Project

router = APIRouter(prefix="/api")


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def quota_view(reading) -> dict | None:
    if reading is None:
        return None
    return {"week_left": reading.week_left, "week_resets_at": _iso(reading.week_resets_at), "five_left": reading.five_left,
            "five_resets_at": _iso(reading.five_resets_at), "at": _iso(reading.at), "source": reading.source,
            "line": book.line(), "fresh": quota.latest() is not None}


@router.get("/quota")
def get_quota() -> dict:
    """The newest reading of any age (the page says how old it is), and the 70% line."""
    return {"quota": quota_view(quota.latest(max_age=None)), "line": book.line()}


@router.post("/quota/read")
async def read_quota() -> dict:
    """อ่านตอนนี้: a tiny call to hear the current numbers."""
    return {"quota": quota_view(await quota.probe()), "line": book.line()}


# ------------------------------------------------------------------ ทำเลย · หยุด (B5.7)
@router.post("/jobs/{job_id}/run")
async def run_now(job_id: int) -> dict:
    """ทำเลย: start a ready job now, outside the night window too (it is checked again first)."""
    try:
        return {"line": await runner.start(job_id, night=False)}
    except runner.RunError as exc:
        raise HTTPException(409, str(exc))


@router.post("/jobs/{job_id}/stop")
def stop_job(job_id: int) -> dict:
    """หยุด: the run stops within seconds and keeps what it did, committed on its branch."""
    try:
        runner.stop(job_id)
    except runner.RunError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True}


# ------------------------------------------------------------------ the page (W4)
def job_view(j: Job, potentials: dict[int, str] | None = None) -> dict:
    risks = plans.names(j.risks)
    efforts = {e: plans.budget_for(plans.rescale(j.estimate, j.effort, e)) for e in plans.EFFORT_COST} if j.estimate else {}
    return {"id": j.id, "project_id": j.project_id, "project": j.project, "potential": (potentials or {}).get(j.project_id, ""),
            "source": j.source, "stuck_at": j.stuck_at,
            "note": j.note, "status": j.status, "title": j.title, "steps": j.steps, "model": j.model, "effort": j.effort,
            "estimate": j.estimate, "budget": j.budget, "used": j.used, "risks": risks, "high_risk": bool(risks),
            "rule_ok": j.rule_ok, "rule_why": j.rule_why, "decision_id": j.decision_id, "why": j.why,
            "approved_until": _iso(j.approved_until), "branch": j.branch, "result": j.result, "plan_tokens": j.plan_tokens,
            "planned_at": _iso(j.planned_at), "started_at": _iso(j.started_at), "finished_at": _iso(j.finished_at),
            "efforts": efforts}


def usage() -> dict:
    """Tokens the secretary used today and in 7 days, and today's background work."""
    from sqlalchemy import func

    from app.core.tables import LLMUsage
    from app.features.briefs import day

    start = day.day_start(day.today(now()))
    total = func.coalesce(func.sum(LLMUsage.tokens_in + LLMUsage.tokens_out), 0)
    with session() as s:
        today = s.scalar(select(total).where(LLMUsage.at >= start))
        jobs = s.scalar(select(total).where(LLMUsage.at >= start, LLMUsage.task.in_(("job", "job_plan"))))
        week = s.scalar(select(total).where(LLMUsage.at >= now() - timedelta(days=7)))
    return {"today": int(today), "jobs_today": int(jobs), "week": int(week)}


@router.get("/jobs")
def jobs_page() -> dict:
    queue.refresh()  # a project you just switched on shows its job straight away (no model: cheap)
    waiting = queue.ordered()
    with session() as s:
        running = s.scalar(select(Job).where(Job.status == "running"))
        recent = s.scalars(select(Job).where(Job.status.in_(("done", "stopped", "failed"))).order_by(Job.finished_at.desc())
                           .limit(10)).all()
        week = now() - timedelta(days=7)
        over = sum(1 for j in s.scalars(select(Job).where(Job.status == "stopped", Job.finished_at >= week))
                   if j.result.startswith("หยุด: เกินงบ"))
        everyone = s.scalars(select(Project)).all()
        pot = {p.id: p.potential for p in everyone}
        projects = [{"id": p.id, "name": p.name} for p in everyone if p.allow_jobs and not queue.blocked(p)]
        views = {"running": job_view(running, pot) if running else None, "recent": [job_view(j, pot) for j in recent]}
    return {"quota": {**(quota_view(quota.latest(max_age=None)) or {}), "line": book.line(), "auto": book.auto()},
            "usage": usage(),
            "kpi": {"auto": sum(1 for j in waiting if j.status == "ready"), "asking": sum(1 for j in waiting if j.status == "asking"),
                    "over_budget": over},
            "queue": [job_view(j, pot) for j in waiting], **views, "projects": sorted(projects, key=lambda p: p["name"].lower()),
            "round_on": clock_mod.enabled("jobs"), "window": "01:00–06:00", "approval_days": APPROVAL_DAYS}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewJob(Strict):
    project_id: int
    note: str = ""


@router.post("/jobs")
async def add_job(body: NewJob) -> dict:
    """ทำต่อ: a job for this project, planned at once (you asked for it, so it doesn't wait for the
    night): then the rule check, so a plan that asks is in #อนุมัติ straight away."""
    try:
        job_id, action_id = queue.add(body.project_id, body.note)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    try:
        verdict = await plans.make(job_id)
    except Exception as exc:  # a PlanError, or Claude unreachable: the job waits in the queue for วางแผนเลย
        return {"id": job_id, "action_id": action_id, "go": None, "why": f"ใส่คิวแล้ว แต่วางแผนไม่สำเร็จ: {exc}"}
    return {"id": job_id, "action_id": action_id, "go": verdict.go, "why": verdict.why}


@router.post("/jobs/{job_id}/plan")
async def plan_now(job_id: int) -> dict:
    """วางแผนเลย: Opus plans it now (instead of waiting for the night), then the rule check."""
    try:
        verdict = await plans.make(job_id)
    except plans.PlanError as exc:
        raise HTTPException(400, str(exc))
    return {"go": verdict.go, "why": verdict.why}


class EffortIn(Strict):
    model: str
    effort: str


@router.put("/jobs/{job_id}/effort")
def set_effort(job_id: int, body: EffortIn) -> dict:
    try:
        return job_view(plans.set_effort(job_id, body.model, body.effort))
    except plans.PlanError as exc:
        raise HTTPException(400, str(exc))


class BudgetIn(Strict):
    budget: int


@router.put("/jobs/{job_id}/budget")
def set_budget(job_id: int, body: BudgetIn) -> dict:
    """ตั้งงบเอง before approving (e.g. a low one, to see the runner stop by itself)."""
    try:
        return job_view(plans.set_budget(job_id, body.budget))
    except plans.PlanError as exc:
        raise HTTPException(400, str(exc))


class AnswerIn(Strict):
    approve: bool


@router.post("/jobs/decisions/{decision_id}")
async def answer(decision_id: int, body: AnswerIn) -> dict:
    """อนุมัติ 3 วัน or ไม่เอา, from the web; the #อนุมัติ card says so too."""
    try:
        job, action_id = plans.answer(decision_id, body.approve)
    except plans.PlanError as exc:
        raise HTTPException(400, str(exc))
    await decisions.settle_card(decision_id)
    return {"job": job_view(job), "action_id": action_id}


class ReviseIn(Strict):
    change: str


@router.post("/jobs/decisions/{decision_id}/revise")
async def revise(decision_id: int, body: ReviseIn) -> dict:
    """แก้แผน: Opus plans again with your change."""
    try:
        verdict = await plans.revise(decision_id, body.change)
    except plans.PlanError as exc:
        raise HTTPException(400, str(exc))
    await decisions.settle_card(decision_id)
    return {"go": verdict.go, "why": verdict.why}


@router.delete("/jobs/{job_id}")
def drop_job(job_id: int) -> dict:
    try:
        return {"action_id": queue.drop(job_id)}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
