"""The secretary agent — Claude via the Agent SDK on the user's Pro login.

We never set ANTHROPIC_API_KEY: the Agent SDK drives the logged-in `claude`
CLI, so this runs on the Claude Pro subscription (no metered API spend). If we
ever need to fall back to the paid API, that's a config change here, not a
rewrite — the rest of the app only calls `ask()`.
"""

from __future__ import annotations

from datetime import datetime

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    create_sdk_mcp_server,
    query,
)

from app.agent.classroom_tools import CLASSROOM_TOOLS
from app.agent.tools import CALENDAR_TOOLS

# Register our tools as in-process MCP servers (calendar + classroom).
_calendar_server = create_sdk_mcp_server(
    name="calendar", version="0.1.0", tools=CALENDAR_TOOLS
)
_classroom_server = create_sdk_mcp_server(
    name="classroom", version="0.1.0", tools=CLASSROOM_TOOLS
)

# SDK MCP tools are namespaced as mcp__<server>__<tool>. Allow-listing them
# means the agent can use ONLY these — no file access, bash, or web tools.
_ALLOWED_TOOLS = [
    "mcp__calendar__list_events",
    "mcp__calendar__create_event",
    "mcp__calendar__update_event",
    "mcp__calendar__delete_event",
    "mcp__classroom__list_todo",
    "mcp__classroom__list_courses",
]


def _system_prompt() -> str:
    # Inject today's date so the agent can resolve "tomorrow", "Friday", etc.
    today = datetime.now().strftime("%A, %Y-%m-%d")
    return (
        "You are a personal scheduling secretary. "
        f"Today is {today} (the user's local time). "
        "Help the user manage their daily and academic schedule. "
        "Use the calendar tools to read, create, update, and delete events. "
        "To update or delete an event, first call list_events to find its id, "
        "then pass that id. When updating, change only the fields the user asked "
        "about. Deleting is irreversible — confirm with the user before deleting. "
        "You can also read the user's academic work from Google Classroom "
        "(read-only): use list_courses for their courses and list_todo for "
        "outstanding assignments (overdue, upcoming, and no-deadline/optional). "
        "When the user gives a relative time like 'tomorrow at 6pm', resolve it "
        "to a concrete ISO 8601 datetime before calling a tool. "
        "Assume an event is one hour long unless the user says otherwise. "
        "Be concise, and confirm what you did."
    )


def _options() -> ClaudeAgentOptions:
    # Built fresh each call so the date in the system prompt stays current.
    return ClaudeAgentOptions(
        system_prompt=_system_prompt(),
        mcp_servers={"calendar": _calendar_server, "classroom": _classroom_server},
        allowed_tools=_ALLOWED_TOOLS,
        # These are our own in-process tools; run them without interactive
        # permission prompts (the app is headless). We'll add explicit
        # confirmation for higher-stakes actions (e.g. M7 email send) later.
        permission_mode="bypassPermissions",
        # Don't load the user's global CLAUDE.md or project settings into the
        # secretary — it should only know what we tell it here.
        setting_sources=[],
    )


async def ask(prompt: str) -> str:
    """Send one message to the secretary and return its text reply."""
    parts: list[str] = []
    async for message in query(prompt=prompt, options=_options()):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
    return "\n".join(parts).strip()
