"""The secretary's clock (นาฬิกาเลขา): scheduled rounds, and catching up on missed ones.

A *round* is one recurring job, such as "read the mail at 00:00" or "back up the
database every night". The full list agreed in stage 1 is ROUNDS below. Each
later phase attaches the work to its round with `attach()`. Until then the
round is only listed: the settings page shows it with the phase it arrives in,
and nothing runs.

APScheduler fires the rounds while the server runs. It can't know what it
missed while the machine was off, because its schedule lives in memory. So
each round's last run is saved in the store ("state.clock"), and at startup
`catch_up()` asks, for each round: "was a scheduled time missed since the
last run?" If one was, the round runs once right away, however many times it
was missed. Nobody wants five backups or two morning briefs in a row.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core import actions
from app.core.config import get_config
from app.core.db import now, session
from app.core.tables import Setting

log = logging.getLogger(__name__)

# The work a round does. It returns a short result for the log ("37 ฉบับ"), or None.
Handler = Callable[[], Awaitable[str | None]]

STATE_KEY = "state.clock"  # {round id: ISO time of its last run}


@dataclass
class Round:
    id: str
    title: str  # what it does, as the settings page (W10) says it
    when: str  # when, in words
    cron: dict  # APScheduler CronTrigger fields, in your time zone
    phase: str  # the build phase that gives it its work
    handler: Handler | None = None

    def trigger(self) -> CronTrigger:
        return CronTrigger(**self.cron, timezone=get_config().tz)


# Every round agreed in stage 1 (PLAN.md 1.1, 2.1, 4.2, P2, P3), plus B1's nightly backup.
ROUNDS: dict[str, Round] = {r.id: r for r in (
    Round("watch", "เฝ้าคนสำคัญและคีย์เวิร์ด", "ทุก 5 นาที", {"minute": "*/5"}, "B2"),
    Round("mail_big", "รอบอ่านอีเมล (ใหญ่)", "00:00", {"hour": 0, "minute": 0}, "B2"),
    Round("mail_small", "รอบอ่านอีเมล (เล็ก)", "12:00", {"hour": 12, "minute": 0}, "B2"),
    Round("projects", "สแกนโปรเจคใน ~/Projects", "06:30", {"hour": 6, "minute": 30}, "B5"),
    Round("morning", "สรุปเช้า", "07:00", {"hour": 7, "minute": 0}, "B4"),
    Round("evening", "ทบทวนเย็น", "21:00", {"hour": 21, "minute": 0}, "B4"),
    Round("ideas", "จัดกลุ่มไอเดีย", "00:00 และ 12:00", {"hour": "0,12", "minute": 5}, "B6"),
    Round("weekly", "ทบทวนรายสัปดาห์", "อาทิตย์ 19:00", {"day_of_week": "sun", "hour": 19, "minute": 0}, "B7"),
    Round("backup", "สำรองฐานข้อมูล (เก็บ 14 วัน)", "ทุกวัน 03:30", {"hour": 3, "minute": 30}, "B1"),
)}


def attach(round_id: str, handler: Handler) -> None:
    """Give a listed round its work. Call this before the clock starts."""
    ROUNDS[round_id].handler = handler


# ------------------------------------------------------------------ last-run memory
def _load_state() -> dict[str, str]:
    with session() as s:
        row = s.get(Setting, STATE_KEY)
        return dict(row.value) if row and row.value else {}


def last_run(round_id: str) -> datetime | None:
    value = _load_state().get(round_id)
    return datetime.fromisoformat(value) if value else None


def _save_last_run(round_id: str, at: datetime) -> None:
    with session() as s:
        row = s.get(Setting, STATE_KEY)
        state = dict(row.value) if row and row.value else {}
        state[round_id] = at.isoformat()
        s.merge(Setting(key=STATE_KEY, value=state))


def missed_since(rnd: Round, last: datetime, at: datetime) -> datetime | None:
    """The first scheduled time after `last` if it is already in the past at `at`, else None."""
    due = rnd.trigger().get_next_fire_time(None, last + timedelta(microseconds=1))
    return due if due is not None and due <= at else None


# ------------------------------------------------------------------ the clock
class Clock:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone=get_config().tz)
        self._running: set[str] = set()

    def active(self) -> list[Round]:
        return [r for r in ROUNDS.values() if r.handler]

    async def start(self) -> None:
        for rnd in self.active():
            # coalesce + max_instances=1: if a round is late or still running, it runs once, not twice
            self.scheduler.add_job(self.fire, rnd.trigger(), args=[rnd.id], id=rnd.id,
                                   coalesce=True, max_instances=1, misfire_grace_time=300)
        self.scheduler.start()
        await self.catch_up()
        log.info("clock started: %s", ", ".join(r.id for r in self.active()) or "no rounds yet")

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def catch_up(self) -> None:
        at = now()
        for rnd in self.active():
            last = last_run(rnd.id)
            if last is None:
                # First time ever: start counting from now instead of running immediately
                _save_last_run(rnd.id, at)
                continue
            if missed := missed_since(rnd, last, at):
                log.info("round %s missed its %s run; running it now", rnd.id, missed.isoformat())
                await self.fire(rnd.id, caught_up=missed)

    async def fire(self, round_id: str, caught_up: datetime | None = None) -> str | None:
        """Run one round now. Errors are logged, never raised, so one bad round can't stop the clock."""
        rnd = ROUNDS[round_id]
        if rnd.handler is None or round_id in self._running:
            return None
        self._running.add(round_id)
        try:
            result = await rnd.handler()
            _save_last_run(round_id, now())
            actions.record(f"round.{round_id}", rnd.title + (" · ทำรอบที่พลาด" if caught_up else ""),
                           result or "", source_label="นาฬิกาเลขา")
            log.info("round %s done%s: %s", round_id, " (catch-up)" if caught_up else "", result or "")
            return result
        except Exception:
            log.exception("round %s failed", round_id)
            return None
        finally:
            self._running.discard(round_id)

    def status(self) -> list[dict]:
        """Every round with its schedule, phase, last and next run (for the settings page)."""
        state = _load_state()
        out = []
        for rnd in ROUNDS.values():
            job = self.scheduler.get_job(rnd.id) if self.scheduler.running else None
            out.append({
                "id": rnd.id, "title": rnd.title, "when": rnd.when, "phase": rnd.phase,
                "active": rnd.handler is not None,
                "last_run": state.get(rnd.id),
                "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
            })
        return out


clock = Clock()


async def run_soon(round_id: str) -> None:
    """Fire a round in the background, e.g. from a "run now" button."""
    asyncio.create_task(clock.fire(round_id))
