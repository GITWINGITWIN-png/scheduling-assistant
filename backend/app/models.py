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
    goal: Mapped[str] = mapped_column(Text, default="")  # short description
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Where the project stands: active = being worked on, waiting = blocked on
    # something/someone, done = finished, dropped = abandoned.
    status: Mapped[str] = mapped_column(
        Enum("active", "waiting", "done", "dropped", name="project_status"),
        default="active",
    )
    # Total hours of work the planner should still book toward the deadline.
    estimated_hours: Mapped[float] = mapped_column(Float, default=0.0)
    # A local git repo to auto-read progress from (M4): last commit, activity.
    repo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Cached from the repo on the last discover/sync, so the UI is fast.
    last_commit_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class DailyBrief(Base):
    """A generated morning brief, cached one per day.

    Generating it costs a Claude call, so we store today's once and reuse it
    (the dashboard lazily creates it on first open; a scheduler pre-warms it).
    """

    __tablename__ = "daily_briefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    for_date: Mapped[str] = mapped_column(String(10), unique=True)  # "YYYY-MM-DD"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


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
