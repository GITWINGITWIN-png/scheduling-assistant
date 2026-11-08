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


# ------------------------------------------------------------------ B9.3: the chat's action tools
import json  # noqa: E402

from app.connectors import gcal  # noqa: E402
from app.core import clock, llm  # noqa: E402
from app.core.rules import book  # noqa: E402
from app.core.tables import Decision, Rule, Task  # noqa: E402
from app.core.timefmt import from_local  # noqa: E402
from app.features import ask_orders as orders  # noqa: E402
from app.features.projects.tables import Project  # noqa: E402
from app.features.schedule import sync  # noqa: E402

VIA = ("#คุยกับเลขา", "https://discord.com/channels/1/2/3")


@pytest.fixture
def calendar(monkeypatch):
    """A fake main calendar ({event id: title}), and the schedule round off."""
    written: dict[str, str] = {}

    def insert(title, start, end, *, all_day=False, location="", description="", calendar="primary", mark="appointment"):
        gid = f"g{len(written) + 1}"
        written[gid] = title
        return gid, f"https://calendar.google.com/event?eid={gid}"

    monkeypatch.setattr(gcal, "insert", insert)
    monkeypatch.setattr(gcal, "delete", lambda event_id, *, calendar="primary": written.pop(event_id, None))
    monkeypatch.setattr(clock, "enabled", lambda name: False)
    return written


def tools(taken=None, **kw):
    taken = taken if taken is not None else orders.Taken()
    return {t.name: t for t in orders.toolset(VIA, taken, request="คำขอทดสอบ", **kw)}, taken


def call(ts, name, **args):
    text = asyncio.run(ts[name].handler(args))["content"][0]["text"]
    try:
        return json.loads(text)
    except ValueError:
        return text


def action(action_id):
    with session() as s:
        return s.get(Action, action_id)


def test_the_tools_are_the_six_groups_and_nothing_that_deletes_sends_or_changes_settings():
    ts, _ = tools()
    assert set(ts) == {"add_task", "edit_task", "finish_task", "add_event", "keep_free", "replan",  # tasks and schedule
                       "set_person_level", "add_person", "close_followup",  # people
                       "add_idea", "add_rule",  # ideas, rules
                       "continue_project", "set_project", "book_project_time",  # projects
                       "answer_waiting", "propose_plan"}  # what waits for you · a plan instead
    assert "propose_plan" not in tools(planning=False)[0]  # carrying out a plan: act, don't plan again


def test_a_task_from_the_chat_is_the_pages_task_and_undo_drops_it(calendar):
    ts, taken = tools()
    out = call(ts, "add_task", title="od-รายงาน datacom", due="2026-11-13T17:00", est_minutes=120)
    assert out["ทำแล้ว"] == "เพิ่มงาน “od-รายงาน datacom”" and "รอบวางตารางปิดอยู่" in out["ตาราง"]
    with session() as s:
        t = s.get(Task, out["id"])
        assert (t.due_at, t.est_minutes, t.source) == (from_local("2026-11-13T17:00"), 120, "you")
    a = action(taken.done[0])
    assert (a.kind, a.source_label, a.source_url) == ("task.add", "#คุยกับเลขา", VIA[1])
    assert call(ts, "edit_task", task_id=out["id"], est_minutes=180)["ทำแล้ว"] == "แก้งานแล้ว"
    assert call(ts, "edit_task", task_id=out["id"]) == "ทำไม่ได้: ไม่มีอะไรให้แก้"
    assert call(ts, "finish_task", task_id=out["id"])["ทำแล้ว"] == "ปิดงานแล้ว"
    assert call(ts, "add_task", title="x", due="ศุกร์หน้า").startswith("ทำไม่ได้: due ต้องเป็นวันเวลา")
    assert len(taken.done) == 3
    for action_id in reversed(taken.done):
        undo(action_id)
    with session() as s:
        assert s.get(Task, out["id"]).status == "dropped"


def test_an_event_goes_into_the_calendar_and_undo_takes_it_out(calendar):
    ts, taken = tools()
    out = call(ts, "add_event", title="od-นัดอาจารย์", start="2026-11-12T10:00", end="2026-11-12T11:00")
    assert out["ทำแล้ว"] == "ลงปฏิทินแล้ว: od-นัดอาจารย์" and list(calendar.values()) == ["od-นัดอาจารย์"]
    assert call(ts, "add_event", title="x", start="2026-11-12T10:00", end="2026-11-12T09:00") == "ทำไม่ได้: เวลาจบต้องหลังเวลาเริ่ม"
    undo(taken.done[0])
    assert calendar == {}


def test_what_cant_be_undone_waits_for_yes_and_runs_once(monkeypatch):
    ran = []

    async def replan_now(via):
        ran.append(via)
        return "ย้าย 2 บล็อก"
    monkeypatch.setattr(sync, "replan_now", replan_now)
    ts, taken = tools()
    said = call(ts, "replan")
    assert said.startswith("ยังไม่ได้ทำ: “วางตารางใหม่ทั้งหมด") and ran == [] and taken.done == []
    decision_id = taken.confirm[0]
    with session() as s:
        assert (s.get(Decision, decision_id).kind, s.get(Decision, decision_id).status) == ("order", "pending")
    assert asyncio.run(orders.confirm(decision_id, True, via=("ปุ่มยืนยัน", ""))) == "วางตารางใหม่แล้ว · ย้าย 2 บล็อก"
    assert ran == [("ปุ่มยืนยัน", "")]
    with pytest.raises(orders.ConfirmError, match="ตอบไปแล้ว"):
        asyncio.run(orders.confirm(decision_id, True, via=VIA))  # a second press doesn't run it again
    call(ts, "replan")
    assert asyncio.run(orders.confirm(taken.confirm[1], False, via=VIA)).startswith("ไม่ทำแล้ว") and len(ran) == 1
    call(ts, "replan")
    with session() as s:
        s.get(Decision, taken.confirm[2]).created_at = now() - orders.ORDER_LIFE * 2
    with pytest.raises(orders.ConfirmError, match="หมดเวลา"):
        asyncio.run(orders.confirm(taken.confirm[2], True, via=VIA))
    assert len(ran) == 1


def test_a_failed_yes_waits_again(monkeypatch):
    async def broken(via):
        raise RuntimeError("Google ไม่ตอบ")
    monkeypatch.setattr(sync, "replan_now", broken)
    ts, taken = tools()
    call(ts, "replan")
    with pytest.raises(orders.ConfirmError, match="ทำไม่สำเร็จ: Google ไม่ตอบ"):
        asyncio.run(orders.confirm(taken.confirm[0], True, via=VIA))
    with session() as s:
        assert s.get(Decision, taken.confirm[0]).status == "pending"  # press again once Google is back


def test_people_orders_change_the_registry_and_undo_puts_it_back():
    with session() as s:
        p = Person(name="od-อ.วิภา", level="interested")
        s.add(p)
        s.flush()
        pid = p.id
    try:
        ts, taken = tools()
        out = call(ts, "set_person_level", person_id=pid, level="important", days=30, note="ที่ปรึกษาโปรเจคจบ")
        assert out == {"ทำแล้ว": "od-อ.วิภา: สำคัญ"}
        with session() as s:
            person = s.get(Person, pid)
            assert (person.level, person.note) == ("important", "ที่ปรึกษาโปรเจคจบ") and person.level_until is not None
        assert call(ts, "set_person_level", person_id=pid, level="boss").startswith("ทำไม่ได้: level ต้องเป็น")
        undo(taken.done[0])
        with session() as s:
            assert s.get(Person, pid).level == "interested"
        assert call(ts, "add_person", address="ไม่ใช่อีเมล") == "ทำไม่ได้: ใส่อีเมลให้ถูกต้อง"
    finally:
        with session() as s:
            s.execute(delete(Person).where(Person.name.like("od-%")))


def test_a_rule_from_a_sentence_is_read_by_the_rule_reader_and_kept(monkeypatch):
    async def fake_run(task, prompt, **kw):
        assert task == "rule"
        return llm.Reply(text='{"type": "appointment_days", "text": "od-ไม่รับนัดวันอาทิตย์", "weekdays": [6]}',
                         model="claude-sonnet-5-5", effort="low", tokens_in=300, tokens_out=40)
    monkeypatch.setattr(llm, "run", fake_run)
    ts, taken = tools()
    out = call(ts, "add_rule", sentence="ไม่รับนัดวันอาทิตย์")
    assert out["ทำแล้ว"] == "ตั้งกติกาแล้ว: od-ไม่รับนัดวันอาทิตย์" and taken.tokens == 340
    with session() as s:
        assert s.scalar(select(Rule).where(Rule.text == "od-ไม่รับนัดวันอาทิตย์")) is not None
    undo(taken.done[0])
    assert all(r["text"] != "od-ไม่รับนัดวันอาทิตย์" for r in (book.view(r) for r in _active_rules()))


def _active_rules():
    with session() as s:
        return [r for r in s.scalars(select(Rule)) if r.enabled]


def test_background_work_only_in_projects_you_opened_and_the_chat_cant_open_one():
    with session() as s:
        p = Project(name="od-finance", path="/tmp/od-finance", is_git=True, allow_jobs=False)
        s.add(p)
        s.flush()
        pid = p.id
    try:
        ts, taken = tools()
        assert call(ts, "continue_project", project_id=pid) == "ทำไม่ได้: ยังไม่ได้เปิด “ให้เลขาทำต่อได้” ที่หน้าโปรเจค"
        out = call(ts, "set_project", project_id=pid, urgency=4, allow_jobs=True)  # allow_jobs isn't one of its fields
        assert out == {"ทำแล้ว": "แก้โปรเจคแล้ว"}
        with session() as s:
            assert (s.get(Project, pid).urgency, s.get(Project, pid).allow_jobs) == (4, False)
    finally:
        with session() as s:
            s.execute(delete(Project).where(Project.id == pid))


def test_answering_what_waits_does_the_same_as_its_buttons_or_waits_for_yes():
    with session() as s:
        plan = Decision(kind="plan", title="od-แผนสอบ", detail={"plan": "1. ...", "started": False})
        weekly = Decision(kind="weekly", title="od-ปรับตาราง", detail={"acts": [["approve", "ทำตามนี้"], ["reject", "ไม่เอา"]]})
        appt = Decision(kind="appointment", title="od-นัดคุยงาน", detail={"event_id": 0})
        order = Decision(kind="order", title="od-วางตารางใหม่", detail={"do": "replan", "args": {}})
        s.add_all([plan, weekly, appt, order])
        s.flush()
        ids = plan.id, weekly.id, appt.id, order.id
    ts, taken = tools()
    assert orders.waiting_view(_get(ids[1]))["ตอบได้"] == {"approve": "ทำตามนี้", "reject": "ไม่เอา"}
    assert call(ts, "answer_waiting", decision_id=ids[3], answer="approve").startswith("ทำไม่ได้: คำสั่งที่รอยืนยัน")
    for decision_id, answer in ((ids[0], "approve"), (ids[1], "approve"), (ids[2], "decline")):
        assert call(ts, "answer_waiting", decision_id=decision_id, answer=answer).startswith("ยังไม่ได้ทำ")
    assert [_get(i).detail["do"] for i in taken.confirm] == ["plan_approve", "weekly", "decline"]
    assert call(ts, "answer_waiting", decision_id=ids[1], answer="both") == "ทำไม่ได้: หัวข้อนี้ตอบได้: approve, reject"
    assert call(ts, "answer_waiting", decision_id=ids[0], answer="reject") == {"ทำแล้ว": "ไม่เอาแผน “od-แผนสอบ”"}
    assert _get(ids[0]).status == "rejected" and action(taken.done[0]).kind == "plan.reject"


def _get(decision_id):
    with session() as s:
        d = s.get(Decision, decision_id)
        s.expunge(d)
        return d


def test_one_order_stops_after_its_limit():
    ts, taken = tools(limit=2)
    call(ts, "add_idea", text="od-ไอเดีย 1")
    call(ts, "add_idea", text="od-ไอเดีย 2")
    assert call(ts, "add_idea", text="od-ไอเดีย 3").startswith("ทำครบ 2 อย่าง")
    with session() as s:
        assert s.scalar(select(Idea).where(Idea.text == "od-ไอเดีย 3")) is None
        s.execute(delete(Idea).where(Idea.text.like("od-%")))
