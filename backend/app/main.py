"""my_secretary v2: the server entry point.

Run from backend/:

    uv run uvicorn app.main:app --reload --port 8000

then open http://localhost:8000. Always-on, it runs as a systemd user service
(deploy/, step 10).

`lifespan` is where the secretary's parts start and stop with the server, in
this order: bring the store up to date, start the clock (catching up on missed
rounds), hook the features into Discord, connect the bot. One process holds
all of it: the API, the web page, the clock and the bot.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app.api import ask as ask_api
from app.api import log as log_api
from app.api import settings as settings_api
from app.connectors import discord_bot
from app.core import db
from app.core.clock import clock
from app.core.config import REPO_DIR
from app.features import actions_discord, ask_discord

VERSION = "2.0.0.dev0"
WEB_DIST = REPO_DIR / "frontend" / "dist"  # `npm run build` in frontend/ writes the web page here

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.migrate()  # new tables/columns from a fresh `git pull` are created here
    await clock.start()  # schedules the rounds and runs any missed while the machine was off
    ask_discord.setup()  # your DMs go to the ask feature; its buttons are registered
    actions_discord.setup()  # the ย้อนกลับ button
    await discord_bot.start()  # connects in the background; the web page works without it
    yield
    await discord_bot.stop()
    clock.stop()


app = FastAPI(title="my_secretary", version=VERSION, lifespan=lifespan)
app.include_router(ask_api.router)
app.include_router(log_api.router)
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
