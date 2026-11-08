"""The web page's ask box (the top bar on every page) and plan decisions.

POST /api/ask streams the answer as NDJSON, one JSON object per line, so the page
can show text as it arrives:

    {"type": "note", "text": "เป็นการวางแผน · ส่งต่อให้ Opus"}   only for plans
    {"type": "text", "text": "..."}                               as many as come
    {"type": "done", "answer": {...}}                             model, effort, sources, decision id
    {"type": "error", "message": "..."}                           instead of done, if Claude failed

The page sends the conversation it shows along with the question (history), the way the Discord
chat reads the channel: a follow-up like "ทำต่อ" or "แล้วเมื่อวานล่ะ" needs what came before it.
"""

import asyncio
import json
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core import llm
from app.features import ask, ask_orders, decisions

router = APIRouter(prefix="/api", tags=["ask"])


class Said(BaseModel):
    """One earlier message in the ask box: yours (คุณ) or the secretary's answer (เลขา)."""
    who: Literal["คุณ", "เลขา"]
    text: str = Field(max_length=8000)


class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    deep: bool = False  # True = "ให้ Opus คิดต่อ"
    history: list[Said] = Field(default_factory=list, max_length=8)  # oldest first; ask._prompt trims it


@router.post("/ask")
async def ask_stream(body: AskIn) -> StreamingResponse:
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def on_text(chunk: str) -> None:
        await queue.put({"type": "text", "text": chunk})

    async def on_note(note: str) -> None:
        await queue.put({"type": "note", "text": note})

    history = [(h.who, h.text) for h in body.history]

    async def work() -> None:
        try:
            if body.deep:
                a = await ask.deepen(body.text, history, on_text=on_text)
            else:
                a = await ask.ask(body.text, history, on_text=on_text, on_note=on_note)
            await queue.put({"type": "done", "answer": {**asdict(a), "footer": a.footer}})
        except llm.LLMError as exc:
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)

    task = asyncio.create_task(work())

    async def lines():
        try:
            while (item := await queue.get()) is not None:
                yield json.dumps(item, ensure_ascii=False) + "\n"
        finally:
            await task  # the answer is saved even if the page is closed midway

    return StreamingResponse(lines(), media_type="application/x-ndjson")


class DecideIn(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    note: str = ""


@router.post("/decisions/{decision_id}")
async def decide(decision_id: int, body: DecideIn) -> dict:
    try:
        d, action_id = ask.decide(decision_id, body.action, body.note)
    except ask.DecisionError as exc:
        raise HTTPException(409, str(exc)) from exc
    await decisions.settle_card(decision_id)  # a card for it in #อนุมัติ (if any) says so too
    return {"id": d.id, "status": d.status, "action_id": action_id}


class ReviseIn(BaseModel):
    change: str = Field(min_length=1, max_length=1000)


@router.post("/decisions/{decision_id}/revise")
async def revise(decision_id: int, body: ReviseIn) -> dict:
    """แก้: Opus rewrites the plan with your change (takes a while; the page shows a spinner)."""
    try:
        a = await ask.revise(decision_id, body.change)
    except ask.DecisionError as exc:
        raise HTTPException(409, str(exc)) from exc
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc)) from exc
    await decisions.settle_card(decision_id)  # the old plan's card in #คุยกับเลขา (if any) says it was changed
    return {**asdict(a), "footer": a.footer}


# ------------------------------------------------------------------ B9: orders
class ConfirmIn(BaseModel):
    yes: bool


@router.post("/orders/{decision_id}")
async def confirm_order(decision_id: int, body: ConfirmIn) -> dict:
    """ทำเลย · ไม่เอา for an order that can't be undone (under an answer, or in the bell).

    409 = answered already (or expired): the page shows what happened instead of the buttons.
    422 = doing it failed: nothing was done, and the buttons stay for another press.
    """
    try:
        said = await ask_orders.confirm(decision_id, body.yes, via=("หน้าเว็บ", ""))
    except ask_orders.ConfirmFailed as exc:
        raise HTTPException(422, str(exc)) from exc
    except ask_orders.ConfirmError as exc:
        raise HTTPException(409, str(exc)) from exc
    await decisions.settle_card(decision_id)  # its buttons in #คุยกับเลขา (if any) say so too
    return {"text": said}


@router.get("/plans/{decision_id}/run")
def plan_run(decision_id: int) -> dict:
    """How carrying out an approved plan is going: {"status": none · running · done · failed, ...}."""
    return ask.run_of(decision_id) or {"status": "none"}
