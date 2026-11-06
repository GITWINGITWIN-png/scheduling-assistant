"""The "activity" round (every 15 minutes, off until B6's check): read ActivityWatch, filter, keep.

Each read takes what happened since the last one, from ActivityWatch on this computer, while you
were at the computer (ActivityWatch's own query cuts the away time out):
1. the privacy filter: a blocked app or title is skipped, and a title with a blocked word is kept
   as HIDDEN (privacy.verdict); any part inside a pause is cut out (privacy.cut_pauses);
2. each window is sorted into a category and maybe a project, by rules (categorize.py);
3. it's kept in `activity`.

The window you're still in keeps growing in ActivityWatch, so every read starts OVERLAP before the
last one ended and replaces that stretch. Reading twice never counts anything twice. A read that
fails (ActivityWatch off, paused, not installed) changes nothing, and the next one catches up,
up to BACKFILL back.

A read leaves no line in สิ่งที่เลขาทำ (it runs 96 times a day). The time page shows when it last
read, and why it couldn't.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from app.connectors import activitywatch as aw
from app.core import settings
from app.core.db import now, session
from app.features.time import privacy
from app.features.time.tables import HIDDEN, Activity

log = logging.getLogger(__name__)

STATE_KEY = "state.activity"  # {"to": the last read's end, "at": when, "error": why the last try failed}
OVERLAP = timedelta(minutes=30)
FIRST = timedelta(days=1)  # the first read ever goes back this far
BACKFILL = timedelta(days=7)  # after a long gap, at most this far

# Called after each read with (start, end, presence spans): B6's plan-vs-actual checks the blocks
# that ended in it (followed.py). The presence spans tell "doing something else" from "away".
READ: list = []


@dataclass
class Read:
    start: datetime
    end: datetime
    kept: int = 0
    skipped: int = 0  # windows the blocklist dropped
    hidden: int = 0
    present: list[tuple[datetime, datetime]] = field(default_factory=list)


def sorter():
    """(app, title) -> (category, project id, project name). Until the category rules arrive
    (categorize.py), everything is kept unsorted."""
    return lambda app, title: ("", None, "")


def read(at: datetime | None = None) -> Read:
    """One read (blocking: runs in a thread). Raises aw.Unreachable when ActivityWatch doesn't answer."""
    at = at or now()
    state = settings.get(STATE_KEY, {}) or {}
    last = datetime.fromisoformat(state["to"]) if state.get("to") else None
    start = max(last - OVERLAP if last else at - FIRST, at - BACKFILL)
    windows = aw.active_windows(start, at)
    present = aw.present(start, at)
    rules, pauses, sort = privacy.rules(), privacy.pauses(), sorter()
    result = Read(start, at, present=[p for s, e in present for p in privacy.cut_pauses(s, e, pauses)])
    rows = []
    for w in windows:
        verdict = rules.verdict(w.app, w.title)
        if verdict == "drop":
            result.skipped += 1
            continue
        title = HIDDEN if verdict == "hide" else w.title
        result.hidden += verdict == "hide"
        category, project_id, project = sort(w.app, title)
        for a, b in privacy.cut_pauses(w.start, w.end, pauses):
            rows.append(Activity(start=a, end=b, app=w.app[:120], title=title[:300], category=category,
                                 project_id=project_id, project=project))
    with session() as s:
        s.execute(delete(Activity).where(Activity.start >= start))
        for row in s.scalars(select(Activity).where(Activity.start < start, Activity.end > start)):
            row.end = start  # its tail is in this read again
        s.add_all(rows)
    result.kept = len(rows)
    settings.put(STATE_KEY, {"to": at.isoformat(), "at": now().isoformat(), "error": ""})
    return result


async def run() -> str | None:
    """The "activity" round."""
    try:
        result = await asyncio.to_thread(read)
    except (aw.Unreachable, aw.Refused) as exc:
        state = settings.get(STATE_KEY, {}) or {}
        settings.put(STATE_KEY, {**state, "error": str(exc)[:300], "error_at": now().isoformat()})
        log.info("couldn't read ActivityWatch: %s", exc)
        return None
    for hook in READ:
        try:
            await hook(result)
        except Exception:
            log.exception("after reading ActivityWatch")
    return None


def last_read() -> dict:
    return settings.get(STATE_KEY, {}) or {}


def setup() -> None:
    from app.core import clock
    clock.attach("activity", run)
