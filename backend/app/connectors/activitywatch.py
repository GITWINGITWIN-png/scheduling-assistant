"""ActivityWatch on this computer (4.1, B6): its REST API on localhost:5600, read only.

awatcher keeps two buckets: aw-watcher-window_<host> (app and title of the window in front) and
aw-watcher-afk_<host> (whether you're at the computer). `active_windows` asks ActivityWatch's own
query language for the window events while you were not away. ActivityWatch cuts the away time
out itself, so the secretary never has to match the two up.

Blocking calls (urllib): run them in a thread. Nothing here filters anything: the privacy filter is
features/time/privacy.py, and awatcher's config is the first line of it.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta

URL = "http://127.0.0.1:5600/api/0"
TIMEOUT = 20


class Unreachable(RuntimeError):
    """ActivityWatch isn't answering (not installed, switched off, or paused)."""


class Refused(RuntimeError):
    """ActivityWatch answered with an error; the message is what it said."""


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime
    app: str
    title: str


def _call(method: str, path: str, body: object | None = None) -> object:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL + path, data=data, method=method, headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return json.loads(res.read() or b"null")
    except urllib.error.HTTPError as exc:  # it answered, with an error
        raise Refused(f"{exc.code}: {exc.read().decode(errors='replace')[:300]}") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as exc:
        raise Unreachable(str(exc)) from exc


def info() -> dict:
    return _call("GET", "/info")  # type: ignore[return-value]


def buckets() -> dict:
    return _call("GET", "/buckets/")  # type: ignore[return-value]


def _period(start: datetime, end: datetime) -> str:
    return f"{start.isoformat()}/{end.isoformat()}"


QUERY_ACTIVE = [
    'afk = flood(query_bucket(find_bucket("aw-watcher-afk_")));',
    'present = filter_keyvals(afk, "status", ["not-afk"]);',
    'win = flood(query_bucket(find_bucket("aw-watcher-window_")));',
    "RETURN = filter_period_intersect(win, present);",
]
QUERY_COVERED = ['afk = flood(query_bucket(find_bucket("aw-watcher-afk_")));', "RETURN = afk;"]
QUERY_PRESENT = [
    'afk = flood(query_bucket(find_bucket("aw-watcher-afk_")));',
    'RETURN = filter_keyvals(afk, "status", ["not-afk"]);',
]


def _events(query: list[str], start: datetime, end: datetime) -> list[dict]:
    """One query over [start, end). A computer with no buckets yet (just installed) has nothing."""
    try:
        out = _call("POST", "/query/", {"timeperiods": [_period(start, end)], "query": query})
    except Refused as exc:
        if "bucket" in str(exc).lower():  # find_bucket: nothing recorded yet
            return []
        raise
    return out[0] if isinstance(out, list) and out else []


def _when(e: dict) -> tuple[datetime, datetime]:
    start = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
    return start, start + timedelta(seconds=float(e.get("duration") or 0))


def active_windows(start: datetime, end: datetime) -> list[Window]:
    """The windows you were in, while not away, between start and end (cut to that span)."""
    out = []
    for e in _events(QUERY_ACTIVE, start, end):
        a, b = _when(e)
        a, b = max(a, start), min(b, end)
        if b > a:
            data = e.get("data") or {}
            out.append(Window(a, b, str(data.get("app", "")), str(data.get("title", ""))))
    out.sort(key=lambda w: w.start)
    return out


def present(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """When you were at the computer (not away), whatever window: B6's plan-vs-actual uses it to
    tell "doing something else" from "not at the computer"."""
    spans = []
    for e in _events(QUERY_PRESENT, start, end):
        a, b = _when(e)
        a, b = max(a, start), min(b, end)
        if b > a:
            spans.append((a, b))
    return sorted(spans)


def covered(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """When the recorder was running at all (away or not): "nothing recorded" isn't "you were away"."""
    spans = []
    for e in _events(QUERY_COVERED, start, end):
        a, b = _when(e)
        a, b = max(a, start), min(b, end)
        if b > a:
            spans.append((a, b))
    return sorted(spans)
