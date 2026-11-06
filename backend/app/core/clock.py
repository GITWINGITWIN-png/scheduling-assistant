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

Each round has an on/off switch (settings page, "clock.enabled"). A round that
arrives with a new phase starts **off**, and you switch it on at that phase's
check. So no new scheduled work starts by itself, even if the machine restarts
in the middle of a phase (the service runs whatever code is checked out).
Only B1's backup is on from the start.
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

# The work a round does. It returns a short result for the log ("37 ฉบับ"), or None when
# there is nothing to tell: then the run leaves no row in สิ่งที่เลขาทำ (the 5-minute rounds
# would otherwise write ~290 empty rows a day). Its last-run time is still saved and shown.
Handler = Callable[[], Awaitable[str | None]]

STATE_KEY = "state.clock"  # {round id: ISO time of its last run}
ENABLED_KEY = "clock.enabled"  # {round id: on/off}; a round not listed uses ON_BY_DEFAULT
ON_BY_DEFAULT = {"backup"}


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


# Every round agreed in stage 1 (PLAN.md 1.1, 2.1, 4.2, P2, P3), plus B1's nightly backup and B3's three.
ROUNDS: dict[str, Round] = {r.id: r for r in (
    Round("watch", "เฝ้าคนสำคัญและคีย์เวิร์ด", "ทุก 5 นาที", {"minute": "*/5"}, "B2"),
    Round("mail_big", "รอบอ่านอีเมล (ใหญ่)", "00:00", {"hour": 0, "minute": 0}, "B2"),
    Round("mail_small", "รอบอ่านอีเมล (เล็ก)", "12:00", {"hour": 12, "minute": 0}, "B2"),
    Round("schedule", "วางและซิงก์ตาราง", "ทุก 15 นาที", {"minute": "*/15"}, "B3"),
    Round("remind", "เตือนก่อนถึงกำหนด", "ทุก 5 นาที", {"minute": "*/5"}, "B3"),
    Round("classroom", "ดึงงานและสื่อจาก Classroom", "ทุก 2 ชั่วโมง", {"hour": "*/2", "minute": 10}, "B3"),
    Round("projects", "สแกนโปรเจคใน ~/Projects", "06:30", {"hour": 6, "minute": 30}, "B5"),
    Round("inbox", "อ่านข่าวจากโปรเจค (~/.secretary/inbox)", "ทุก 5 นาที", {"minute": "*/5"}, "B5"),
    Round("jobs", "งานเบื้องหลังในโปรเจค", "ทุก 15 นาที 01:00–06:00", {"hour": "1-5", "minute": "*/15"}, "B5"),
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


def enabled(round_id: str) -> bool:
    with session() as s:
        row = s.get(Setting, ENABLED_KEY)
        return bool((row.value or {}).get(round_id, round_id in ON_BY_DEFAULT)) if row else round_id in ON_BY_DEFAULT


def set_enabled(round_id: str, on: bool, via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    """Switch a round on or off (recorded, undoable). Returns the action id."""
    if round_id not in ROUNDS:
        raise KeyError(round_id)
    old = enabled(round_id)
    with session() as s:
        row = s.get(Setting, ENABLED_KEY)
        state = dict(row.value) if row and row.value else {}
        state[round_id] = on
        s.merge(Setting(key=ENABLED_KEY, value=state))
    return actions.record("settings.round", f"{'เปิด' if on else 'ปิด'}รอบ{ROUNDS[round_id].title}", ROUNDS[round_id].when,
                          source_label=via[0], source_url=via[1], undo={"round_id": round_id, "old": old})


async def _undo_enabled(undo: dict) -> None:
    with session() as s:
        row = s.get(Setting, ENABLED_KEY)
        state = dict(row.value) if row and row.value else {}
        state[undo["round_id"]] = undo["old"]
        s.merge(Setting(key=ENABLED_KEY, value=state))


actions.register_undo("settings.round", _undo_enabled)


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
        if not enabled(round_id):
            log.info("round %s is switched off; skipped", round_id)
            return None
        self._running.add(round_id)
        try:
            result = await rnd.handler()
            _save_last_run(round_id, now())
            if result or caught_up:  # a caught-up run is always worth a line, even a quiet one
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
                "active": rnd.handler is not None, "enabled": enabled(rnd.id),
                "last_run": state.get(rnd.id),
                "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
            })
        return out


clock = Clock()


async def run_soon(round_id: str) -> None:
    """Fire a round in the background, e.g. from a "run now" button."""
    asyncio.create_task(clock.fire(round_id))
