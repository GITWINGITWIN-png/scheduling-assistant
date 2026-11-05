"""my_secretary v2: the server entry point.

Run from backend/:

    uv run uvicorn app.main:app --reload --port 8000

For now it only answers /api/health. The later B1 steps hang everything else
off this one app: the store opens at startup (step 3), the secretary's clock
starts with it (step 5), the Discord bot runs alongside (step 6), and the
built web pages are served from here too (step 9).
"""

from fastapi import FastAPI

app = FastAPI(title="my_secretary", version="2.0.0.dev0")


@app.get("/api/health")
def health() -> dict[str, str]:
    """A cheap "is the server up?" check: curl it now; the web page and the
    always-on setup (step 10) use it later."""
    return {"status": "ok", "version": app.version}
