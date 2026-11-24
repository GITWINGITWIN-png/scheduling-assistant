"""Plans for the background work (3.2, B5.6): Opus reads where a project is stuck and plans how to
go on; then the rule checker decides whether the plan may start by itself.

The planner (task "job_plan": Opus, effort high, changeable in settings) gets the stuck step,
your note (it sets how far the job goes), where the job starts (base.py: the secretary's own
branch while its work isn't merged), your rules for the background work (the rule book's notes)
and the high-risk kinds, and may look at the project as it is there, through three read-only
tools (tools.py). It answers with the
steps, the model and effort to do them with, the tokens it expects, and the high-risk kinds the
plan has. The plan's own words are checked against the 7 agreed kinds too (book.flags), so a
kind the planner left out still asks.

Budget = estimate × 1.2. Changing the effort before you approve scales the estimate
(EFFORT_COST): the W4 panel's "lower to medium ≈ 90k, raise to xhigh ≈ 220k".

`decide()` is the rule check (core/rules/check.py), done after planning and again just before a
job starts. Go: the job is ready (tonight's window, or "do it now"). Ask: a "job" decision waits in
#Approval (ASKED hooks post the card); Approve makes this plan good for 3 days, Revise plan asks
Opus again with your change, Decline takes the job out.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from app.core import actions, llm
from app.core.db import now, session
from app.core.rules import book, learn
from app.core.rules.check import APPROVAL_DAYS, Verdict, check
from app.core.tables import Decision
from app.core.timefmt import thai_datetime
from app.features.jobs import base, quota
from app.features.jobs.queue import blocked, close_ask
from app.features.jobs.tables import Job
from app.features.jobs.tools import project_tools
from app.features.projects.tables import Project

log = logging.getLogger(__name__)

EFFORT_COST = {"low": 0.4, "medium": 0.6, "high": 1.0, "xhigh": 1.5, "max": 2.0}  # tokens for the same work, relative
MARGIN = 1.2  # budget = estimate × 1.2
ESTIMATE_RANGE = (5_000, 2_000_000)
MAX_STEPS = 8

# Called with (job id, decision id) when a plan has to ask you (cards.py posts the D5 card).
ASKED: list[Callable[[int, int], Awaitable[None]]] = []

Via = tuple[str, str]
WEB: Via = ("หน้างานเบื้องหลัง", "")

SYSTEM = """วางแผนงานเบื้องหลังหนึ่งงานในโปรเจคของผู้ใช้ Claude Code จะทำตามแผนนี้เองตอนกลางคืน บน branch แยกของงาน ไม่ push
ดูโปรเจคด้วยเครื่องมือ (อ่านอย่างเดียว) เท่าที่จำเป็น เริ่มจาก PROGRESS.md แล้วตอบเป็น JSON ก้อนเดียว ไม่มีข้อความอื่น:
{"title": "ชื่องานสั้นๆ", "steps": ["ขั้นที่ทำได้จริง 1–6 ข้อ"], "model": "sonnet" หรือ "opus",
 "effort": "low" | "medium" | "high" | "xhigh" | "max", "estimate": โทเคนทั้งงาน (จำนวนเต็ม),
 "risks": ["รหัสงานเสี่ยงสูงที่แผนนี้มี"], "why": "ทำไมเลือกโมเดล effort และงบนี้ หนึ่งบรรทัด"}
- ถ้าผู้ใช้สั่งมา ทำตามที่สั่ง (สั่งให้ทำทุกขั้นที่เหลือ ก็วางหลายขั้นได้ในงบที่สมเหตุผล) · ถ้าไม่ได้สั่งอะไร หรือสั่งแค่ "ทำต่อ" ทำเฉพาะขั้นที่ค้าง
- งานเริ่มจากจุดที่บอกใน [เริ่มจาก] ไฟล์ที่อ่านได้คือไฟล์ ณ จุดนั้น ขั้นที่ติ๊กแล้วใน PROGRESS.md ตรงนั้นคือทำเสร็จแล้ว ห้ามทำซ้ำ
- ในขั้นตอนเขียนแต่สิ่งที่จะทำ ไม่ต้องเขียนข้อห้าม (เช่น ห้าม push ห้ามติดตั้ง) ระบบกันไว้ให้แล้ว
- เลือกโมเดลและ effort ที่พอดีกับงาน ไม่เกินจำเป็น: งานตรงไปตรงมาใช้ sonnet · งานที่ต้องคิดเยอะใช้ opus
- estimate นับทุกโทเคนที่อ่านและเขียนตลอดงาน รวมการอ่านไฟล์และรันเทสต์ซ้ำ · ทุกครั้งที่ Claude Code คิด จะอ่านคำสั่งของระบบราว 10k โทเคนซ้ำ (นับด้วย): งานเล็กมาก (ไฟล์เดียว) ราว 50k · งานกลางราว 150k–300k
- risks ใส่ทุกข้อที่เข้าข่ายหรืออาจเข้าข่าย ถ้าไม่มีให้ใส่ []"""


class PlanError(ValueError):
    """The plan couldn't be made or used; the message says why, in words."""


@dataclass
class Plan:
    title: str
    steps: list[str]
    model: str
    effort: str
    estimate: int
    risks: list[str] = field(default_factory=list)
    why: str = ""


def budget_for(estimate: int) -> int:
    return round(estimate * MARGIN)


def rescale(estimate: int, old: str, new: str) -> int:
    """The same work at another effort."""
    return round(estimate * EFFORT_COST[new] / EFFORT_COST[old])


def _json(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def read_plan(text: str, known: set[str]) -> Plan:
    """The planner's answer, checked (no model). Raises PlanError when it isn't a usable plan."""
    data = _json(text)
    if data is None:
        raise PlanError("คนวางแผนไม่ได้ตอบเป็นแผน")
    steps = [str(x).strip()[:300] for x in data.get("steps") or [] if str(x).strip()][:MAX_STEPS]
    if not steps:
        raise PlanError("แผนไม่มีขั้นตอน")
    try:
        estimate = int(data.get("estimate") or 0)
    except (TypeError, ValueError):
        estimate = 0
    if estimate <= 0:
        raise PlanError("แผนไม่ได้ประมาณโทเคน")
    lo, hi = ESTIMATE_RANGE
    model = data.get("model") if data.get("model") in llm.MODELS else "opus"
    effort = data.get("effort") if data.get("effort") in EFFORT_COST else "high"
    risks = [k for k in dict.fromkeys(data.get("risks") or []) if k in known]
    return Plan(str(data.get("title") or steps[0]).strip()[:200], steps, model, effort, max(lo, min(hi, estimate)),
                risks, str(data.get("why") or "").strip()[:300])


def _prompt(job: Job, risks: list[dict], change: str, start: str = "") -> str:
    lines = [f"[โปรเจค] {job.project}"]
    if start:
        lines.append(f"[เริ่มจาก] {start}")
    if job.stuck_at:
        lines.append(f"[ขั้นที่ค้างใน PROGRESS.md] {job.stuck_at}")
    if job.note:
        lines.append(f"[ผู้ใช้สั่ง] {job.note}")
    lines.append("[รหัสงานเสี่ยงสูง]")
    lines += [f"- {r['key']}: {r['text']}" + (f" ({r['hint']})" if r["hint"] else "") for r in risks]
    if change:
        lines += ["[แผนเดิม]", *[f"{i}. {s}" for i, s in enumerate(job.steps, 1)],
                  f"(โมเดล {job.model} · effort {job.effort} · {job.estimate} โทเคน)", f"[ผู้ใช้ขอแก้] {change}",
                  "เขียนแผนใหม่ทั้งแผนตามที่ขอแก้"]
    return "\n".join(lines)


def names(keys: list[str]) -> list[str]:
    """High-risk keys as the rule book shows them."""
    by = {r["key"]: r["text"] for r in book.risks()}
    return [by.get(k, k) for k in keys]


async def make(job_id: int, *, change: str = "", via: Via = WEB) -> Verdict:
    """Plan the job (again, with your change, for Revise plan), then check it against the rules."""
    with session() as s:
        job = s.get(Job, job_id)
        if job is None:
            raise PlanError("ไม่พบงานนี้")
        if job.status not in ("queued", "asking", "ready"):
            raise PlanError("งานนี้เริ่มไปแล้วหรือจบแล้ว")
        p = s.get(Project, job.project_id)
        if why := blocked(p):  # saved first: raising inside the session would roll it back
            job.status, job.result = "paused", why  # it comes back with the project (queue.refresh)
            close_ask(s, job)
        elif job.decision_id and (d := s.get(Decision, job.decision_id)) is not None and d.status == "pending":
            d.status, d.answered_at = "revised", now()  # the plan that waited for you is being replaced
        root = Path(p.path) if p is not None else None
        s.flush()  # before expunge, or the changes above are lost
        s.expunge(job)
    if why:
        raise PlanError(why)
    risks = book.risks()
    where = base.find(root, job.project)  # what the job will start from: the planner reads the same
    reply = await llm.run("job_plan", _prompt(job, risks, change, where.words()), system=SYSTEM + book.prompt_block("jobs"),
                          tools=project_tools(root, where.ref), max_turns=16)
    tokens = reply.tokens_in + reply.tokens_out
    try:
        plan = read_plan(reply.text, {r["key"] for r in risks})
    except PlanError as exc:
        with session() as s:
            j = s.get(Job, job_id)
            j.plan_tokens += tokens
            j.result = f"วางแผนไม่สำเร็จ: {exc}"
        actions.record("job.plan", "วางแผนงานเบื้องหลังไม่สำเร็จ", f"{job.project}: {exc}", source_label=via[0],
                       source_url=via[1], tokens=tokens)
        raise
    words = book.flags(" ".join([plan.title, *plan.steps]))
    with session() as s:
        j = s.get(Job, job_id)
        j.title, j.steps, j.model, j.effort, j.why = plan.title, plan.steps, plan.model, plan.effort, plan.why
        j.estimate, j.budget = plan.estimate, budget_for(plan.estimate)
        j.risks = list(dict.fromkeys([*plan.risks, *words]))
        j.plan_tokens += tokens
        j.planned_at, j.result = now(), ""
        j.approved_until = None  # a new plan needs its own approval ("that plan only")
        if change:
            j.note = (j.note + "\n" if j.note else "") + f"ขอแก้: {change}"
    actions.record("job.plan", "แก้แผนงานเบื้องหลังตามที่ขอ" if change else "วางแผนงานเบื้องหลัง", f"{job.project}: {plan.title}",
                   source_label=via[0], source_url=via[1], tokens=tokens)
    return await decide(job_id)


async def decide(job_id: int, at: datetime | None = None) -> Verdict:
    """The rule check for a planned job: ready, or ask you (once per plan)."""
    at = at or now()
    with session() as s:
        job = s.get(Job, job_id)
        risks, project, approved_until = list(job.risks), job.project, job.approved_until
    week_left = await quota.week_left()
    verdict = check(risks=names(risks), week_left=week_left, at=at, line=book.line(), auto=book.auto(),
                    approved_until=approved_until, standing=book.standing_for(project))
    asked = None
    with session() as s:
        job = s.get(Job, job_id)
        job.rule_ok, job.rule_why = verdict.go, verdict.why
        if verdict.go:
            job.status = "ready"
        else:
            job.status = "asking"
            pending = job.decision_id and (d := s.get(Decision, job.decision_id)) is not None and d.status == "pending"
            if not pending:
                d = Decision(kind="job", title=f"{job.project}: {job.title}",
                             detail={"job_id": job.id, "project": job.project, "stuck_at": job.stuck_at, "steps": job.steps,
                                     "model": job.model, "effort": job.effort, "budget": job.budget,
                                     "risks": names(job.risks), "why": verdict.why})
                s.add(d)
                s.flush()
                job.decision_id = asked = d.id
    if asked is not None:
        for hook in ASKED:
            try:
                await hook(job_id, asked)
            except Exception:
                log.exception("couldn't post the plan of job %s to #อนุมัติ", job_id)
    return verdict


def _pending_job(s, decision_id: int) -> tuple[Decision, Job]:
    d = s.get(Decision, decision_id)
    if d is None or d.kind != "job":
        raise PlanError("ไม่พบแผนนี้")
    if d.status != "pending":
        raise PlanError("แผนนี้ตัดสินไปแล้ว")
    job = s.get(Job, d.detail["job_id"])
    if job is None or job.status != "asking" or job.decision_id != d.id:
        raise PlanError("งานนี้ไม่ได้รอคำตอบแล้ว")
    return d, job


def answer(decision_id: int, approve: bool, *, via: Via = WEB) -> tuple[Job, int]:
    """Approve 3 days (this plan only) or Decline. -> (the job, the action id)."""
    at = now()
    with session() as s:
        d, job = _pending_job(s, decision_id)
        old = {"status": job.status, "approved_until": job.approved_until.isoformat() if job.approved_until else None,
               "rule_ok": job.rule_ok, "rule_why": job.rule_why}
        d.answered_at = at
        if approve:
            d.status = "approved"
            job.status, job.approved_until = "ready", at + timedelta(days=APPROVAL_DAYS)
            job.rule_ok, job.rule_why = True, f"คุณอนุมัติแผนนี้แล้ว ใช้ได้ถึง {thai_datetime(job.approved_until)}"
        else:
            d.status = "rejected"
            job.status, job.result = "rejected", "คุณไม่เอาแผนนี้"
        s.flush()
        s.expunge(job)
    action_id = actions.record("job.approve" if approve else "job.reject",
                               f"อนุมัติแผนงานเบื้องหลัง {APPROVAL_DAYS} วัน" if approve else "ไม่เอาแผนงานเบื้องหลัง",
                               d.title, source_label=via[0], source_url=via[1],
                               undo={"decision_id": decision_id, "job_id": job.id, "old": old})
    try:
        learn.refresh()  # "You approve X's background plans every time" waits in the rule book
    except Exception:
        log.exception("couldn't look for patterns after a plan answer")
    return job, action_id


def set_effort(job_id: int, model: str, effort: str, *, via: Via = WEB) -> Job:
    """Before you approve: another model or effort; the estimate and budget follow the effort."""
    if model not in llm.MODELS or effort not in EFFORT_COST:
        raise PlanError("ไม่รู้จักโมเดลหรือ effort นี้")
    with session() as s:
        job = s.get(Job, job_id)
        if job is None or job.status != "asking":
            raise PlanError("ปรับได้เฉพาะแผนที่รอคุณอนุมัติ")
        before = f"{job.model} · {job.effort} · {job.budget:,}"
        job.estimate = rescale(job.estimate, job.effort, effort)
        job.model, job.effort, job.budget = model, effort, budget_for(job.estimate)
        if d := s.get(Decision, job.decision_id):
            d.detail = {**d.detail, "model": model, "effort": effort, "budget": job.budget}
        s.flush()
        s.expunge(job)
    actions.record("job.effort", "ปรับโมเดลและ effort ของแผน", f"{job.project}: {before} → {model} · {effort} · {job.budget:,}",
                   source_label=via[0], source_url=via[1])
    return job


async def set_budget(job_id: int, tokens: int, *, via: Via = WEB) -> Job:
    """A budget of your own, before the job starts (the plan's is its estimate × 1.2); the runner
    stops past it. On a plan waiting for you or ready to go. Lowering is always fine; raising the
    budget of a plan you approved takes the approval back, and the rules decide again (it may ask
    you again)."""
    lo, hi = 1_000, ESTIMATE_RANGE[1]
    if not lo <= tokens <= hi:
        raise PlanError(f"งบต้องอยู่ระหว่าง {lo:,}–{hi:,} โทเคน")
    with session() as s:
        job = s.get(Job, job_id)
        if job is None or job.status not in ("asking", "ready"):
            raise PlanError("ตั้งงบได้เฉพาะแผนที่ยังไม่เริ่ม")
        before, job.budget = job.budget, tokens
        again = job.status == "ready" and job.approved_until is not None and tokens > before
        if again:
            job.approved_until = None
        if job.decision_id and (d := s.get(Decision, job.decision_id)) is not None and d.status == "pending":
            d.detail = {**d.detail, "budget": tokens}
        project = job.project
    actions.record("job.budget", "ตั้งงบของแผนเอง", f"{project}: {before:,} → {tokens:,} โทเคน", source_label=via[0],
                   source_url=via[1])
    if again:
        await decide(job_id)
    with session() as s:
        job = s.get(Job, job_id)
        s.expunge(job)
    return job


async def revise(decision_id: int, change: str, *, via: Via = WEB) -> Verdict:
    """Revise plan: Opus plans again with your change; the old request is marked revised."""
    if not change.strip():
        raise PlanError("บอกด้วยว่าจะแก้อะไร")
    with session() as s:
        d, job = _pending_job(s, decision_id)
        d.status, d.answer, d.answered_at = "revised", change.strip(), now()
        job_id = job.id
    return await make(job_id, change=change.strip(), via=via)


async def _undo_answer(undo: dict) -> None:
    with session() as s:
        job, d = s.get(Job, undo["job_id"]), s.get(Decision, undo["decision_id"])
        if job is None or d is None:
            raise actions.UndoError("ไม่พบงานนี้แล้ว")
        if job.status not in ("ready", "rejected"):
            raise actions.UndoError("งานนี้เริ่มไปแล้ว ย้อนไม่ได้ · หยุดได้ที่หน้างานเบื้องหลัง")
        old = undo["old"]
        job.status, job.rule_ok, job.rule_why = old["status"], old["rule_ok"], old["rule_why"]
        job.approved_until = datetime.fromisoformat(old["approved_until"]) if old["approved_until"] else None
        job.result = ""
        d.status, d.answered_at = "pending", None


actions.register_undo("job.approve", _undo_answer)
actions.register_undo("job.reject", _undo_answer)
