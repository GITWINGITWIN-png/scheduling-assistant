"""Ignored-assignment store (M5+).

Small helpers over the IgnoredAssignment table so to-dos, nudges, the brief, and
the agent all share one notion of "ignored". Used wherever assignments are shown.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import IgnoredAssignment


def ignored_ids(db: Session) -> set[str]:
    """The set of assignment ids the user has ignored."""
    return set(db.scalars(select(IgnoredAssignment.assignment_id)).all())


def ignore(db: Session, assignment_id: str, title: str = "", course: str = "") -> None:
    if db.get(IgnoredAssignment, assignment_id) is None:
        db.add(IgnoredAssignment(assignment_id=assignment_id, title=title, course=course))
        db.commit()


def unignore(db: Session, assignment_id: str) -> None:
    db.execute(delete(IgnoredAssignment).where(IgnoredAssignment.assignment_id == assignment_id))
    db.commit()


def list_ignored(db: Session) -> list[dict]:
    rows = db.scalars(select(IgnoredAssignment)).all()
    return [{"assignment_id": r.assignment_id, "title": r.title, "course": r.course} for r in rows]
