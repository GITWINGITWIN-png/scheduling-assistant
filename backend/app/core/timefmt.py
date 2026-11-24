"""Times shown to you: your time zone, Thai day and month names, Buddhist-era year.

The store keeps UTC (core/db.UTCDateTime). Convert only here, at the moment of
showing a time.
"""

from datetime import datetime

from app.core.config import get_config

DAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]
DAYS_SHORT = ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."]
MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def local(dt: datetime) -> datetime:
    return dt.astimezone(get_config().tz)


def from_local(value: str | None) -> datetime | None:
    """A time written without a zone ("2026-11-10T17:00", from a page or from the chat) is your
    local time. One with a zone is kept as it is. Raises ValueError when it isn't a date."""
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=get_config().tz)


def thai_date(dt: datetime, long: bool = False) -> str:
    """'Wed 5 Nov 2569', or with long=True 'Wednesday 5 Nov 2569'."""
    d = local(dt)
    day = f"วัน{DAYS[d.weekday()]}" if long else DAYS_SHORT[d.weekday()]
    return f"{day} {d.day} {MONTHS[d.month - 1]} {d.year + 543}"


def thai_datetime(dt: datetime, long: bool = False) -> str:
    return f"{thai_date(dt, long)} {local(dt):%H:%M}"
