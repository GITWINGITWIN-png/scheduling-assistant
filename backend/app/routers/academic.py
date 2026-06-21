"""Academic endpoints (M3) — backed by Google Classroom (read-only).

Feeds the dashboard's Academic page. All reads come from the *school* account
via the classroom service. Fetches are slowish (many Classroom calls), so the
service caches results for a few minutes.

Classroom is read-only, so "ignore this assignment" is tracked locally (see
services/dismissed.py) and filtered out of to-dos, nudges, and the brief.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import cache, classroom, dismissed

router = APIRouter(prefix="/academic", tags=["academic"])

# Classroom changes slowly; serve the snapshot for 30 min, then refresh in the bg.
_ASSIGNMENTS_TTL = 1800


class IgnoreIn(BaseModel):
    assignment_id: str
    title: str = ""
    course: str = ""


@router.get("/courses")
def courses(active_only: bool = True):
    """The user's courses (active only by default)."""
    try:
        return classroom.list_courses(active_only=active_only)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/assignments")
def assignments(
    background_tasks: BackgroundTasks,
    active_only: bool = True,
    refresh: bool = False,
    db: Session = Depends(get_db),
):
    """Every assignment, each tagged submitted/overdue and `ignored`.

    Served from a DB snapshot for instant skimming (stale-while-revalidate: a
    stale snapshot is returned immediately and refreshed in the background;
    `refresh=true` forces a fresh Google fetch). Ignored flags are applied on top
    of the cached data each call, so ignoring is instant and never needs a refetch.
    """
    def fetch():
        # Bypass the in-memory cache so the DB snapshot is the single source of truth.
        return classroom.list_assignments(active_only=active_only, use_cache=False)

    try:
        env = cache.serve(
            f"assignments:{active_only}",
            fetch,
            ttl=_ASSIGNMENTS_TTL,
            refresh=refresh,
            add_task=background_tasks.add_task,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    excluded = dismissed.ignored_ids(db)
    for a in env["data"]:
        a["ignored"] = a["id"] in excluded
    return env


@router.get("/todo")
def todo(active_only: bool = True, db: Session = Depends(get_db)):
    """Outstanding work (minus ignored), grouped into overdue/upcoming/no_deadline."""
    try:
        return classroom.list_todo_grouped(active_only=active_only, exclude_ids=dismissed.ignored_ids(db))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/ignored")
def ignored(db: Session = Depends(get_db)):
    """The assignments the user has ignored (for review / un-ignoring)."""
    return dismissed.list_ignored(db)


@router.post("/ignore")
def add_ignore(body: IgnoreIn, db: Session = Depends(get_db)):
    """Ignore an assignment so it stops showing in to-dos, nudges, and the brief."""
    dismissed.ignore(db, body.assignment_id, body.title, body.course)
    return {"ignored": body.assignment_id}


@router.delete("/ignore/{assignment_id}")
def remove_ignore(assignment_id: str, db: Session = Depends(get_db)):
    """Un-ignore an assignment."""
    dismissed.unignore(db, assignment_id)
    return {"unignored": assignment_id}
