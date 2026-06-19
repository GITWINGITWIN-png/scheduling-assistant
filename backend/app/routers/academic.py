"""Academic endpoints (M3) — backed by Google Classroom (read-only).

Feeds the dashboard's Academic page. All reads come from the *school* account
via the classroom service. Fetches are slowish (many Classroom calls), so the
service caches results for a few minutes.
"""

from fastapi import APIRouter, HTTPException

from app.services import classroom

router = APIRouter(prefix="/academic", tags=["academic"])


@router.get("/courses")
def courses(active_only: bool = True):
    """The user's courses (active only by default)."""
    try:
        return classroom.list_courses(active_only=active_only)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/assignments")
def assignments(active_only: bool = True):
    """Every assignment across active courses, each tagged submitted/overdue."""
    try:
        return classroom.list_assignments(active_only=active_only)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/todo")
def todo(active_only: bool = True):
    """Outstanding work only, grouped into overdue / upcoming / no_deadline."""
    try:
        return classroom.list_todo_grouped(active_only=active_only)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
