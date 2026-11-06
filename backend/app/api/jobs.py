"""B5's web API for the background work (W4) and the rule book (W8): the quota, and (later
steps) the rules, the queue, the plans and the runner."""

from __future__ import annotations

from fastapi import APIRouter

from app.features.jobs import quota

router = APIRouter(prefix="/api")


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def quota_view(reading) -> dict | None:
    if reading is None:
        return None
    return {"week_left": reading.week_left, "week_resets_at": _iso(reading.week_resets_at), "five_left": reading.five_left,
            "five_resets_at": _iso(reading.five_resets_at), "at": _iso(reading.at), "source": reading.source,
            "line": quota.LINE, "fresh": quota.latest() is not None}


@router.get("/quota")
def get_quota() -> dict:
    """The newest reading of any age (the page says how old it is), and the 70% line."""
    return {"quota": quota_view(quota.latest(max_age=None)), "line": quota.LINE}


@router.post("/quota/read")
async def read_quota() -> dict:
    """อ่านตอนนี้: a tiny call to hear the current numbers."""
    return {"quota": quota_view(await quota.probe()), "line": quota.LINE}
