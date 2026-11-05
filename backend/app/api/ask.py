"""The web page's ask box (the top bar on every page) and plan decisions.

POST /api/ask streams the answer as NDJSON, one JSON object per line, so the page
can show text as it arrives:

    {"type": "note", "text": "เป็นการวางแผน · ส่งต่อให้ Opus"}   only for plans
    {"type": "text", "text": "..."}                               as many as come
    {"type": "done", "answer": {...}}                             model, effort, sources, decision id
    {"type": "error", "message": "..."}                           instead of done, if Claude failed
"""

import asyncio
import json
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core import llm
from app.features import ask

router = APIRouter(prefix="/api", tags=["ask"])


class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    deep: bool = False  # True = "ให้ Opus คิดต่อ"


@router.post("/ask")
async def ask_stream(body: AskIn) -> StreamingResponse:
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def on_text(chunk: str) -> None:
        await queue.put({"type": "text", "text": chunk})

    async def on_note(note: str) -> None:
        await queue.put({"type": "note", "text": note})

    async def work() -> None:
        try:
            if body.deep:
                a = await ask.deepen(body.text, on_text=on_text)
            else:
                a = await ask.ask(body.text, on_text=on_text, on_note=on_note)
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
def decide(decision_id: int, body: DecideIn) -> dict:
    try:
        d = ask.decide(decision_id, body.action, body.note)
    except ask.DecisionError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"id": d.id, "status": d.status}
