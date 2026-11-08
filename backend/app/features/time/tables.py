"""activity · การใช้เวลา and privacy_rules · ตัวกรอง (features 4.1 and P12, B6).

activity: what you did on this computer, from ActivityWatch, after the privacy filter. One row is
one stretch of one window while you were at the computer (not idle), cut at the edges of each
read. A window on the blocklist never gets a row. A title with a word you don't want kept is
stored as HIDDEN.

privacy_rules: the blocklist you edit on the time page, starting from the defaults agreed at the
B6 plan. Three kinds:
- app: an app (its window class, e.g. "keepassxc"). Never recorded.
- title: a window title that names a site or a private window ("kasikorn", "Private Browsing").
  Never recorded. Without a browser extension the title is all there is to go by.
- word: a word in a title ("รหัสผ่าน"). The time is kept under its app, and the title is hidden.
Case never matters. A latin value must stand on its own, so "scb" isn't found in "scbx". A Thai
value is found anywhere, because Thai has no spaces between words.
"""

from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, now

KINDS = {"app": "แอป", "title": "เว็บและชื่อหน้าต่าง", "word": "คำในชื่อหน้าต่าง (ซ่อนชื่อ)"}
HIDDEN = "(ซ่อนชื่อหน้าต่าง)"


class Activity(Base):
    __tablename__ = "activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    start: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    end: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    app: Mapped[str] = mapped_column(String(120), default="")
    title: Mapped[str] = mapped_column(Text, default="")  # after the filter (HIDDEN when a word matched)
    category: Mapped[str] = mapped_column(String(12), default="", index=True)  # categorize.CATEGORIES key ("" = not sorted yet)
    project_id: Mapped[int | None] = mapped_column(Integer, default=None, index=True)
    project: Mapped[str] = mapped_column(String(200), default="")  # its name, as it was


class PrivacyRule(Base):
    __tablename__ = "privacy_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(6))  # a KINDS key
    value: Mapped[str] = mapped_column(String(120))
    note: Mapped[str] = mapped_column(Text, default="")  # what it is, in your words ("ธนาคาร", "Firefox")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
