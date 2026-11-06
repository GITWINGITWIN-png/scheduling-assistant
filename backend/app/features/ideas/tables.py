"""ideas · ไอเดีย and idea_groups · กลุ่มไอเดีย (features 4.2 and P11, B6).

An idea comes in through one of three doors, one message or one popup = one idea:
- the Super+I popup (source "key"), which posts to the secretary on localhost;
- a message in #ไอเดีย on Discord ("discord"), typed on the iPad, the phone or here;
- the ideas page ("web").

Tags, and where they came from (`tagged`):
- "you": the tags you kept in the popup or on the page, or the #tags you typed. They are final,
  so a round never adds to them. That includes an empty list: you removed the suggestions.
- "rules": the round's rules found them. Until OmniRoute is connected there is no model
  (the user's choice at the B6 plan), so the rules are #tags, project names and the tags
  you already use.
- "": not tagged yet. The next round looks at it.

A group is one tag, so all "#backtest" ideas are one group (rules only, the same choice). Its
name starts as the tag, and you can rename it on the ideas page. When a group has grown enough
(GROWN ideas), the round proposes it once: open a project, make it a task, or not yet (P11).
"""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, now

SOURCES = {"key": "คีย์ลัด", "discord": "#ไอเดีย", "web": "หน้าเว็บ"}
GROUP_STATUSES = {
    "open": "กำลังโต",
    "asked": "เสนอแล้ว",  # grown enough: waiting for your answer (a Decision of kind "idea")
    "later": "ยังก่อน",  # you said not yet: asked again once it has grown by AGAIN_AFTER more
    "project": "เป็นโปรเจคแล้ว",
    "task": "เป็นงานแล้ว",
}


class IdeaGroup(Base):
    __tablename__ = "idea_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag: Mapped[str] = mapped_column(String(80), unique=True)  # the tag that makes the group
    name: Mapped[str] = mapped_column(Text)  # the tag at first; you can rename it
    status: Mapped[str] = mapped_column(String(8), default="open", index=True)  # a GROUP_STATUSES key
    asked_size: Mapped[int] = mapped_column(Integer, default=0)  # its size when it was last proposed
    decision_id: Mapped[int | None] = mapped_column(ForeignKey("decisions.id"), default=None)
    project_id: Mapped[int | None] = mapped_column(Integer, default=None)  # "เปิดโปรเจค": the project made from it
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), default=None)  # "ทำเป็นงาน"
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)


class Idea(Base):
    __tablename__ = "ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(10))  # a SOURCES key
    source_ref: Mapped[str] = mapped_column(String(32), default="", index=True)  # the Discord message id
    tags: Mapped[list] = mapped_column(JSON, default=list)  # without "#", in order: yours first
    tagged: Mapped[str] = mapped_column(String(6), default="")  # "" not yet · you · rules (see above)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("idea_groups.id"), default=None, index=True)
    grouped_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)  # when a round placed it
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)
