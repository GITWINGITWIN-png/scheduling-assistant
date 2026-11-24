"""Turn a time as people write it into a real date and time (no model, no tokens).

    parse("tomorrow 10 am", ref)        -> tomorrow 10:00
    parse("2 pm next Friday", ref)      -> Friday of next week, 14:00
    parse("7 Nov 2569 14.00 hrs", ref)  -> 2026-11-07 14:00
    parse("Nov 7 at 3pm", ref)          -> the next 7 November, 15:00
    parse("2026-11-07", ref)            -> that day, no time (an all-day entry)

`ref` is when the email was sent: "tomorrow" means the day after the email, not
the day the secretary reads it. Times are in your time zone.

If no date can be worked out (only "next week", say), it returns None instead of
guessing. A missing appointment is better than a wrong one in your calendar.

Thai clock words follow everyday use: "10 in the morning" = 10:00, "afternoon 2" = 14:00,
"4 in the evening" = 16:00, "8 at night" = 20:00, "2 am" = 02:00, "half past noon" = 12:30.
Thai years (2569, or 69) are Buddhist Era and are converted (-543).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.core.config import get_config


@dataclass(frozen=True)
class When:
    start: datetime  # aware, in your time zone
    has_time: bool  # False: only a date was given (an all-day entry)


THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
THAI_NUMBERS = {  # longest first, so "twelve" isn't read as "ten" + "two"
    "สิบสอง": 12, "สิบเอ็ด": 11, "สิบ": 10, "เก้า": 9, "แปด": 8, "เจ็ด": 7, "หก": 6,
    "ห้า": 5, "สี่": 4, "สาม": 3, "สอง": 2, "หนึ่ง": 1,
}
THAI_MONTHS = [
    ("มกราคม", "ม.ค."), ("กุมภาพันธ์", "ก.พ."), ("มีนาคม", "มี.ค."), ("เมษายน", "เม.ย."),
    ("พฤษภาคม", "พ.ค."), ("มิถุนายน", "มิ.ย."), ("กรกฎาคม", "ก.ค."), ("สิงหาคม", "ส.ค."),
    ("กันยายน", "ก.ย."), ("ตุลาคม", "ต.ค."), ("พฤศจิกายน", "พ.ย."), ("ธันวาคม", "ธ.ค."),
]
EN_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
THAI_DAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัส", "ศุกร์", "เสาร์", "อาทิตย์"]
EN_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _year(y: str | None, ref: date) -> int | None:
    if not y:
        return None
    n = int(y)
    if n < 100:  # "69" in Thai writing is 2569; "26" is 2026
        n += 2500 if n >= 50 else 2000
    return n - 543 if n > 2400 else n


def _month_day(year: int | None, month: int, day: int, ref: date) -> date | None:
    """A date with an optional year: without one, the next such day on or after the email."""
    try:
        if year:
            return date(year, month, day)
        d = date(ref.year, month, day)
        return d if d >= ref - timedelta(days=1) else date(ref.year + 1, month, day)
    except ValueError:
        return None


def _find_date(text: str, ref: date) -> tuple[date | None, str, bool]:
    """-> (the date, the text with the date removed so its numbers aren't read as a time,
    whether a date was written at all: "31 Feb" is written but doesn't exist)."""
    def cut(m: re.Match) -> str:
        return text[:m.start()] + " " + text[m.end():]

    if m := re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text):
        return _month_day(_year(m.group(1), ref), int(m.group(2)), int(m.group(3)), ref), cut(m), True
    if m := re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", text):  # day/month/year, as written in Thailand
        return _month_day(_year(m.group(3), ref), int(m.group(2)), int(m.group(1)), ref), cut(m), True
    for i, (full, short) in enumerate(THAI_MONTHS):
        pattern = rf"(\d{{1,2}})\s*(?:{re.escape(full)}|{re.escape(short)}|{re.escape(short.replace('.', ''))})\.?\s*(?:พ\.ศ\.\s*)?(\d{{4}}|\d{{2}}(?!\s*[:.]\d))?"
        if m := re.search(pattern, text):
            return _month_day(_year(m.group(2), ref), i + 1, int(m.group(1)), ref), cut(m), True
    for i, name in enumerate(EN_MONTHS):
        if m := re.search(rf"\b{name}[a-z]*\.?\s+(\d{{1,2}})(?!\d)(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?", text):  # Nov 7, 2026 (not the "20" of 2026)
            return _month_day(_year(m.group(2), ref), i + 1, int(m.group(1)), ref), cut(m), True
        if m := re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{name}[a-z]*\.?(?:,?\s+(\d{{4}}))?", text):  # 7 Nov 2026
            return _month_day(_year(m.group(2), ref), i + 1, int(m.group(1)), ref), cut(m), True

    nxt = bool(re.search(r"หน้า|\bnext\b", text))
    for names in (THAI_DAYS, EN_DAYS):
        for i, name in enumerate(names):
            if re.search(rf"(?<![a-z]){name}" if names is EN_DAYS else name, text):
                ahead = (i - ref.weekday()) % 7
                if nxt:  # "next Friday" (in Thai) / "next Friday": that day in the coming calendar week
                    return ref + timedelta(days=7 - ref.weekday() + i), text, True
                return ref + timedelta(days=ahead), text, True
    for words, days in ((("มะรืน", "day after tomorrow"), 2), (("พรุ่งนี้", "tomorrow"), 1),
                        (("วันนี้", "คืนนี้", "today", "tonight", "เย็นนี้", "บ่ายนี้", "เช้านี้"), 0)):
        if any(w in text for w in words):
            return ref + timedelta(days=days), text, True
    return None, text, False


def _find_time(text: str) -> time | None:
    for word, n in THAI_NUMBERS.items():
        text = text.replace(word, f" {n} ")
    half = 30 if "ครึ่ง" in text else 0

    if "เที่ยงคืน" in text:
        return time(0, 0)
    if m := re.search(r"(\d{1,2})[:.](\d{2})\s*(am|pm|a\.m\.|p\.m\.)?", text):
        h, mi = int(m.group(1)), int(m.group(2))
        if m.group(3) and m.group(3).startswith("p") and h < 12:
            h += 12
        if m.group(3) and m.group(3).startswith("a") and h == 12:
            h = 0
        return time(h % 24, mi) if mi < 60 else None
    if m := re.search(r"(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)", text):
        h = int(m.group(1)) % 12 + (12 if m.group(2).startswith("p") else 0)
        return time(h, 0)
    if "เที่ยง" in text:
        return time(12, half)
    if m := re.search(r"บ่าย\s*(\d{1,2})?\s*(?:โมง)?", text):
        n = int(m.group(1)) if m.group(1) else 1  # "one in the afternoon" = 13:00
        return time(12 + n if n < 12 else n, half)
    if m := re.search(r"(\d{1,2})\s*โมงเย็น", text):
        n = int(m.group(1))
        return time(n + 12 if n < 12 else n, half)
    if m := re.search(r"(\d{1,2})\s*ทุ่ม", text):
        return time((18 + int(m.group(1))) % 24, half)
    if m := re.search(r"ตี\s*(\d{1,2})", text):
        return time(int(m.group(1)) % 24, half)
    if m := re.search(r"(\d{1,2})\s*โมง(เช้า)?", text):
        n = int(m.group(1))
        if m.group(2):  # "8 in the morning" = 8:00; old style "four in the morning" = 10:00
            return time(n if n >= 6 else n + 6, half)
        return time(n if 7 <= n <= 12 else (n + 12) % 24, half)  # "10 o'clock" = 10:00, "4 o'clock" = 16:00
    return None


def parse(text: str, ref: datetime) -> When | None:
    """The start of an appointment written as `text`, counting from `ref` (when it was written)."""
    tz = get_config().tz
    ref_local = ref.astimezone(tz)
    clean = " ".join(text.translate(THAI_DIGITS).lower().replace("ค.ศ.", " ").replace("เวลา", " ").split())
    day, rest, written = _find_date(clean, ref_local.date())
    if written and day is None:
        return None  # a date that doesn't exist: don't fall back to "today"
    at = _find_time(rest)
    if day is None:
        if at is None:
            return None
        day = ref_local.date()  # only a time: that day, or the next if it had already passed
        if datetime.combine(day, at, tz) < ref_local:
            day += timedelta(days=1)
    return When(datetime.combine(day, at or time(0, 0), tz), at is not None)
