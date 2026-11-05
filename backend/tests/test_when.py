"""core/when.py: written times -> real times (B2 step 6, agreed as automatic tests).

Every case counts from the same moment: Thursday 5 Nov 2026, 15:30 in Bangkok,
as if that's when the email was sent. Expected values are local times:
"YYYY-MM-DD HH:MM", "YYYY-MM-DD" for a date with no time (all day), or None
when the secretary must not guess.

Run: cd backend && uv run pytest
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.core.when import parse

BKK = ZoneInfo("Asia/Bangkok")
REF = datetime(2026, 11, 5, 15, 30, tzinfo=BKK)  # a Thursday afternoon


def show(text: str, ref: datetime = REF) -> str | None:
    w = parse(text, ref)
    if w is None:
        return None
    return w.start.strftime("%Y-%m-%d %H:%M") if w.has_time else w.start.strftime("%Y-%m-%d")


@pytest.mark.parametrize("text, expected", [
    # what the model writes when it is sure
    ("2026-11-07 14:00", "2026-11-07 14:00"),
    ("2026-11-07T09:30", "2026-11-07 09:30"),
    ("2026-11-07", "2026-11-07"),
    # Thai dates, with Buddhist years, short and full month names, Thai digits
    ("7 พ.ย. 2569 14.00 น.", "2026-11-07 14:00"),
    ("7 พฤศจิกายน 69 เวลา 09.00 น.", "2026-11-07 09:00"),
    ("12/11/69 13:30", "2026-11-12 13:30"),
    ("12/11/2026 08:15", "2026-11-12 08:15"),
    ("๑๔.๓๐ น. ๑๐ พ.ย.", "2026-11-10 14:30"),
    ("3 ธ.ค.", "2026-12-03"),
    ("3 ม.ค.", "2027-01-03"),  # no year and already past this year: next January
    # Thai words for relative days
    ("พรุ่งนี้ 10 โมง", "2026-11-06 10:00"),
    ("มะรืนนี้ 10 โมงครึ่ง", "2026-11-07 10:30"),
    ("คืนนี้ 2 ทุ่ม", "2026-11-05 20:00"),
    ("ตี 2 พรุ่งนี้", "2026-11-06 02:00"),
    # weekdays: this week's, or next week's with หน้า / next
    ("วันจันทร์ 9:00", "2026-11-09 09:00"),
    ("วันศุกร์ 10 โมง", "2026-11-06 10:00"),
    ("บ่ายสอง วันศุกร์หน้า", "2026-11-13 14:00"),
    ("4 โมงเย็น วันเสาร์", "2026-11-07 16:00"),
    ("วันพฤหัส 9 โมงเช้า", "2026-11-05 09:00"),  # the same weekday counts as today
    # Thai clock words
    ("พรุ่งนี้ บ่ายโมง", "2026-11-06 13:00"),
    ("พรุ่งนี้ เที่ยง", "2026-11-06 12:00"),
    ("พรุ่งนี้ เที่ยงครึ่ง", "2026-11-06 12:30"),
    ("พรุ่งนี้ เที่ยงคืน", "2026-11-06 00:00"),
    ("พรุ่งนี้ สิบโมง", "2026-11-06 10:00"),
    ("พรุ่งนี้ 4 โมง", "2026-11-06 16:00"),  # everyday speech: สี่โมง = 4 pm
    ("พรุ่งนี้ 1 ทุ่มครึ่ง", "2026-11-06 19:30"),
    # English
    ("Nov 7 at 3pm", "2026-11-07 15:00"),
    ("7th November 2026, 2:30 PM", "2026-11-07 14:30"),
    ("November 7, 2026 10am", "2026-11-07 10:00"),
    ("tomorrow 10:30", "2026-11-06 10:30"),
    ("next Monday 9am", "2026-11-09 09:00"),
    ("Friday 12 am", "2026-11-06 00:00"),
    # only a time: today if it's still ahead, otherwise tomorrow
    ("6 โมงเย็น", "2026-11-05 18:00"),
    ("10 โมง", "2026-11-06 10:00"),
    # an explicit date beats a weekday that disagrees with it (7 Nov 2026 is a Saturday)
    ("วันศุกร์ที่ 7 พฤศจิกายน 2569 เวลา 09.00 น.", "2026-11-07 09:00"),
    # no usable date: never guess
    ("สัปดาห์หน้า", None),
    ("November 2026", None),
    ("เร็วๆ นี้", None),
    ("31 ก.พ. 10:00", None),  # written, but doesn't exist
    ("", None),
])
def test_parse(text: str, expected: str | None) -> None:
    assert show(text) == expected


def test_counts_from_the_email_not_from_today() -> None:
    """ "พรุ่งนี้" in an email sent on 1 Nov means 2 Nov, whenever the secretary reads it."""
    assert show("พรุ่งนี้ 10 โมง", datetime(2026, 11, 1, 9, 0, tzinfo=BKK)) == "2026-11-02 10:00"


def test_result_is_in_bangkok_time() -> None:
    w = parse("2026-11-07 14:00", REF)
    assert w is not None and w.start.utcoffset().total_seconds() == 7 * 3600
