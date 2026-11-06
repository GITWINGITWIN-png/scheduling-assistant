"""The runner (3.2, B5.7): Claude Code does a planned job in its project, on a branch of its own.

Where: a git worktree under ~/.secretary/worktrees/, on the branch secretary/<job>-<project>,
made from the project's current commit. Your own folder isn't touched (your uncommitted changes
aren't in the job either), nor main, nothing is pushed; the commits wait on that branch for you
to look at and merge. The worktree is removed afterwards, the branch stays.

How: the Agent SDK with Claude Code's own instructions plus the job's and the project's
CLAUDE.md (read by us: the project's .claude settings and hooks, and yours, are not loaded, so no
allow rule can get round the guard), and ponytail (the plugin, by its folder, switched on for the job:
PONYTAIL_DEFAULT_MODE=full). No MCP servers, no subagents. The model and effort are the plan's.

The guard (guard.py) answers every permission question. The run stops by itself (interrupt)
past its budget, when the same call repeats (going round in circles), at the end of the night
window (06:00) or MAX_MINUTES, or when you press หยุด. Whatever it stopped at, its changes are
committed on the branch ("งานค้าง") so nothing is lost.

Before a job starts it is checked again: the project still open to the secretary, the step in
PROGRESS.md the same (else it's planned again), the rules (core/rules/check.py: an approval
older than 3 days, or a quota now below the line, asks you), and the 5-hour window not nearly
spent (FIVE_HOUR_FLOOR). One job at a time.

The "jobs" round (01:00–06:00, every 15 minutes, starts switched off): start the first ready
job, or else plan the first queued one. ทำเลย starts a ready job at any time.

(Claude Code's own bash sandbox would add a layer, but on this machine it switches itself off,
socat missing, and then runs unsandboxed: checked 2026-11-06. So it isn't used.)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, PermissionResultAllow,
                              PermissionResultDeny, RateLimitEvent, ResultMessage, TextBlock, ToolUseBlock)

from sqlalchemy import select

from app.core import actions, llm
from app.core.config import get_config
from app.core.db import now, session
from app.features.jobs import plan as plans
from app.features.jobs import queue, quota
from app.features.jobs.guard import Budget, Loop, judge
from app.features.jobs.tables import Job
from app.features.projects import progress
from app.features.projects.tables import Project

log = logging.getLogger(__name__)

NIGHT = (time(1, 0), time(6, 0))  # the window agreed at the B5 plan
MAX_MINUTES = 120
FIVE_HOUR_FLOOR = 20.0  # a new job doesn't start with less than this % of the 5-hour window left
MAX_TURNS = 80
TOOLS = ["Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep", "Bash", "TodoWrite"]
WATCH_EVERY = 10.0  # seconds between the watchdog's looks (a long test run sends no messages)

# Called with the job id when a run ends (cards and briefs say how it went, B5.9).
FINISHED: list[Callable[[int], Awaitable[None]]] = []

Client = ClaudeSDKClient  # the tests put a scripted client here


class RunError(ValueError):
    """The job can't start now; the message says why."""


@dataclass
class Run:
    job_id: int
    deadline: datetime
    stop_asked: asyncio.Event = field(default_factory=asyncio.Event)
    why: str = ""  # the first reason it was stopped
    task: asyncio.Task | None = None


RUNNING: dict[int, Run] = {}


# ------------------------------------------------------------------ small pieces
def in_night(at: datetime) -> bool:
    t = at.astimezone(get_config().tz).time()
    return NIGHT[0] <= t < NIGHT[1]


def night_end(at: datetime) -> datetime:
    local = at.astimezone(get_config().tz)
    return datetime.combine(local.date(), NIGHT[1], get_config().tz)


def slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.").lower()[:40] or "project"


def worktrees() -> Path:
    return get_config().data_dir / "worktrees"


def _git(cwd: Path, *args: str, check: bool = True) -> str:
    out = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=120)
    if check and out.returncode:
        raise RunError(f"git {args[0]} ไม่สำเร็จ: {(out.stderr or out.stdout).strip()[:300]}")
    return out.stdout.strip()


def node_dir() -> str | None:
    """Where node is (ponytail's hooks need it; the service's PATH doesn't have nvm's)."""
    if found := shutil.which("node"):
        return str(Path(found).parent)
    versions = sorted((Path.home() / ".nvm" / "versions" / "node").glob("v*/bin/node"),
                      key=lambda p: [int(x) for x in re.findall(r"\d+", p.parent.parent.name)])
    return str(versions[-1].parent) if versions else None


def ponytail() -> list[dict]:
    """The ponytail plugin, by its folder (from the plugins you installed), or none."""
    try:
        data = json.loads((Path.home() / ".claude" / "plugins" / "installed_plugins.json").read_text())
    except (OSError, ValueError):
        return []
    for name, installs in (data.get("plugins") or {}).items():
        if name.startswith("ponytail@"):
            for i in installs:
                if Path(i.get("installPath", "")).is_dir():
                    return [{"type": "local", "path": i["installPath"]}]
    return []


def claude_md(root: Path) -> str:
    for name in ("CLAUDE.md", ".claude/CLAUDE.md"):
        f = root / name
        if f.is_file():
            return f.read_text(errors="replace")[:8000]
    return ""


APPEND = """\n\n# งานเบื้องหลังจากเลขา
นี่คืองานที่ผู้ใช้ไม่ได้นั่งดูอยู่ ทำตามแผนในข้อความให้จบโดยไม่ต้องถาม (ไม่มีใครตอบ)
- ทำงานบน branch {branch} นี้เท่านั้น commit ทุกครั้งที่จบหนึ่งขั้น ห้าม push ห้ามสลับ branch
- commit เฉพาะไฟล์ที่ตั้งใจแก้ ไม่เอาไฟล์ที่เครื่องสร้างเอง (เช่น __pycache__ ไฟล์ build)
- แก้ไฟล์ได้เฉพาะในโฟลเดอร์นี้ ไฟล์ลับ (.env กุญแจ โทเคน) ห้ามแตะ
- คำสั่งที่ถูกห้าม อย่าหาทางอ้อม ให้ข้ามส่วนนั้นแล้วจดไว้ในสรุป
- ขั้นใน PROGRESS.md ที่ทำเสร็จ ให้ติ๊ก [x] ในไฟล์นั้นด้วย
- ถ้าเจอเรื่องที่ต้องให้ผู้ใช้ตัดสิน ให้หยุดแล้วเขียนว่าค้างตรงไหน เพราะอะไร
- ทำให้น้อยที่สุดที่แก้ได้ครบ (ponytail)
- จบแล้วเขียนสรุปสั้นๆ: ทำอะไรไป commit อะไร เหลืออะไร"""


def _prompt(job: Job) -> str:
    lines = [f"งานเบื้องหลัง #{job.id} · โปรเจค {job.project}"]
    if job.stuck_at:
        lines.append(f"ขั้นที่ค้างใน PROGRESS.md: {job.stuck_at}")
    if job.note:
        lines.append(f"ผู้ใช้สั่ง: {job.note}")
    lines += ["แผน:", *[f"{i}. {s}" for i, s in enumerate(job.steps, 1)],
              f"งบ {job.budget:,} โทเคน · เกินแล้วงานจะถูกหยุดเอง"]
    return "\n".join(lines)


# ------------------------------------------------------------------ starting
async def start(job_id: int, *, night: bool = False, via: tuple[str, str] = ("หน้างานเบื้องหลัง", "")) -> str:
    """Start a ready job in the background (checked again first). -> a line saying what happened.
    Raises RunError when it can't start now."""
    with session() as s:
        if RUNNING or s.scalar(select(Job.id).where(Job.status == "running")):  # one at a time, in any copy of the secretary
            raise RunError("มีงานเบื้องหลังกำลังทำอยู่ ทำทีละงาน")
        job = s.get(Job, job_id)
        if job is None:
            raise RunError("ไม่พบงานนี้")
        if job.status != "ready":
            raise RunError("งานนี้ยังไม่พร้อม: ต้องมีแผนที่ผ่านกฎหรือคุณอนุมัติแล้ว")
        p = s.get(Project, job.project_id)
        why = queue.blocked(p)
        if why:
            job.status, job.result = "paused", why
            queue.close_ask(s, job)
        moved, nxt = False, ""
        if not why and job.source == "progress":
            nxt = progress.read(Path(p.path)).get("next", "")
            if nxt != job.stuck_at:  # you (or a merged branch) did that step meanwhile
                moved = True
                queue.replan(job)
                job.stuck_at = nxt
                if not nxt:
                    job.status, job.result = "dropped", "PROGRESS.md ไม่มีขั้นที่ค้างแล้ว"
        name = job.project
    if why:
        raise RunError(why)
    if moved:
        raise RunError(f"{name} ไปต่อแล้ว" + (f" (ขั้นถัดไป: {nxt}) · จะวางแผนใหม่" if nxt else " · ไม่มีขั้นที่ค้างแล้ว"))
    verdict = await plans.decide(job_id)
    if not verdict.go:
        raise RunError(f"ต้องถามคุณก่อน: {verdict.why}")
    reading = quota.latest()
    if reading is not None and reading.five_left is not None and reading.five_left < FIVE_HOUR_FLOOR:
        raise RunError(f"โควตา 5 ชั่วโมงเหลือ {reading.five_left:.0f}% · รอให้รีเซ็ตก่อน")
    at = now()
    deadline = at + timedelta(minutes=MAX_MINUTES)
    if night:
        deadline = min(deadline, night_end(at))
    run = Run(job_id, deadline)
    RUNNING[job_id] = run
    run.task = asyncio.create_task(_run(job_id, run, via), name=f"job-{job_id}")
    return f"เริ่ม {name}"


def stop(job_id: int) -> None:
    """หยุด: the run stops at its next look (within seconds), and keeps what it did."""
    run = RUNNING.get(job_id)
    if run is None:
        raise RunError("งานนี้ไม่ได้กำลังทำ")
    run.why = run.why or "คุณสั่งหยุด"
    run.stop_asked.set()


# ------------------------------------------------------------------ the run
async def _run(job_id: int, run: Run, via: tuple[str, str]) -> None:
    with session() as s:
        job = s.get(Job, job_id)
        p = s.get(Project, job.project_id)
        project_root = Path(p.path)
        job.branch = f"secretary/{job.id}-{slug(job.project)}"
        job.status, job.started_at, job.used, job.result = "running", now(), 0, ""
        s.flush()
        s.expunge(job)
    wt = worktrees() / f"{slug(job.project)}-{job.id}"
    base = ""
    summary, status, used, denied = "", "failed", 0, []
    try:
        base = _git(project_root, "rev-parse", "HEAD")
        base_branch = _git(project_root, "rev-parse", "--abbrev-ref", "HEAD")
        worktrees().mkdir(parents=True, exist_ok=True)
        _git(project_root, "worktree", "add", "-b", job.branch, str(wt), base)
        summary, used, denied, finished = await _drive(job, wt, run)
        status = "stopped" if run.why else ("done" if finished else "failed")
        # its own paragraph: Claude's words below are Markdown (the jobs page shows them so)
        summary = f"เริ่มจาก {base_branch} ({base[:7]})" + (f"\n\n{summary}" if summary else "")
    except Exception as exc:
        log.exception("job %s failed", job_id)
        summary = f"ทำไม่สำเร็จ: {exc}"
    finally:
        commits = _wrap_up(project_root, wt, job, base, run.why)
        RUNNING.pop(job_id, None)
    words = {"done": "ทำเสร็จ", "stopped": f"หยุด: {run.why}", "failed": "ไม่สำเร็จ"}[status]
    tail = f" · ถูกห้าม {len(denied)} ครั้ง" if denied else ""
    result = f"{words} · {commits} commit บน {job.branch} · ใช้ {used:,} / งบ {job.budget:,} โทเคน{tail}\n{summary}".strip()
    with session() as s:
        j = s.get(Job, job_id)
        j.status, j.used, j.finished_at, j.result = status, used, now(), result[:4000]
    actions.record("job.run", f"งานเบื้องหลัง{words}", f"{job.project}: {job.title}", source_label=via[0],
                   source_url=via[1], tokens=used)
    for hook in FINISHED:
        try:
            await hook(job_id)
        except Exception:
            log.exception("couldn't tell how job %s went", job_id)


async def _drive(job: Job, wt: Path, run: Run) -> tuple[str, int, list[str], bool]:
    """Claude Code at work. -> (its last words, tokens used, refusals, finished normally)."""
    budget, loop, denied = Budget(job.budget), Loop(), []
    allowed = set(job.risks) if job.approved_until else set()  # what you approved, nothing more

    async def can_use_tool(name: str, data: dict, ctx) -> PermissionResultAllow | PermissionResultDeny:
        why = judge(name, data, root=wt, allowed=allowed)
        if why:
            denied.append(f"{name}: {why}")
            return PermissionResultDeny(message=why)
        return PermissionResultAllow()

    # ponytail on for this run only: your own default (off) stays as it is, and the plugin keeps
    # its mode per folder, so your sessions keep theirs. Its hooks need node, which the
    # service's PATH doesn't have (nvm).
    env = {"PONYTAIL_DEFAULT_MODE": "full"}
    if nd := node_dir():
        env["PATH"] = f"{nd}:{os.environ.get('PATH', '')}"
    project_rules = claude_md(wt)
    options = ClaudeAgentOptions(
        model=job.model or None, effort=job.effort or None,
        system_prompt={"type": "preset", "preset": "claude_code",
                       "append": APPEND.format(branch=job.branch)
                       + (f"\n\n# CLAUDE.md ของโปรเจค\n{project_rules}" if project_rules else "")},
        tools=TOOLS + (["WebFetch", "WebSearch"] if "download" in allowed else []),
        setting_sources=[], plugins=ponytail(), strict_mcp_config=True, mcp_servers={},
        permission_mode="default", can_use_tool=can_use_tool, max_turns=MAX_TURNS, cwd=str(wt), env=env)
    last_words, result = "", None
    async with Client(options=options) as client:

        async def halt(why: str) -> None:
            if not run.why:
                run.why = why
            try:
                await client.interrupt()
            except Exception:
                log.warning("couldn't interrupt job %s", job.id)

        async def watch() -> None:
            while True:
                try:
                    await asyncio.wait_for(run.stop_asked.wait(), timeout=WATCH_EVERY)
                    await halt(run.why or "คุณสั่งหยุด")
                    return
                except TimeoutError:
                    if now() >= run.deadline:
                        await halt("หมดช่วงกลางคืน" if run.deadline == night_end(run.deadline) else f"ครบ {MAX_MINUTES} นาที")
                        return

        await client.query(_prompt(job))
        watcher = asyncio.create_task(watch())
        saved = 0
        try:
            async for m in client.receive_response():
                if isinstance(m, AssistantMessage):
                    used = budget.add(m.message_id or m.uuid or str(id(m)), m.usage)
                    for block in m.content:
                        if isinstance(block, TextBlock) and block.text.strip():
                            last_words = block.text.strip()
                        elif isinstance(block, ToolUseBlock) and loop.see(block.name, block.input) and not run.why:
                            await halt("วนซ้ำ: เรียกคำสั่งเดิมซ้ำหลายครั้ง")
                    if budget.over and not run.why:
                        await halt("เกินงบ")
                    if used - saved > 5_000:  # the jobs page shows it filling up
                        saved = used
                        with session() as s:
                            s.get(Job, job.id).used = used
                elif isinstance(m, RateLimitEvent):
                    llm.rate_limit(m)
                elif isinstance(m, ResultMessage):
                    result = m
        finally:
            watcher.cancel()
    # The final report has the whole run's usage, except after an interrupt (then it may have none):
    # whichever says more is right.
    final = result.usage if result is not None and result.usage and Budget.tokens(result.usage) >= budget.used else budget.usage
    used = Budget.tokens(final)
    llm.record_usage("job", job.model, job.effort, final, result.duration_ms if result else 0,
                     ok=bool(result and not result.is_error))
    finished = result is not None and not result.is_error and not run.why
    return (result.result if result and result.result else last_words)[:1500], used, denied, finished


def _wrap_up(project_root: Path, wt: Path, job: Job, base: str, why: str) -> int:
    """Commit what's left on the job's branch, remove the worktree (the branch stays). -> commits made."""
    if not wt.is_dir():
        return 0
    try:
        if _git(wt, "status", "--porcelain", check=False):
            _git(wt, "add", "-A")
            ident = [] if _git(wt, "config", "user.email", check=False) else ["-c", "user.name=my_secretary", "-c", "user.email=secretary@localhost"]
            message = f"เลขา: งานค้างของงาน #{job.id}" + (f" (หยุดเพราะ{why})" if why else "")
            subprocess.run(["git", "-C", str(wt), *ident, "commit", "-q", "-m", message], capture_output=True, timeout=60)
        count = int(_git(wt, "rev-list", "--count", f"{base}..HEAD", check=False) or 0) if base else 0
        _git(project_root, "worktree", "remove", "--force", str(wt), check=False)
        return count
    except Exception:
        log.exception("couldn't wrap up job %s", job.id)
        return 0


def recover() -> list[int]:
    """At startup: a job still marked running was cut off (the machine or the service stopped).
    Keep what it did on its branch and say so. -> the job ids."""
    out = []
    with session() as s:
        for job in s.scalars(select(Job).where(Job.status == "running")).all():
            p = s.get(Project, job.project_id)
            if p is not None:
                _wrap_up(Path(p.path), worktrees() / f"{slug(job.project)}-{job.id}", job, "", "เลขาปิดระหว่างทำ")
            job.status, job.finished_at = "stopped", now()
            job.result = (f"หยุด: เลขาปิดระหว่างทำ · งานที่ทำไปอยู่บน {job.branch}\n" + job.result).strip()
            out.append(job.id)
    return out


# ------------------------------------------------------------------ the round
async def round_tick() -> str | None:
    """The "jobs" round: in the night window, start the first ready job, or else plan the next one."""
    at = now()
    if not in_night(at):
        return "นอกช่วง 01:00–06:00 · ไม่เริ่มงานใหม่"  # only a catch-up run lands here
    if RUNNING:
        return None
    queue.refresh(at)
    for job in queue.ordered(("ready",)):
        try:
            return await start(job.id, night=True, via=("นาฬิกาเลขา", ""))
        except RunError as exc:
            log.info("job %s didn't start: %s", job.id, exc)
    reading = quota.latest()
    if reading is not None and reading.five_left is not None and reading.five_left < FIVE_HOUR_FLOOR:
        return f"โควตา 5 ชั่วโมงเหลือ {reading.five_left:.0f}% · ยังไม่วางแผนงานใหม่"
    for job in queue.ordered(("queued",)):
        try:
            verdict = await plans.make(job.id, via=("นาฬิกาเลขา", ""))
        except plans.PlanError as exc:
            return f"วางแผน {job.project} ไม่สำเร็จ: {exc}"
        return f"วางแผน {job.project} · " + ("ผ่านกฎ รอทำ" if verdict.go else "ถามคุณใน #อนุมัติ")
    return None


def setup() -> None:
    from app.core import clock

    if stopped := recover():
        log.warning("jobs %s were cut off while running; their work is kept on their branches", stopped)
    clock.attach("jobs", round_tick)
