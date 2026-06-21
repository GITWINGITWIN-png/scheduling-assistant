"""Mail endpoints (M6) — Google Gmail (read-only) + local-LLM extraction + pins.

Feeds the dashboard's Mail page:
  - GET  /mail/unread        browse unread inbox (free Google API call)
  - GET  /mail/today         browse today's inbox, read+unread (free)
  - GET  /mail/search?q=     search with Gmail query syntax (free)
  - POST /mail/scan?scope=   local-LLM extraction, unread|today (Ollama, no tokens)
  - GET  /mail/scan/today    today's cached daily scan (pre-warmed each morning)
  - GET/POST/DELETE /mail/pins   pin an email to the Projects page (+ calendar)

The scan endpoints are the only ones that run a model, and it's the *local* one —
no Claude tokens, mail bodies stay on the machine, and scans never touch the
calendar. The single place email leads to a calendar write is an explicit pin.
"""

import functools

import anyio
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services import cache, gmail, local_llm, mail_extract, mail_store, pins

router = APIRouter(prefix="/mail", tags=["mail"])

# Mail moves faster than coursework; serve the snapshot for 10 min, then refresh.
_MAIL_TTL = 600


class PinIn(BaseModel):
    email_id: str
    subject: str = ""
    sender: str = ""
    link: str = ""
    date: str | None = None  # extracted ISO date, if any → drives the calendar event
    note: str = ""


# --- Browse / search (free Google API) ---


@router.get("/unread")
def unread(background_tasks: BackgroundTasks, limit: int = 20, refresh: bool = False):
    """The user's unread inbox mail (newest first), from the DB snapshot.

    Stale-while-revalidate: served instantly, refreshed in the background when
    older than the TTL; `refresh=true` forces a fresh Gmail fetch.
    """
    try:
        return cache.serve(
            "mail:unread",
            lambda: gmail.list_unread(max_results=limit),
            ttl=_MAIL_TTL,
            refresh=refresh,
            add_task=background_tasks.add_task,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/today")
def today(background_tasks: BackgroundTasks, limit: int = 40, refresh: bool = False):
    """Today's inbox mail, read or unread (newest first), from the DB snapshot."""
    try:
        return cache.serve(
            "mail:today",
            lambda: gmail.list_today(max_results=limit),
            ttl=_MAIL_TTL,
            refresh=refresh,
            add_task=background_tasks.add_task,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/search")
def search(q: str, limit: int = 20):
    """Search mail with Gmail query syntax (e.g. 'from:prof newer_than:30d').

    Not cached — searches are ad-hoc and varied; they hit Gmail live.
    """
    try:
        return gmail.list_messages(q, max_results=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# --- Local-LLM extraction (no Claude tokens, on-device) ---


@router.get("/local-status")
async def local_status():
    """Whether the local model server (Ollama) is reachable, for a UI hint."""
    return {"up": await local_llm.is_up(), "model": settings.ollama_model}


@router.post("/scan")
async def scan(scope: str = "unread", limit: int = 40):
    """Extract schedule items with the LOCAL model. scope = 'unread' | 'today'.

    Schedule-worthy items (dated, or deadline/meeting/event) are AUTO-PINNED to the
    Projects page, and dated ones are added to the calendar — the user reviews and
    unpins what they don't want. Each returned item carries a `pinned` flag.
    """
    try:
        result = await mail_extract.scan(scope=scope, max_emails=limit)
    except local_llm.OllamaError as e:
        # Local model down / not pulled — a clear, actionable 503 for the UI.
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Auto-pin in a worker thread (pins do blocking calendar I/O); offloading keeps
    # the event loop free while still completing before we respond, so the UI gets
    # accurate pinned state immediately.
    pinned = await anyio.to_thread.run_sync(pins.auto_pin_items, result["items"])
    for it in result["items"]:
        it["pinned"] = it["email_id"] in pinned
    result["auto_pinned"] = len(pinned)
    return result


@router.get("/scan/today")
async def scan_today(force: bool = False):
    """Today's cached daily scan (pre-warmed by the scheduler; lazy otherwise)."""
    try:
        return await mail_store.get_or_create_today(force=force)
    except local_llm.OllamaError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# --- Pins (promote an email to the Projects page; dated pins → calendar) ---


@router.get("/pins")
def list_pins():
    """All pinned emails (shown in the Projects page's 'From email' section)."""
    return pins.list_pins()


@router.post("/pins")
async def add_pin(body: PinIn):
    """Pin an email. If it has a date, also create a calendar event for it.

    When no date is supplied (e.g. pinning an old email straight from the inbox,
    never scanned), we do a deeper, higher-effort re-read of just that email with
    the local model to recover its date + a readable summary first.
    """
    date, note = body.date, body.note
    if not date:
        # Deep re-read this one email to enrich an otherwise bare pin.
        try:
            msg = await anyio.to_thread.run_sync(gmail.get_message, body.email_id)
            info = await mail_extract.deep_extract(msg)
            date = info.get("date")
            note = note or info.get("note", "")
        except local_llm.OllamaError:
            pass  # local model offline — pin without enrichment rather than fail
        except Exception:
            pass  # couldn't fetch/parse — still let the pin go through

    try:
        return await anyio.to_thread.run_sync(
            functools.partial(
                pins.pin,
                email_id=body.email_id,
                subject=body.subject,
                sender=body.sender,
                link=body.link,
                date=date,
                note=note,
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/pins/{email_id}")
def remove_pin(email_id: str):
    """Un-pin an email, removing any calendar event we created for it."""
    pins.unpin(email_id)
    return {"unpinned": email_id}
