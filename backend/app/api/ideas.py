"""B6's ideas page (W6) and the door the Super+I popup knocks on (POST /api/ideas)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.core.db import session
from app.features.ideas import store
from app.features.ideas.tables import SOURCES, Idea

router = APIRouter(prefix="/api")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def idea_row(i: Idea, group_name: str = "") -> dict:
    return {"id": i.id, "text": i.text, "source": i.source, "source_name": SOURCES.get(i.source, i.source),
            "tags": i.tags, "tagged": i.tagged, "group_id": i.group_id, "group": group_name, "at": _iso(i.created_at)}


@router.get("/ideas")
def ideas_page() -> dict:
    with session() as s:
        recent = s.scalars(select(Idea).order_by(Idea.created_at.desc()).limit(30)).all()
        total = s.scalar(select(func.count()).select_from(Idea)) or 0
        ungrouped = s.scalar(select(func.count()).select_from(Idea).where(Idea.group_id.is_(None))) or 0
        return {"recent": [idea_row(i) for i in recent], "total": total, "ungrouped": ungrouped}


class NewIdea(Strict):
    text: str
    tags: list[str] | None = None  # the ones you kept (final); None: the next round tags it
    source: str = "web"  # web · key (the popup)


@router.post("/ideas")
def add_idea(body: NewIdea) -> dict:
    if body.source not in ("web", "key"):
        raise HTTPException(422, "source ต้องเป็น web หรือ key")
    try:
        return store.add(body.text, source=body.source, tags=body.tags)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/ideas/suggest")
def suggest(text: str = "") -> dict:
    """The popup and the page ask as you type: the tags the rules see, and the group they lead to."""
    tags = store.suggest(text) if text.strip() else []
    return {"tags": tags, "group": store.group_preview(tags)}


class TagsIn(Strict):
    tags: list[str]


@router.put("/ideas/{idea_id}/tags")
def set_tags(idea_id: int, body: TagsIn) -> dict:
    try:
        return store.set_tags(idea_id, body.tags)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.delete("/ideas/{idea_id}")
def remove(idea_id: int) -> dict:
    return {"action_id": store.remove(idea_id)}
