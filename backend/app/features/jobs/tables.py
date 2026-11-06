"""quota and jobs (stage 3's data model) for the background work. (rules live in core/tables.py:
other parts read them too.)"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, now


class QuotaReading(Base):
    """quota · โควตา: what your Claude plan has left, as the CLI reports it with every call
    (RateLimitEvent: the 7-day and 5-hour windows). Kept when it changes, or every 10 minutes."""

    __tablename__ = "quota_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)
    week_left: Mapped[float] = mapped_column(Float)  # percent of the 7-day window left
    week_resets_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    five_left: Mapped[float | None] = mapped_column(Float, nullable=True)  # percent of the 5-hour window left
    five_resets_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="sdk")  # where it was read: sdk (RateLimitEvent)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)


class Job(Base):
    """jobs · คิวงานเบื้องหลัง (2.2, 3.2, B5): one piece of work the secretary does in a project
    while you're away: the next step in the project's PROGRESS.md, or what you asked with ทำต่อ.

    status: queued (waiting for its plan) · asking (the plan waits for you in #อนุมัติ) · ready
      (may start: the rules allow it, or you approved it) · running · done · stopped (over budget,
      going round in circles, or you stopped it) · failed · rejected (you said ไม่เอา) · dropped
      (you took it out of the queue) · paused (the project was switched off or hidden; it comes
      back with the project)
    """

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    project: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(10), default="progress")  # progress · you
    stuck_at: Mapped[str] = mapped_column(Text, default="")  # ค้างที่: the step in PROGRESS.md
    note: Mapped[str] = mapped_column(Text, default="")  # what you added with ทำต่อ, or asked to change
    status: Mapped[str] = mapped_column(String(10), default="queued", index=True)
    # the plan (B5.6)
    title: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[list] = mapped_column(JSON, default=list)
    model: Mapped[str] = mapped_column(String(10), default="")
    effort: Mapped[str] = mapped_column(String(10), default="")
    estimate: Mapped[int] = mapped_column(Integer, default=0)  # tokens the planner expects at that effort
    budget: Mapped[int] = mapped_column(Integer, default=0)  # estimate × 1.2: the runner stops past it
    risks: Mapped[list] = mapped_column(JSON, default=list)  # high-risk kinds: "download"..., "rule12" (yours)
    why: Mapped[str] = mapped_column(Text, default="")  # the planner's one line on its choices
    plan_tokens: Mapped[int] = mapped_column(Integer, default=0)  # what making the plan cost
    planned_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # the rule check
    rule_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rule_why: Mapped[str] = mapped_column(Text, default="")
    decision_id: Mapped[int | None] = mapped_column(ForeignKey("decisions.id"), nullable=True)
    approved_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # the run (B5.7)
    branch: Mapped[str] = mapped_column(String(120), default="")
    used: Mapped[int] = mapped_column(Integer, default=0)  # tokens so far
    result: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
