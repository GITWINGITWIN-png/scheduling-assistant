"""Gmail access (M6) — the email input source. READ-ONLY.

Mirrors the discipline of the Classroom service (M3): least-privilege, read-only,
and isolated behind a small normalized surface. The only scope we request is
`gmail.readonly` — the secretary can *read* mail to find schedule items and
answer questions, but cannot send, delete, or even mark-as-read. (Sending is
M7, and will be explicitly approval-gated.)

Account note: Gmail lives on the **personal** account — the same one that owns
the calendar. Both share one cached token (token.json). To avoid the two
features fighting over that file (each re-consenting and overwriting the
other's scopes), Gmail requests the UNION of calendar + gmail scopes. After one
consent the token holds both; the calendar, which only needs its own subset, is
then always satisfied and never triggers a re-consent.
"""

from __future__ import annotations

import base64
import time
from email.utils import parsedate_to_datetime

from googleapiclient.discovery import build

from app.services import calendar as _calendar
from app.services.google_auth import get_credentials

GMAIL_READONLY = "https://www.googleapis.com/auth/gmail.readonly"

# Request calendar + gmail together so one consent covers the personal account
# (see module docstring on why this prevents a re-consent ping-pong).
SCOPES = [*_calendar.SCOPES, GMAIL_READONLY]

ACCOUNT = "personal"

# A Gmail "scan" makes one list call + one get per message, so it's worth a short
# cache for repeated page loads (the extractor and the UI reuse one fetch).
_CACHE_TTL_SECONDS = 120
_recent_cache: dict[str, tuple[float, list[dict]]] = {}


def _service():
    """Build a Gmail API client (personal account, read-only scope)."""
    return build("gmail", "v1", credentials=get_credentials(ACCOUNT, SCOPES))


def _header(headers: list[dict], name: str) -> str:
    """Pull one header value (case-insensitive) from a message's header list."""
    name = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name:
            return h.get("value", "")
    return ""


def _decode_part(data: str) -> str:
    """Decode a base64url message part to text (Gmail uses URL-safe base64)."""
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", "replace")


def _extract_body(payload: dict) -> str:
    """Best-effort plain-text body from a Gmail payload.

    Prefers text/plain; walks multipart trees; ignores attachments. We cap length
    elsewhere — here we just get readable text for the model / preview.
    """
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    if mime == "text/plain" and body.get("data"):
        return _decode_part(body["data"])

    # Recurse into multipart messages, preferring the first text/plain we find.
    parts = payload.get("parts", [])
    for part in parts:
        text = _extract_body(part)
        if text:
            return text
    # Fall back to text/html stripped of tags only if no plain text existed.
    if mime == "text/html" and body.get("data"):
        return _strip_html(_decode_part(body["data"]))
    return ""


def _strip_html(html: str) -> str:
    """Very light HTML→text: drop tags. Good enough for extraction/preview."""
    import re

    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize(msg: dict) -> dict:
    """Shape one Gmail message into the dict the UI/agent/extractor consume."""
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])
    date_raw = _header(headers, "Date")
    try:
        date_iso = parsedate_to_datetime(date_raw).isoformat() if date_raw else None
    except (TypeError, ValueError):
        date_iso = None
    label_ids = msg.get("labelIds", [])
    return {
        "id": msg.get("id", ""),
        "thread_id": msg.get("threadId", ""),
        "from": _header(headers, "From"),
        "subject": _header(headers, "Subject"),
        "date": date_iso,
        "snippet": msg.get("snippet", ""),
        "body": _extract_body(payload),
        "unread": "UNREAD" in label_ids,
        "link": f"https://mail.google.com/mail/u/0/#all/{msg.get('id', '')}",
    }


def list_messages(query: str, max_results: int = 20, use_cache: bool = True) -> list[dict]:
    """Search mail with Gmail's query syntax and return normalized messages.

    `query` is whatever you'd type in the Gmail search box, e.g.
    "is:unread in:inbox", "from:prof subject:exam", "newer_than:14d".
    Newest first. Results are cached briefly per query.
    """
    if use_cache:
        cached = _recent_cache.get(query)
        if cached and (time.time() - cached[0]) < _CACHE_TTL_SECONDS:
            return cached[1]

    svc = _service()
    listed = (
        svc.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    out: list[dict] = []
    for ref in listed.get("messages", []):
        full = (
            svc.users()
            .messages()
            .get(userId="me", id=ref["id"], format="full")
            .execute()
        )
        out.append(_normalize(full))

    _recent_cache[query] = (time.time(), out)
    return out


def get_message(message_id: str) -> dict:
    """Fetch one message by id, fully normalized (incl. body).

    Used when pinning an email we never scanned (e.g. an old, already-read one):
    we pull the full message so the deep re-read has the whole body to work with.
    """
    full = (
        _service()
        .users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    return _normalize(full)


def list_unread(max_results: int = 20) -> list[dict]:
    """The user's unread inbox mail."""
    return list_messages("is:unread in:inbox", max_results=max_results)


def list_today(max_results: int = 40) -> list[dict]:
    """Every inbox email from today (read OR unread), newest first.

    Uses Gmail's `after:` date filter at local midnight. This is the source for
    the "Today (all)" scan and the daily auto-scan — since extraction runs on the
    free local model, reading already-read mail costs nothing but a little GPU.
    """
    from datetime import datetime

    # Gmail's after: takes Y/M/D and is interpreted in the account's timezone;
    # "after: today" therefore means "everything that arrived today".
    today = datetime.now().astimezone().strftime("%Y/%m/%d")
    return list_messages(f"in:inbox after:{today}", max_results=max_results)
