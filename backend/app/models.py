"""Database models for the smart layer.

These are intentionally minimal for M0 — just enough to prove the database
works and to sketch the shape of the project-aware planner we build in M4.
We'll expand these as we go.
"""

from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Project(Base):
    """A piece of work the secretary should schedule time toward.

    The headline feature plans backward from `deadline` using the remaining
    effort across this project's tasks. `repo_path` lets us later auto-read
    progress from git activity / a TODO file.
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(Text, default="")
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Optional: a local repo to auto-detect progress from (M4 stretch goal).
    repo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Task(Base):
    """A unit of work inside a Project, with an effort estimate in hours."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String(300))
    estimated_hours: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(
        Enum("todo", "in_progress", "done", name="task_status"), default="todo"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="tasks")
