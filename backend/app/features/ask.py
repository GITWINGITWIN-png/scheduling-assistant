"""Ask the secretary (ถามเลขา, feature P10): quick answers from Sonnet, plans from Opus.

The flow (D7, and your notes on it):

1. Every message goes to **Sonnet, effort low** first. It looks things up with
   read-only tools over the store and answers with its sources.
2. If the message asks for a **plan or an order to start work**, Sonnet doesn't
   answer it. It replies with one HANDOFF line instead, and the message goes to
   **Opus, effort high**, which writes the plan. The plan is saved as a
   decision you approve, change or reject.
3. "ให้ Opus คิดต่อ" sends the same question to **Opus** when the quick answer
   isn't enough.

Sorting with Sonnet's own reply costs no extra call: one Sonnet call either
answers or hands off.

This module is the logic only. The Discord side is features/ask_discord.py
and the web side is api/ask.py; both call the functions below.

B1's tools read what B1 stores: the action log, waiting decisions, model usage
and the clock. B7 extends them to every part of the store.
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Annotated

from claude_agent_sdk import tool
from sqlalchemy import func, select

from app.core import actions, llm
from app.core.clock import clock
from app.core.db import now, session
from app.core.tables import Action, Decision, LLMUsage
from app.core.timefmt import thai_datetime

# The name each tool goes by when it's listed as a source under an answer
SOURCE_NAMES = {
    "recent_actions": "บันทึกสิ่งที่เลขาทำ",
    "pending_decisions": "เรื่องที่รอคุณ",
    "model_usage": "การใช้โมเดล",
    "secretary_status": "นาฬิกาเลขา",
}

ASK_SYSTEM = """คุณคือ "เลขา" เลขาส่วนตัวของผู้ใช้ (my_secretary v2) ทำงานบนเครื่องของผู้ใช้
ตอบภาษาไทย สั้น ตรง เป็นกันเอง ใช้ข้อมูลจริงจากเครื่องมือเท่านั้น ถ้าไม่มีข้อมูลให้บอกตรงๆ ว่าไม่มี ห้ามเดา

ข้อความที่ขอให้ "วางแผน" หรือ "สั่งให้ทำงาน/เริ่มงาน/ทำต่อ" ไม่ต้องตอบเอง
ให้ตอบเพียงบรรทัดเดียว: HANDOFF: <สรุปสิ่งที่ผู้ใช้ขอ 1 ประโยค>
แล้วระบบจะส่งต่อให้ Opus วางแผน

ตอนนี้เลขาอยู่ในช่วงพัฒนา B1: มีบันทึกสิ่งที่เลขาทำ เรื่องที่รอตัดสิน การใช้โมเดล และนาฬิกาเลขา
ส่วนอีเมล ตาราง โปรเจค ไอเดีย และการใช้เวลา ยังไม่มีข้อมูล (มาในช่วง B2–B6) ถ้าถามเรื่องเหล่านี้ ให้บอกว่ามาในช่วงไหน"""

PLAN_SYSTEM = """คุณคือ "เลขา" เลขาส่วนตัวของผู้ใช้ กำลังวางแผนตามที่ผู้ใช้ขอ ตอบภาษาไทย
รูปแบบคำตอบ:
บรรทัดแรก: ชื่อแผนสั้นๆ (ไม่ต้องมีคำว่า "แผน:" นำหน้า)
จากนั้น ขั้นตอนเป็นรายการเลข 3–7 ข้อ แต่ละข้อบอกว่าใครทำ (เลขา หรือ คุณ) และทำเมื่อไร
ถ้ามีงานที่เลขาทำเอง บอกโมเดล effort และงบโทเคนโดยประมาณ
ถ้ามีเวลาที่ผู้ใช้ต้องใช้ ปิดด้วยบรรทัด "เวลาคุณ: ..."
ตอนนี้เลขายังเริ่มงานในโปรเจคเองไม่ได้ (มาในช่วง B5) และยังไม่เห็นตารางหรืออีเมล (B2–B3)
ให้วางแผนจากสิ่งที่ผู้ใช้บอก และบอกตรงๆ ว่าส่วนไหนต้องรอช่วงนั้น"""


# ------------------------------------------------------------------ tools (read-only)
def _text(value) -> dict:
    return {"content": [{"type": "text", "text": value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)}]}


@tool("recent_actions", "สิ่งที่เลขาทำเอง ย้อนหลังตามจำนวนวัน (ล่าสุดก่อน) พร้อมเวลา ที่มา และโทเคน",
      {"days": Annotated[int, "ย้อนหลังกี่วัน เช่น 1 = วันนี้"]})
async def recent_actions(args: dict) -> dict:
    since = now() - timedelta(days=max(1, int(args.get("days") or 1)))
    with session() as s:
        rows = s.scalars(select(Action).where(Action.at >= since).order_by(Action.at.desc()).limit(50)).all()
    return _text([{"เวลา": thai_datetime(a.at), "ทำอะไร": a.summary, "กับอะไร": a.target, "ที่มา": a.source_label,
                   "โทเคน": a.tokens, "ย้อนแล้ว": bool(a.undone_at)} for a in rows] or "ยังไม่มีบันทึกในช่วงนี้")


@tool("pending_decisions", "เรื่องที่รอผู้ใช้ตัดสิน (แผนจาก Opus ฯลฯ)", {})
async def pending_decisions(args: dict) -> dict:
    with session() as s:
        rows = s.scalars(select(Decision).where(Decision.status == "pending").order_by(Decision.created_at)).all()
    return _text([{"ชนิด": d.kind, "เรื่อง": d.title, "เมื่อ": thai_datetime(d.created_at)} for d in rows] or "ไม่มีเรื่องที่รอ")


@tool("model_usage", "โทเคนที่เลขาใช้ แยกตามงานและโมเดล ย้อนหลังตามจำนวนวัน",
      {"days": Annotated[int, "ย้อนหลังกี่วัน"]})
async def model_usage(args: dict) -> dict:
    since = now() - timedelta(days=max(1, int(args.get("days") or 7)))
    with session() as s:
        rows = s.execute(select(LLMUsage.task, LLMUsage.model, func.count(), func.sum(LLMUsage.tokens_in), func.sum(LLMUsage.tokens_out))
                         .where(LLMUsage.at >= since).group_by(LLMUsage.task, LLMUsage.model)).all()
    return _text([{"งาน": t, "โมเดล": m, "ครั้ง": n, "โทเคนเข้า": i or 0, "โทเคนออก": o or 0} for t, m, n, i, o in rows] or "ยังไม่มีการใช้")


@tool("secretary_status", "รอบงานของนาฬิกาเลขา: รอบไหนทำงานแล้ว รอบไหนมาในช่วงไหน ครั้งล่าสุดและครั้งถัดไป", {})
async def secretary_status(args: dict) -> dict:
    return _text(clock.status())


TOOLS = [recent_actions, pending_decisions, model_usage, secretary_status]


# ------------------------------------------------------------------ answers
@dataclass
class Answer:
    kind: str  # "answer" or "plan"
    text: str
    model: str  # "Sonnet" / "Opus"
    effort: str
    seconds: float
    tokens: int
    sources: list[str] = field(default_factory=list)
    decision_id: int | None = None  # for plans
    title: str = ""  # for plans

    @property
    def footer(self) -> str:
        if self.kind == "plan":
            return f"วางแผนโดย {self.model} · effort {self.effort} · ใช้ {self.tokens / 1000:.1f}k โทเคน"
        src = " · ".join(self.sources) if self.sources else "ไม่ได้ค้นข้อมูล"
        return f"{self.model} · effort {self.effort} · ตอบใน {self.seconds:.0f} วินาที · ที่มา: {src}"


TextSink = Callable[[str], Awaitable[None]] | None


def _prompt(text: str, history: list[tuple[str, str]] = ()) -> str:
    lines = [f"[ตอนนี้: {thai_datetime(now(), long=True)}]"]
    if history:
        lines.append("[บทสนทนาก่อนหน้า]")
        lines += [f"{who}: {said[:500]}" for who, said in history]
        lines.append("[ข้อความใหม่]")
    lines.append(text)
    return "\n".join(lines)


def _sources(reply: llm.Reply) -> list[str]:
    return list(dict.fromkeys(SOURCE_NAMES.get(t, t) for t in reply.tools_used))


HANDOFF_NOTE = "เป็นการวางแผน · ส่งต่อให้ Opus"


# Where a message came from, for the action log's "ที่มา" (the web page, or a link to the Discord message)
Via = tuple[str, str]
WEB: Via = ("หน้าเว็บ", "")


async def ask(text: str, history: list[tuple[str, str]] = (), on_text: TextSink = None,
              on_note: TextSink = None, via: Via = WEB) -> Answer:
    """Sonnet answers, or hands off to Opus for a plan (on_note hears the hand-off)."""
    async def stream_unless_handoff(chunk: str) -> None:
        if on_text and not chunk.lstrip().upper().startswith("HANDOFF"):
            await on_text(chunk)

    reply = await llm.run("ask", _prompt(text, history), system=ASK_SYSTEM, tools=TOOLS, on_text=stream_unless_handoff)
    if reply.text.lstrip().upper().startswith("HANDOFF"):
        if on_note:
            await on_note(HANDOFF_NOTE)
        return await plan(text, history, on_text=on_text, sorted_by=reply, via=via)
    actions.record("ask", "ตอบคำถาม", text, source_label=via[0], source_url=via[1], tokens=reply.tokens)
    return Answer("answer", reply.text, reply.model_name, reply.effort, reply.duration_ms / 1000, reply.tokens, _sources(reply))


async def deepen(text: str, history: list[tuple[str, str]] = (), on_text: TextSink = None, via: Via = WEB) -> Answer:
    """"ให้ Opus คิดต่อ": the same question, thought through by Opus."""
    system = ASK_SYSTEM + "\nตอนนี้ผู้ใช้ขอให้คิดละเอียดขึ้นกว่าคำตอบเร็ว: ค้นให้ครบ อธิบายเหตุผล"
    reply = await llm.run("ask_deep", _prompt(text, history), system=system, tools=TOOLS, on_text=on_text)
    if reply.text.lstrip().upper().startswith("HANDOFF"):
        return await plan(text, history, on_text=on_text, via=via)
    actions.record("ask.deep", "ตอบคำถาม · Opus คิดต่อ", text, source_label=via[0], source_url=via[1], tokens=reply.tokens)
    return Answer("answer", reply.text, reply.model_name, reply.effort, reply.duration_ms / 1000, reply.tokens, _sources(reply))


async def plan(text: str, history: list[tuple[str, str]] = (), on_text: TextSink = None,
               sorted_by: llm.Reply | None = None, previous: Decision | None = None, change: str = "",
               via: Via = WEB) -> Answer:
    """Opus writes a plan, which is saved as a decision waiting for you."""
    prompt = _prompt(text, history)
    if previous is not None:
        prompt += f"\n\n[แผนเดิม]\n{previous.detail.get('plan', '')}\n\n[ผู้ใช้ขอแก้]\n{change}\nเขียนแผนใหม่ทั้งแผนตามที่ขอแก้"
    reply = await llm.run("plan", prompt, system=PLAN_SYSTEM, tools=TOOLS, on_text=on_text)
    lines = reply.text.strip().splitlines()
    title = (lines[0].strip(" #*") if lines else "แผน")[:200]
    body = "\n".join(lines[1:]).strip() or reply.text
    tokens = reply.tokens + (sorted_by.tokens if sorted_by else 0)
    with session() as s:
        d = Decision(kind="plan", title=title, detail={
            "request": text, "plan": body, "model": reply.model_name, "effort": reply.effort, "tokens": tokens,
            "revises": previous.id if previous is not None else None, "started": False,
        })
        s.add(d)
        s.flush()
        decision_id = d.id
    actions.record("plan.made", "แก้แผนตามที่ขอ" if previous is not None else "วางแผน · รอคุณตัดสิน", title,
                   source_label=via[0], source_url=via[1], tokens=tokens)
    return Answer("plan", body, reply.model_name, reply.effort, reply.duration_ms / 1000, tokens, _sources(reply), decision_id, title)


# ------------------------------------------------------------------ deciding a plan
class DecisionError(ValueError):
    """The decision doesn't exist or was already decided. The message says which."""


def decide(decision_id: int, action: str, note: str = "", via: Via = WEB) -> tuple[Decision, int]:
    """Approve or reject a plan, and return it with the id of the logged (undoable) action.

    "edit" (revise) goes through revise() instead.
    """
    if action not in ("approve", "reject"):
        raise DecisionError(f"ไม่รู้จักคำสั่ง {action}")
    with session() as s:
        d = s.get(Decision, decision_id)
        if d is None:
            raise DecisionError("ไม่พบเรื่องนี้")
        if d.status != "pending":
            raise DecisionError(f"เรื่องนี้ตัดสินไปแล้ว ({d.status})")
        d.status = "approved" if action == "approve" else "rejected"
        d.answer = note
        d.answered_at = now()
    summary = "อนุมัติแผน · รอเริ่ม" if action == "approve" else "ไม่เอาแผน"
    action_id = actions.record(f"plan.{action}", summary, d.title, source_label=via[0], source_url=via[1],
                               undo={"decision_id": d.id})
    return d, action_id


async def _reopen_plan(data: dict) -> None:
    """Undo for plan.approve / plan.reject: the plan waits for you again, if it hasn't started."""
    with session() as s:
        d = s.get(Decision, data.get("decision_id"))
        if d is None:
            raise actions.UndoError("ไม่พบแผนนี้แล้ว")
        if d.detail.get("started"):
            raise actions.UndoError("แผนนี้เริ่มทำไปแล้ว ย้อนไม่ได้ · หยุดได้ที่หน้างานเบื้องหลัง")
        if d.status not in ("approved", "rejected"):
            raise actions.UndoError(f"แผนนี้ไม่ได้อยู่ในสถานะที่ย้อนได้ ({d.status})")
        d.status, d.answered_at = "pending", None


actions.register_undo("plan.approve", _reopen_plan)
actions.register_undo("plan.reject", _reopen_plan)


async def revise(decision_id: int, change: str, via: Via = WEB) -> Answer:
    """แก้: Opus rewrites the plan with your change; the old one is marked revised."""
    with session() as s:
        old = s.get(Decision, decision_id)
        if old is None or old.status != "pending":
            raise DecisionError("แผนนี้แก้ไม่ได้แล้ว (ไม่พบ หรือตัดสินไปแล้ว)")
        old.status, old.answer, old.answered_at = "revised", change, now()
    return await plan(old.detail.get("request", old.title), previous=old, change=change, via=via)
