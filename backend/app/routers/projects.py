"""Projects endpoint (M2 scaffold).

Backs the dashboard's Projects page. The Project table exists (from M0) but is
empty until M4's planner populates it — so this returns whatever is there
(likely [] for now). Shape will grow (status, last-commit) when we build M4.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    projects = db.scalars(select(Project)).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "goal": p.goal,
            "deadline": p.deadline,
        }
        for p in projects
    ]
