"""The rule checker (3.2, B5): may a background plan start by itself, or does it ask you first?

The rule agreed at the B5 plan, checked in this order:

1. A plan you approved may start, for 3 days after you approved it (that plan only).
2. When the quota can't be read, every plan asks.
3. A plan with any high-risk work asks, however much quota is left.
4. A standing rule of yours for the project ("Finance work can be done without asking") lets it start.
5. Otherwise it starts by itself only while more than the line (70%) of the week's quota is
   left, and only while you leave that rule switched on. Everything else asks.

Pure: everything comes in as arguments (the caller reads the quota, the book and the
approval), so the tests can try every case without a database.

Whatever the answer, a running job still has its token budget and stops when it's spent
(the runner's job, B5.7).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from app.core.timefmt import thai_datetime

APPROVAL_DAYS = 3  # how long your "approval" covers a plan


@dataclass(frozen=True)
class Verdict:
    go: bool  # True: it may start by itself, False: it asks you in #approvals
    why: str  # one line for the card and the jobs page


def check(*, risks: Iterable[str], week_left: float | None, at: datetime, line: float = 70.0, auto: bool = True,
          approved_until: datetime | None = None, standing: str = "") -> Verdict:
    """risks: the names of the high-risk kinds the plan has (as the rule book shows them).
    week_left: % of the week's quota left, None when it can't be read.
    approved_until: when your approval of this plan runs out (None: not approved).
    standing: the text of your standing rule for the plan's project ("" when none)."""
    risks = [r for r in risks if r]
    if approved_until is not None and at < approved_until:
        return Verdict(True, f"คุณอนุมัติแผนนี้แล้ว ใช้ได้ถึง {thai_datetime(approved_until)}")
    if week_left is None:
        return Verdict(False, "อ่านโควตาไม่ได้ ทุกแผนถามคุณก่อน")
    if risks:
        return Verdict(False, "งานเสี่ยงสูง: " + " · ".join(risks))
    if standing:
        return Verdict(True, f"ตามกติกาของคุณ: {standing}")
    if not auto:
        return Verdict(False, "คุณปิดการทำเองไว้ ทุกแผนถามคุณก่อน")
    if week_left > line:
        return Verdict(True, f"โควตาเหลือ {week_left:.0f}% เกินเส้น {line:.0f}%")
    return Verdict(False, f"โควตาเหลือ {week_left:.0f}% ไม่เกินเส้น {line:.0f}%")
