"""Email → schedule-item extraction (M6), powered by the LOCAL model.

This is the one place the secretary reads an email's contents and pulls out
"things that belong on a calendar": deadlines, meetings, appointments, events.
It runs on Ollama (see services/local_llm.py), NOT Claude — so it's free, fully
local (mail bodies never leave the machine), and doesn't spend the Pro budget.

Critically, this only ever *suggests*. Nothing here writes to the calendar. The
user reviews the extracted items and decides — same philosophy as the project
planner's preview-then-commit. (Auto-booking from email would be exactly the
kind of silent, hard-to-undo action we avoid.)
"""

from __future__ import annotations

from datetime import datetime

from app.config import settings
from app.services import gmail, local_llm

# Keep bodies bounded: enough for context, small enough to stay fast and within
# the model's window even with several emails in one scan.
_MAX_BODY_CHARS = 4000


def _system_prompt() -> str:
    today = datetime.now().strftime("%A, %Y-%m-%d")
    return (
        "You extract calendar-worthy items from a single email. "
        f"Today is {today}. The email may be in Thai or English. "
        "Return ONLY a JSON object of the form "
        '{"items": [{"type": ..., "title": ..., "datetime": ..., "note": ...}]}. '
        "Each item: "
        "`type` is one of \"deadline\", \"meeting\", \"event\", or \"other\"; "
        "`title` is a short label (a few words); "
        "`datetime` is ISO 8601 (resolve relative dates like 'tomorrow' against "
        "today; use a date-only string if no time is given; use null if there is "
        "no date at all); "
        "`note` is a short optional phrase of context (or empty). "
        "Only include items that genuinely involve a time, date, or deadline. "
        "IGNORE promotional, marketing, sales, and newsletter emails entirely — "
        "a limited-time sale or 'this weekend only' offer is NOT a schedule item. "
        "Never invent dates that are not in the email. "
        'If the email has none, return {"items": []}.'
    )


def _user_prompt(msg: dict) -> str:
    body = (msg.get("body") or msg.get("snippet") or "")[:_MAX_BODY_CHARS]
    return (
        f"From: {msg.get('from', '')}\n"
        f"Subject: {msg.get('subject', '')}\n"
        f"Date: {msg.get('date', '')}\n\n"
        f"{body}"
    )


async def _extract_one(msg: dict) -> list[dict]:
    """Ask the local model for the schedule items in one email."""
    result = await local_llm.chat_json(_system_prompt(), _user_prompt(msg))
    # The model returns {"items": [...]}, but be forgiving if it returns a bare list.
    items = result.get("items", []) if isinstance(result, dict) else result
    if not isinstance(items, list):
        return []

    out: list[dict] = []
    for it in items:
        if not isinstance(it, dict) or not it.get("title"):
            continue
        # Drop pure noise: a vague "other" with no date carries no schedule value
        # (this is where leftover promo/newsletter chatter tends to land).
        if it.get("type", "other") == "other" and not it.get("datetime"):
            continue
        out.append(
            {
                "type": it.get("type", "other"),
                "title": it["title"],
                "datetime": it.get("datetime"),
                "note": it.get("note", ""),
                # Trace each suggestion back to its source email for the UI.
                "email_id": msg.get("id", ""),
                "email_subject": msg.get("subject", ""),
                "email_from": msg.get("from", ""),
                "link": msg.get("link", ""),
            }
        )
    return out


async def scan_unread(max_emails: int = 20) -> dict:
    """Scan unread inbox mail and return extracted schedule suggestions.

    Returns {"items": [...], "scanned": N, "model": "..."} — suggestions only,
    nothing is written anywhere. Emails are processed one at a time (the local
    model is serialized; see local_llm), which is fine for a background scan.
    """
    emails = gmail.list_unread(max_results=max_emails)
    items: list[dict] = []
    for msg in emails:
        items.extend(await _extract_one(msg))
    return {
        "items": items,
        "scanned": len(emails),
        "model": settings.ollama_model,
    }
