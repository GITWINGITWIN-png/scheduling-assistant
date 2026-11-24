"""B6's ideas page (W6) and the door the Super+I popup knocks on (POST /api/ideas)."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.core import actions, clock
from app.core.db import now, session
from app.features import decisions
from app.features.ideas import groups, store
from app.features.ideas.tables import GROUP_STATUSES, SOURCES, Idea, IdeaGroup

router = APIRouter(prefix="/api")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def idea_row(i: Idea, group_name: str = "") -> dict:
    return {"id": i.id, "text": i.text, "source": i.source, "source_name": SOURCES.get(i.source, i.source),
            "tags": i.tags, "tagged": i.tagged, "group_id": i.group_id, "group": group_name, "at": _iso(i.created_at)}


def group_row(s, g: IdeaGroup, at) -> dict:
    """A group card (W6 ②): its size, how it grew this week, its tags, what it's about."""
    ideas = s.scalars(select(Idea).where(Idea.group_id == g.id).order_by(Idea.created_at.desc())).all()
    week = sum(1 for i in ideas if i.created_at >= at - timedelta(days=7))
    last = ideas[0].created_at if ideas else g.created_at
    tags: dict[str, int] = {}
    for i in ideas:
        for tag in i.tags or []:
            tags[tag] = tags.get(tag, 0) + 1
    if g.created_at >= at - timedelta(days=7) and week == len(ideas):
        grew = "ใหม่"
    elif week:
        grew = f"+{week} สัปดาห์นี้"
    else:
        grew = f"นิ่ง {max(1, (at - last).days // 7)} สัปดาห์" if (at - last).days >= 7 else "ไม่มีใหม่สัปดาห์นี้"
    return {"id": g.id, "name": g.name, "tag": g.tag, "status": g.status, "status_name": GROUP_STATUSES.get(g.status, g.status),
            "size": len(ideas), "week": week, "grew": grew, "last": _iso(last), "about": groups.about_project(s, g.id) or "",
            "tags": sorted(tags, key=lambda x: (-tags[x], x != g.tag))[:3], "decision_id": g.decision_id,
            "waiting": g.status == "asked", "project_id": g.project_id, "task_id": g.task_id,
            "ideas": [{"id": i.id, "text": i.text, "source": i.source, "at": _iso(i.created_at)} for i in ideas[:20]]}


@router.get("/ideas")
def ideas_page() -> dict:
    at = now()
    with session() as s:
        names = {g.id: g.name for g in s.scalars(select(IdeaGroup))}
        recent = s.scalars(select(Idea).order_by(Idea.created_at.desc()).limit(30)).all()
        total = s.scalar(select(func.count()).select_from(Idea)) or 0
        ungrouped = s.scalar(select(func.count()).select_from(Idea).where(Idea.group_id.is_(None))) or 0
        rows = [group_row(s, g, at) for g in s.scalars(select(IdeaGroup).where(IdeaGroup.status != "project")
                                                         .order_by(IdeaGroup.updated_at.desc()))]
    rows = [r for r in rows if r["size"]]
    # the ones waiting for you first, then the biggest, then the newest
    rows.sort(key=lambda r: (not r["waiting"], r["status"] in ("task", "later"), -r["size"], r["last"] or ""), reverse=False)
    return {"recent": [idea_row(i, names.get(i.group_id, "")) for i in recent], "total": total, "ungrouped": ungrouped,
            "groups": rows, "grown": groups.GROWN, "round_on": clock.enabled("ideas")}


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


# ------------------------------------------------------------------ a grown group (P11)
class ProjectIn(Strict):
    name: str


async def _settled(group_id: int) -> None:
    with session() as s:
        d = s.get(IdeaGroup, group_id).decision_id
    if d:
        await decisions.settle_card(d)  # its #ideas card says so too


@router.get("/ideas/groups/{group_id}/folder")
def folder(group_id: int) -> dict:
    return {"name": groups.suggested_folder(group_id)}


@router.post("/ideas/groups/{group_id}/project")
async def open_project(group_id: int, body: ProjectIn) -> dict:
    try:
        project_id, action_id = groups.open_project(group_id, body.name)
    except groups.AnswerError as exc:
        raise HTTPException(422, str(exc)) from exc
    await _settled(group_id)
    return {"project_id": project_id, "action_id": action_id}


@router.post("/ideas/groups/{group_id}/task")
async def make_task(group_id: int) -> dict:
    try:
        task_id, action_id = groups.make_task(group_id)
    except groups.AnswerError as exc:
        raise HTTPException(422, str(exc)) from exc
    await _settled(group_id)
    return {"task_id": task_id, "action_id": action_id}


@router.post("/ideas/groups/{group_id}/later")
async def later(group_id: int) -> dict:
    try:
        action_id = groups.later(group_id)
    except groups.AnswerError as exc:
        raise HTTPException(422, str(exc)) from exc
    await _settled(group_id)
    return {"action_id": action_id}


class NameIn(Strict):
    name: str


@router.put("/ideas/groups/{group_id}/name")
def rename(group_id: int, body: NameIn) -> dict:
    try:
        return {"action_id": groups.rename(group_id, body.name)}
    except groups.AnswerError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/ideas/round")
async def round_now() -> dict:
    """Group now: the same work as the 12:00 and 00:00 round, now (also when the round is off)."""
    line = await groups.run()
    if line:
        actions.record("round.ideas", "จัดกลุ่มไอเดีย (กดจัดกลุ่มเลย)", line, source_label="หน้าเว็บ")
    return {"line": line or "ไม่มีไอเดียใหม่ให้จัด"}
