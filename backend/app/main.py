"""FastAPI entry point.

M0 wires up: the database, a health check, and the calendar smoke-test routes.
Run it with:  uv run uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs to try the endpoints.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import academic, calendar, chat, mail, proactive, projects
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
app.include_router(mail.router)


@app.get("/healthz")
def health():
    return {"status": "ok", "service": "my_secretary", "milestone": "M6"}


# Serve the built React app (frontend/dist) from this same server, so the whole
# thing is reachable on a single port (e.g. over Tailscale from a phone/iPad).
# Mounted LAST and at "/" so the API routes above always match first; anything
# else falls through to the static files. With HashRouter on the frontend, the
# only HTML path ever requested is "/", which `html=True` serves as index.html.
# Run `npm run build` in frontend/ to (re)generate dist.
_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
