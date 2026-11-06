"""quota, rules and jobs (stage 3's data model) for the background work."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, Integer, String, Text
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
