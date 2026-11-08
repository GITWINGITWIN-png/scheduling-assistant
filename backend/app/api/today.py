"""The today page (W1): everything of today on one page, from what the other features know.

- hello: the morning brief's numbers ("เช้านี้: …", W1 ②), the same line as in #สรุป, with the
  brief in full behind "ดูสรุปเช้าฉบับเต็ม"; before today's brief exists, the same numbers
  counted now.
- the day as rows (W1 ③): แผน (appointments, work blocks, due dates) and เลขา (the daily rounds
  that ran today, and the ones still to come), and ทำจริง (B6): what ActivityWatch saw, by project
  or category, through the privacy filter.
- เรื่องสำคัญ (W1 ⑤): today's mail from important people or matching a keyword, with what
  the secretary did; the same count as the side menu's number.
- งานเบื้องหลัง and ข่าวโปรเจค (W1 ⑥ ⑦, B5): what runs and waits, today's runs on the เลขา row,
  and the projects' news.
What waits for you comes from /api/decisions (the bell's rows).
"""

from datetime import datetime, time, timedelta

from fastapi import APIRouter
from sqlalchemy import select

from app.connectors import discord_bot as dc
from app.core import clock
from app.core.config import get_config
from app.core.db import now, session
from app.core.tables import Action, Message
from app.core.timefmt import local
from app.features.briefs import day, morning
from app.features.briefs.tables import Brief
from app.features.time import insights

router = APIRouter(prefix="/api")

# The rounds the เลขา row shows: the ones that run once or twice a day. The frequent ones (every
# few minutes) would only be noise on a day's row.
DAILY = ("mail_big", "morning", "mail_small", "evening", "backup", "projects", "weekly")


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def greeting(at: datetime) -> str:
    h = local(at).hour
    return "สวัสดีตอนเช้าครับ" if h < 12 else "สวัสดีตอนบ่ายครับ" if h < 17 else "สวัสดีตอนเย็นครับ"


def _brief(d: str) -> dict | None:
    with session() as s:
        b = s.scalar(select(Brief).where(Brief.kind == "morning", Brief.day == d))
        if b is None:
            return None
        m = s.get(Message, b.message_id) if b.message_id else None
        link = ""
        if m is not None and (ch := dc.bot.channels.get(m.channel)) is not None:
            link = f"https://discord.com/channels/{ch.guild.id}/{ch.id}/{m.discord_id}"
        return {"made_at": _iso(b.made_at), "title": b.title, "headline": b.headline, "fields": b.fields,
                "footer": b.footer, "sent": m is not None, "link": link}


def _secretary(at: datetime) -> list[dict]:
    """The เลขา row: daily rounds that ran today (from the log), then the ones still to come today."""
    start = day.day_start(day.today(at))
    with session() as s:
        ran = s.scalars(select(Action).where(Action.kind.in_([f"round.{r}" for r in DAILY]), Action.at >= start,
                                             Action.at < at).order_by(Action.at)).all()
        out = [{"at": _iso(a.at), "title": clock.ROUNDS[a.kind.removeprefix("round.")].title, "done": True,
                "line": a.target} for a in ran]
    end = start + timedelta(days=1)
    for rid in DAILY:
        rnd = clock.ROUNDS[rid]
        if rnd.handler is None or not clock.enabled(rid):
            continue
        nxt = rnd.trigger().get_next_fire_time(None, at)
        if nxt is not None and nxt < end:
            out.append({"at": _iso(nxt), "title": rnd.title, "done": False, "line": ""})
    return out


def _news(at: datetime) -> list[dict]:
    """ข่าวโปรเจค (W1 ⑦): the last two days', the projects that matter most first."""
    from app.features.projects.tables import Project, ProjectNews

    with session() as s:
        rows = s.execute(select(ProjectNews, Project.potential).outerjoin(Project, Project.id == ProjectNews.project_id)
                         .where(ProjectNews.at >= at - timedelta(days=2), ProjectNews.kind != "bad")
                         .order_by(ProjectNews.at.desc()).limit(20)).all()
    order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "F": 5}
    rows.sort(key=lambda r: (not r[0].urgent, order.get(r[1] or "C", 3)))
    return [{"id": n.id, "project": n.project, "title": n.title, "body": n.body, "at": _iso(n.at), "potential": pot or "",
             "urgent": n.urgent, "failed": n.failed, "needs_you": n.needs_you, "link": n.link} for n, pot in rows[:5]]


def _jobs(at: datetime) -> dict:
    """งานเบื้องหลัง (W1 ⑥): what's running with its budget, the queue, and what ran today (B5)."""
    from app.features.jobs import queue
    from app.features.jobs.tables import Job

    start = day.day_start(day.today(at))
    with session() as s:
        running = s.scalar(select(Job).where(Job.status == "running"))
        ran = s.scalars(select(Job).where(Job.started_at >= start - timedelta(hours=8), Job.started_at < at,
                                          Job.status.in_(("running", "done", "stopped", "failed"))).order_by(Job.started_at)).all()
        view = ({"id": running.id, "project": running.project, "title": running.title, "used": running.used,
                 "budget": running.budget, "started_at": _iso(running.started_at), "model": running.model,
                 "effort": running.effort} if running else None)
        runs = [{"id": j.id, "project": j.project, "title": j.title, "status": j.status, "start": _iso(j.started_at),
                 "end": _iso(j.finished_at or at), "line": day.job_line(j.result)} for j in ran]
    waiting = [{"id": j.id, "project": j.project, "title": j.title or j.stuck_at, "status": j.status,
                "approved_until": _iso(j.approved_until)} for j in queue.ordered()[:5]]
    return {"running": view, "queue": waiting, "runs": runs, "round_on": clock.enabled("jobs")}


@router.get("/today")
def today_page() -> dict:
    at = now()
    d = day.today(at)
    brief = _brief(d.isoformat())
    items = day.agenda(d)
    return {
        "greeting": greeting(at),
        "brief": brief,
        "headline": brief["headline"] if brief else morning.compose(at)["headline"],
        "morning_on": clock.enabled("morning"),
        "plan": [{"start": _iso(i.start), "end": _iso(i.end), "title": i.title, "kind": i.kind, "sub": i.sub} for i in items],
        "secretary": _secretary(at),
        "actual": insights.today_actual(d),  # B6: the ทำจริง row
        "recording": clock.enabled("activity"),
        "important": [{"id": m.id, "who": m.who, "summary": m.summary, "at": _iso(m.sent_at), "done": m.done, "link": m.link}
                      for m in day.important_mail(day.day_start(d), at)],
        "news": _news(at),
        "jobs": _jobs(at),
        "hours": [7, 23],
        "web": get_config().web_url,
        "day_start": _iso(datetime.combine(d, time(0), get_config().tz)),
    }
