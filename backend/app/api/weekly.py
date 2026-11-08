"""B7's weekly review on the web: answer a topic from the bell or the today page, accept a whole
review, and "ส่งตอนนี้" (make this week's review now, without waiting for Sunday 19:00)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.features.weekly import review

router = APIRouter(prefix="/api")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnswerIn(Strict):
    act: str  # one of the topic's buttons: approve · reject · both · book


@router.post("/weekly/decisions/{decision_id}")
async def answer(decision_id: int, body: AnswerIn) -> dict:
    try:
        return {"text": await review.answer(decision_id, body.act, via=("หน้าเว็บ", ""))}
    except review.AnswerError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/weekly/{brief_id}/all")
async def accept_all(brief_id: int) -> dict:
    return {"done": await review.accept_all(brief_id, via=("หน้าเว็บ", ""))}


@router.post("/weekly/run")
async def run_now() -> dict:
    """ส่งตอนนี้: this week's review now (it replaces one already made this week; its waiting topics expire)."""
    title = await review.send(again=True)
    return {"title": title or ""}
