"""Planning tools for the agent (M4, chat-driven).

Smart planning lives in chat now, not a button — so you can express it in plain
language ("plan project A for next week, mornings only, leave project B alone").
These two tools give the agent what it needs; it then uses the existing calendar
tools (list/create/delete_event) to actually book or replace work blocks.

The deterministic core still owns the hard part: `get_free_slots` returns REAL
free times, so the agent places work in genuine gaps instead of guessing.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from claude_agent_sdk import tool
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Project
from app.services import calendar as cal
from app.services import planner


@tool(
    "list_projects",
    "List the user's projects with status, deadline, remaining hours, and last "
    "commit. Call this before planning so you know what to schedule and by when.",
    {},
)
async def list_projects(args: dict) -> dict:
    with SessionLocal() as db:
        projects = db.scalars(select(Project)).all()
    if not projects:
        return {"content": [{"type": "text", "text": "No projects yet."}]}
    lines = [
        f"- {p.name}: status={p.status}, "
        f"deadline={p.deadline.isoformat() if p.deadline else 'none'}, "
        f"remaining_hours={p.estimated_hours}, "
        f"last_commit={p.last_commit_at.isoformat() if p.last_commit_at else 'none'}"
        for p in projects
    ]
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


@tool(
    "get_free_slots",
    "List REAL free time slots in the user's calendar (within working hours, "
    "skipping existing events) where work blocks can go. Always schedule using "
    "these exact times so you never double-book. Args: days_ahead (default 14), "
    "block_hours (default 1.5).",
    {
        "type": "object",
        "properties": {
            "days_ahead": {"type": "integer", "description": "Days from now to look ahead"},
            "block_hours": {"type": "number", "description": "Slot length in hours"},
        },
        "required": [],
    },
)
async def get_free_slots(args: dict) -> dict:
    days = int(args.get("days_ahead") or 14)
    block_hours = float(args.get("block_hours") or 1.5)
    now = datetime.now().astimezone()
    until = now + timedelta(days=days)

    events = cal.list_events(now, until, max_results=250)
    busy = planner._busy_intervals(events, now.tzinfo)
    slots = planner.free_slots(
        now, until, busy,
        work_start=planner.DEFAULTS["work_start"],
        work_end=planner.DEFAULTS["work_end"],
        block_hours=block_hours,
    )
    if not slots:
        return {"content": [{"type": "text", "text": f"No free {block_hours}h slots in the next {days} days."}]}

    lines = [f"- {s.isoformat()} to {e.isoformat()}" for s, e in slots[:60]]
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


# Collected for registration in secretary.py
PLANNER_TOOLS = [list_projects, get_free_slots]
