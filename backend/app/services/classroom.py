"""Google Classroom access (M3) — the academic input source.

Read-only and least-privilege, on the **school** Google account (separate from
the personal account that owns the calendar/gmail). The credential loader
(`google_auth.get_credentials`) keeps the school token in its own file.

Scope choices, deliberately:
  - courses.readonly        -> the list of courses (we use names to label work)
  - coursework.me.readonly  -> the user's own assignments, due dates, submissions
  - announcements.readonly  -> course announcements
We do NOT request any `classroom.courseworkmaterials.*` scope. Reading course
*materials* is reserved for a future, separate study/learning project — this
secretary only needs the *schedule* (what's due, when, and whether it's done).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.services.google_auth import get_credentials

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
]

# Classroom is on the user's separate school account.
ACCOUNT = "school"

# Submission states that mean "handled" — the student turned it in, or the
# teacher returned/graded it. Everything else (NEW / CREATED /
# RECLAIMED_BY_STUDENT) is still outstanding and can be turned in.
SUBMITTED_STATES = {"TURNED_IN", "RETURNED"}

# A full assignment fetch makes ~2 API calls per active course, so it's slow.
# Cache the result briefly so one page load (and the agent) reuse a single fetch.
# (The `overdue` flag is frozen at fetch time, but 5 minutes' drift is harmless.)
_CACHE_TTL_SECONDS = 300
_assignments_cache: dict[bool, tuple[float, list[dict]]] = {}


def _service():
    """Build a Google Classroom API client (school account)."""
    return build("classroom", "v1", credentials=get_credentials(ACCOUNT, SCOPES))


def _due_datetime(coursework: dict) -> str | None:
    """Combine Classroom's split dueDate + dueTime (both UTC) into an ISO string.

    Returns None when an assignment has no due date. When a date is given but no
    time, Classroom means "end of that day", so we default to 23:59 UTC.
    """
    d = coursework.get("dueDate")
    if not d:
        return None
    t = coursework.get("dueTime", {})
    dt = datetime(
        d["year"],
        d["month"],
        d["day"],
        t.get("hours", 23),
        t.get("minutes", 59),
        t.get("seconds", 0),
        tzinfo=timezone.utc,
    )
    return dt.isoformat()


def _paged(request_fn, key: str) -> list[dict]:
    """Collect every page of a Classroom list call into one list.

    `request_fn(page_token)` should return the API request for that page.
    """
    items: list[dict] = []
    page_token = None
    while True:
        resp = request_fn(page_token).execute()
        items.extend(resp.get(key, []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return items


def list_courses(active_only: bool = True, service=None) -> list[dict]:
    """Return the user's courses (active only by default)."""
    svc = service or _service()
    courses = _paged(
        lambda pt: svc.courses().list(pageSize=100, pageToken=pt), "courses"
    )
    if active_only:
        courses = [c for c in courses if c.get("courseState") == "ACTIVE"]
    return courses


def list_coursework(course_id: str, service=None) -> list[dict]:
    """Return the assignments (course work) for one course."""
    svc = service or _service()
    return _paged(
        lambda pt: svc.courses()
        .courseWork()
        .list(courseId=course_id, pageSize=100, pageToken=pt),
        "courseWork",
    )


def list_my_submissions(course_id: str, service=None) -> list[dict]:
    """Return the user's own submissions across all coursework in a course.

    `courseWorkId="-"` is Classroom's wildcard for "every assignment".
    """
    svc = service or _service()
    return _paged(
        lambda pt: svc.courses()
        .courseWork()
        .studentSubmissions()
        .list(
            courseId=course_id,
            courseWorkId="-",
            userId="me",
            pageSize=100,
            pageToken=pt,
        ),
        "studentSubmissions",
    )


def list_assignments(active_only: bool = True, use_cache: bool = True) -> list[dict]:
    """Flatten assignments across all (active) courses into one schedule list.

    Each item is normalized for the UI/agent:
        {course, course_id, id, title, due (ISO|None), state, late,
         submitted, overdue, link}
    where `state` is the submission state (NEW / CREATED / TURNED_IN /
    RETURNED / RECLAIMED_BY_STUDENT). Sorted by due date; undated assignments
    sort to the end. Results are cached for a few minutes (see `use_cache`).
    """
    if use_cache:
        cached = _assignments_cache.get(active_only)
        if cached and (time.time() - cached[0]) < _CACHE_TTL_SECONDS:
            return cached[1]

    svc = _service()
    now = datetime.now(timezone.utc)
    out: list[dict] = []

    for course in list_courses(active_only=active_only, service=svc):
        cid = course["id"]
        cname = course.get("name", "")
        try:
            work = list_coursework(cid, service=svc)
            subs = {
                s.get("courseWorkId"): s
                for s in list_my_submissions(cid, service=svc)
            }
        except HttpError as e:
            # A missing-scope error is a global config problem, not a per-course
            # quirk — never hide it, or "0 assignments" looks like empty courses.
            if "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in str(e):
                raise
            # Otherwise this is a course we just can't read as a student
            # (e.g. teacher-only coursework) — skip it and keep going.
            continue

        for cw in work:
            sub = subs.get(cw["id"], {})
            state = sub.get("state", "NEW")
            due = _due_datetime(cw)
            submitted = state in SUBMITTED_STATES
            # Open + past its due date → still turn-in-able, but late.
            overdue = bool(due and not submitted and datetime.fromisoformat(due) < now)
            out.append(
                {
                    "course": cname,
                    "course_id": cid,
                    "id": cw["id"],
                    "title": cw.get("title", ""),
                    "due": due,
                    "state": state,
                    "late": sub.get("late", False),
                    "submitted": submitted,
                    "overdue": overdue,
                    "link": cw.get("alternateLink"),
                }
            )

    # Soonest due first; undated (None) last.
    out.sort(key=lambda a: (a["due"] is None, a["due"] or ""))
    _assignments_cache[active_only] = (time.time(), out)
    return out


def list_todo(active_only: bool = True, exclude_ids: set[str] = frozenset()) -> list[dict]:
    """Only the assignments that still need action (not yet turned in).

    Drops anything already TURNED_IN or RETURNED (and anything in `exclude_ids`,
    i.e. assignments the user has ignored), so what remains is everything you can
    still submit — whether upcoming or `overdue`. Soonest due first, undated last.
    """
    return [
        a
        for a in list_assignments(active_only=active_only)
        if not a["submitted"] and a["id"] not in exclude_ids
    ]


def list_todo_grouped(
    active_only: bool = True, exclude_ids: set[str] = frozenset()
) -> dict[str, list[dict]]:
    """Outstanding work split into the three buckets the Academic page shows:

        overdue      — past its due date, still open (turn in late)
        upcoming     — has a future due date, still open (turn in on time)
        no_deadline  — open but no due date (often optional)
    """
    todo = list_todo(active_only=active_only, exclude_ids=exclude_ids)
    return {
        "overdue": [a for a in todo if a["overdue"]],
        "upcoming": [a for a in todo if a["due"] and not a["overdue"]],
        "no_deadline": [a for a in todo if not a["due"]],
    }
