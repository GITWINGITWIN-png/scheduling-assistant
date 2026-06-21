"""Projects endpoints (M4).

Backs the dashboard's Projects page and feeds the planner. Projects can be added
two ways (the "both" choice): auto-discovered from a folder of git repos, or
created/edited manually for goals, deadlines, and effort estimates.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project
from app.services import calendar as cal
from app.services import planner, repos

router = APIRouter(prefix="/projects", tags=["projects"])


# --- request bodies ---
class ProjectCreate(BaseModel):
    name: str
    goal: str = ""
    deadline: datetime | None = None
    status: str = "active"
    estimated_hours: float = 0.0
    repo_path: str | None = None


class ProjectUpdate(BaseModel):
    # All optional: send only the fields you want to change.
    name: str | None = None
    goal: str | None = None
    deadline: datetime | None = None
    status: str | None = None
    estimated_hours: float | None = None
    repo_path: str | None = None


class DiscoverIn(BaseModel):
    root: str  # a folder containing git repos, e.g. "~/Projects"


class PlanBlock(BaseModel):
    title: str
    start: datetime
    end: datetime


class PlanCommit(BaseModel):
    blocks: list[PlanBlock]


def _serialize(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "goal": p.goal,
        "deadline": p.deadline,
        "status": p.status,
        "estimated_hours": p.estimated_hours,
        "repo_path": p.repo_path,
        "last_commit_at": p.last_commit_at,
    }


def _get_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    """All projects, most-recently-committed first (undated sink to the bottom)."""
    projects = db.scalars(select(Project)).all()
    projects = sorted(projects, key=lambda p: p.last_commit_at or datetime.min, reverse=True)
    return [_serialize(p) for p in projects]


@router.post("")
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    """Manually add a project."""
    project = Project(**body.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return _serialize(project)


@router.patch("/{project_id}")
def update_project(project_id: int, body: ProjectUpdate, db: Session = Depends(get_db)):
    """Edit a project — only the fields you send are changed."""
    project = _get_or_404(db, project_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return _serialize(project)


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Remove a project (does not touch its git repo, only our record of it)."""
    project = _get_or_404(db, project_id)
    db.delete(project)
    db.commit()
    return {"deleted": project_id}


@router.post("/discover")
def discover(body: DiscoverIn, db: Session = Depends(get_db)):
    """Scan a folder for git repos and upsert them as projects.

    New repos become `active` projects (you fill in deadline/effort after).
    Existing ones (matched by repo_path) just get their last-commit refreshed —
    your goal/deadline/effort are left untouched.
    """
    found = repos.discover_repos(body.root)
    existing = {
        p.repo_path: p
        for p in db.scalars(select(Project)).all()
        if p.repo_path is not None
    }

    synced: list[Project] = []
    for r in found:
        last = datetime.fromisoformat(r["last_commit_at"]) if r["last_commit_at"] else None
        project = existing.get(r["path"])
        if project is None:
            project = Project(name=r["name"], repo_path=r["path"], last_commit_at=last)
            db.add(project)
        else:
            project.last_commit_at = last
        synced.append(project)

    db.commit()
    for p in synced:
        db.refresh(p)
    return [_serialize(p) for p in synced]


@router.get("/{project_id}/progress")
def progress(project_id: int, db: Session = Depends(get_db)):
    """Read live git progress for a project's repo (no-op if it has no repo)."""
    project = _get_or_404(db, project_id)
    if not project.repo_path:
        return {"repo_path": None, "message": "No repo linked to this project."}
    return {"repo_path": project.repo_path, **repos.read_progress(project.repo_path)}


@router.post("/{project_id}/plan")
def plan(project_id: int, db: Session = Depends(get_db)):
    """Preview a plan: proposed work blocks in the calendar's free gaps.

    This is read-only — nothing is written to the calendar. Show the blocks to
    the user, then POST them to /plan/commit once they approve.
    """
    project = _get_or_404(db, project_id)
    try:
        return planner.make_plan(project)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{project_id}/plan/commit")
def commit_plan(project_id: int, body: PlanCommit, db: Session = Depends(get_db)):
    """Create calendar events for approved plan blocks."""
    project = _get_or_404(db, project_id)
    note = f"Auto-planned by my_secretary for project: {project.name}"
    try:
        links = [
            cal.create_event(b.title, b.start, b.end, description=note).get("htmlLink", "")
            for b in body.blocks
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"created": len(links), "links": links}
