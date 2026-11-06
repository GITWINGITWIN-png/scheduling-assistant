"""B5's web API for the rule book (W8): every rule in one place, a rule typed as a sentence,
and your answers to what the secretary learned.

The page's "กติกาของคุณ" starts with the rules the secretary already follows from your
settings (`system`): their values stay where they're set, the page only shows them and links
there. Then the rules you added and the learned ones you accepted (rows of `rules`).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.core import actions, settings
from app.core.db import session
from app.core.rules import book, learn, parse
from app.core.tables import Rule
from app.features.projects.tables import Project

router = APIRouter(prefix="/api")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def system() -> list[dict]:
    """The rules that live in your settings, as the rule book shows them."""
    from app.features.mail import watch
    from app.features.schedule import sync

    hours = sync.rules_dict()
    return [
        {"key": "schedule", "text": f"วางบล็อกงานระหว่าง {hours['day_start']}–{hours['day_end']}", "used_by": ["planner"],
         "edit": "/settings#rules"},
        {"key": "mail", "text": f"อีเมลที่มีคำว่า {' · '.join(watch.keywords())} แจ้งทันที", "used_by": ["mail"],
         "edit": "/settings#mail"},
        {"key": "jobs", "text": f"งานเบื้องหลังทำเองได้เมื่อโควตาเหลือเกิน {book.line():.0f}% และไม่ใช่งานเสี่ยงสูง",
         "used_by": ["jobs"], "enabled": book.auto(), "line": book.line(), "edit": "line"},
        {"key": "never", "text": "ไม่ส่งข้อความหาคนอื่นแทนฉัน", "used_by": ["all"], "fixed": True,
         "note": "อ่านอีเมลได้อย่างเดียว ส่งไม่ได้ · Discord ส่งถึงคุณคนเดียว · งานเบื้องหลังที่จะส่งข้อความถามคุณก่อนทุกครั้ง"},
    ]


@router.get("/rules")
def rules_page() -> dict:
    waiting = learn.refresh()
    with session() as s:
        rows = [book.view(r) for r in s.scalars(select(Rule).where(Rule.kind != "high_risk").order_by(Rule.id))]
    mine = [r for r in rows if r["kind"] == "yours" or (r["kind"] == "learned" and r["status"] == "active")]
    learned = [r for r in rows if r["kind"] == "learned" and r["status"] != "active"]
    learned.sort(key=lambda r: r["status"] != "pending")  # waiting first, then the ones you turned down
    risks = book.risks()
    sys_rules = system()
    return {"system": sys_rules, "yours": mine, "learned": learned, "risks": risks, "parts": book.PARTS,
            "counts": {"yours": len(sys_rules) + len(mine), "learned": waiting, "risks": len(risks)}}


# ------------------------------------------------------------------ a rule typed as a sentence
def context() -> parse.Context:
    from app.features.mail import watch
    from app.features.schedule import sync

    with session() as s:
        projects = {p.name: p.allow_jobs for p in s.scalars(select(Project).where(Project.hidden.is_(False),
                                                                                  Project.missing.is_(False)))}
    hours = sync.rules_dict()
    return parse.Context(projects, hours["day_start"], hours["day_end"], tuple(watch.keywords()))


class SentenceIn(Strict):
    text: str


@router.post("/rules/parse")
async def parse_sentence(body: SentenceIn) -> dict:
    """What the sentence would become (nothing is saved yet)."""
    p, tokens = await parse.parse(body.text, context())
    return {**p.__dict__, "ok": p.ok, "tokens": tokens}


class RuleIn(Strict):
    kind: str
    text: str
    used_by: list[str] = []
    effect: dict | None = None
    change: dict | None = None


@router.post("/rules")
def add_rule(body: RuleIn) -> dict:
    """ใช้กติกานี้: save what the page shows, checked again the same way as the model's answer."""
    raw = {**(body.effect or {}), **(body.change or {}), "type": body.kind, "text": body.text, "used_by": body.used_by}
    p = parse.proposal(body.text, raw, context())
    if not p.ok:
        raise HTTPException(400, p.why)
    if p.kind == "schedule_hours":
        from app.features.schedule import sync
        action_id = _setting(sync.RULES_KEY, {**(settings.get(sync.RULES_KEY, {}) or {}), **p.change}, p.text)
        return {"action_id": action_id, "why": p.why}
    if p.kind == "mail_keywords":
        from app.features.mail import watch
        action_id = _setting(watch.KEYWORDS_KEY, watch.keywords() + p.change["add"], p.text)
        return {"action_id": action_id, "why": p.why}
    try:
        rule_id, action_id = book.add(p.text, p.used_by, effect=p.effect, kind="high_risk" if p.kind == "high_risk" else "yours")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"rule_id": rule_id, "action_id": action_id, "why": p.why}


def _setting(key: str, value, text: str) -> int:
    """A rule that is really one of your settings: change the setting (recorded, undoable)."""
    old = settings.get(key)
    settings.put(key, value)
    return actions.record("rule.setting", "ตั้งกติกาจากประโยค", text, source_label=book.WEB[0],
                          undo={"key": key, "old": old})


async def _undo_setting(undo: dict) -> None:
    settings.put(undo["key"], undo["old"])


actions.register_undo("rule.setting", _undo_setting)


# ------------------------------------------------------------------ editing
class RuleEdit(Strict):
    text: str | None = None
    used_by: list[str] | None = None
    enabled: bool | None = None


@router.patch("/rules/{rule_id}")
def edit_rule(rule_id: int, body: RuleEdit) -> dict:
    try:
        return book.edit(rule_id, text=body.text, used_by=body.used_by, enabled=body.enabled)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int) -> dict:
    try:
        return {"action_id": book.delete(rule_id)}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class LearnedIn(Strict):
    accept: bool


@router.post("/rules/{rule_id}/answer")
def answer_learned(rule_id: int, body: LearnedIn) -> dict:
    try:
        return book.answer_learned(rule_id, body.accept)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class JobsRuleIn(Strict):
    auto: bool | None = None
    line: float | None = None


@router.put("/rules/jobs")
def set_jobs_rule(body: JobsRuleIn) -> dict:
    try:
        action_id = book.set_jobs(auto_on=body.auto, line_pct=body.line)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"auto": book.auto(), "line": book.line(), "action_id": action_id}
