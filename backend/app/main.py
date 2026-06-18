"""FastAPI entry point.

M0 wires up: the database, a health check, and the calendar smoke-test routes.
Run it with:  uv run uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs to try the endpoints.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import calendar, chat, projects


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables on startup.
    init_db()
    yield


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


@app.get("/")
def health():
    return {"status": "ok", "service": "my_secretary", "milestone": "M2"}
