"""Google Calendar on the main account (google.CALENDAR_ACCOUNT): read a window, write, move, delete.

Two calendars are used:

- **primary**: your own calendar. Appointments the secretary found in email go here (B2),
  and everything on it counts as busy time when work blocks are placed.
- **"เลขา"** (BLOCKS_NAME): a separate calendar the secretary creates for its work blocks
  (B3, the user's choice: "แยกชื่อเลขาออกมา"). You can hide it or delete it as a whole in
  Google Calendar without touching your real appointments. Its id is saved in the
  settings ("state.calendar"); if you delete it, the next write creates it again.

Everything the secretary writes carries a private mark (extendedProperties.private
"secretary"), so reading the calendar back tells its entries from yours.
Synchronous, like gmail.py: call through asyncio.to_thread.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.connectors import google
from app.core import settings
from app.core.config import get_config

BLOCKS_NAME = "เลขา"
STATE_KEY = "state.calendar"  # {"blocks": calendar id}
MARK = "secretary"  # extendedProperties.private key on everything the secretary writes


@dataclass
class CalEvent:
    id: str
    title: str
    start: datetime  # aware; for an all-day event, local midnight
    end: datetime
    all_day: bool
    location: str
    link: str
    mark: str  # what the secretary wrote it as ("block", "appointment"), or "" if it's yours
    busy: bool  # False for events marked "free" (transparency) or ones you declined
    recurring: bool  # one day of a repeating event (a weekly class): not reminded about
    description: str = ""  # as plain text (see plain_text)
    color: str = ""  # its own colour (COLORS), or "" when it shows in its calendar's colour


# Google Calendar's event colours: colorId -> (the colour Google draws it in today, its Thai name).
# An event without a colorId takes its calendar's colour.
COLORS = {"1": ("#7986cb", "ลาเวนเดอร์"), "2": ("#33b679", "เขียวอ่อน"), "3": ("#8e24aa", "ม่วง"),
          "4": ("#e67c73", "ชมพู"), "5": ("#f6bf26", "เหลือง"), "6": ("#f4511e", "ส้ม"), "7": ("#039be5", "ฟ้า"),
          "8": ("#616161", "เทา"), "9": ("#3f51b5", "น้ำเงิน"), "10": ("#0b8043", "เขียว"), "11": ("#d50000", "แดง")}
COLOR_IDS = {hex_: color_id for color_id, (hex_, _) in COLORS.items()}


SIGNATURE = "ลงโดยเลขา"  # the last line of every description the secretary writes


def plain_text(description: str) -> str:
    """An event description as plain text. Google Calendar's own editor stores HTML (<br>, <b>,
    <a href>); a link's address is kept. The secretary's "ลงโดยเลขา" line is dropped."""
    text = description or ""
    if re.search(r"<[a-zA-Z/][^>]*>", text):
        text = re.sub(r'<a\s[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                      lambda m: m.group(2) if m.group(2).strip() == m.group(1) else f"{m.group(2)} ({m.group(1)})",
                      text, flags=re.S | re.I)
        text = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[: -len(SIGNATURE)].rstrip() if text.endswith(SIGNATURE) else text


def _service():
    return build("calendar", "v3", credentials=google.credentials(google.CALENDAR_ACCOUNT, google.CALENDAR),
                 cache_discovery=False)


def _missing(exc: HttpError) -> bool:
    return exc.resp.status in (404, 410)


# ------------------------------------------------------------------ the "เลขา" calendar
def blocks_calendar(*, create: bool = True) -> str | None:
    """The id of the "เลขา" calendar, created if needed (unless create=False)."""
    svc = _service()
    saved = (settings.get(STATE_KEY) or {}).get("blocks")
    if saved:
        try:
            cal = svc.calendarList().get(calendarId=saved).execute()
            if not cal.get("deleted"):
                return saved
        except HttpError as exc:
            if not _missing(exc):
                raise
    # Not saved (or deleted): reuse a "เลขา" calendar you own before making another one, so
    # losing the saved id (a fresh database, a test run) never leaves duplicates behind.
    token = None
    while True:
        page = svc.calendarList().list(minAccessRole="owner", pageToken=token).execute()
        for cal in page.get("items", []):
            if cal.get("summary") == BLOCKS_NAME and not cal.get("deleted"):
                settings.put(STATE_KEY, {**(settings.get(STATE_KEY) or {}), "blocks": cal["id"]})
                return cal["id"]
        token = page.get("nextPageToken")
        if not token:
            break
    if not create:
        return None
    body = {"summary": BLOCKS_NAME, "timeZone": get_config().timezone,
            "description": "บล็อกงานที่เลขาวางให้ · ซ่อนหรือลบทั้งปฏิทินได้ ไม่กระทบนัดจริงในปฏิทินหลัก"}
    cal_id = svc.calendars().insert(body=body).execute()["id"]
    settings.put(STATE_KEY, {**(settings.get(STATE_KEY) or {}), "blocks": cal_id})
    return cal_id


# ------------------------------------------------------------------ writing
def _when(start: datetime, end: datetime, all_day: bool) -> dict:
    tz = get_config().timezone
    if all_day:
        return {"start": {"date": start.date().isoformat()},
                "end": {"date": (max(end, start + timedelta(days=1))).date().isoformat()}}
    return {"start": {"dateTime": start.isoformat(), "timeZone": tz},
            "end": {"dateTime": end.isoformat(), "timeZone": tz}}


def insert(title: str, start: datetime, end: datetime, *, all_day: bool = False, location: str = "",
           description: str = "", calendar: str = "primary", mark: str = "appointment") -> tuple[str, str]:
    """Create the event. -> (event id, link to open it in Google Calendar)."""
    body = {"summary": title, "location": location, "description": description, **_when(start, end, all_day),
            "extendedProperties": {"private": {MARK: mark}},
            "source": {"title": "เลขา", "url": "http://localhost:8000/schedule"}}
    if mark == "block":
        body["reminders"] = {"useDefault": False, "overrides": []}  # the secretary reminds in #ด่วน instead
    ev = _service().events().insert(calendarId=calendar, body=body).execute()
    return ev["id"], ev.get("htmlLink", "")


def move(event_id: str, start: datetime, end: datetime, *, calendar: str = "primary") -> bool:
    """Change an event's time. False if it no longer exists (you deleted it)."""
    try:
        _service().events().patch(calendarId=calendar, eventId=event_id, body=_when(start, end, False)).execute()
        return True
    except HttpError as exc:
        if _missing(exc):
            return False
        raise


def recolor(event_id: str, color_id: str, *, calendar: str = "primary") -> bool:
    """Give the event one of COLORS ("" = back to its calendar's colour). False if it no longer exists."""
    try:
        _service().events().patch(calendarId=calendar, eventId=event_id, body={"colorId": color_id or None}).execute()
        return True
    except HttpError as exc:
        if _missing(exc):
            return False
        raise


def retext(event_id: str, title: str, description: str, *, calendar: str = "primary") -> bool:
    """Change an event's title and description. False if it no longer exists."""
    try:
        _service().events().patch(calendarId=calendar, eventId=event_id,
                                  body={"summary": title, "description": description}).execute()
        return True
    except HttpError as exc:
        if _missing(exc):
            return False
        raise


def delete(event_id: str, *, calendar: str = "primary") -> None:
    """Remove the event; an event already deleted by hand counts as done."""
    try:
        _service().events().delete(calendarId=calendar, eventId=event_id).execute()
    except HttpError as exc:
        if not _missing(exc):
            raise


# ------------------------------------------------------------------ reading
def _parse_time(t: dict) -> tuple[datetime, bool]:
    if "dateTime" in t:
        return datetime.fromisoformat(t["dateTime"]), False
    day = datetime.fromisoformat(t["date"])  # all-day: a date only, so local midnight
    return day.replace(tzinfo=get_config().tz), True


def window(start: datetime, end: datetime, *, calendar: str = "primary") -> list[CalEvent]:
    """Every event overlapping [start, end), repeating ones expanded into single days."""
    svc, out, token = _service(), [], None
    while True:
        r = svc.events().list(calendarId=calendar, timeMin=start.isoformat(), timeMax=end.isoformat(),
                              singleEvents=True, orderBy="startTime", maxResults=250, pageToken=token).execute()
        for e in r.get("items", []):
            if e.get("status") == "cancelled" or "start" not in e:
                continue
            s, all_day = _parse_time(e["start"])
            en, _ = _parse_time(e["end"])
            declined = any(a.get("self") and a.get("responseStatus") == "declined" for a in e.get("attendees", []))
            out.append(CalEvent(id=e["id"], title=e.get("summary", "(ไม่มีชื่อ)"), start=s, end=en, all_day=all_day,
                                location=e.get("location", ""), link=e.get("htmlLink", ""),
                                mark=e.get("extendedProperties", {}).get("private", {}).get(MARK, ""),
                                busy=e.get("transparency") != "transparent" and not declined,
                                recurring="recurringEventId" in e, description=plain_text(e.get("description", "")),
                                color=COLORS.get(str(e.get("colorId", "")), ("", ""))[0]))
        token = r.get("nextPageToken")
        if not token:
            return out
