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


class IgnoredAssignment(Base):
    """A Classroom assignment the user chose to ignore.

    Classroom is read-only, so "ignore" is tracked here locally. Ignored
    assignments are filtered out of to-dos, nudges, and the daily brief — handy
    for old homework from finished courses that can never be turned in. We keep
    the title/course so the "ignored" list is readable when un-ignoring.
    """

    __tablename__ = "ignored_assignments"

    assignment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    course: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PinnedEmail(Base):
    """An email the user "pinned" as interesting (M6).

    Pinned mail shows on the Projects page in a separate "From email" section and
    is treated like a lightweight project. If the email carried a date, we also
    create a calendar event for it and remember its id here, so un-pinning can
    remove that event too. (Gmail itself stays read-only — this is all local.)
    """

    __tablename__ = "pinned_emails"

    email_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(String(500), default="")
    sender: Mapped[str] = mapped_column(String(300), default="")
    link: Mapped[str] = mapped_column(String(500), default="")
    note: Mapped[str] = mapped_column(String(500), default="")
    # The extracted date (ISO 8601), if any — drives the calendar event + deadline.
    date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # The calendar event we created for a dated pin (so unpin can delete it).
    calendar_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DailyMailScan(Base):
    """Cached result of the daily local-LLM scan over today's mail (M6).

    The scan is free (local model) but still takes a little time, so we cache one
    result per day — the scheduler pre-warms it each morning and the Mail page
    reads it lazily, mirroring how `DailyBrief` works. `content` is the JSON scan
    payload (items + counts) as text.
    """

    __tablename__ = "daily_mail_scans"

    for_date: Mapped[str] = mapped_column(String(10), primary_key=True)  # "YYYY-MM-DD"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Snapshot(Base):
    """A cached snapshot of an expensive read, so the UI can skim instantly.

    Google reads are slow (Classroom ~2 calls/course; Gmail 1 list + 1 get/msg),
    so we persist the last fetch here and serve it immediately. Each row is one
    logical dataset keyed by a string (e.g. "assignments:True", "mail:unread",
    "calendar:<start>:<end>"); `content` is the JSON payload and `fetched_at`
    drives the "updated N ago" label + stale-while-revalidate refresh. Surviving
    restarts is the whole point — unlike the per-process in-memory caches.
    """

    __tablename__ = "snapshots"

    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)


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
