"""B6's time page (W7): what you did on this computer, from ActivityWatch through the privacy filter,
and the privacy card (W7 ④ ⑤): the recording switch, หยุดบันทึก, and the blocklist."""

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.features.time import privacy, pull, recorder
from app.features.time.tables import KINDS

router = APIRouter(prefix="/api")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def privacy_card() -> dict:
    return {"recorder": recorder.status(), "rules": privacy.listed(), "kinds": KINDS, "last_read": pull.last_read()}


@router.get("/time")
def time_page() -> dict:
    return {"privacy": privacy_card()}


class SwitchIn(Strict):
    on: bool


@router.put("/time/recording")
async def switch(body: SwitchIn) -> dict:
    try:
        action_id = await asyncio.to_thread(recorder.set_on, body.on)
    except recorder.RecorderError as exc:
        raise HTTPException(422, str(exc)) from exc
    if body.on:  # read at once, so the page shows something without waiting a quarter of an hour
        await pull.run()
    return {"action_id": action_id, **privacy_card()}


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
