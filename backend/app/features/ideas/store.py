"""The ideas store (4.2): one function adds an idea from any door. Also here: the tags the rules
suggest, the group an idea would join, and the outbox the popup writes when the secretary isn't
running.

Tags without a model (the user's choice at the B6 plan, until OmniRoute is connected):
1. the #tags you type: "#backtest across markets" -> backtest;
2. the projects it names, as registered on the projects page: "feed research-lab" -> research-lab;
3. the tags you already use that appear in it: once "sound" is a tag, "...is the sound when the computer turns on" gets it.

Thai is written without spaces between words, so (2) and (3) look for the word anywhere in the
text. A Latin word must stand on its own, so "art" isn't found inside "start". Case, "-", "_" and
spaces don't matter: "My_Secretary", "my-secretary" and "my secretary" are the same project.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select

from app.core import actions
from app.core.config import get_config
from app.core.db import now, session
from app.features.ideas.tables import SOURCES, Idea, IdeaGroup

log = logging.getLogger(__name__)

MAX_TEXT = 4000
MAX_TAGS = 5
MIN_KNOWN = 3  # a tag you use must be at least this long before the rules look for it in new ideas

THAI = "฀-๿"  # Python's \w misses Thai vowel and tone marks (they are "marks", not letters)
HASHTAG = re.compile(rf"(?<![\w{THAI}/#&])#([\w{THAI}][\w{THAI}\-.]*)")  # not page#part, C#, /#/route


def clean(tag: str) -> str:
    """How a tag is kept: no "#", lower case, spaces as "-", at most 40 characters."""
    t = re.sub(r"\s+", "-", tag.strip().lstrip("#").strip(" .-_").lower())
    return t[:40].strip(".-")


def hashtags(text: str) -> list[str]:
    return _unique(clean(m) for m in HASHTAG.findall(text))


def _unique(tags) -> list[str]:
    out: list[str] = []
    for t in tags:
        if t and t not in out:
            out.append(t)
    return out


def _norm(s: str) -> str:
    return re.sub(r"[\s_\-]+", " ", s.lower()).strip()


def _found(word: str, text_norm: str) -> bool:
    """Is `word` in the (normalised) text? Latin edges need a boundary, Thai edges don't."""
    w = _norm(word)
    if not w:
        return False
    left = r"(?<![a-z0-9])" if re.match(r"[a-z0-9]", w) else ""
    right = r"(?![a-z0-9])" if re.search(r"[a-z0-9]$", w) else ""
    return re.search(left + re.escape(w) + right, text_norm) is not None


# ------------------------------------------------------------------ what the rules know
def project_tags() -> dict[str, str]:
    """{tag: project name} for every project on the projects page (not hidden, still there)."""
    from app.features.projects.tables import Project

    with session() as s:
        names = s.scalars(select(Project.name).where(Project.hidden.is_(False), Project.missing.is_(False))).all()
    return {clean(n): n for n in names if clean(n)}


def vocabulary() -> list[str]:
    """The tags you already use, the most used first."""
    count: Counter[str] = Counter()
    with session() as s:
        for tags in s.scalars(select(Idea.tags)):
            count.update(tags or [])
        count.update({t: 0 for t in s.scalars(select(IdeaGroup.tag))})
    return [t for t, _ in count.most_common()]


def suggest(text: str, *, projects: dict[str, str] | None = None, known: list[str] | None = None) -> list[str]:
    """The tags the rules would give this text, in order: #tags, projects, tags you use."""
    projects = project_tags() if projects is None else projects
    known = vocabulary() if known is None else known
    norm = _norm(text)
    found = hashtags(text)
    found += [tag for tag, name in projects.items() if _found(name, norm)]
    found += [tag for tag in known if len(tag) >= MIN_KNOWN and _found(tag, norm)]
    return _unique(found)[:MAX_TAGS]


def primary(tags: list[str], projects: dict[str, str] | None = None, sizes: dict[str, int] | None = None) -> str | None:
    """The tag that decides the group. Not a project, so "#backtest #finance" is the backtest group
    (about finance) rather than one big finance group. Among the others, the one whose group is
    biggest already (`sizes`: {tag: ideas}), so related ideas grow one group instead of starting
    many small ones that never grow enough; with no group yet, the first."""
    projects = project_tags() if projects is None else projects
    own = [t for t in tags if t not in projects] or tags[:1]
    if not own:
        return None
    sizes = sizes or {}
    return max(own, key=lambda t: (sizes.get(t, 0), -own.index(t)))


def group_sizes() -> dict[str, int]:
    """{tag: how many ideas its group has}."""
    with session() as s:
        rows = s.execute(select(IdeaGroup.tag, func.count(Idea.id)).join(Idea, Idea.group_id == IdeaGroup.id)
                         .group_by(IdeaGroup.tag)).all()
    return {tag: n for tag, n in rows}


def group_preview(tags: list[str], *, joining: bool = True) -> dict | None:
    """The group these tags lead to: {"name", "size", "new"} (size counts this idea when joining)."""
    tag = primary(tags, sizes=group_sizes())
    if tag is None:
        return None
    with session() as s:
        g = s.scalar(select(IdeaGroup).where(IdeaGroup.tag == tag))
        size = s.scalar(select(func.count()).select_from(Idea).where(Idea.group_id == g.id)) if g else 0
        return {"name": g.name if g else tag, "size": size + joining, "new": g is None, "tag": tag}


# ------------------------------------------------------------------ adding, changing, removing
def add(text: str, *, source: str, source_ref: str = "", tags: list[str] | None = None,
        at: datetime | None = None) -> dict:
    """Keep one idea. tags=None (a #Ideas message: there was nothing to choose from): the #tags
    you typed, and the next round adds what the rules find after them. A list (the popup, the
    page: you saw the suggestions) is final: what you kept, plus what you typed.
    -> {"id", "tags", "group"} (the group it will join at the next round)."""
    if source not in SOURCES:
        raise ValueError(f"ไม่รู้จักทางเข้า {source}")
    text = text.strip()
    if not text:
        raise ValueError("ไอเดียว่างอยู่")
    if len(text) > MAX_TEXT:
        text = text[: MAX_TEXT - 1] + "…"
    typed = hashtags(text)
    if tags is None:
        final, tagged = typed, ""
    else:
        final, tagged = _unique([*(clean(t) for t in tags), *typed])[:MAX_TAGS], "you"
    with session() as s:
        idea = Idea(text=text, source=source, source_ref=source_ref, tags=final, tagged=tagged, created_at=at or now())
        s.add(idea)
        s.flush()
        idea_id = idea.id
    log.info("idea %s from %s, tags %s", idea_id, source, final)
    return {"id": idea_id, "tags": final, "group": group_preview(final)}


def by_ref(source_ref: str) -> int | None:
    with session() as s:
        return s.scalar(select(Idea.id).where(Idea.source == "discord", Idea.source_ref == source_ref))


def change_text(idea_id: int, text: str) -> None:
    """You edited the message. Tags that came from its #tags follow the new text."""
    text = text.strip()
    if not text:
        return
    with session() as s:
        idea = s.get(Idea, idea_id)
        if idea is None:
            return
        old_typed = hashtags(idea.text)
        idea.text = text[:MAX_TEXT]
        if idea.tagged != "you":  # not chosen by you: the next round tags and places it again
            new = hashtags(text)
            if new != old_typed:
                idea.tags, idea.tagged = new, ""
                idea.group_id, idea.grouped_at = None, None


def set_tags(idea_id: int, tags: list[str], *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> dict:
    """You changed an idea's tags on the page: they're yours now, and it moves to its group at once
    (you're looking at the page; the round would only do the same later)."""
    from app.features.ideas import groups  # here: groups imports this module

    final = _unique(clean(t) for t in tags)[:MAX_TAGS]
    with session() as s:
        idea = s.get(Idea, idea_id)
        if idea is None:
            raise ValueError("ไม่พบไอเดียนี้")
        if final != idea.tags:
            idea.group_id, idea.grouped_at = None, None
        idea.tags, idea.tagged = final, "you"
    groups.place([idea_id])
    actions.record("idea.tags", "แก้แท็กไอเดีย", " ".join(f"#{t}" for t in final) or "ไม่มีแท็ก",
                   source_label=via[0], source_url=via[1])
    return {"id": idea_id, "tags": final, "group": group_preview(final, joining=False)}


def remove(idea_id: int, *, via: tuple[str, str] = ("หน้าเว็บ", ""), log_it: bool = True) -> int | None:
    """-> the action id (undo brings the idea back), or None."""
    with session() as s:
        idea = s.get(Idea, idea_id)
        if idea is None:
            return None
        saved = {"text": idea.text, "source": idea.source, "source_ref": idea.source_ref, "tags": idea.tags,
                 "tagged": idea.tagged, "created_at": idea.created_at.isoformat()}
        s.delete(idea)
    if not log_it:
        return None
    return actions.record("idea.remove", "ลบไอเดีย", saved["text"][:120], source_label=via[0], source_url=via[1], undo=saved)


async def _undo_remove(undo: dict) -> None:
    with session() as s:
        s.add(Idea(text=undo["text"], source=undo["source"], source_ref=undo["source_ref"], tags=undo["tags"],
                   tagged=undo["tagged"], created_at=datetime.fromisoformat(undo["created_at"])))


actions.register_undo("idea.remove", _undo_remove)


def jot(text: str, *, via: tuple[str, str]) -> dict:
    """An idea from an order in the chat (B9, "จดไอเดีย …"). Kept like a #ไอเดีย message: the
    #tags you typed, and the next round adds what the rules find. Unlike the other ways in, it
    is recorded, so the answer's ย้อนกลับ removes it. -> add()'s answer and "action_id"."""
    out = add(text, source="chat")
    out["action_id"] = actions.record("idea.add", "จดไอเดีย", text.strip()[:120], source_label=via[0], source_url=via[1],
                                      undo={"idea_id": out["id"]})
    return out


async def _undo_add(undo: dict) -> None:
    with session() as s:
        if (idea := s.get(Idea, undo["idea_id"])) is None:
            raise actions.UndoError("ไอเดียนี้ถูกลบไปแล้ว")
        s.delete(idea)


actions.register_undo("idea.add", _undo_add)


# ------------------------------------------------------------------ the popup's outbox
def outbox() -> Path:
    """Where the popup keeps ideas while the secretary is down (one JSON object per line)."""
    return get_config().data_dir / "ideas-outbox.jsonl"


def import_outbox() -> int:
    """Take in what the popup kept (at startup and every ideas round). -> how many.

    The file is renamed before it's read, so an idea the popup appends meanwhile lands in a new
    file and waits for the next time instead of being lost."""
    box = outbox()
    work = box.with_name(box.name + ".importing")
    if box.exists() and not work.exists():
        box.rename(work)
    if not work.exists():
        return 0
    n = 0
    bad: list[str] = []
    for line in work.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            at = datetime.fromisoformat(item["at"]) if item.get("at") else None
            add(str(item["text"]), source="key", tags=item.get("tags"), at=at if at and at.tzinfo else None)
            n += 1
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("an idea in the outbox couldn't be read (%s): %s", exc, line[:200])
            bad.append(line)
    if bad:
        with box.with_name(box.name + ".bad").open("a", encoding="utf-8") as f:
            f.write("\n".join(bad) + "\n")
    work.unlink()
    return n
