"""What the secretary learns from your answers (P8, W8 ③): patterns in what you approved and
turned down, offered as rules. None is used until you press "ใช้เป็นกติกา"; "ไม่ใช่" keeps it
from being offered again. No model: counting only.

The patterns (later phases add more):

- appointment days: you turned down appointments on one weekday at least 3 times in 4 weeks
  and accepted none on that day -> "คุณมักไม่รับนัดวันเสาร์". Once you accept it, such requests
  say so on their card; they still wait for your answer.
- background plans: every plan for one project approved, at least 5 in 4 weeks -> "คุณอนุมัติ
  แผนงานเบื้องหลังของ finance ทุกครั้ง"; once you accept it, that project's low-risk plans may
  start without asking (a standing rule; high-risk work still asks).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.core.db import now, session
from app.core.tables import Decision, Event, Rule
from app.core.timefmt import DAYS, local

WINDOW = timedelta(days=28)
TIMES = 3  # "ปฏิเสธ 3 ครั้งใน 4 สัปดาห์"


@dataclass(frozen=True)
class Found:
    key: str  # stable, so the same pattern is one row however often it's found
    text: str
    evidence: str
    used_by: list[str]
    effect: dict


def appointment_days(s, at: datetime) -> list[Found]:
    answered = s.scalars(select(Decision).where(Decision.kind == "appointment", Decision.status.in_(("approved", "rejected")),
                                                Decision.answered_at >= at - WINDOW)).all()
    no, yes = Counter(), Counter()
    for d in answered:
        ev = s.get(Event, (d.detail or {}).get("event_id"))
        if ev is not None:
            (no if d.status == "rejected" else yes)[local(ev.starts_at).weekday()] += 1
    return [Found(f"learned.appointment_day.{day}", f"คุณมักไม่รับนัดวัน{DAYS[day]}", f"ปฏิเสธ {n} ครั้งใน 4 สัปดาห์",
                  ["mail"], {"type": "appointment_days", "weekdays": [day]})
            for day, n in sorted(no.items()) if n >= TIMES and not yes[day]]


JOB_TIMES = 5  # "อนุมัติ 5 จาก 5"


def job_approvals(s, at: datetime) -> list[Found]:
    answered = s.scalars(select(Decision).where(Decision.kind == "job", Decision.status.in_(("approved", "rejected")),
                                                Decision.answered_at >= at - WINDOW)).all()
    yes, no = Counter(), Counter()
    for d in answered:
        (yes if d.status == "approved" else no)[(d.detail or {}).get("project", "")] += 1
    return [Found(f"learned.job_auto.{name}", f"คุณอนุมัติแผนงานเบื้องหลังของ {name} ทุกครั้ง", f"อนุมัติ {n} จาก {n} ใน 4 สัปดาห์",
                  ["jobs"], {"type": "job_auto", "project": name})
            for name, n in sorted(yes.items()) if name and n >= JOB_TIMES and not no[name]]


DETECTORS: list[Callable[..., list[Found]]] = [appointment_days, job_approvals]


def refresh(at: datetime | None = None) -> int:
    """Look again. A new pattern waits for you; one that no longer holds is dropped if you
    hadn't answered it yet (what you accepted or turned down stays). -> how many wait."""
    at = at or now()
    with session() as s:
        found = {f.key: f for detect in DETECTORS for f in detect(s, at)}
        rows = {r.key: r for r in s.scalars(select(Rule).where(Rule.kind == "learned"))}
        for key, f in found.items():
            if (r := rows.get(key)) is None:
                s.add(Rule(kind="learned", status="pending", key=key, text=f.text, evidence=f.evidence,
                           used_by=f.used_by, effect=f.effect))
            elif r.status == "pending":
                r.evidence = f.evidence
        for key, r in rows.items():
            if r.status == "pending" and key not in found:
                s.delete(r)
        s.flush()
        return s.scalar(select(func.count()).select_from(Rule).where(Rule.kind == "learned", Rule.status == "pending")) or 0
