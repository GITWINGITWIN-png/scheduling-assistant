"""A rule typed as a sentence ("Don't schedule work on Sundays"): what it becomes, and saving it.

The rule book page (W8) shows what the sentence would become and saves it when you press
Use this rule; an order in the chat (B9) does both at once. Either way the result is the same:
- a rule in the book (core/rules/book.py),
- or, for the planner's hours and the mail watch's keywords, a change to that setting.
Both are recorded in What the secretary did and can be undone.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core import actions, settings
from app.core.db import session
from app.core.rules import book, parse
from app.features.projects.tables import Project


def context() -> parse.Context:
    from app.features.mail import watch
    from app.features.schedule import sync

    with session() as s:
        projects = {p.name: p.allow_jobs for p in s.scalars(select(Project).where(Project.hidden.is_(False),
                                                                                  Project.missing.is_(False)))}
    hours = sync.rules_dict()
    return parse.Context(projects, hours["day_start"], hours["day_end"], tuple(watch.keywords()))


def save(p: parse.Proposal, *, via: tuple[str, str] = book.WEB) -> dict:
    """Keep a checked proposal. -> {"action_id", "why"} (+ "rule_id" for a rule in the book).
    Raises ValueError when it can't be kept."""
    if not p.ok:
        raise ValueError(p.why)
    if p.kind == "schedule_hours":
        from app.features.schedule import sync
        action_id = _setting(sync.RULES_KEY, {**(settings.get(sync.RULES_KEY, {}) or {}), **p.change}, p.text, via)
        return {"action_id": action_id, "why": p.why}
    if p.kind == "mail_keywords":
        from app.features.mail import watch
        action_id = _setting(watch.KEYWORDS_KEY, watch.keywords() + p.change["add"], p.text, via)
        return {"action_id": action_id, "why": p.why}
    rule_id, action_id = book.add(p.text, p.used_by, effect=p.effect, kind="high_risk" if p.kind == "high_risk" else "yours",
                                  via=via)
    return {"rule_id": rule_id, "action_id": action_id, "why": p.why}


async def from_sentence(text: str, *, via: tuple[str, str] = book.WEB) -> tuple[dict, int]:
    """Read the sentence (Sonnet, the "rule" task) and keep what it becomes. -> (save()'s answer
    with the rule's text, tokens). Raises ValueError when the sentence can't be a rule."""
    p, tokens = await parse.parse(text, context())
    return {**save(p, via=via), "text": p.text}, tokens


def _setting(key: str, value, text: str, via: tuple[str, str]) -> int:
    """A rule that is really one of your settings: change the setting (recorded, undoable)."""
    old = settings.get(key)
    settings.put(key, value)
    return actions.record("rule.setting", "ตั้งกติกาจากประโยค", text, source_label=via[0], source_url=via[1],
                          undo={"key": key, "old": old})


async def _undo_setting(undo: dict) -> None:
    settings.put(undo["key"], undo["old"])


actions.register_undo("rule.setting", _undo_setting)
