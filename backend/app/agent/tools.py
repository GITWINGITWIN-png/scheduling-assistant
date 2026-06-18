"""Calendar tools exposed to the Claude agent.

We wrap the plain `CalendarService` functions as in-process "SDK MCP" tools.
The Agent SDK runs these inside this same Python process (no separate server),
so during a conversation the agent can call list_events / create_event directly.

Each tool is an async function decorated with `@tool(name, description, schema)`
and must return `{"content": [{"type": "text", "text": ...}]}`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from claude_agent_sdk import tool

from app.services import calendar as cal


@tool(
    "list_events",
    "List the user's upcoming calendar events for the next N days (default 7).",
    {"days": int},
)
async def list_events(args: dict) -> dict:
    days = int(args.get("days") or 7)
    now = datetime.now(timezone.utc)
    events = cal.list_events(now, now + timedelta(days=days))

    if not events:
        text = f"No events in the next {days} days."
    else:
        lines = []
        for e in events:
            # Timed events use dateTime; all-day events use date.
            start = e["start"].get("dateTime", e["start"].get("date", "?"))
            # Include the id so the agent can update/delete this event later.
            lines.append(f"- [{e['id']}] {start}: {e.get('summary', '(no title)')}")
        text = "\n".join(lines)

    return {"content": [{"type": "text", "text": text}]}


@tool(
    "create_event",
    "Create a calendar event. `start` and `end` must be ISO 8601 datetimes, "
    "e.g. 2026-06-19T18:00:00.",
    {"summary": str, "start": str, "end": str, "description": str},
)
async def create_event(args: dict) -> dict:
    start = datetime.fromisoformat(args["start"])
    end = datetime.fromisoformat(args["end"])
    created = cal.create_event(
        summary=args["summary"],
        start=start,
        end=end,
        description=args.get("description", ""),
    )
    link = created.get("htmlLink", "")
    return {
        "content": [
            {"type": "text", "text": f"Created '{args['summary']}'. {link}".strip()}
        ]
    }


@tool(
    "update_event",
    "Update an existing event by its id (get the id from list_events first). "
    "Pass only the fields you want to change. start/end are ISO 8601 datetimes.",
    {
        "type": "object",
        "properties": {
            "event_id": {"type": "string", "description": "The event's id"},
            "summary": {"type": "string"},
            "start": {"type": "string", "description": "New start, ISO 8601"},
            "end": {"type": "string", "description": "New end, ISO 8601"},
            "description": {"type": "string"},
        },
        "required": ["event_id"],
    },
)
async def update_event(args: dict) -> dict:
    fields: dict = {}
    if args.get("summary"):
        fields["summary"] = args["summary"]
    if args.get("description"):
        fields["description"] = args["description"]
    if args.get("start"):
        fields["start"] = datetime.fromisoformat(args["start"])
    if args.get("end"):
        fields["end"] = datetime.fromisoformat(args["end"])

    updated = cal.update_event(args["event_id"], **fields)
    return {
        "content": [
            {"type": "text", "text": f"Updated '{updated.get('summary', '(event)')}'."}
        ]
    }


@tool(
    "delete_event",
    "Delete an event by its id (get the id from list_events first). This is "
    "irreversible, so make sure the user has confirmed before calling it.",
    {"event_id": str},
)
async def delete_event(args: dict) -> dict:
    cal.delete_event(args["event_id"])
    return {"content": [{"type": "text", "text": "Event deleted."}]}


# Collected for registration in secretary.py
CALENDAR_TOOLS = [list_events, create_event, update_event, delete_event]
