"""Chat endpoint — talk to the secretary over HTTP (M1).

This is what the React dashboard (M2) will call. For now you can hit it from
/docs or the terminal REPL in scripts/chat.py.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.secretary import ask

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatIn(BaseModel):
    message: str


@router.post("")
async def chat(body: ChatIn):
    try:
        reply = await ask(body.message)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
