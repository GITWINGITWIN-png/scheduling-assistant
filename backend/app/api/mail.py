"""B2's web API: appointment requests (and, from step 9, the people and email page W2)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.features.mail import extract

router = APIRouter(prefix="/api")


class AppointmentIn(BaseModel):
    accept: bool


@router.post("/appointments/{decision_id}")
async def answer_appointment(decision_id: int, body: AppointmentIn) -> dict:
    """รับนัด (into the calendar, undoable) or ไม่ไป, for an appointment waiting in the bell / #อนุมัติ."""
    try:
        d, action_id = await extract.decide(decision_id, body.accept, via=("หน้าเว็บ", ""))
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {"id": d.id, "status": d.status, "action_id": action_id}
