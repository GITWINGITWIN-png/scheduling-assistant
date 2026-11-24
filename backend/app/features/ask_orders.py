"""B9, giving orders through chat: the tools Opus uses to carry out an order, and the confirm step.

Every tool calls the same function as a button on the page, so an order does exactly what the
button does: the same result, the same record in the secretary's action log, the same Undo. Tools are
made for each call (toolset()), so each one knows where the order came from (`via`, for the
log's "Source") and writes what it did into that call's `Taken`. The answer shows that list, with
an Undo button for each.

What can be undone is done at once (answer 1.A at the plan). What can't waits: the tool saves
it as a decision of kind "order", and the answer shows Do it now / Decline. Only a press of that
button carries it out. Opus can't confirm its own request (answer_waiting refuses kind "order"),
and an unanswered one expires after a day. What waits this way:
- replanning the whole schedule;
- answering a weekly review topic;
- opening a project from an idea group (it makes a folder);
- declining an appointment;
- approving a plan (the secretary then carries it out).

Not given to the chat (agreed at the plan): anything outward (Gmail stays read-only), deleting,
settings (rounds, models, theme, recording), and switching on let the secretary continue working on a project.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from claude_agent_sdk import SdkMcpTool, tool
from sqlalchemy import select

from app.core.db import now, session
from app.core.tables import Decision
from app.core.timefmt import from_local

log = logging.getLogger(__name__)

Via = tuple[str, str]
MAX_ACTIONS = 25  # in one order (Discord's 25 buttons): more is a sign something went wrong, so the tools stop
ORDER_LIFE = timedelta(days=1)  # a request for confirm left this long expires

LEVEL_WORDS = {"important": "สำคัญ", "interested": "สนใจ", "ignored": "ไม่สนใจ"}
KIND_NAMES = {"appointment": "นัดจากอีเมล", "course": "วิชาใน Classroom", "plan": "แผนจากแชท",
              "project_level": "ระดับของโปรเจคใหม่", "job": "แผนงานเบื้องหลัง", "idea": "กลุ่มไอเดียที่โตพอ",
              "weekly": "หัวข้อทบทวนรายสัปดาห์", "order": "คำสั่งที่รอผู้ใช้ยืนยัน"}
# What answer_waiting takes for each kind (a weekly topic takes its own buttons, detail["acts"]).
ANSWERS = {
    "appointment": {"accept": "รับนัด ลงปฏิทิน", "decline": "ไม่ไป (ย้อนไม่ได้: รอผู้ใช้ยืนยัน)"},
    "course": {"follow": "ติดตามวิชานี้", "ignore": "ไม่ติดตาม"},
    "project_level": {"set": "ตั้งระดับ: ใส่ potential (S–F) และ urgency (0–5)"},
    "job": {"approve": "อนุมัติแผนงานเบื้องหลัง", "reject": "ไม่เอาแผนนี้"},
    "idea": {"task": "ทำเป็นงานในตาราง", "later": "ยังก่อน", "project": "เปิดเป็นโปรเจค (ย้อนไม่ได้: รอผู้ใช้ยืนยัน)"},
    "plan": {"approve": "ใช้แผนนี้: เลขาลงมือทำตามแผน (รอผู้ใช้ยืนยัน)", "reject": "ไม่เอาแผนนี้"},
}


@dataclass
class Taken:
    """What one Opus call did, for the answer under it."""

    done: list[int] = field(default_factory=list)  # action ids, in the order they happened
    confirm: list[int] = field(default_factory=list)  # "order" decisions waiting for confirm
    plan: int | None = None  # a plan it proposed instead of acting (a decision id)
    tokens: int = 0  # what models called by the tools used (reading a rule, planning a background job)
    notes: list[str] = field(default_factory=list)  # what a tool couldn't do, in words

    @property
    def count(self) -> int:
        return len(self.done) + len(self.confirm)


class ConfirmError(ValueError):
    """Do it now / Decline can't be answered any more (gone, answered, expired): nothing is left to press,
    and the message says what happened, for the page and Discord to show in place of the buttons."""


class ConfirmFailed(ConfirmError):
    """Do it now was pressed but doing it failed: nothing was done, and it waits for another press."""


def answered(d: Decision) -> str:
    """What became of an order that no longer waits, in words."""
    if d.status == "expired":
        return "คำสั่งนี้หมดเวลาแล้ว สั่งใหม่ได้"
    if d.status == "approved":
        return f"ทำแล้ว: {d.answer}" if d.answer else f"กำลังทำอยู่: {d.title}"  # answer is set when it's done
    return f"ไม่ทำแล้ว: {d.title}"


def _text(value) -> dict:
    return {"content": [{"type": "text", "text": value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)}]}


def _schema(required: dict[str, tuple[str, str]], optional: dict[str, tuple[str, str]] | None = None) -> dict:
    """A JSON schema from {name: (type, description)}; the optional fields may be left out."""
    fields = {**required, **(optional or {})}
    return {"type": "object", "properties": {k: {"type": typ, "description": desc} for k, (typ, desc) in fields.items()},
            "required": list(required)}


def _str(args: dict, key: str) -> str:
    return str(args.get(key) or "").strip()


def _num(args: dict, key: str) -> int | None:
    """A number the model may leave out, send empty, or send as text."""
    value = args.get(key)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} ต้องเป็นตัวเลข")


def _need(args: dict, key: str) -> int:
    """A number the tool can't work without (an id, a weekday)."""
    value = _num(args, key)
    if value is None:
        raise ValueError(f"ต้องใส่ {key}")
    return value


def _when(args: dict, key: str) -> datetime | None:
    value = _str(args, key)
    try:
        return from_local(value) if value else None
    except ValueError:
        raise ValueError(f"{key} ต้องเป็นวันเวลาแบบ 2026-11-13T17:00")


def waiting_view(d: Decision) -> dict:
    """One waiting item as the chat's tools list it: its id and what it can be answered with."""
    answers = dict(d.detail.get("acts", [])) if d.kind == "weekly" else ANSWERS.get(d.kind, {})
    return {"id": d.id, "ชนิด": KIND_NAMES.get(d.kind, d.kind), "เรื่อง": d.title,
            "ตอบได้": answers or "ผู้ใช้ต้องตอบที่ปุ่มของมันเอง"}


# ------------------------------------------------------------------ the confirm step
async def _settle(decision_id: int, via: Via) -> None:
    from app.features import decisions

    await decisions.settle_card(decision_id, where=via[0])  # its card in Discord says so too


async def _settle_idea(group_id: int, via: Via) -> None:
    from app.features.ideas.tables import IdeaGroup

    with session() as s:
        decision_id = s.get(IdeaGroup, group_id).decision_id
    if decision_id:
        await _settle(decision_id, via)


async def _do_replan(args: dict, via: Via) -> str:
    from app.features.schedule import sync

    return f"วางตารางใหม่แล้ว · {await sync.replan_now(via)}"


async def _do_decline(args: dict, via: Via) -> str:
    from app.features.mail import extract

    d, _ = await extract.decide(args["decision_id"], False, via=via)
    await _settle(d.id, via)
    return f"ไม่ไปนัด “{d.title}” แล้ว"


async def _do_idea_project(args: dict, via: Via) -> str:
    from app.features.ideas import groups

    name = args.get("name") or groups.suggested_folder(args["group_id"])
    groups.open_project(args["group_id"], name, via=via)
    await _settle_idea(args["group_id"], via)
    return f"เปิดโปรเจค ~/Projects/{name} จากกลุ่มไอเดียแล้ว"


async def _do_weekly(args: dict, via: Via) -> str:
    from app.features.weekly import review

    said = await review.answer(args["decision_id"], args["act"], via=via)
    await _settle(args["decision_id"], via)
    return said


async def _do_plan_approve(args: dict, via: Via) -> str:
    from app.features import ask

    d, _ = ask.decide(args["decision_id"], "approve", via=via)
    await _settle(d.id, via)
    return f"ใช้แผน “{d.title}” แล้ว"


CONFIRMABLE: dict[str, Callable[[dict, Via], Awaitable[str]]] = {
    "replan": _do_replan, "decline": _do_decline, "idea_project": _do_idea_project, "weekly": _do_weekly,
    "plan_approve": _do_plan_approve,
}


def expire_old(at: datetime | None = None) -> int:
    """Requests for ยืนยัน older than a day expire (the bell shouldn't keep yesterday's orders)."""
    at = at or now()
    with session() as s:
        old = s.scalars(select(Decision).where(Decision.kind == "order", Decision.status == "pending",
                                               Decision.created_at < at - ORDER_LIFE)).all()
        for d in old:
            d.status, d.answered_at = "expired", at
        return len(old)


def ask_first(do: str, args: dict, words: str, via: Via, taken: Taken) -> str:
    """Save what can't be undone as a request for confirmation, instead of doing it."""
    expire_old()
    with session() as s:
        d = Decision(kind="order", title=words[:200], detail={"do": do, "args": args, "via": list(via)})
        s.add(d)
        s.flush()
        taken.confirm.append(d.id)
    return f"ยังไม่ได้ทำ: “{words}” ย้อนกลับไม่ได้ จึงรอผู้ใช้กดยืนยัน (ปุ่มทำเลย · ไม่เอา อยู่ใต้คำตอบ) · บอกผู้ใช้ด้วย"


async def confirm(decision_id: int, yes: bool, *, via: Via) -> str:
    """Do it now / Decline, pressed by you. -> what happened, in words. Raises ConfirmError."""
    with session() as s:
        d = s.get(Decision, decision_id)
        if d is None or d.kind != "order":
            raise ConfirmError("ไม่พบคำสั่งนี้")
        if d.status == "pending" and d.created_at < now() - ORDER_LIFE:
            d.status, d.answered_at = "expired", now()
        if d.status != "pending":
            raise ConfirmError(answered(d))
        # settled before it runs, so a second press can't run it twice
        d.status, d.answered_at = ("approved" if yes else "rejected"), now()
        do, args, words = d.detail["do"], d.detail["args"], d.title
    if not yes:
        return f"ไม่ทำแล้ว: {words}"
    try:
        said = await CONFIRMABLE[do](args, via)
    except Exception as exc:  # nothing was done: it waits again, so you can press once more
        with session() as s:
            d = s.get(Decision, decision_id)
            d.status, d.answered_at = "pending", None
        if not isinstance(exc, ValueError):
            log.exception("confirmed order %s (%s) failed", decision_id, do)
        raise ConfirmFailed(f"ทำไม่สำเร็จ: {exc} · กดทำเลยอีกครั้งได้") from exc
    with session() as s:
        s.get(Decision, decision_id).answer = said[:500]
    return said


# ------------------------------------------------------------------ the tools
def toolset(via: Via, taken: Taken, *, request: str = "", planning: bool = True,
            limit: int = MAX_ACTIONS) -> list[SdkMcpTool]:
    """The tools for one Opus call. planning=False (carrying out a plan you approved): no
    propose_plan. `request` is your message, kept with a proposed plan."""
    from app.features.schedule import sync

    made: list[SdkMcpTool] = []
    # At the limit Opus stops and says what is left. In the chat, "continue" then carries on: the next
    # message brings this answer along (ask._prompt). A plan's run has no chat turn to carry on from.
    full = (f"ทำครบ {limit} อย่างในคำสั่งเดียวแล้ว · หยุดตรงนี้ บอกผู้ใช้ว่ายังเหลืออะไร (บอกชื่อให้ครบ) "
            + ("และพิมพ์ “ทำต่อ” ให้ทำที่เหลือได้" if planning else "ให้สั่งต่อในแชท"))

    def action(name: str, description: str, required: dict, optional: dict | None = None, *, acts: bool = True):
        def wrap(fn: Callable[[dict], Awaitable]):
            async def handler(args: dict) -> dict:
                if acts and taken.count >= limit:
                    return _text(full)
                try:
                    return _text(await fn(args))
                except ValueError as exc:  # what you asked for can't be done (as the page would say)
                    taken.notes.append(f"{name}: {exc}")
                    return _text(f"ทำไม่ได้: {exc}")
                except Exception as exc:  # Google down, a bug...: say so instead of failing the whole answer
                    log.exception("order tool %s failed", name)
                    taken.notes.append(f"{name}: {exc}")
                    return _text(f"ทำไม่สำเร็จ: {exc}")

            made.append(tool(name, description, _schema(required, optional))(handler))
            return fn
        return wrap

    async def planned(line_from: str = "") -> str:
        line = await sync.replan_if_on(via)
        return line or line_from or "รอบวางตารางปิดอยู่ จึงยังไม่ได้จองเวลา (เปิดได้ที่หน้าตั้งค่า)"

    # ---- 1. tasks and schedule
    @action("add_task", "เพิ่มงานของผู้ใช้ลงตาราง เลขาจะจองเวลาทำให้ก่อนกำหนดส่ง · ย้อนกลับได้",
            {"title": ("string", "ชื่องาน")},
            {"due": ("string", "กำหนดส่ง เวลาท้องถิ่น แบบ 2026-11-13T17:00 · ไม่ใส่ = ไม่มีกำหนด"),
             "est_minutes": ("integer", "เวลาทำรวมเป็นนาที · ไม่ใส่ = ค่าเริ่มต้นของตาราง"),
             "details": ("string", "รายละเอียด เช่น ส่งที่ไหน ลิงก์")})
    async def add_task(args):
        from app.features.schedule import tasks

        task_id, action_id = tasks.add(_str(args, "title"), due_at=_when(args, "due"), est_minutes=_num(args, "est_minutes"),
                                       details=_str(args, "details"), via=via)
        taken.done.append(action_id)
        return {"ทำแล้ว": f"เพิ่มงาน “{_str(args, 'title')}”", "id": task_id, "ตาราง": await planned()}

    @action("edit_task", "แก้งานที่มีอยู่ (ดู id จากเครื่องมือ tasks): ชื่อ กำหนดส่ง เวลาทำ รายละเอียด · ใส่เฉพาะที่แก้ · ย้อนกลับได้",
            {"task_id": ("integer", "id ของงาน")},
            {"title": ("string", "ชื่อใหม่"), "due": ("string", "กำหนดส่งใหม่ แบบ 2026-11-13T17:00"),
             "est_minutes": ("integer", "เวลาทำรวมใหม่ (นาที)"), "details": ("string", "รายละเอียดใหม่")})
    async def edit_task(args):
        from app.features.schedule import tasks

        changes = {}
        if _str(args, "title"):
            changes["title"] = _str(args, "title")
        if _str(args, "due"):
            changes["due_at"] = _when(args, "due")
        if _num(args, "est_minutes"):
            changes["est_minutes"] = _num(args, "est_minutes")
        if _str(args, "details"):
            changes["details"] = _str(args, "details")
        if not changes:
            raise ValueError("ไม่มีอะไรให้แก้")
        task_id = _need(args, "task_id")
        taken.done.append(tasks.edit(task_id, via=via, **changes))
        if {"title", "details"} & changes.keys():
            await sync.retext(task_id)  # the blocks already in the calendar say the new text too
        return {"ทำแล้ว": "แก้งานแล้ว", "id": task_id, "ตาราง": await planned()}

    @action("finish_task", "บันทึกว่างานเสร็จแล้ว: ไม่จองเวลาและไม่เตือนอีก · ย้อนกลับได้", {"task_id": ("integer", "id ของงาน")})
    async def finish_task(args):
        from app.features.schedule import tasks

        taken.done.append(tasks.done(_need(args, "task_id"), via=via))
        return {"ทำแล้ว": "ปิดงานแล้ว", "ตาราง": await planned()}

    @action("add_event", "ลงนัดหรือกิจกรรมใน Google Calendar หลักของผู้ใช้ (เลขาเตือนก่อนถึงเวลา และวางงานหลบให้) · ย้อนกลับได้ (ลบออกจากปฏิทิน)",
            {"title": ("string", "ชื่อนัด"), "start": ("string", "เริ่ม แบบ 2026-11-12T10:00 · ทั้งวันใส่แค่วันที่ 2026-11-12"),
             "end": ("string", "จบ แบบ 2026-11-12T11:00 · ทั้งวันใส่วันสุดท้าย")},
            {"all_day": ("boolean", "ทั้งวัน"), "location": ("string", "สถานที่"), "details": ("string", "รายละเอียด")})
    async def add_event(args):
        from datetime import date

        from app.features.schedule import events

        if args.get("all_day"):
            try:
                start, end = events.whole_days(date.fromisoformat(_str(args, "start")[:10]), date.fromisoformat(_str(args, "end")[:10]))
            except ValueError:
                raise ValueError("วันที่ต้องเป็นแบบ 2026-11-12")
        else:
            start, end = _when(args, "start"), _when(args, "end")
            if not (start and end):
                raise ValueError("ใส่ทั้งเวลาเริ่มและเวลาจบ")
        event_id, action_id = await events.add(_str(args, "title"), start, end, all_day=bool(args.get("all_day")),
                                               location=_str(args, "location"), description=_str(args, "details"), via=via)
        taken.done.append(action_id)
        return {"ทำแล้ว": f"ลงปฏิทินแล้ว: {_str(args, 'title')}", "id": event_id, "ตาราง": await planned()}

    @action("keep_free", "ตั้งกติกาไม่วางบล็อกงานช่วงหนึ่งของทุกสัปดาห์ เช่น บ่ายวันอังคาร · ย้อนกลับได้",
            {"weekday": ("integer", "0 = จันทร์ … 6 = อาทิตย์"), "part": ("string", "เช้า (06–12) · บ่าย (12–17) · เย็น (17–24)")})
    async def keep_free(args):
        from app.features.time import followed

        _, action_id = followed.avoid_rule(_need(args, "weekday"), _str(args, "part"), via=via)
        taken.done.append(action_id)
        return {"ทำแล้ว": "ตั้งกติกาแล้ว · ตารางใหม่จะหลบช่วงนี้", "ตาราง": await planned()}

    @action("replan", "วางตารางใหม่ทั้งหมดตอนนี้ (ย้ายบล็อกงานที่ยังไม่ถึงเวลา) · ย้อนกลับไม่ได้: รอผู้ใช้ยืนยัน", {})
    async def replan(args):
        return ask_first("replan", {}, "วางตารางใหม่ทั้งหมด (ย้ายบล็อกงานที่ยังไม่ถึงเวลา)", via, taken)

    # ---- 2. people
    @action("set_person_level", "ตั้งระดับคนในทะเบียน (ดู id จาก people_and_mail): important · interested · ignored "
            "· คนสำคัญใส่ days ได้ (กี่วัน) และ note (เหตุผล) · ย้อนกลับได้",
            {"person_id": ("integer", "id ของคน"), "level": ("string", "important · interested · ignored")},
            {"days": ("integer", "สำคัญกี่วัน · ไม่ใส่ = ไม่มีวันหมด"), "note": ("string", "เหตุผลที่สำคัญ")})
    async def set_person_level(args):
        from app.features.mail import people
        from app.features.mail.tables import Person

        level = _str(args, "level")
        if level not in LEVEL_WORDS:
            raise ValueError("level ต้องเป็น important · interested · ignored")
        person_id = _need(args, "person_id")
        taken.done.append(people.set_level(person_id, level, days=_num(args, "days"), note=_str(args, "note") or None, via=via))
        with session() as s:
            name = s.get(Person, person_id).name
        return {"ทำแล้ว": f"{name}: {LEVEL_WORDS[level]}"}

    @action("add_person", "เพิ่มคนสำคัญเข้าทะเบียนจากอีเมล ก่อนที่เขาจะเขียนมา · ย้อนกลับได้",
            {"address": ("string", "อีเมล")},
            {"name": ("string", "ชื่อ"), "days": ("integer", "สำคัญกี่วัน · ไม่ใส่ = 90 · 0 = ไม่มีวันหมด"), "note": ("string", "เหตุผล")})
    async def add_person(args):
        from app.features.mail import people

        address = _str(args, "address")
        if "@" not in address:
            raise ValueError("ใส่อีเมลให้ถูกต้อง")
        days = _num(args, "days")
        person_id, action_id = people.add(address, _str(args, "name"), days=90 if days is None else (days or None),
                                          note=_str(args, "note"), via=via)
        taken.done.append(action_id)
        return {"ทำแล้ว": f"เพิ่ม {_str(args, 'name') or address} เป็นคนสำคัญแล้ว", "id": person_id}

    @action("close_followup", "ปิดเรื่องค้าง (ดู id จาก waiting_replies) เมื่อตอบแล้วหรือไม่ต้องตามแล้ว · ย้อนกลับได้",
            {"followup_id": ("integer", "id ของเรื่องค้าง")})
    async def close_followup(args):
        from app.features.mail import followups

        taken.done.append(followups.done(_need(args, "followup_id"), via=via))
        return {"ทำแล้ว": "ปิดเรื่องค้างแล้ว"}

    # ---- 3. ideas
    @action("add_idea", "จดไอเดียลงคลัง (ใส่ #แท็กในข้อความได้ เลขาจัดกลุ่มรอบเที่ยงและเที่ยงคืน) · ย้อนกลับได้",
            {"text": ("string", "ไอเดียตามที่ผู้ใช้พูด")})
    async def add_idea(args):
        from app.features.ideas import store

        out = store.jot(_str(args, "text"), via=via)
        taken.done.append(out["action_id"])
        return {"ทำแล้ว": "จดไอเดียแล้ว", "แท็ก": out["tags"], "กลุ่มที่น่าจะเข้า": (out["group"] or {}).get("name", "")}

    # ---- 4. rules
    @action("add_rule", "ตั้งกติกาจากประโยคของผู้ใช้ (เช่น ไม่รับนัดวันอาทิตย์ · ห้ามงานเบื้องหลังลงโปรแกรมใหม่) "
            "เข้าสมุดกติกา หรือปรับค่าที่ตรงกัน · ย้อนกลับได้",
            {"sentence": ("string", "กติกาเป็นประโยคเดียว")})
    async def add_rule(args):
        from app.features import rule_sentences

        out, tokens = await rule_sentences.from_sentence(_str(args, "sentence"), via=via)
        taken.tokens += tokens
        taken.done.append(out["action_id"])
        return {"ทำแล้ว": f"ตั้งกติกาแล้ว: {out['text']}", "ผล": out["why"]}

    # ---- 5. projects
    @action("continue_project", "สั่งงานเบื้องหลังให้ทำต่อในโปรเจค (ดู id จาก projects) เหมือนปุ่มทำต่อที่หน้าโปรเจค: "
            "เลขาวางแผนทันที แล้วทำเองตามกฎหรือส่งขออนุมัติใน #อนุมัติ · ทำได้เฉพาะโปรเจคที่เปิดให้เลขาทำต่อได้ · ย้อนกลับได้ก่อนเริ่ม",
            {"project_id": ("integer", "id ของโปรเจค")}, {"note": ("string", "ให้ทำอะไร ถ้าผู้ใช้บอก")})
    async def continue_project(args):
        from app.features.jobs import plan as plans
        from app.features.jobs import queue

        job_id, action_id = queue.add(_need(args, "project_id"), _str(args, "note"), via=via)
        taken.done.append(action_id)
        try:
            verdict = await plans.make(job_id, via=via)
        except Exception as exc:  # the job waits in the queue for plan now, as on the page
            return {"ทำแล้ว": "ใส่คิวแล้ว", "แผน": f"วางแผนไม่สำเร็จ: {exc}"}
        return {"ทำแล้ว": "ใส่คิวและวางแผนแล้ว", "แผน": verdict.why, "ทำเองได้": verdict.go}

    @action("set_project", "แก้สถานะหรือระดับของโปรเจค (ดู id จาก projects) · ใส่เฉพาะที่แก้ · ย้อนกลับได้",
            {"project_id": ("integer", "id ของโปรเจค")},
            {"status": ("string", "idea · active · paused · auto · done"), "potential": ("string", "S A B C D E F"),
             "urgency": ("integer", "0 (ไม่รีบ) – 5 (เร่งสุด)")})
    async def set_project(args):
        from app.features.projects import edit

        changes = {k: v for k, v in (("status", _str(args, "status")), ("potential", _str(args, "potential").upper()),
                                     ("urgency", _num(args, "urgency"))) if v not in (None, "")}
        try:
            taken.done.append(edit.edit(_need(args, "project_id"), changes, via=via))
        except edit.EditError as exc:
            raise ValueError(str(exc)) from exc
        return {"ทำแล้ว": "แก้โปรเจคแล้ว"}

    @action("book_project_time", "จองเวลาทำขั้นถัดไปของโปรเจคในตาราง (เลขาหาช่องว่างแรก) · ย้อนกลับได้",
            {"project_id": ("integer", "id ของโปรเจค"), "minutes": ("integer", "กี่นาที (15–600)")})
    async def book_project_time(args):
        from app.features.projects import advice

        minutes = _num(args, "minutes") or 120
        if not 15 <= minutes <= 600:
            raise ValueError("เวลา 15 นาทีถึง 10 ชั่วโมง")
        task_id, action_id = advice.book(_need(args, "project_id"), minutes, via=via)
        taken.done.append(action_id)
        return {"ทำแล้ว": f"จองเวลา {minutes} นาทีแล้ว", "id": task_id, "ตาราง": await planned()}

    # ---- 6. what waits for you
    @action("answer_waiting", "ตอบเรื่องที่รอผู้ใช้ตัดสิน (ดู id และคำตอบที่ใช้ได้จาก pending_decisions) · "
            "บางคำตอบย้อนกลับไม่ได้ จะรอผู้ใช้กดยืนยันก่อน",
            {"decision_id": ("integer", "id ของเรื่อง"), "answer": ("string", "คำตอบตามที่ pending_decisions บอก")},
            {"potential": ("string", "S–F (ระดับโปรเจค)"), "urgency": ("integer", "0–5 (ระดับโปรเจค)")})
    async def answer_waiting(args):
        return await _answer(_need(args, "decision_id"), _str(args, "answer").lower(), args, via, taken)

    # ---- a plan instead of acting
    if planning:
        @action("propose_plan", "ใช้แทนการลงมือ เมื่อคำขอเป็นการวางแผนหลายขั้นหรือหลายวัน หรือยังไม่ชัดพอจะทำ: "
                "เก็บแผนไว้ให้ผู้ใช้กด ใช้แผนนี้ · แก้ · ไม่เอา (ยังไม่ทำอะไร) · เรียกครั้งเดียว และไม่ต้องลงมือทำอย่างอื่นในคำตอบเดียวกัน",
                {"title": ("string", "ชื่อแผนสั้นๆ"),
                 "plan": ("string", "ขั้นตอนเป็นรายการเลข 3–7 ข้อ แต่ละข้อบอกว่าใครทำ (เลขา หรือ คุณ) และเมื่อไร "
                                    "· ถ้ามีเวลาที่ผู้ใช้ต้องใช้ ปิดด้วยบรรทัด เวลาคุณ: …")}, acts=False)
        async def propose_plan(args):
            if taken.plan is not None:
                raise ValueError("เสนอแผนไปแล้วหนึ่งแผน")
            title, body = _str(args, "title") or "แผน", _str(args, "plan")
            if not body:
                raise ValueError("ใส่ขั้นตอนของแผน")
            with session() as s:
                d = Decision(kind="plan", title=title[:200], detail={"request": request, "plan": body, "started": False,
                                                                     "revises": None})
                s.add(d)
                s.flush()
                taken.plan = d.id
            return "เก็บแผนไว้ให้ผู้ใช้ตัดสินแล้ว · ตอบสั้นๆ ว่าวางแผนให้แล้ว ไม่ต้องเขียนแผนซ้ำ"

    return made


async def _answer(decision_id: int | None, answer: str, args: dict, via: Via, taken: Taken):
    """answer_waiting: the same answer as the item's own buttons, or a request for confirmation."""
    with session() as s:
        d = s.get(Decision, decision_id) if decision_id else None
        if d is None:
            raise ValueError("ไม่พบเรื่องนี้")
        if d.status != "pending":
            raise ValueError("เรื่องนี้ตอบไปแล้ว")
        kind, title, detail = d.kind, d.title, dict(d.detail or {})
    if kind == "order":
        raise ValueError("คำสั่งที่รอยืนยัน ผู้ใช้ต้องกดปุ่มทำเลยหรือไม่เอาเอง")
    if kind == "weekly":
        acts = dict(detail.get("acts", []))
        if answer not in acts:
            raise ValueError(f"หัวข้อนี้ตอบได้: {', '.join(acts)}")
        return ask_first("weekly", {"decision_id": decision_id, "act": answer}, f"ทบทวนรายสัปดาห์: {acts[answer]} · {title}",
                         via, taken)
    answers = ANSWERS.get(kind, {})
    if answer not in answers:
        raise ValueError(f"ตอบได้: {', '.join(answers)}" if answers else "เรื่องนี้ผู้ใช้ต้องตอบที่ปุ่มของมันเอง")

    if kind == "appointment" and answer == "decline":
        return ask_first("decline", {"decision_id": decision_id}, f"ไม่ไปนัด “{title}”", via, taken)
    if kind == "idea" and answer == "project":
        return ask_first("idea_project", {"group_id": detail["group_id"]}, f"เปิดโปรเจคจากกลุ่มไอเดีย “{title}”", via, taken)
    if kind == "plan" and answer == "approve":
        return ask_first("plan_approve", {"decision_id": decision_id}, f"ใช้แผน “{title}” (เลขาลงมือทำตามแผน)", via, taken)

    if kind == "appointment":
        from app.features.mail import extract

        _, action_id = await extract.decide(decision_id, True, via=via)
        said = f"รับนัด “{title}” ลงปฏิทินแล้ว"
    elif kind == "course":
        from app.features.classroom import sync as classroom

        _, action_id = await classroom.decide(decision_id, answer == "follow", via=via)
        said = f"{'ติดตาม' if answer == 'follow' else 'ไม่ติดตาม'}วิชา {title} แล้ว"
    elif kind == "project_level":
        from app.features.projects import scan

        urgency = _num(args, "urgency")
        _, action_id = scan.set_levels(decision_id, _str(args, "potential").upper(), -1 if urgency is None else urgency, via=via)
        said = f"ตั้งระดับโปรเจค {title} แล้ว"
    elif kind == "job":
        from app.features.jobs import plan as plans

        _, action_id = plans.answer(decision_id, answer == "approve", via=via)
        said = f"{'อนุมัติ' if answer == 'approve' else 'ไม่เอา'}แผนงานเบื้องหลัง “{title}” แล้ว"
    elif kind == "idea":
        from app.features.ideas import groups

        try:
            action_id = groups.make_task(detail["group_id"], via=via)[1] if answer == "task" else groups.later(detail["group_id"], via=via)
        except groups.AnswerError as exc:
            raise ValueError(str(exc)) from exc
        said = f"กลุ่มไอเดีย “{title}”: {ANSWERS['idea'][answer]}"
    else:  # plan · reject
        from app.features import ask

        _, action_id = ask.decide(decision_id, "reject", via=via)
        said = f"ไม่เอาแผน “{title}”"
    if action_id:
        taken.done.append(action_id)
    await _settle(decision_id, via)
    return {"ทำแล้ว": said}
