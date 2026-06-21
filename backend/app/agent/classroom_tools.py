"""Google Classroom tools for the agent (read-only).

The academic counterpart to the calendar tools. These let the secretary answer
"what's overdue?", "what do I still need to turn in?", and "what courses am I
taking?" — all read-only, against the school account.
"""

from __future__ import annotations

from claude_agent_sdk import tool

from app.db import SessionLocal
from app.services import classroom, dismissed


def _fmt(a: dict) -> str:
    due = (a["due"] or "").split("T")[0] or "no due date"
    return f"- {due} | {a['course']} — {a['title']} [{a['state']}]"


@tool(
    "list_todo",
    "List the user's outstanding Google Classroom assignments (not yet turned "
    "in), grouped into overdue, upcoming (has a future due date), and "
    "no-deadline/optional.",
    {},
)
async def list_todo(args: dict) -> dict:
    with SessionLocal() as db:
        excluded = dismissed.ignored_ids(db)
    grouped = classroom.list_todo_grouped(exclude_ids=excluded)
    sections = []
    for key, label in (
        ("overdue", "OVERDUE"),
        ("upcoming", "UPCOMING"),
        ("no_deadline", "NO DEADLINE / OPTIONAL"),
    ):
        items = grouped[key]
        body = "\n".join(_fmt(a) for a in items) if items else "  (none)"
        sections.append(f"{label} ({len(items)}):\n{body}")
    return {"content": [{"type": "text", "text": "\n\n".join(sections)}]}


@tool(
    "list_courses",
    "List the user's active Google Classroom courses by name.",
    {},
)
async def list_courses(args: dict) -> dict:
    courses = classroom.list_courses()
    text = "\n".join(f"- {c.get('name')}" for c in courses) or "No active courses."
    return {"content": [{"type": "text", "text": text}]}


# Collected for registration in secretary.py
CLASSROOM_TOOLS = [list_todo, list_courses]
