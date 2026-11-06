"""briefs · สรุปที่ส่งแล้ว (stage 3's data model): every morning brief and evening review the
secretary made, one per kind per day. The today page opens the morning one in full, and a
brief that exists for today is never made again, so a restart or a round caught up at 08:00
can't post a second one."""

from datetime import datetime

from sqlalchemy import JSON, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, now


class Brief(Base):
    __tablename__ = "briefs"
    __table_args__ = (UniqueConstraint("kind", "day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))  # morning · evening (weekly comes in B7)
    day: Mapped[str] = mapped_column(String(10), index=True)  # your local date, "2026-11-06"
    made_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    title: Mapped[str] = mapped_column(Text, default="")
    headline: Mapped[str] = mapped_column(Text, default="")  # the one line with the day's numbers (D2 ①)
    fields: Mapped[list] = mapped_column(JSON, default=list)  # [[name, text], ...] as sent
    footer: Mapped[str] = mapped_column(Text, default="")
    tokens: Mapped[int] = mapped_column(Integer, default=0)  # what this brief itself used: 0, templates only
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # the messages row once Discord has it
