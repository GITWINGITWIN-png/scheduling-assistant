"""The daily brief generator (M5).

Gathers today's context — calendar, what's due soon, planned work blocks — and
asks Claude (Agent SDK, Pro login) to write a short, friendly morning brief.
This is the one regularly-scheduled token use; it's generated at most once a day
and cached (see models.DailyBrief).
"""

from __future__ import annotations

from datetime import datetime, time

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

from app.services import calendar as cal
from app.services import nudges

_SYSTEM = (
    "You are a personal secretary writing the user's morning brief. Keep it "
    "short and useful: a one-line greeting, then a few concrete bullets covering "
    "today's schedule, anything overdue, what's due soon, and a gentle nudge "
    "about projects that need planning. Be encouraging and specific; no filler, "
    "no made-up items — only use what you're given. Use plain text only: simple "
    "dash bullets are fine, but no markdown bold/headers (no ** or #)."
)


def _gather() -> str:
    """Build the plain-text context block the brief is written from."""
    now = datetime.now().astimezone()
    day_end = datetime.combine(now.date(), time(23, 59), tzinfo=now.tzinfo)

    events = cal.list_events(now, day_end, max_results=50)
    lines = [f"DATE: {now.strftime('%A, %Y-%m-%d')}", "", "TODAY'S REMAINING CALENDAR:"]
    if events:
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date", "?"))
            lines.append(f"- {start[11:16] if 'T' in start else start} {e.get('summary', '(no title)')}")
    else:
        lines.append("- (nothing left on the calendar today)")

    n = nudges.compute_nudges(days=7)
    lines += ["", "OVERDUE:"]
    lines += [f"- {i['label']} ({i['sublabel']})" for i in n["overdue"]] or ["- (none)"]
    lines += ["", "DUE SOON (next 7 days):"]
    lines += [f"- {i['label']} ({i['sublabel']}) due {i['due'][:10] if i['due'] else '?'}" for i in n["due_soon"]] or ["- (none)"]
    lines += ["", "PLANNING SUGGESTIONS:"]
    lines += [f"- {s}" for s in n["suggestions"]] or ["- (none)"]

    return "\n".join(lines)


async def generate_brief() -> str:
    """Compose today's brief with Claude from the gathered context."""
    options = ClaudeAgentOptions(
        system_prompt=_SYSTEM,
        allowed_tools=[],      # writing only — no tools
        setting_sources=[],
        permission_mode="bypassPermissions",
    )
    prompt = "Write today's morning brief from this context:\n\n" + _gather()

    parts: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
    return "\n".join(parts).strip()
