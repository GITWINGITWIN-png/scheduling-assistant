"""Classroom's tables: the courses the secretary has seen, and what it took from them (U1, B3)."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, now

STATES = {  # what the secretary does with a course, in your words
    "ended": "จบแล้ว",  # it was there at the first sync (the user: every course then had finished)
    "asking": "รอคุณตอบ",  # new, or busy again: waiting in #approvals "follow this course?"
    "followed": "ติดตาม",  # deadlines become tasks, materials are downloaded
    "ignored": "ไม่ติดตาม",
}


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # Classroom's course id
    name: Mapped[str] = mapped_column(Text)
    section: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String(10), default="asking")  # a STATES key
    folder: Mapped[str] = mapped_column(Text, default="")  # where its materials go, e.g. ~/Projects/datacom/media
    # The newest coursework or material time seen; something newer wakes an ended course up.
    last_activity: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class CourseItem(Base):
    """course_items (coursework and materials from Classroom): one piece of coursework, material or announcement."""

    __tablename__ = "course_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # Classroom's id
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))  # work · material · announcement
    title: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    link: Mapped[str] = mapped_column(Text, default="")
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), default=None)
    turned_in: Mapped[bool] = mapped_column(Boolean, default=False)
    files: Mapped[list] = mapped_column(JSON, default=list)  # [{"name", "path"}] downloaded into the course folder
    links: Mapped[list] = mapped_column(JSON, default=list)  # [{"title", "url"}] links, videos, forms
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)  # Classroom's updateTime
    synced_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
