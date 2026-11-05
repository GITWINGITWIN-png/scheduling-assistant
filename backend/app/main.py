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
from app.core.clock import clock

VERSION = "2.0.0.dev0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.migrate()  # new tables/columns from a fresh `git pull` are created here
    await clock.start()  # schedules the rounds and runs any missed while the machine was off
    yield
    clock.stop()


app = FastAPI(title="my_secretary", version=VERSION, lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    """A cheap "is the server up?" check: curl it now; the web page and the
    always-on setup (step 10) use it later."""
    return {"status": "ok", "version": VERSION}
