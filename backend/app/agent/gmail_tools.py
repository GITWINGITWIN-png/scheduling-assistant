"""Gmail tools for the agent (read-only).

These let the secretary look things up in the user's mail when chatting —
"did the registrar email about the deadline?", "what's unread?" — without ever
sending or modifying anything. Reading mail is a free Google API call; only the
*extraction* job (services/mail_extract) spends compute, and that runs locally.

We hand the model compact summaries (sender, subject, date, snippet), not full
bodies, to keep replies focused and the context small.
"""

from __future__ import annotations

from claude_agent_sdk import tool

from app.services import gmail


def _fmt(m: dict) -> str:
    date = (m.get("date") or "").split("T")[0] or "?"
    unread = "• " if m.get("unread") else "  "
    return f"{unread}{date} | {m.get('from', '')} — {m.get('subject', '(no subject)')}\n    {m.get('snippet', '')}"


@tool(
    "search_email",
    "Search the user's Gmail (read-only) using Gmail query syntax, e.g. "
    "'from:registrar', 'subject:exam newer_than:14d', 'is:unread'. Returns "
    "matching messages (sender, subject, date, snippet), newest first.",
    {"query": str},
)
async def search_email(args: dict) -> dict:
    query = (args.get("query") or "").strip() or "in:inbox"
    msgs = gmail.list_messages(query, max_results=15)
    text = "\n".join(_fmt(m) for m in msgs) or "No matching emails."
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "recent_unread_email",
    "List the user's unread inbox emails (read-only): sender, subject, date, "
    "and a snippet. Use this for 'what's in my inbox?' / 'anything new?'.",
    {},
)
async def recent_unread_email(args: dict) -> dict:
    msgs = gmail.list_unread(max_results=15)
    text = "\n".join(_fmt(m) for m in msgs) or "No unread email."
    return {"content": [{"type": "text", "text": text}]}


# Collected for registration in secretary.py
GMAIL_TOOLS = [search_email, recent_unread_email]
