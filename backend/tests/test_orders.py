"""B9's orders in the chat: what each order does, that it can be undone, and what has to wait for
ยืนยัน (no model here: the tools are called directly, and Opus is faked where it's needed)."""

import asyncio

import pytest
from sqlalchemy import delete, select

from app.core import actions, db
from app.core.db import now, session
from app.core.tables import Action
from app.features.ideas import store
from app.features.ideas.tables import Idea
from app.features.mail import followups
from app.features.mail.tables import Followup, Person


@pytest.fixture(scope="module", autouse=True)
def _db():
    db.migrate()


def undo(action_id: int) -> None:
    asyncio.run(actions.undo(action_id))


# ------------------------------------------------------------------ B9.2: undo for what had none
def test_an_idea_jotted_from_the_chat_is_recorded_and_undo_removes_it():
    out = store.jot("ให้เลขาอ่านสรุปเช้าเป็นเสียง #เสียง", via=("#คุยกับเลขา", "https://discord.com/x"))
    with session() as s:
        idea = s.get(Idea, out["id"])
        assert (idea.source, idea.tags, idea.tagged) == ("chat", ["เสียง"], "")  # the round tags the rest
        a = s.get(Action, out["action_id"])
        assert (a.kind, a.source_label) == ("idea.add", "#คุยกับเลขา")
    undo(out["action_id"])
    with session() as s:
        assert s.get(Idea, out["id"]) is None


def test_closing_a_followup_is_recorded_once_and_undo_opens_it_again():
    with session() as s:
        p = Person(name="od-อ.ธนา", level="important")
        s.add(p)
        s.flush()
        f = Followup(account="you", person_id=p.id, thread_id="od-t1", subject="ส่งร่างบทที่ 2", waiting_on="you", since=now())
        s.add(f)
        s.flush()
        fid, pid = f.id, p.id
    try:
        action_id = followups.done(fid, via=("#คุยกับเลขา", ""))
        with session() as s:
            assert s.get(Followup, fid).closed_at is not None
            assert s.get(Action, action_id).target == "od-อ.ธนา: ส่งร่างบทที่ 2"
        with pytest.raises(ValueError, match="ปิดไปแล้ว"):
            followups.done(fid)
        undo(action_id)
        with session() as s:
            assert s.get(Followup, fid).closed_at is None
    finally:
        with session() as s:
            s.execute(delete(Followup).where(Followup.id == fid))
            s.execute(delete(Person).where(Person.id == pid))
