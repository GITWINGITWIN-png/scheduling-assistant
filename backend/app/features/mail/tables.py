"""B2's tables (PLAN.md data model d2: people, emails, followups).

Times are UTC (UTCDateTime), like every table in v2. Email bodies are never stored, only
the summary the secretary wrote ("เก็บสรุป ไม่เก็บเนื้อหาเต็ม").
"""

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, now

LEVELS = {"important": "สำคัญ", "interested": "สนใจ", "ignored": "ไม่สนใจ"}
SOURCES = {  # why a person is at their level, in your words
    "you": "คุณตั้ง",
    "first_mail": "ส่งมาครั้งแรก",
    "bulk_tab": "อีเมลแรกอยู่แท็บโปรโมชัน/โซเชียล/ฟอรัม",
    "secretary": "เลขาเสนอ คุณอนุมัติ",
}


class Person(Base):
    """people · ทะเบียนคน: one person, whatever addresses they write from (feature 1.2).

    - important (สำคัญ): you set it, usually with an end date (`level_until`); their mail
      alerts #ด่วน at once, is read in full, and their appointments go straight into the
      calendar. You can add someone before they ever write.
    - interested (สนใจ): everyone new starts here, and anyone you demote; summarised per
      person in the 00:00 and 12:00 rounds, appointments come to #อนุมัติ.
    - ignored (ไม่สนใจ): only subjects are read, grouped per sender.

    An important person past `level_until` stays important until you decide (the weekly
    review, B7, proposes it); the W2 page marks them as expired meanwhile.
    """

    __tablename__ = "people"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    level: Mapped[str] = mapped_column(String(12), default="interested")  # a LEVELS key
    level_source: Mapped[str] = mapped_column(String(20), default="first_mail")  # a SOURCES key
    level_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")  # your reason (โน้ตเหตุผล); cleared once you decide again
    demote_reason: Mapped[str] = mapped_column(Text, default="")
    last_mail_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)


class PersonAddress(Base):
    """person_addresses: every address a person writes from, lowercase."""

    __tablename__ = "person_addresses"

    address: Mapped[str] = mapped_column(String(320), primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)


class Email(Base):
    """emails · อีเมลที่เลขาเห็นแล้ว: one row per Gmail message, with what was made of it.

    stage: seen (only the header so far) → read (read in full at once: important person,
    keyword or a reply you were waiting for) · summarized (in a round) · skimmed (subject only).
    """

    __tablename__ = "emails"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # Gmail message id
    account: Mapped[str] = mapped_column(String(20))
    thread_id: Mapped[str] = mapped_column(String(32), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True)
    sender: Mapped[str] = mapped_column(String(320), default="")
    sender_name: Mapped[str] = mapped_column(String(200), default="")
    subject: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    from_me: Mapped[bool] = mapped_column(Boolean, default=False)
    level: Mapped[str] = mapped_column(String(12), default="")  # the sender's level when it arrived
    flagged: Mapped[str] = mapped_column(String(100), default="")  # why it was read at once, e.g. "keyword:สอบ"
    stage: Mapped[str] = mapped_column(String(12), default="seen", index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    needs_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class Followup(Base):
    """followups · เรื่องค้าง: a thread where someone owes a reply (feature P6).

    waiting_on "you": they wrote last and it needs your answer. "them": you wrote last.
    While a thread waits on them, that person counts as important for it, so their reply
    alerts at once ("คนที่คุณรอคำตอบเป็นคนสำคัญอัตโนมัติ").
    """

    __tablename__ = "followups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account: Mapped[str] = mapped_column(String(20))
    thread_id: Mapped[str] = mapped_column(String(32), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), nullable=True)
    subject: Mapped[str] = mapped_column(Text, default="")
    waiting_on: Mapped[str] = mapped_column(String(8))  # "you" | "them"
    since: Mapped[datetime] = mapped_column(UTCDateTime)
    remind_after_days: Mapped[int] = mapped_column(Integer, default=3)
    reminded_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
