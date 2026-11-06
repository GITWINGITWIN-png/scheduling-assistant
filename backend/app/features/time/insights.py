"""What the time page shows (W7 ① ② ③), from `activity` and the schedule's blocks. Rules only, no model.

- per day (per hour for "วันนี้"), by category (①);
- per project, against the time the schedule set aside for it (②): a project's plan is the blocks
  of its tasks in the same days, up to now (blocks still to come aren't short yet);
- behaviours the rules notice (③): the two hours you focus best (the most work, code or
  studying, with the fewest app switches per hour of it; a meeting or browsing isn't focus),
  whether you switch apps much more after 22:00, the projects that got far less than planned, and
  your longest stretch on one project;
- what the rules couldn't sort (อื่นๆ), the biggest first, so you can sort it yourself.

An "app switch" is a change of app between two windows that follow each other closely (within
SWITCH_GAP), so walking away isn't counted as switching.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from app.core.config import get_config
from app.core.db import session
from app.core.tables import Block, Task
from app.core.timefmt import local
from app.features.time.categorize import CATEGORIES
from app.features.time.tables import Activity

SWITCH_GAP = timedelta(minutes=3)
MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
MONTHS_LONG = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน",
               "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
DAYS = ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."]
SHORT_OF_PLAN = 0.7  # a project with less than this share of its plan is noticed
FOCUS_SLOTS = 4  # half hours: the focus window is two hours
WORK = ("code", "study")


def span(range_: str, at: datetime) -> tuple[datetime, datetime, str]:
    """[start, end) of วันนี้ · สัปดาห์นี้ · เดือนนี้, and how the page names it."""
    tz = get_config().tz
    d = local(at).date()
    if range_ == "today":
        start = datetime.combine(d, time(0), tz)
        return start, start + timedelta(days=1), f"{d.day} {MONTHS[d.month - 1]}"
    if range_ == "month":
        first = d.replace(day=1)
        nxt = (first + timedelta(days=32)).replace(day=1)
        return datetime.combine(first, time(0), tz), datetime.combine(nxt, time(0), tz), f"{MONTHS_LONG[d.month - 1]} {d.year + 543}"
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    label = (f"{monday.day}–{sunday.day} {MONTHS[monday.month - 1]}" if monday.month == sunday.month
             else f"{monday.day} {MONTHS[monday.month - 1]} – {sunday.day} {MONTHS[sunday.month - 1]}")
    start = datetime.combine(monday, time(0), tz)
    return start, start + timedelta(days=7), label


def rows(start: datetime, end: datetime) -> list[Activity]:
    """The kept stretches inside [start, end), cut to it."""
    with session() as s:
        out = s.scalars(select(Activity).where(Activity.end > start, Activity.start < end).order_by(Activity.start)).all()
        s.expunge_all()
    for r in out:
        r.start, r.end = max(r.start, start), min(r.end, end)
    return [r for r in out if r.end > r.start]


def minutes(r: Activity) -> float:
    return (r.end - r.start).total_seconds() / 60


def buckets(range_: str, start: datetime, end: datetime, rs: list[Activity]) -> list[dict]:
    """① One bar per day (per hour for วันนี้): minutes per category."""
    tz = get_config().tz
    if range_ == "today":
        edges = [start + timedelta(hours=h) for h in range(25)]
        names = [f"{h:02d}" for h in range(24)]
    else:
        days = (end - start).days
        edges = [datetime.combine(start.astimezone(tz).date() + timedelta(days=i), time(0), tz) for i in range(days + 1)]
        names = [DAYS[e.weekday()] if range_ == "week" else str(e.day) for e in edges[:-1]]
    out = [{"label": n, "start": a.isoformat(), "minutes": defaultdict(float)} for n, a in zip(names, edges[:-1])]
    for r in rs:
        for i, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
            lo, hi = max(r.start, a), min(r.end, b)
            if hi > lo:
                out[i]["minutes"][r.category or "other"] += (hi - lo).total_seconds() / 60
    for o in out:
        o["minutes"] = {k: round(v) for k, v in o["minutes"].items() if v >= 0.5}
    return out


def planned(start: datetime, end: datetime) -> dict[str, float]:
    """Minutes the schedule set aside per project in [start, end) (its tasks' blocks)."""
    with session() as s:
        got = s.execute(select(Task.project, Block.starts_at, Block.ends_at).join(Task, Task.id == Block.task_id)
                        .where(Task.project != "", Block.status.in_(("planned", "pinned")),
                               Block.starts_at < end, Block.ends_at > start)).all()
    out: dict[str, float] = defaultdict(float)
    for project, a, b in got:
        out[project] += (min(b, end) - max(a, start)).total_seconds() / 60
    return out


def projects(start: datetime, end: datetime, rs: list[Activity]) -> list[dict]:
    """② Each project: minutes on it, its plan, and how much it's short."""
    done: dict[str, float] = defaultdict(float)
    for r in rs:
        if r.project:
            done[r.project] += minutes(r)
    plan = planned(start, end)
    names = sorted(set(done) | set(plan), key=lambda n: -max(done.get(n, 0), plan.get(n, 0)))
    return [{"name": n, "minutes": round(done.get(n, 0)), "planned": round(plan.get(n, 0)),
             "short": max(0, round(plan.get(n, 0) - done.get(n, 0)))} for n in names]


def switches(rs: list[Activity]) -> list[datetime]:
    """When you changed app while working (two windows close together, different apps)."""
    out = []
    for prev, cur in zip(rs, rs[1:]):
        if cur.app != prev.app and cur.start - prev.end <= SWITCH_GAP:
            out.append(cur.start)
    return out


def _hm(minutes_: float) -> str:
    h, m = divmod(round(minutes_), 60)
    return " ".join(x for x in (f"{h} ชม." if h else "", f"{m} นาที" if m else "") if x) or "0 นาที"


def behaviours(range_: str, rs: list[Activity], per_project: list[dict]) -> list[dict]:
    """③ What the rules notice, each with why it's said."""
    out: list[dict] = []
    if not rs:
        return out
    tz = get_config().tz
    active = defaultdict(float)  # half-hour slot of the day -> minutes at the computer
    work = defaultdict(float)  # the same, of code and studying only (what focus is about)
    for r in rs:
        t = r.start
        while t < r.end:
            slot = local(t).hour * 2 + local(t).minute // 30
            nxt = min(r.end, datetime.combine(local(t).date(), time(slot // 2, 30 * (slot % 2)), tz) + timedelta(minutes=30))
            active[slot] += (nxt - t).total_seconds() / 60
            if r.category in WORK:
                work[slot] += (nxt - t).total_seconds() / 60
            t = nxt
    sw = defaultdict(int)
    for at in switches(rs):
        sw[local(at).hour * 2 + local(at).minute // 30] += 1
    days = max(1, len({local(r.start).date() for r in rs}))
    best = None
    for first in range(0, 48 - FOCUS_SLOTS + 1):
        slots = range(first, first + FOCUS_SLOTS)
        mins = sum(work[s] for s in slots)
        # two hours you work right through on an average day: every half hour of it at least half
        # used, so a window at the edge of your work (half empty, so few switches) can't win
        if mins < 90 or any(work[s] < 0.5 * 30 * days for s in slots):
            continue
        rate = sum(sw[s] for s in slots) / (mins / 60)
        if best is None or (rate, -mins) < (best[0], -best[2]):
            best = (rate, first, mins)
    if best is not None:
        a = best[1]
        out.append({"icon": "bolt", "title": f"โฟกัสดีสุด {a // 2:02d}:{30 * (a % 2):02d}–{(a + FOCUS_SLOTS) // 2:02d}:{30 * ((a + FOCUS_SLOTS) % 2):02d}",
                    "sub": f"ช่วงนี้สลับแอปน้อยที่สุด ({best[0]:.0f} ครั้งต่อชั่วโมง) เหมาะกับงานคิดยาก"})
    late = range(44, 48)  # 22:00–24:00
    late_min = sum(active[s] for s in late)
    early_min = sum(v for s, v in active.items() if s < 44)
    if late_min >= 30 and early_min >= 60:
        late_rate = sum(sw[s] for s in late) / (late_min / 60)
        early_rate = sum(v for s, v in sw.items() if s < 44) / (early_min / 60)
        if late_rate >= max(1.5 * early_rate, 3):
            cats = defaultdict(float)
            for r in rs:
                if local(r.start).hour >= 22:
                    cats[r.category or "other"] += minutes(r)
            top = max(cats, key=cats.get) if cats else "other"
            more = (f"บ่อยขึ้น {late_rate / early_rate:.0f} เท่า" if early_rate
                    else f"บ่อย {late_rate:.0f} ครั้งต่อชั่วโมง (ช่วงอื่นแทบไม่สลับ)")
            out.append({"icon": "eye", "title": f"หลัง 22:00 สลับแอป{more}", "sub": f"ส่วนใหญ่เป็น{CATEGORIES.get(top, 'อื่นๆ')}"})
    for p in per_project:
        if p["planned"] >= 120 and p["minutes"] < SHORT_OF_PLAN * p["planned"]:
            out.append({"icon": "trend", "title": f"{p['name']} ได้เวลาน้อยกว่าแผน {100 - round(100 * p['minutes'] / p['planned'])}%",
                        "sub": f"ทำ {_hm(p['minutes'])} จากแผน {_hm(p['planned'])} · บล็อกที่หลุดกลับไปให้ตัววางตารางหาเวลาใหม่",
                        "link": "/schedule"})
    longest = None  # the longest stretch on one project, small gaps closed
    run_start = run_end = run_name = None
    for r in rs:
        if r.project and r.project == run_name and r.start - run_end <= SWITCH_GAP:
            run_end = r.end
        else:
            if run_name and (longest is None or run_end - run_start > longest[0]):
                longest = (run_end - run_start, run_name, run_start)
            run_start, run_end, run_name = (r.start, r.end, r.project) if r.project else (None, None, None)
    if run_name and (longest is None or run_end - run_start > longest[0]):
        longest = (run_end - run_start, run_name, run_start)
    if longest and longest[0] >= timedelta(minutes=45):
        when = local(longest[2])
        out.append({"icon": "clock", "title": f"ทำ {longest[1]} ต่อเนื่องนานสุด {_hm(longest[0].total_seconds() / 60)}",
                    "sub": f"{DAYS[when.weekday()]} {when.day} {MONTHS[when.month - 1]} เริ่ม {when:%H:%M}"})
    return out


def unsorted(rs: list[Activity], limit: int = 6) -> list[dict]:
    """อื่นๆ: what the rules couldn't place, by app (and the title that took most of it)."""
    by_app: dict[str, float] = defaultdict(float)
    titles: dict[tuple[str, str], float] = defaultdict(float)
    for r in rs:
        if (r.category or "other") == "other":
            by_app[r.app] += minutes(r)
            titles[(r.app, r.title)] += minutes(r)
    out = []
    for app in sorted(by_app, key=lambda a: -by_app[a])[:limit]:
        title = max((t for a, t in titles if a == app), key=lambda t: titles[(app, t)])
        out.append({"app": app, "title": title, "minutes": round(by_app[app])})
    return [o for o in out if o["minutes"] >= 1]


def page(range_: str, at: datetime) -> dict:
    start, end, label = span(range_, at)
    rs = rows(start, min(end, at))
    per_project = projects(start, min(end, at), rs)  # the plan so far, against what's done so far
    return {"range": range_, "label": label, "start": start.isoformat(), "end": end.isoformat(),
            "categories": CATEGORIES, "bars": buckets(range_, start, end, rs), "projects": per_project,
            "behaviours": behaviours(range_, rs, per_project), "unsorted": unsorted(rs),
            "total": round(sum(minutes(r) for r in rs)), "days_with_data": len({local(r.start).date() for r in rs})}


def today_actual(d: date) -> list[dict]:
    """W1's ทำจริง row: the day's stretches by project or category, small gaps closed."""
    tz = get_config().tz
    start = datetime.combine(d, time(0), tz)
    out: list[dict] = []
    for r in rows(start, start + timedelta(days=1)):
        key = r.project or CATEGORIES.get(r.category or "other", "อื่นๆ")
        if out and out[-1]["what"] == key and r.start - datetime.fromisoformat(out[-1]["end"]) <= SWITCH_GAP:
            out[-1]["end"] = r.end.isoformat()
        else:
            out.append({"start": r.start.isoformat(), "end": r.end.isoformat(), "what": key, "category": r.category or "other",
                        "project": r.project})
    return [o for o in out if (datetime.fromisoformat(o["end"]) - datetime.fromisoformat(o["start"])) >= timedelta(minutes=5)]
