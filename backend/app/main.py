"""my_secretary v2: the server entry point.

Run from backend/:

    uv run uvicorn app.main:app --reload --port 8000

`lifespan` is where the secretary's parts start and stop with the server. The
store is brought up to date first (step 3). The later B1 steps add the
secretary's clock (step 5) and the Discord bot (step 6), and the built web
pages are served from here too (step 9).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core import db
from app.api import ask as ask_api
from app.connectors import discord_bot
from app.core.clock import clock
from app.features import ask_discord

VERSION = "2.0.0.dev0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.migrate()  # new tables/columns from a fresh `git pull` are created here
    await clock.start()  # schedules the rounds and runs any missed while the machine was off
    ask_discord.setup()  # your DMs go to the ask feature; its buttons are registered
    await discord_bot.start()  # connects in the background; the web page works without it
    yield
    await discord_bot.stop()
    clock.stop()


app = FastAPI(title="my_secretary", version=VERSION, lifespan=lifespan)
app.include_router(ask_api.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    """A cheap "is the server up?" check: curl it now; the web page and the
    always-on setup (step 10) use it later."""
    return {"status": "ok", "version": VERSION}
