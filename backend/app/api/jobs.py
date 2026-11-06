"""B5's web API for the background work (W4): the quota, and (later steps) the queue, the plans
and the runner. The rule book (W8) has its own, api/rules.py."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.rules import book
from app.features.jobs import quota, runner

router = APIRouter(prefix="/api")


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def quota_view(reading) -> dict | None:
    if reading is None:
        return None
    return {"week_left": reading.week_left, "week_resets_at": _iso(reading.week_resets_at), "five_left": reading.five_left,
            "five_resets_at": _iso(reading.five_resets_at), "at": _iso(reading.at), "source": reading.source,
            "line": book.line(), "fresh": quota.latest() is not None}


@router.get("/quota")
def get_quota() -> dict:
    """The newest reading of any age (the page says how old it is), and the 70% line."""
    return {"quota": quota_view(quota.latest(max_age=None)), "line": book.line()}


@router.post("/quota/read")
async def read_quota() -> dict:
    """อ่านตอนนี้: a tiny call to hear the current numbers."""
    return {"quota": quota_view(await quota.probe()), "line": book.line()}


# ------------------------------------------------------------------ ทำเลย · หยุด (B5.7)
@router.post("/jobs/{job_id}/run")
async def run_now(job_id: int) -> dict:
    """ทำเลย: start a ready job now, outside the night window too (it is checked again first)."""
    try:
        return {"line": await runner.start(job_id, night=False)}
    except runner.RunError as exc:
        raise HTTPException(409, str(exc))


@router.post("/jobs/{job_id}/stop")
def stop_job(job_id: int) -> dict:
    """หยุด: the run stops within seconds and keeps what it did, committed on its branch."""
    try:
        runner.stop(job_id)
    except runner.RunError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True}
