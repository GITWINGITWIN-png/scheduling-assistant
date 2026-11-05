"""The shared tables every part of the secretary uses (PLAN.md, "ระบบ · ใช้ร่วมกันทุกส่วน").

Each feature's own tables (people, emails, projects...) live with that feature
and arrive in its phase. Here are the ones several phases share: the five from
B1, and events + tasks from B2 (B3-B5 add to them). `rules` and `briefs` come
with B5 and B4.

Every table has a comment saying what it holds, and the fields follow the data
model board (d2) of the plan.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, now


class Setting(Base):
    """settings · ตั้งค่า: your preferences, one row per key, the value as JSON.

    For example "llm.tasks" -> {"ask": {"model": "sonnet", "effort": "low"}, ...}
    and "ui.theme" -> "cs". It also holds small pieces of the secretary's own
    state that must survive a restart, under the "state." prefix (for example
    when each clock round last ran).
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)


class Action(Base):
    """action_log · สิ่งที่เลขาทำ: one row per thing the secretary did (feature P9).

    Written by core/actions.py and nothing else. `undo` holds what is needed to
    reverse the action, and stays empty for actions that cannot be undone.
    """

    __tablename__ = "action_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)
    kind: Mapped[str] = mapped_column(String(50), index=True)  # e.g. "round.backup", "ask", "plan.approve"
    summary: Mapped[str] = mapped_column(Text)  # ทำอะไร, in your words: "สำรองฐานข้อมูล"
    target: Mapped[str] = mapped_column(Text, default="")  # กับอะไร: "secretary-2026-11-05.db"
    source_label: Mapped[str] = mapped_column(Text, default="")  # ที่มา, shown as a link's text
    source_url: Mapped[str] = mapped_column(Text, default="")
    undo: Mapped[dict | None] = mapped_column(JSON, default=None)  # how to reverse it; None = can't
    undone_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    tokens: Mapped[int | None] = mapped_column(Integer, default=None)  # model tokens, if a model was used


class LLMUsage(Base):
    """llm_usage · การใช้โมเดล: one row per model call (core/llm.py writes it).

    The token counts behind the quota line, and the evidence for "which task
    costs what" when you tune models and effort in settings.
    """

    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)
    task: Mapped[str] = mapped_column(String(50), index=True)  # "ask", "plan", ...
    model: Mapped[str] = mapped_column(String(50))
    effort: Mapped[str] = mapped_column(String(20), default="")
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(default=True)


class Message(Base):
    """messages · ข้อความที่บอทส่ง: every message the bot posted on Discord.

    It lets a button pressed days later find what it belongs to, and keeps a
    short copy of the text so the chat has some memory.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    channel: Mapped[str] = mapped_column(String(20))  # chat · urgent · summary · approve · ideas (or where a hint went: dm, #general)
    discord_id: Mapped[int] = mapped_column(BigInteger, index=True)  # Discord's id (a large integer)
    kind: Mapped[str] = mapped_column(String(50))  # "answer", "plan", "did", ...
    ref: Mapped[str] = mapped_column(String(100), default="")  # what its buttons act on: "decision:12"
    content: Mapped[str] = mapped_column(Text, default="")


class Decision(Base):
    """decisions · เรื่องที่รอคุณตัดสิน: anything waiting for your yes or no.

    In B1 these are plans from Opus. Later phases add appointments, project
    levels, people changes and ideas.
    """

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    kind: Mapped[str] = mapped_column(String(30), index=True)  # plan · appointment · project_level · person_level · idea
    title: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)  # kind-specific: the plan text, the question...
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), default=None)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending · approved · rejected
    answer: Mapped[str] = mapped_column(Text, default="")  # your note, e.g. what to change
    answered_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class Event(Base):
    """events · นัด: an appointment the secretary knows about (features 1.3, 3.1).

    B2 creates them from email (source "email"). B3 also copies in what is on your own
    calendar (source "calendar", source_ref = the Google event id), so busy time and
    reminders work from one table.
    status: placed (in Google Calendar, `gcal_id` set) · proposed (waiting in #อนุมัติ)
    · declined (you said no) · removed (undone, or deleted from the calendar).
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    location: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20))  # email · calendar · you · project
    source_ref: Mapped[str] = mapped_column(String(64), default="")  # e.g. the Gmail message id
    gcal_id: Mapped[str] = mapped_column(String(128), default="")
    link: Mapped[str] = mapped_column(Text, default="", server_default="")  # opens it in Google Calendar
    recurring: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # a weekly class: no reminders
    status: Mapped[str] = mapped_column(String(12), default="proposed", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class Task(Base):
    """tasks · งานและเดดไลน์: something you have to do (features P4, 3.1, U1).

    B2 adds work people ask for by email; B3 adds Classroom deadlines; B5 project work.
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20))  # email · classroom · project · you
    source_ref: Mapped[str] = mapped_column(String(64), default="")
    project: Mapped[str] = mapped_column(String(200), default="")
    est_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None: the default for its source
    # How the planner places it: early (start soon, done a day before the due date; the
    # default) or late (as close to the due date as fits), the user's choice at the B3 plan.
    plan_mode: Mapped[str] = mapped_column(String(8), default="early", server_default="early")
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)  # open · done · dropped
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class Block(Base):
    """blocks · บล็อกในตาราง: time set aside for a task, in the "เลขา" calendar (3.1, B3; B6 adds what really happened).

    status: planned (the planner may move it) · pinned (you moved it in Google Calendar,
    so it stays where you put it) · deleted (you deleted it there: its time counts as
    busy) · removed (a re-plan took it back, or the "เลขา" calendar was deleted).
    A block in the past counts as work done on its task, until B6 can check.
    """

    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime)
    gcal_id: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(10), default="planned", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class Reminder(Base):
    """reminders · เตือน: one "1 day before" / "1 hour before" message, sent once (P5, B3).

    `due_at` is the time being reminded about, so an appointment moved to a new time
    gets reminded again for the new time.
    """

    __tablename__ = "reminders"
    __table_args__ = (UniqueConstraint("kind", "ref_id", "lead", "due_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(8))  # event · task
    ref_id: Mapped[int] = mapped_column(Integer)
    lead: Mapped[str] = mapped_column(String(4))  # 1d · 1h
    due_at: Mapped[datetime] = mapped_column(UTCDateTime)
    sent_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), default=None)
