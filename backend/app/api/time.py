"""B6's time page (W7): what you did on this computer, from ActivityWatch through the privacy filter,
and the privacy card (W7 ④ ⑤): the recording switch, หยุดบันทึก, and the blocklist."""

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.core.db import now
from app.features.time import categorize, insights, privacy, pull, recorder
from app.features.time.tables import KINDS

router = APIRouter(prefix="/api")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def privacy_card() -> dict:
    return {"recorder": recorder.status(), "rules": privacy.listed(), "kinds": KINDS, "last_read": pull.last_read()}


@router.get("/time")
def time_page(range: str = "week") -> dict:  # noqa: A002  (the page's word: วันนี้ · สัปดาห์นี้ · เดือนนี้)
    if range not in ("today", "week", "month"):
        raise HTTPException(422, "range ต้องเป็น today, week หรือ month")
    return {"privacy": privacy_card(), **insights.page(range, now()), "rules": categorize.yours()}


class CategoryIn(Strict):
    field: str  # app · title
    match: str
    category: str
    project: str = ""


@router.post("/time/categories")
def add_category(body: CategoryIn) -> dict:
    """จัดหมวด from อื่นๆ: a rule of yours, and everything kept is sorted again."""
    try:
        return {"action_id": categorize.add_rule(body.field, body.match, body.category, body.project)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


class SwitchIn(Strict):
    on: bool


@router.put("/time/recording")
async def switch(body: SwitchIn) -> dict:
    try:
        action_id = await asyncio.to_thread(recorder.set_on, body.on)
    except recorder.RecorderError as exc:
        raise HTTPException(422, str(exc)) from exc
    if body.on:  # read at once, so the page shows something without waiting a quarter of an hour
        if await asyncio.to_thread(_answers_within, 15):  # awatcher waits 5 s for the desktop, then starts its server
            await pull.run()
    return {"action_id": action_id, **privacy_card()}


def _answers_within(seconds: int) -> bool:
    """Wait (blocking) until ActivityWatch's server answers, at most `seconds`."""
    import time

    from app.connectors import activitywatch as aw

    for _ in range(seconds):
        try:
            aw.info()
            return True
        except (aw.Unreachable, aw.Refused):
            time.sleep(1)
    return False


class PauseIn(Strict):
    minutes: int = 60


@router.post("/time/pause")
async def pause(body: PauseIn) -> dict:
    try:
        until, action_id = await asyncio.to_thread(recorder.pause, body.minutes)
    except recorder.RecorderError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"until": until.isoformat(), "action_id": action_id, **privacy_card()}


@router.post("/time/resume")
async def resume() -> dict:
    try:
        action_id = await asyncio.to_thread(recorder.resume)
    except recorder.RecorderError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"action_id": action_id, **privacy_card()}


class RuleIn(Strict):
    kind: str
    value: str
    note: str = ""


@router.post("/time/privacy")
async def add_rule(body: RuleIn) -> dict:
    try:
        action_id = await privacy.add(body.kind, body.value, body.note)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"action_id": action_id, **privacy_card()}


@router.delete("/time/privacy/{rule_id}")
async def remove_rule(rule_id: int) -> dict:
    try:
        action_id = await privacy.remove(rule_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"action_id": action_id, **privacy_card()}
