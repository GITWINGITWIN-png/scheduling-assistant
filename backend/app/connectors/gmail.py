"""Gmail, read-only: what's new, a message's header, a message's text, a thread's order.

Only `gmail.readonly` is used: the secretary can never send, delete or mark mail.

"What's new" uses Gmail's history: every mailbox has a counter (historyId) that
grows with each change. The secretary keeps the last counter it saw and asks
"what was added since?", one cheap call every 5 minutes, read mail included.
Gmail keeps about a week of history. After a longer gap it answers 404, and the
secretary falls back to a search over the last few days.

The Google client is synchronous; callers run these through asyncio.to_thread so
the bot and the web page keep answering meanwhile.
"""

from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import getaddresses, parseaddr

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.connectors import google

SKIP_LABELS = {"SPAM", "TRASH", "DRAFT"}


@dataclass
class Header:
    id: str
    thread_id: str
    sender: str  # address, lowercase
    sender_name: str
    to: list[str]
    subject: str
    snippet: str
    sent_at: datetime  # UTC
    labels: set[str]

    @property
    def from_me(self) -> bool:
        return "SENT" in self.labels


def _service(account: str):
    return build("gmail", "v1", credentials=google.credentials(account), cache_discovery=False)


def profile(account: str) -> tuple[str, str]:
    """(your address on this account, the mailbox's current historyId)."""
    p = _service(account).users().getProfile(userId="me").execute()
    return p["emailAddress"].lower(), p["historyId"]


def added_since(account: str, history_id: str) -> tuple[list[str], str] | None:
    """Ids of messages added since history_id, and the new historyId. None if that's too old."""
    svc, ids, token, latest = _service(account), [], None, history_id
    try:
        while True:
            r = svc.users().history().list(userId="me", startHistoryId=history_id, historyTypes=["messageAdded"],
                                           pageToken=token, maxResults=500).execute()
            latest = r.get("historyId", latest)
            for h in r.get("history", []):
                for added in h.get("messagesAdded", []):
                    m = added["message"]
                    if not SKIP_LABELS & set(m.get("labelIds", [])) and m["id"] not in ids:
                        ids.append(m["id"])
            token = r.get("nextPageToken")
            if not token:
                return ids, latest
    except HttpError as exc:
        if exc.resp.status == 404:  # history this old is gone
            return None
        raise


def search(account: str, query: str, limit: int = 500) -> list[str]:
    """Message ids matching a Gmail search, newest first (e.g. "newer_than:7d")."""
    svc, ids, token = _service(account), [], None
    while len(ids) < limit:
        r = svc.users().messages().list(userId="me", q=query, pageToken=token, maxResults=min(500, limit)).execute()
        ids += [m["id"] for m in r.get("messages", [])]
        token = r.get("nextPageToken")
        if not token:
            break
    return ids[:limit]


def _headers(payload: dict) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def header(account: str, message_id: str) -> Header | None:
    """One message's header and snippet (no body). None if it's gone, spam, trash or a draft."""
    try:
        m = _service(account).users().messages().get(
            userId="me", id=message_id, format="metadata", metadataHeaders=["From", "To", "Cc", "Subject"]).execute()
    except HttpError as exc:
        if exc.resp.status == 404:
            return None
        raise
    labels = set(m.get("labelIds", []))
    if labels & SKIP_LABELS:
        return None
    h = _headers(m.get("payload", {}))
    name, address = parseaddr(h.get("from", ""))
    to = [a.lower() for _, a in getaddresses([h.get("to", ""), h.get("cc", "")]) if a]
    return Header(id=m["id"], thread_id=m["threadId"], sender=address.lower(), sender_name=name, to=to,
                  subject=h.get("subject", "").strip(), snippet=html.unescape(m.get("snippet", "")),
                  sent_at=datetime.fromtimestamp(int(m["internalDate"]) / 1000, timezone.utc), labels=labels)


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", text)
    return html.unescape(re.sub(r"<[^>]+>", " ", text))


def body(account: str, message_id: str, limit: int = 12000) -> str:
    """The message's text: the plain part, or the HTML part with its tags removed. Cut at `limit`
    characters, which is plenty for reading and keeps a long newsletter from eating tokens."""
    m = _service(account).users().messages().get(userId="me", id=message_id, format="full").execute()
    plain, rich = [], []

    def walk(part: dict) -> None:
        mime, data = part.get("mimeType", ""), part.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            rich.append(_strip_html(_decode(data)))
        for p in part.get("parts", []) or []:
            walk(p)

    walk(m.get("payload", {}))
    text = "\n".join(plain) if plain else "\n".join(rich)
    text = re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()
    return text[:limit] + ("\n…(ตัดส่วนที่เหลือ)" if len(text) > limit else "")


def thread_order(account: str, thread_id: str) -> list[tuple[str, bool, datetime]]:
    """Each message of a thread, oldest first: (id, sent by you, when). For follow-ups."""
    t = _service(account).users().threads().get(userId="me", id=thread_id, format="minimal").execute()
    return [(m["id"], "SENT" in m.get("labelIds", []),
             datetime.fromtimestamp(int(m["internalDate"]) / 1000, timezone.utc))
            for m in t.get("messages", []) if not SKIP_LABELS & set(m.get("labelIds", []))]
