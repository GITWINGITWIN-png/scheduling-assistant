"""The settings page (W10), the theme (W11), and the small status the shell shows on every page."""

from datetime import datetime, time, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from app.connectors import discord_bot, google
from app.core import codestamp, llm, themes
from app.core import clock as clock_mod
from app.core.clock import clock
from app.core.config import get_config
from app.core.db import now, session
from app.core.tables import Decision, LLMUsage
from app.core.timefmt import local
from app.features.mail import watch
from app.features.mail.tables import Email

router = APIRouter(prefix="/api", tags=["settings"])

# Model choices agreed for later phases: shown greyed out until their phase (W10 ①)
PLANNED_TASKS = [
    {"label": "เตือนนัด · ซิงก์ปฏิทิน", "model": "สคริปต์", "effort": "—", "phase": ""},  # built in B3: no phase, not greyed
    {"label": "งานเบื้องหลัง", "model": "Opus", "effort": "ต่อแผน", "phase": "B5"},
    {"label": "ย่อข่าวโปรเจค", "model": "OmniRoute", "effort": "—", "phase": "B5"},
    {"label": "จัดหมวดหน้าต่าง", "model": "กติกา → Omni", "effort": "—", "phase": "B6"},
    {"label": "แท็กไอเดีย", "model": "OmniRoute", "effort": "—", "phase": "B6"},
]

# Connections and the phase each arrives in (W10 ④); Discord's status is live
SERVICES = [
    {"icon": "eye", "name": "ActivityWatch", "detail": "บนเครื่องนี้ + ตัวกรอง", "phase": "B6"},
    {"icon": "robot", "name": "OmniRoute", "detail": "API แบบ OpenAI · งานเล็ก", "phase": "B6"},
]


@router.get("/settings")
def get_settings() -> dict:
    tasks = []
    for task, default in llm.DEFAULT_TASKS.items():
        current = llm.task_settings(task)
        tasks.append({"task": task, "label": default["label"], "model": current["model"], "effort": current["effort"],
                      "default_model": default["model"], "default_effort": default["effort"]})
    return {
        "tasks": tasks, "models": list(llm.MODELS), "efforts": list(llm.EFFORTS), "planned_tasks": PLANNED_TASKS,
        "theme": themes.current_theme(),
        "themes": [{"id": k, "name": n, "sub": sub} for k, (n, sub, _) in themes.THEMES.items()],
        "clock": clock.status(),
        "discord": discord_bot.status(),
        # live since B2: Gmail (every account) + Calendar (google.CALENDAR_ACCOUNT), with your address
        # on each (the mail settings card that listed them moved here, W10)
        "google": [{**g, "address": watch.address_of(g["id"])} for g in google.status()],
        "services": SERVICES,
    }


class RoundIn(BaseModel):
    on: bool


@router.put("/settings/rounds/{round_id}")
def put_round(round_id: str, body: RoundIn) -> dict:
    """The on/off switch of one clock round (a new phase's rounds start off)."""
    try:
        action_id = clock_mod.set_enabled(round_id, body.on)
    except KeyError:
        raise HTTPException(404, "no such round")
    return {"round": round_id, "on": body.on, "action_id": action_id}


class TaskIn(BaseModel):
    model: str
    effort: str


@router.put("/settings/llm/{task}")
def put_task(task: str, body: TaskIn) -> dict:
    try:
        action_id = llm.set_task(task, body.model, body.effort)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"task": task, **llm.task_settings(task), "action_id": action_id}


class ThemeIn(BaseModel):
    theme: str


@router.put("/settings/theme")
def put_theme(body: ThemeIn) -> dict:
    try:
        themes.set_theme(body.theme)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"theme": body.theme}


@router.get("/status")
def status() -> dict:
    """For the shell on every page: the bell's count, this week's tokens, whether Discord is up,
    whether the backend code on disk is newer than the running one (restart banner), and the
    side menu's counts (the plan's W screens: the red number next to a page).

    counts.people: emails from important people today, the ones the today page's
    "เรื่องสำคัญ" lists (the user's reading of the plan's "คนและอีเมล 2", 2026-11-06)."""
    midnight = datetime.combine(local(now()).date(), time(0), get_config().tz)
    with session() as s:
        pending = s.scalar(select(func.count()).select_from(Decision).where(Decision.status == "pending")) or 0
        week = s.scalar(select(func.sum(LLMUsage.tokens_in + LLMUsage.tokens_out))
                        .where(LLMUsage.at >= now() - timedelta(days=7))) or 0
        important_today = s.scalar(select(func.count()).select_from(Email).where(
            Email.from_me.is_(False), Email.level == "important", Email.sent_at >= midnight)) or 0
    return {"pending": pending, "tokens_week": int(week), "discord": discord_bot.status()["connected"],
            "theme": themes.current_theme(), "stale": codestamp.stale(), "counts": {"people": important_today}}


@router.get("/decisions")
def decisions(status: str = "pending") -> dict:
    """What waits for you (the bell): plans (B1), appointments from email (B2), Classroom courses (B3)."""
    with session() as s:
        rows = s.scalars(select(Decision).where(Decision.status == status).order_by(Decision.created_at.desc()).limit(50)).all()
    return {"items": [{"id": d.id, "kind": d.kind, "title": d.title, "plan": d.detail.get("plan", ""),
                       "request": d.detail.get("request", ""), "model": d.detail.get("model", ""),
                       "effort": d.detail.get("effort", ""), "tokens": d.detail.get("tokens"),
                       "when": d.detail.get("when", ""), "from": d.detail.get("from", ""),  # appointment (B2)
                       "subject": d.detail.get("subject", ""),
                       "folder": d.detail.get("folder", ""), "exists": d.detail.get("exists", False),  # course (B3)
                       "link": d.detail.get("link", ""),
                       "created_at": d.created_at.isoformat()} for d in rows]}
