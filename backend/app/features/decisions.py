"""เรื่องที่รอคุณตัดสิน in one place (B4): every request waiting for your yes or no (plans B1,
appointments B2, Classroom courses B3) lives in `decisions`, and the bell, the today page and
#อนุมัติ all answer it through the same functions, so the result is the same wherever you
press. This module keeps the two places looking the same too: a request answered on the web
gets its #อนุมัติ card edited to say so, without its buttons, instead of looking open.

It also tells whether an appointment that waits for you clashes with another one (W1:
"ไม่ชนนัดอื่น"), so you can answer without opening the calendar, and whether it goes against a
rule in your rule book (B5: "คุณมักไม่รับนัดวันเสาร์").
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.connectors import discord_bot as dc
from app.core.db import session
from app.core.tables import Decision, Event, Message

log = logging.getLogger(__name__)

SETTLED = {
    ("appointment", "approved"): "✅ รับนัดแล้ว · ลงปฏิทินแล้ว", ("appointment", "rejected"): "ไม่ไปนัดนี้",
    ("course", "approved"): "✅ ติดตามวิชานี้แล้ว", ("course", "rejected"): "ไม่ติดตามวิชานี้",
    ("plan", "approved"): "✅ อนุมัติแผนแล้ว", ("plan", "rejected"): "ไม่เอาแผนนี้",
    ("project_level", "approved"): "✅ ตั้งระดับโปรเจคแล้ว",
    ("job", "approved"): "✅ อนุมัติแผนแล้ว · ใช้ได้ 3 วัน", ("job", "rejected"): "ไม่เอาแผนนี้",
    ("job", "revised"): "แก้แผนแล้ว · แผนใหม่ส่งตามมา", ("job", "cancelled"): "งานนี้ออกจากคิวแล้ว",
}


async def settle_card(decision_id: int, where: str = "หน้าเว็บ") -> None:
    """After an answer on the web: edit the request's #อนุมัติ message to say how it went (best
    effort: when Discord is down, the card only keeps its buttons, which then say it's settled)."""
    with session() as s:
        d = s.get(Decision, decision_id)
        m = s.get(Message, d.message_id) if d is not None and d.message_id else None
        text = SETTLED.get((d.kind, d.status)) if d is not None else None
        target = (m.channel, m.discord_id) if m is not None else None
    if not (text and target) or not dc.bot.ready_event.is_set() or dc.bot.is_closed():
        return
    channel = dc.bot.channels.get(target[0])
    if channel is None:
        return
    try:
        await channel.get_partial_message(target[1]).edit(content=f"{text} (ตอบจาก{where})", view=None)
    except Exception as exc:
        log.warning("couldn't update the card of decision %s: %s", decision_id, exc)


def clashes(decisions: list[Decision]) -> dict[int, str]:
    """For each waiting appointment: "" when nothing else is at that time, else what is."""
    out: dict[int, str] = {}
    with session() as s:
        for d in decisions:
            if d.kind != "appointment" or not (ev := s.get(Event, d.detail.get("event_id"))):
                continue
            other = s.scalars(select(Event.title).where(Event.status == "placed", Event.id != ev.id, Event.all_day.is_(False),
                                                        Event.starts_at < ev.ends_at, Event.ends_at > ev.starts_at)).all()
            out[d.id] = " · ".join(other)
    return out


def rule_notes(decisions: list[Decision]) -> dict[int, str]:
    """For each waiting appointment: the rule of yours it goes against, or "" (B5, the rule book)."""
    from app.core.rules import book

    out: dict[int, str] = {}
    with session() as s:
        for d in decisions:
            if d.kind == "appointment" and (ev := s.get(Event, d.detail.get("event_id"))):
                out[d.id] = book.appointment_note(ev.starts_at)
    return out
