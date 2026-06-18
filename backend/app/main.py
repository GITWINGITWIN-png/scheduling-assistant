"""FastAPI entry point.

M0 wires up: the database, a health check, and the calendar smoke-test routes.
Run it with:  uv run uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs to try the endpoints.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.routers import calendar, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables on startup.
    init_db()
    yield


app = FastAPI(title="my_secretary", version="0.1.0", lifespan=lifespan)

app.include_router(calendar.router)
app.include_router(chat.router)


@app.get("/")
def health():
    return {"status": "ok", "service": "my_secretary", "milestone": "M1"}
