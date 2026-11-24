"""A rule typed as a sentence (W8 item 5: "Type it as a sentence. The secretary turns it into a rule, which you check before using it.").

One small call (task "rule": Sonnet, effort low, no tools) reads the sentence and names what
kind of rule it is. The answer is checked here (`proposal`, no model, so the tests can try it)
and comes back to the page as a proposal: what the rule will say, who uses it, and what will
change. Nothing is saved until you press "Apply this rule" (api/rules.py applies it).

The kinds, from the most concrete:
- appointment_days: "Don't accept Sunday appointments" -> such requests say so on their card
- schedule_hours: "Don't schedule work before 9 am" -> the planner's hours (the same setting as the
  schedule rules in settings)
- mail_keywords: "Email containing the word funding, notify immediately" -> the mail watch's keywords
- high_risk: "Editing the .env file must ask first" -> a high-risk kind of your own
- job_auto: "Finance work can be done by itself, straight away" -> its low-risk plans start without asking
- note: anything else a model can follow, for Ask the Secretary and/or the background planner
- unsupported: what the secretary can't do (it says why instead of pretending)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.core import llm
from app.core.timefmt import DAYS

KINDS = ("appointment_days", "schedule_hours", "mail_keywords", "high_risk", "job_auto", "note", "unsupported")

SYSTEM = """แปลงกติกาที่ผู้ใช้พิมพ์เป็น JSON หนึ่งก้อน ตอบแค่ JSON
{"type": "...", "text": "กติกาเขียนสั้นๆ ชัดเจน", ...ฟิลด์ของ type นั้น}
type ที่ใช้ได้:
- appointment_days: ไม่รับนัดบางวัน · "weekdays": [0-6] (0 = จันทร์ ... 6 = อาทิตย์)
- schedule_hours: ช่วงเวลาที่ให้วางบล็อกงานในตาราง · "day_start" และ/หรือ "day_end" แบบ "HH:MM"
- mail_keywords: คำในอีเมลที่ต้องแจ้งทันที · "add": ["คำ"]
- high_risk: งานแบบหนึ่งที่งานเบื้องหลังต้องถามก่อนทุกครั้ง
- job_auto: ให้งานเบื้องหลังของโปรเจคหนึ่งเริ่มเองได้ไม่ต้องถาม · "project": ชื่อตามรายการโปรเจค
- note: กติกาอื่นที่คนตอบคำถาม (ask) หรือคนวางแผนงานเบื้องหลัง (jobs) ทำตามได้ · "used_by": ["ask"], ["jobs"] หรือทั้งสอง
- unsupported: ทำตามไม่ได้ เช่น ต้องส่งข้อความหาคนอื่นแทนผู้ใช้ · "why": เหตุผลสั้นๆ"""


@dataclass(frozen=True)
class Context:
    """What the check needs to know about now (api/rules.py reads it)."""
    projects: dict[str, bool] = field(default_factory=dict)  # name -> "let the secretary continue" is on
    day_start: str = "09:00"
    day_end: str = "22:00"
    keywords: tuple[str, ...] = ()


@dataclass
class Proposal:
    kind: str
    text: str  # as the rule book will show it
    used_by: list[str]
    why: str  # what will happen, or (unsupported) why not
    effect: dict | None = None  # appointment_days · job_auto: what the code follows
    change: dict | None = None  # schedule_hours {"day_start", "day_end"} · mail_keywords {"add": [...]}

    @property
    def ok(self) -> bool:
        return self.kind != "unsupported"


def _json(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _hhmm(value) -> str | None:
    m = re.fullmatch(r"([01]?\d|2[0-3])[:.]([0-5]\d)", str(value or "").strip())
    return f"{int(m[1]):02d}:{m[2]}" if m else None


def no(why: str, text: str = "") -> Proposal:
    return Proposal("unsupported", text, [], why)


def proposal(sentence: str, raw: dict | None, ctx: Context) -> Proposal:
    """The model's answer, checked against what the secretary can really do."""
    if raw is None or raw.get("type") not in KINDS:
        return no("เลขาแปลงประโยคนี้เป็นกติกาไม่ได้ ลองเขียนให้ชัดขึ้น", sentence)
    kind = raw["type"]
    text = str(raw.get("text") or sentence).strip()[:300]
    if kind == "unsupported":
        return no(str(raw.get("why") or "เลขายังทำตามกติกานี้ไม่ได้").strip(), text)
    if kind == "appointment_days":
        days = sorted({d for d in raw.get("weekdays") or [] if isinstance(d, int) and 0 <= d <= 6})
        if not days:
            return no("ไม่รู้ว่าวันไหน", text)
        names = " ".join(f"วัน{DAYS[d]}" for d in days)
        return Proposal(kind, text, ["mail"], f"นัดที่ขอเข้ามา{names} จะขึ้นว่าขัดกติกานี้ (ยังรอคุณตอบเหมือนเดิม)",
                        effect={"type": kind, "weekdays": days})
    if kind == "schedule_hours":
        start, end = _hhmm(raw.get("day_start")), _hhmm(raw.get("day_end"))
        if not (start or end):
            return no("ไม่รู้ว่าเวลาไหน", text)
        new_start, new_end = start or ctx.day_start, end or ctx.day_end
        if new_start >= new_end:
            return no(f"เวลาเริ่ม {new_start} ต้องก่อนเวลาเลิก {new_end}", text)
        return Proposal(kind, text, ["planner"], f"ตัววางตารางจะวางบล็อกงาน {new_start}–{new_end} (ตอนนี้ {ctx.day_start}–{ctx.day_end})",
                        change={"day_start": new_start, "day_end": new_end})
    if kind == "mail_keywords":
        have = {k.lower() for k in ctx.keywords}
        add = list(dict.fromkeys(w.strip() for w in raw.get("add") or [] if isinstance(w, str) and w.strip()))
        new = [w for w in add if w.lower() not in have]
        if not new:
            return no("มีคำนี้ในรายการแจ้งทันทีอยู่แล้ว" if add else "ไม่รู้ว่าคำไหน", text)
        return Proposal(kind, text, ["mail"], f"ตัวอ่านอีเมลจะแจ้งทันทีเมื่อเจอคำว่า {' · '.join(new)}", change={"add": new})
    if kind == "high_risk":
        return Proposal(kind, text, ["jobs"], "งานเบื้องหลังที่มีงานแบบนี้จะถามคุณก่อนทุกครั้ง แม้โควตาเหลือเยอะ")
    if kind == "job_auto":
        wanted = str(raw.get("project") or "").strip().lower()
        name = next((n for n in ctx.projects if n.lower() == wanted), None)
        if name is None:
            return no(f"ไม่พบโปรเจคชื่อ {raw.get('project') or '(ไม่ได้บอก)'} ในทะเบียน", text)
        why = f"แผนเสี่ยงต่ำของ {name} จะเริ่มเองได้แม้โควตาไม่เกินเส้น · งานเสี่ยงสูงยังถามเสมอ"
        if not ctx.projects[name]:
            why += " · ต้องเปิด “ให้เลขาทำต่อได้” ที่หน้าโปรเจคด้วย"
        return Proposal(kind, text, ["jobs"], why, effect={"type": kind, "project": name})
    used_by = [p for p in raw.get("used_by") or [] if p in ("ask", "jobs")] or ["ask", "jobs"]
    who = " · ".join({"ask": "ถามเลขา", "jobs": "ตัวคุมงานเบื้องหลัง"}[p] for p in used_by)
    return Proposal("note", text, used_by, f"{who} อ่านกติกานี้ทุกครั้ง")


async def parse(sentence: str, ctx: Context) -> tuple[Proposal, int]:
    """-> (the proposal, tokens used)."""
    sentence = sentence.strip()
    if not sentence:
        return no("พิมพ์กติกาก่อน"), 0
    prompt = f"[โปรเจค] {', '.join(ctx.projects) or '-'}\n[กติกา] {sentence[:500]}"
    reply = await llm.run("rule", prompt, system=SYSTEM, max_turns=1)
    return proposal(sentence, _json(reply.text), ctx), reply.tokens_in + reply.tokens_out
