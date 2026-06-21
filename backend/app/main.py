"""FastAPI entry point.

M0 wires up: the database, a health check, and the calendar smoke-test routes.
Run it with:  uv run uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs to try the endpoints.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import academic, calendar, chat, proactive, projects
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables, then start the proactive scheduler.
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="my_secretary", version="0.1.0", lifespan=lifespan)

# Allow the Vite dev server (React app) to call this API from the browser.
# Browsers block cross-origin requests unless the API opts in via CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(calendar.router)
app.include_router(chat.router)
app.include_router(projects.router)
app.include_router(academic.router)
app.include_router(proactive.router)


@app.get("/")
def health():
    return {"status": "ok", "service": "my_secretary", "milestone": "M5"}
