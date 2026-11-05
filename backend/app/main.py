"""my_secretary v2: the server entry point.

Run from backend/:

    uv run uvicorn app.main:app --reload --port 8000

then open http://localhost:8000. Always-on, it runs as a systemd user service
(deploy/, step 10).

`lifespan` is where the secretary's parts start and stop with the server, in
this order: bring the store up to date, start the clock (catching up on missed
rounds), hook the features into Discord, connect the bot. One process holds
all of it: the API, the web page, the clock and the bot.

Only one process at a time runs the clock and the bot (core/worker.py). A second
copy, e.g. on :8001 next to the service, serves the web page and API only, and
takes over if the first one stops.
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app.api import ask as ask_api
from app.api import log as log_api
from app.api import mail as mail_api
from app.api import settings as settings_api
from app.connectors import discord_bot
from app.core import backup, db, worker
from app.core.clock import clock
from app.core.config import REPO_DIR
from app.features import actions_discord, ask_discord
from app.features.mail import cards as mail_cards
from app.features.mail import extract as mail_extract
from app.features.mail import followups as mail_followups
from app.features.mail import rounds as mail_rounds
from app.features.mail import watch as mail_watch
from app.features.schedule import remind as schedule_remind
from app.features.schedule import sync as schedule_sync

VERSION = "2.0.0.dev0"
WEB_DIST = REPO_DIR / "frontend" / "dist"  # `npm run build` in frontend/ writes the web page here

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


async def start_background() -> None:
    """The worker's parts: only the process holding the worker lock runs these."""
    backup.setup()  # the nightly backup is the clock's first round with work (B1)
    mail_watch.setup()  # B2: the 5-minute watch (starts switched off until B2's check)
    mail_rounds.setup()  # B2: the 00:00 and 12:00 reading rounds (also off until then)
    mail_extract.setup()  # appointments and tasks from what the rounds read
    mail_followups.setup()  # who owes a reply, and the reminders
    mail_cards.setup()  # #ด่วน · #อนุมัติ · #สรุป cards (after extract, so they can say what was done)
    schedule_sync.setup()  # B3: plan blocks and sync with Google Calendar every 15 min (off until B3's check)
    schedule_remind.setup()  # B3: "tomorrow" / "in an hour" in #ด่วน every 5 min (off until the check)
    await clock.start()  # schedules the rounds and runs any missed while the machine was off
    ask_discord.setup()  # your DMs go to the ask feature; its buttons are registered
    actions_discord.setup()  # the ย้อนกลับ button
    await discord_bot.start()  # connects in the background; the web page works without it


async def wait_to_take_over() -> None:
    """For a second copy: check now and then whether the worker stopped, and take over if so."""
    while not worker.claim():
        await asyncio.sleep(worker.LOCK_RETRY)
    log.info("the other secretary stopped; this one now runs the clock and the Discord bot")
    discord_bot.bot.problem = ""
    await start_background()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.migrate()  # new tables/columns from a fresh `git pull` are created here
    waiting: asyncio.Task | None = None
    if worker.claim():
        await start_background()
    else:
        discord_bot.bot.problem = (f"เลขาอีกตัว (pid {worker.holder()}) ดูแลนาฬิกาและ Discord อยู่ · "
                                   "ตัวนี้เปิดแค่หน้าเว็บ เพื่อไม่ให้ตอบซ้ำ")
        log.warning("another secretary (pid %s) runs the clock and the Discord bot; "
                    "this one serves the web page and API only", worker.holder())
        waiting = asyncio.create_task(wait_to_take_over(), name="wait-to-take-over")
    yield
    if waiting:
        waiting.cancel()
        with suppress(asyncio.CancelledError):
            await waiting
    if worker.is_worker():
        await discord_bot.stop()
        clock.stop()


app = FastAPI(title="my_secretary", version=VERSION, lifespan=lifespan)
app.include_router(ask_api.router)
app.include_router(log_api.router)
app.include_router(mail_api.router)
app.include_router(settings_api.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    """A cheap "is the server up?" check (curl it; the always-on setup uses it too)."""
    return {"status": "ok", "version": VERSION}


@app.get("/{path:path}", include_in_schema=False)
def web(path: str):
    """The web page. Real files (scripts, styles, fonts) are served as they are. Every other
    path (/log, /settings, ...) gets index.html, and the page's router shows the right screen."""
    if path.startswith("api/"):
        raise HTTPException(404, "no such API")
    root = WEB_DIST.resolve()
    file = (WEB_DIST / path).resolve()
    if path and file.is_file() and file.is_relative_to(root):  # never serve anything outside dist/
        return FileResponse(file)
    index = WEB_DIST / "index.html"
    if not index.exists():
        return HTMLResponse("<p>ยังไม่ได้ build หน้าเว็บ: <code>cd frontend && npm install && npm run build</code></p>", 503)
    return FileResponse(index)
