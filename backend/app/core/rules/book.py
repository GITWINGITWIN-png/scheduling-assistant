"""The rule book (P8, B5, W8): your rules, what the secretary learned from your answers, and the
high-risk work it always asks about first.

The rows of `rules` come in three kinds:

- yours: a rule you added, usually typed as a sentence (parse.py turns it into a rule you check
  before it's saved). Most are notes: the parts that use a model (Ask the Secretary, the background
  planner) read them with every call (`prompt_block`). A few the code follows itself, through
  their `effect`: "Don't accept Saturday appointments" marks Saturday appointment requests (`appointment_note`),
  "Finance work can be done without asking" lets that project's low-risk plans start by themselves (`standing_for`), and B7's schedule rules keep blocks out of hours you keep missing
  (`block_avoid`) or fill your focus hours first (`focus_window`).
- learned: a pattern in your answers (learn.py), used only after you press "Use as a rule".
- high_risk: work that always asks you first, however much quota is left: the 7 kinds agreed
  at the plan (RISKS: fixed, they can't be removed) and any you add. `flags()` spots the 7 in a
  plan's text, a second net under the planner's own flags (B5.6).

The page also shows the rules the secretary already follows from your settings (the
schedule's hours, the mail keywords, the 70% line); their values stay where they are set
(api/rules.py builds that list). Every change here is recorded and can be undone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from app.core import actions, settings
from app.core.db import session
from app.core.tables import Rule
from app.core.timefmt import local

PARTS = {  # who reads a rule ("used by")
    "planner": "ตัววางตาราง",
    "mail": "ตัวอ่านอีเมล",
    "jobs": "ตัวคุมงานเบื้องหลัง",
    "ask": "ถามเลขา",
    "clock": "นาฬิกาเลขา",
    "all": "ทุกส่วน",
}
NOTE_PARTS = ("ask", "jobs")  # the parts with a model: the only ones a plain note can reach

AUTO_KEY = "jobs.auto"  # False: every background plan asks you first, whatever the quota
LINE_KEY = "jobs.line"  # the quota line (% of the week left), agreed at 70
DEFAULT_LINE = 70.0

Via = tuple[str, str]
WEB: Via = ("สมุดกติกา", "")


@dataclass(frozen=True)
class Risk:
    key: str
    text: str  # as the rule book shows it
    hint: str  # what counts, for the planner and the page
    words: tuple[str, ...]  # regexes that spot it in a plan's text (lower-cased)


RISKS: tuple[Risk, ...] = (
    Risk("download", "โหลดของจากภายนอก",
         "ดาวน์โหลดไฟล์ ข้อมูลหรือโมเดล ติดตั้งแพ็กเกจ (pip · uv add · npm) หรือ clone repo อื่น",
         (r"ดาวน์โหลด", r"โหลด(?:ไฟล์|ข้อมูล|โมเดล|แพ็กเกจ|ชุดข้อมูล)", r"ติดตั้ง", r"\binstall", r"\bdownload",
          r"\buv\s+(?:add|pip)\b", r"\bnpm\s+(?:i|add)\b", r"\b(?:yarn|pnpm)\s+add\b", r"\bcurl\b", r"\bwget\b",
          r"\bgit\s+clone\b", r"\bfrom_pretrained\b", r"huggingface")),
    Risk("recheck", "งานที่ตรวจซ้ำไปมา",
         "ต้องตรวจผลแล้วแก้ซ้ำไปมาหลายรอบ เช่น ลองไปเรื่อยๆ จนกว่าจะได้ผลที่ต้องการ",
         (r"ตรวจซ้ำ", r"ซ้ำไปมา", r"ไป\s*ๆ\s*มา\s*ๆ", r"ลองซ้ำ", r"รันซ้ำ", r"ลองไปเรื่อย", r"หลายรอบ",
          r"back and forth", r"\brepeatedly\b", r"\bretry", r"\bre-?run\b", r"trial and error")),
    Risk("loop", "งานที่อาจวนจนเปลืองโทเคน",
         "อาจวนทำซ้ำโดยไม่รู้จบ เช่น ไล่ทุกไฟล์ทั้ง repo · grid search · scrape หลายหน้า",
         (r"วน(?:ลูป|ซ้ำ|ไปเรื่อย|จน)", r"\bloop\b", r"(?:ไล่|แก้|อ่าน|ตรวจ)\s*(?:ทุกไฟล์|ทั้ง\s*repo)", r"\bgrid\s*search", r"hyperparameter",
          r"brute[\s-]*force", r"\bscrap(?:e|ing)\b", r"\bcrawl", r"ไม่จำกัดรอบ", r"\buntil\b")),
    Risk("delete", "ลบหรือเขียนทับไฟล์/ข้อมูล",
         "ลบหรือเขียนทับไฟล์ ข้อมูล ฐานข้อมูล หรือประวัติ git (reset --hard · rm -rf · drop table)",
         (r"ลบ(?:ไฟล์|โฟลเดอร์|ข้อมูล|ฐานข้อมูล|ตาราง|branch|ประวัติ|ทิ้ง|ทั้งหมด)", r"เขียนทับ", r"ล้าง(?:ข้อมูล|ฐานข้อมูล|ไฟล์)",
          r"\brm\s+-\w*[rf]", r"\bdelete\s+(?:the\s+|all\s+)?(?:files?|folders?|director|data|tables?|database|branch)",
          r"\bdrop\s+(?:table|database|column)", r"\btruncate\b", r"\boverwrit", r"reset\s+--hard", r"\bgit\s+clean\b",
          r"--force\b|\bpush\s+-f\b")),
    Risk("push", "push หรือ deploy",
         "push · เปิด PR · deploy · publish หรือ upload ขึ้นที่อื่น",
         (r"\bpush\b", r"\bdeploy", r"\bpublish", r"\brelease\b", r"\bupload", r"อัปโหลด", r"pull request",
          r"\bgh\s+(?:pr|release)\b", r"เปิด\s*pr\b", r"ขึ้น\s*(?:server|เซิร์ฟเวอร์|production|prod)\b",
          r"\b(?:vercel|netlify|heroku|fly\.io|railway)\b")),
    Risk("message", "ส่งข้อความหาคนอื่น",
         "ส่งอีเมล ข้อความ โพสต์ หรือแจ้งเตือนถึงคนอื่น",
         (r"ส่ง(?:ข้อความ|อีเมล|เมล|ไลน์|แชท)", r"โพสต์", r"\bsend\s+(?:an?\s+|the\s+)?(?:e-?mails?|messages?|mail|dm)\b",
          r"\bemail\s+(?:to|the)\b", r"\bnotify\b", r"\bsmtp\b", r"webhook", r"\btweet",
          r"\bpost\s+(?:to|on)\b", r"\bcomment\s+on\b")),
    Risk("money", "ใช้เงิน",
         "ซื้อ จ่าย สมัครบริการที่เสียเงิน หรือใช้ API แบบจ่ายเงิน",
         (r"จ่าย(?:เงิน|ค่า)", r"ซื้อ", r"ชำระ", r"สมัคร(?:สมาชิก|แพ็กเกจ|บริการ)", r"เติมเงิน", r"บัตรเครดิต", r"เสียเงิน",
          r"\bpay(?:ment)?s?\b", r"\bpurchase", r"\bbuy\b", r"\bbilling\b", r"\bsubscri(?:be|ption)",
          r"credit\s*card", r"\bstripe\b", r"paid\s+(?:api|plan|tier)", r"\$\s?\d", r"\d\s*(?:บาท|thb|usd)\b")),
)
RISK_KEYS = {r.key: r for r in RISKS}
_WORDS = {r.key: [re.compile(w) for w in r.words] for r in RISKS}
# A mention right after a no doesn't count: "do not push", "no need to install packages", "without installing".
# (Found at B5's check: a plain slugify plan said "do not install extra packages" and "do not push" and was
# flagged as a download and a push.) Thai runs words together, so up to 12 letters may sit between.
_NEGATED = re.compile(r"(?:ไม่|ห้าม|อย่า|ยกเว้น|\bno\b|\bnot\b|\bnever\b|\bwithout\b|\bdon'?t\b|\bavoid\b)"
                      r"[\s:\-]*(?:\S+\s+){0,2}\S{0,12}$")


# ------------------------------------------------------------------ reading the book
def seed() -> None:
    """Make sure the 7 agreed high-risk kinds are in the book (at every start; new ones only)."""
    with session() as s:
        have = set(s.scalars(select(Rule.key).where(Rule.kind == "high_risk")))
        for r in RISKS:
            if f"risk.{r.key}" not in have:
                s.add(Rule(kind="high_risk", text=r.text, used_by=["jobs"], key=f"risk.{r.key}", fixed=True))


def risk_key(rule: Rule) -> str:
    """The name a plan's flags use: "download" for one of the 7, "rule<id>" for one you added."""
    return rule.key.removeprefix("risk.") if rule.fixed and rule.key else f"rule{rule.id}"


def risks() -> list[dict]:
    """Every high-risk kind in use: the 7 first, then yours. {key, text, hint, fixed, id}."""
    with session() as s:
        rows = s.scalars(select(Rule).where(Rule.kind == "high_risk", Rule.enabled.is_(True))
                         .order_by(Rule.fixed.desc(), Rule.id)).all()
        order = {r.key: i for i, r in enumerate(RISKS)}
        rows = sorted(rows, key=lambda r: (not r.fixed, order.get(risk_key(r), 99), r.id))
        return [{"id": r.id, "key": risk_key(r), "text": r.text, "fixed": r.fixed,
                 "hint": RISK_KEYS[risk_key(r)].hint if risk_key(r) in RISK_KEYS else ""} for r in rows]


def _said(pattern: re.Pattern, text: str) -> bool:
    """The pattern is in the text, and not as something the plan says it won't do."""
    return any(not _NEGATED.search(text[max(0, m.start() - 40):m.start()]) for m in pattern.finditer(text))


def flags(text: str) -> list[str]:
    """Which of the 7 agreed kinds a plan's text mentions (in RISKS order). Words, no model: a
    second net under the planner's own flags, so a kind it left out still asks; what the plan
    says it won't do ("must not push") doesn't count."""
    low = text.lower()
    return [key for key, words in _WORDS.items() if any(_said(w, low) for w in words)]


def _in_use(s, *kinds: str):
    return s.scalars(select(Rule).where(Rule.kind.in_(kinds), Rule.status == "active", Rule.enabled.is_(True))
                     .order_by(Rule.id)).all()


def notes_for(part: str) -> list[str]:
    """The notes (rules without an effect) a part reads: yours and the learned ones you accepted."""
    with session() as s:
        return [r.text for r in _in_use(s, "yours", "learned")
                if r.effect is None and (part in (r.used_by or []) or "all" in (r.used_by or []))]


def prompt_block(part: str) -> str:
    """Your notes, to add to a model's instructions ("" when there are none)."""
    notes = notes_for(part)
    return "\n\n[กติกาที่ผู้ใช้ตั้งไว้ ทำตามเสมอ]\n" + "\n".join(f"- {n}" for n in notes) if notes else ""


def _effects(kind: str) -> list[Rule]:
    with session() as s:
        rows = [r for r in _in_use(s, "yours", "learned") if (r.effect or {}).get("type") == kind]
        s.expunge_all()
    return rows


def appointment_note(starts_at: datetime | None) -> str:
    """A rule this appointment request goes against ("You usually don't take Saturday appointments"), or "". The
    request still waits for you: the rule only says so on its card."""
    if starts_at is None:
        return ""
    day = local(starts_at).weekday()
    return next((r.text for r in _effects("appointment_days") if day in r.effect.get("weekdays", [])), "")


def standing_for(project: str) -> str:
    """A rule that lets this project's low-risk plans start without asking (its text), or ""."""
    return next((r.text for r in _effects("job_auto") if r.effect.get("project") == project), "")


def block_avoid() -> list[dict]:
    """B7: the hours the planner never books ({"weekday", "from", "to"}), from your rules."""
    return [r.effect for r in _effects("block_avoid")]


def focus_window() -> dict | None:
    """B7: your focus hours ({"from", "to"}), filled first each day; the newest rule if several."""
    rows = sorted(_effects("focus_first"), key=lambda r: r.id)
    return rows[-1].effect if rows else None


def auto() -> bool:
    return bool(settings.get(AUTO_KEY, True))


def line() -> float:
    return float(settings.get(LINE_KEY, DEFAULT_LINE))


# ------------------------------------------------------------------ changing it (recorded, undoable)
def view(r: Rule) -> dict:
    return {"id": r.id, "kind": r.kind, "text": r.text, "used_by": list(r.used_by or []), "enabled": r.enabled,
            "status": r.status, "effect": r.effect, "evidence": r.evidence, "fixed": r.fixed,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None}


def _check_parts(used_by: list[str]) -> list[str]:
    bad = [p for p in used_by if p not in PARTS]
    if bad:
        raise ValueError(f"ไม่รู้จักส่วน {', '.join(bad)}")
    return list(dict.fromkeys(used_by))


def add(text: str, used_by: list[str], *, effect: dict | None = None, kind: str = "yours", via: Via = WEB) -> tuple[int, int]:
    """A new rule (yours, or a high-risk kind you add). -> (its id, the action id)."""
    text = text.strip()
    if not text:
        raise ValueError("ใส่ข้อความกติกาก่อน")
    if kind not in ("yours", "high_risk"):
        raise ValueError("เพิ่มได้แค่กติกาของคุณหรืองานเสี่ยงสูง")
    used_by = _check_parts(used_by or (["jobs"] if kind == "high_risk" else list(NOTE_PARTS)))
    with session() as s:
        row = Rule(kind=kind, text=text[:300], used_by=used_by, effect=effect)
        s.add(row)
        s.flush()
        rule_id = row.id
    what = "เพิ่มงานเสี่ยงสูง" if kind == "high_risk" else "เพิ่มกติกา"
    action_id = actions.record("rule.add", what, text, source_label=via[0], source_url=via[1], undo={"rule_id": rule_id})
    return rule_id, action_id


def edit(rule_id: int, *, text: str | None = None, used_by: list[str] | None = None, enabled: bool | None = None,
         via: Via = WEB) -> dict:
    """-> the rule as the page shows it, with the action id."""
    with session() as s:
        r = s.get(Rule, rule_id)
        if r is None:
            raise ValueError("ไม่พบกติกานี้")
        if r.fixed:
            raise ValueError("งานเสี่ยงสูง 7 อย่างที่ตกลงไว้ แก้หรือปิดไม่ได้")
        old = {"text": r.text, "used_by": list(r.used_by or []), "enabled": r.enabled}
        if text is not None:
            if not text.strip():
                raise ValueError("ข้อความกติกาว่างไม่ได้")
            r.text = text.strip()[:300]
        if used_by is not None:
            if r.effect is None and not set(used_by) & {*NOTE_PARTS, "all"}:
                raise ValueError("กติกาแบบข้อความต้องมีถามเลขาหรือตัวคุมงานเบื้องหลังใช้ เพราะสองส่วนนี้เท่านั้นที่อ่านข้อความได้")
            r.used_by = _check_parts(used_by)
        if enabled is not None:
            r.enabled = enabled
        s.flush()
        out = view(r)
    summary = ("เปิดกติกา" if enabled else "ปิดกติกา") if enabled is not None and text is None and used_by is None else "แก้กติกา"
    out["action_id"] = actions.record("rule.edit", summary, out["text"], source_label=via[0], source_url=via[1],
                                      undo={"rule_id": rule_id, "old": old})
    return out


def delete(rule_id: int, *, via: Via = WEB) -> int:
    """-> the action id."""
    with session() as s:
        r = s.get(Rule, rule_id)
        if r is None:
            raise ValueError("ไม่พบกติกานี้")
        if r.fixed:
            raise ValueError("งานเสี่ยงสูง 7 อย่างที่ตกลงไว้ ลบไม่ได้")
        row = {k: getattr(r, k) for k in ("kind", "text", "used_by", "enabled", "status", "effect", "key", "evidence")}
        s.delete(r)
    return actions.record("rule.delete", "ลบกติกา", row["text"], source_label=via[0], source_url=via[1], undo={"row": row})


def answer_learned(rule_id: int, accept: bool, *, via: Via = WEB) -> dict:
    """Use as a rule (accept: it's used from now on) or Not this (never suggested again)."""
    with session() as s:
        r = s.get(Rule, rule_id)
        if r is None or r.kind != "learned":
            raise ValueError("ไม่พบสิ่งที่เลขาเรียนรู้นี้")
        if r.status != "pending":
            raise ValueError("ตอบไปแล้ว")
        r.status, r.enabled = ("active", True) if accept else ("dismissed", False)
        s.flush()
        out = view(r)
    out["action_id"] = actions.record("rule.learned", "ใช้เป็นกติกา" if accept else "ไม่ใช้สิ่งที่เลขาเรียนรู้", out["text"],
                                      source_label=via[0], source_url=via[1], undo={"rule_id": rule_id})
    return out


def set_jobs(*, auto_on: bool | None = None, line_pct: float | None = None, via: Via = WEB) -> int:
    """The rule "Background work can run by itself when more than 70% of the quota is left": its switch and its line. -> the action id."""
    if line_pct is not None and not 10 <= line_pct <= 100:
        raise ValueError("เส้นโควตาต้องอยู่ระหว่าง 10–100%")
    old = {AUTO_KEY: settings.get(AUTO_KEY), LINE_KEY: settings.get(LINE_KEY)}
    if auto_on is not None:
        settings.put(AUTO_KEY, auto_on)
    if line_pct is not None:
        settings.put(LINE_KEY, round(line_pct))
    words = []
    if line_pct is not None:
        words.append(f"เส้น {line():.0f}%")
    if auto_on is not None:
        words.append("เปิดให้ทำเอง" if auto_on else "ปิด: ทุกแผนถามก่อน")
    return actions.record("rule.jobs", "เปลี่ยนกติกางานเบื้องหลัง", " · ".join(words), source_label=via[0], source_url=via[1],
                          undo={"old": old})


# ------------------------------------------------------------------ undo
async def _undo_add(undo: dict) -> None:
    with session() as s:
        if r := s.get(Rule, undo["rule_id"]):
            s.delete(r)


async def _undo_edit(undo: dict) -> None:
    with session() as s:
        r = s.get(Rule, undo["rule_id"])
        if r is None:
            raise actions.UndoError("กติกานี้ถูกลบไปแล้ว")
        for k, v in undo["old"].items():
            setattr(r, k, v)


async def _undo_delete(undo: dict) -> None:
    with session() as s:
        s.add(Rule(**undo["row"]))


async def _undo_learned(undo: dict) -> None:
    with session() as s:
        if r := s.get(Rule, undo["rule_id"]):
            r.status, r.enabled = "pending", True


async def _undo_jobs(undo: dict) -> None:
    for k, v in undo["old"].items():
        settings.put(k, v)


actions.register_undo("rule.add", _undo_add)
actions.register_undo("rule.edit", _undo_edit)
actions.register_undo("rule.delete", _undo_delete)
actions.register_undo("rule.learned", _undo_learned)
actions.register_undo("rule.jobs", _undo_jobs)
