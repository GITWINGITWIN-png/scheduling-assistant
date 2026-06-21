"""Deadline nudges (M5) — tokenless.

Computes what needs attention soon, combining Google Classroom assignments with
project deadlines from the database. No Claude here — it's all dates and
filtering, so the dashboard can show it freely.

This also backs the "nightly replan" in its suggest-only form: instead of
editing the calendar, it flags active projects that are due soon with hours
still to do, suggesting you ask the chat to plan them.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Project
from app.services import classroom


def _item(kind: str, label: str, sublabel: str, due: str | None) -> dict:
    return {"type": kind, "label": label, "sublabel": sublabel, "due": due}


def compute_nudges(days: int = 7) -> dict:
    """Return overdue items, things due within `days`, and replan suggestions."""
    now = datetime.now().astimezone()
    horizon = now + timedelta(days=days)

    overdue: list[dict] = []
    due_soon: list[dict] = []
    suggestions: list[str] = []

    # --- Classroom assignments (cached read) ---
    grouped = classroom.list_todo_grouped()
    for a in grouped["overdue"]:
        overdue.append(_item("assignment", a["title"], a["course"], a["due"]))
    for a in grouped["upcoming"]:
        if a["due"] and datetime.fromisoformat(a["due"]) <= horizon:
            due_soon.append(_item("assignment", a["title"], a["course"], a["due"]))

    # --- Project deadlines (database) ---
    with SessionLocal() as db:
        projects = [p for p in db.scalars(select(Project)).all() if p.status == "active"]

    for p in projects:
        if not p.deadline:
            continue
        deadline = p.deadline if p.deadline.tzinfo else p.deadline.replace(tzinfo=now.tzinfo)
        if deadline < now:
            overdue.append(_item("project", p.name, "project deadline passed", deadline.isoformat()))
        elif deadline <= horizon:
            hours = p.estimated_hours or 0
            due_soon.append(_item("project", p.name, f"{hours}h remaining", deadline.isoformat()))
            # Suggest-only "replan": flag it; never touches the calendar.
            if hours > 0:
                days_left = max(0, (deadline - now).days)
                suggestions.append(
                    f"{p.name} is due in {days_left}d with {hours}h left — "
                    "ask the chat to plan it."
                )

    due_soon.sort(key=lambda i: i["due"] or "")
    return {"overdue": overdue, "due_soon": due_soon, "suggestions": suggestions}
