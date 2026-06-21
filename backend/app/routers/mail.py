"""Mail endpoints (M6) — Google Gmail (read-only) + local-LLM extraction.

Feeds the dashboard's Mail page. Three things:
  - GET  /mail/unread      browse unread inbox (free Google API call)
  - GET  /mail/search?q=   search with Gmail query syntax (free Google API call)
  - POST /mail/scan        local-LLM pass that extracts schedule items (Ollama)

The scan is the only endpoint that runs a model, and it runs the *local* one —
no Claude tokens, mail bodies stay on the machine. It returns suggestions only;
nothing is written to the calendar here.
"""

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.services import gmail, local_llm, mail_extract

router = APIRouter(prefix="/mail", tags=["mail"])


@router.get("/unread")
def unread(limit: int = 20):
    """The user's unread inbox mail (newest first)."""
    try:
        return gmail.list_unread(max_results=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/search")
def search(q: str, limit: int = 20):
    """Search mail with Gmail query syntax (e.g. 'from:prof newer_than:30d')."""
    try:
        return gmail.list_messages(q, max_results=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/local-status")
async def local_status():
    """Whether the local model server (Ollama) is reachable, for a UI hint."""
    return {"up": await local_llm.is_up(), "model": settings.ollama_model}


@router.post("/scan")
async def scan(limit: int = 20):
    """Extract schedule items from unread mail using the LOCAL model.

    Suggestions only — the user reviews them; nothing is added to the calendar.
    """
    try:
        return await mail_extract.scan_unread(max_emails=limit)
    except local_llm.OllamaError as e:
        # Local model down / not pulled — a clear, actionable 503 for the UI.
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
