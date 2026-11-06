"""projects · ทะเบียนโปรเจค (stage 3's data model): every folder under ~/Projects.

status: idea · active · paused · auto · done (ไอเดีย / กำลังทำ / พัก / รันอัตโนมัติ / จบแล้ว).
potential S–F and urgency 0–5, **5 the most urgent** (the user's choice at the B5 plan,
2026-11-06, matching the approved mockups); both order the background-work queue and the
advice, and decide which project news is urgent. A project starts at C · 2 until you set it.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, now

STATUSES = {"idea": "ไอเดีย", "active": "กำลังทำ", "paused": "พัก", "auto": "รันอัตโนมัติ", "done": "จบแล้ว"}
POTENTIALS = ("S", "A", "B", "C", "D", "F")
DEFAULT_POTENTIAL, DEFAULT_URGENCY = "C", 2


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))  # the folder's name
    path: Mapped[str] = mapped_column(Text, unique=True)
    status: Mapped[str] = mapped_column(String(10), default="paused")
    potential: Mapped[str] = mapped_column(String(1), default=DEFAULT_POTENTIAL)
    urgency: Mapped[int] = mapped_column(Integer, default=DEFAULT_URGENCY)  # 5 = most urgent
    level_set: Mapped[bool] = mapped_column(Boolean, default=False)  # you set potential and urgency
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)  # not a project (a backup, a copy): you hid it
    allow_jobs: Mapped[bool] = mapped_column(Boolean, default=False)  # ให้เลขาทำต่อได้ (off for every project at first)
    is_git: Mapped[bool] = mapped_column(Boolean, default=False)
    last_activity: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)  # last commit, or the folder's change
    commits_14d: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[dict] = mapped_column(JSON, default=dict)  # from its PROGRESS.md (progress.py)
    missing: Mapped[bool] = mapped_column(Boolean, default=False)  # the folder isn't there any more
    first_seen: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    scanned_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class ProjectNews(Base):
    """project_news · ข่าวโปรเจค (2.3): what projects drop in ~/.secretary/inbox (inbox.py), one row
    per file. urgent: a failure or a question in a project that matters (potential S–A or urgency
    4–5): sent to #ด่วน at once; the rest waits for the morning brief."""

    __tablename__ = "project_news"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    project: Mapped[str] = mapped_column(String(200))  # the inbox folder's name
    kind: Mapped[str] = mapped_column(String(10))  # report · schedule · status · bad (a file that couldn't be read)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)  # when it happened (the file says), else when read
    failed: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_you: Mapped[bool] = mapped_column(Boolean, default=False)
    urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # the #ด่วน card, when sent
    file: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
