"""B6's ideas store: the tag rules (no model), the doors (popup, page, #ไอเดีย) and the popup's outbox."""

import asyncio
import json
from types import SimpleNamespace

import discord
import pytest
from sqlalchemy import delete, select

from app.core import db
from app.core.db import session
from app.features.ideas import cards, store
from app.features.ideas.tables import Idea, IdeaGroup


@pytest.fixture(scope="module", autouse=True)
def _db():
    db.migrate()


@pytest.fixture(autouse=True)
def _empty():
    with session() as s:
        s.execute(delete(Idea))
        s.execute(delete(IdeaGroup))


# ------------------------------------------------------------------ the tag rules
def test_hashtags_keep_thai_vowels_and_skip_urls_and_code_names():
    # Thai vowel and tone marks aren't \w in Python: a plain \w+ would cut #เสียง to #เส
    assert store.hashtags("ให้เลขาอ่านเป็น #เสียง และ #เลขา ด้วย") == ["เสียง", "เลขา"]
    assert store.hashtags("#Backtest ข้ามตลาด #backtest.") == ["backtest"]
    assert store.hashtags("ดู https://x.com/page#part และ app/#/route หรือ C# ก็ได้") == []


def test_project_names_match_whatever_the_separator_but_latin_words_stand_alone():
    projects = {"research-lab": "research-lab", "my_secretary": "my_secretary", "data-mining": "data mining", "art": "art"}
    assert store.suggest("อยากให้ feed Research_Lab มีภาพ", projects=projects, known=[]) == ["research-lab"]
    assert store.suggest("my secretary พูดได้", projects=projects, known=[]) == ["my_secretary"]
    assert store.suggest("สรุป data-mining HW3", projects=projects, known=[]) == ["data-mining"]
    assert store.suggest("start the engine", projects=projects, known=[]) == []  # "art" is inside "start"


def test_the_tags_you_already_use_are_found_inside_thai_text():
    known = ["เสียง", "เลขา", "ai"]  # "ai" is too short to look for: it would be in everything
    assert store.suggest("ให้เลขาอ่านสรุปเช้าเป็นเสียงตอนเปิดคอม", projects={}, known=known) == ["เสียง", "เลขา"]
    assert store.suggest("#podcast สรุปเป็นเสียง", projects={}, known=known) == ["podcast", "เสียง"]  # #tags first


def test_the_group_is_a_tag_that_isnt_a_project_and_the_biggest_group_wins():
    projects = {"finance": "Finance"}
    assert store.primary(["finance", "backtest"], projects) == "backtest"
    assert store.primary(["finance"], projects) == "finance"
    assert store.primary([], projects) is None
    assert store.primary(["เสียง", "เลขา"], projects) == "เสียง"  # no group yet: the first
    assert store.primary(["เสียง", "เลขา"], projects, {"เลขา": 3}) == "เลขา"  # join the one that's growing
    assert store.primary(["เสียง", "เลขา"], projects, {"เลขา": 3, "เสียง": 3}) == "เสียง"  # a tie: the first


# ------------------------------------------------------------------ the doors
def test_tags_from_the_popup_are_final_but_a_discord_message_waits_for_the_round():
    popup = store.add("ให้เลขาพูดสรุป #เสียง", source="key", tags=["เลขา"])
    assert popup["tags"] == ["เลขา", "เสียง"]  # what you kept, then what you typed
    plain = store.add("แอปจดรายจ่าย", source="discord", source_ref="111")
    typed = store.add("backtest หลายตลาด #backtest", source="discord", source_ref="112")
    kept_none = store.add("จัดห้องทำงาน", source="web", tags=[])  # you removed every suggestion
    with session() as s:
        rows = {i.id: (i.tags, i.tagged) for i in s.scalars(select(Idea))}
    assert rows[popup["id"]] == (["เลขา", "เสียง"], "you")
    assert rows[plain["id"]] == ([], "")  # the next round looks at it
    assert rows[typed["id"]] == (["backtest"], "")  # your #tag, and the round may add a project after it
    assert rows[kept_none["id"]] == ([], "you")  # final: the round must not add them back
    assert popup["group"] == {"name": "เลขา", "size": 1, "new": True, "tag": "เลขา"}
    with pytest.raises(ValueError):
        store.add("   ", source="web")


def test_a_message_in_ideas_is_kept_and_marked_and_edit_and_delete_follow_it():
    reactions, replies = [], []

    async def react(emoji):
        reactions.append(emoji)

    msg = SimpleNamespace(id=555, content="สรุป paper เป็น podcast #podcast", attachments=[], add_reaction=react)
    asyncio.run(cards.on_idea(msg))
    assert reactions == ["✅"]
    idea_id = store.by_ref("555")
    asyncio.run(cards.on_edit(555, "สรุป paper เป็นคลิปเสียง #เสียง"))
    with session() as s:
        idea = s.get(Idea, idea_id)
        assert (idea.text, idea.tags) == ("สรุป paper เป็นคลิปเสียง #เสียง", ["เสียง"])  # its #tags follow the text
    asyncio.run(cards.on_delete(555))
    assert store.by_ref("555") is None

    async def refuse(emoji):  # a server where the bot may not add reactions
        raise discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Missing Permissions")

    async def reply(text, mention_author):
        replies.append(text)
        return SimpleNamespace(id=1, content=text, embeds=[])

    asyncio.run(cards.on_idea(SimpleNamespace(id=556, content="จัดห้องทำงาน", attachments=[], add_reaction=refuse, reply=reply)))
    assert replies == ["✓ จดแล้ว"] and store.by_ref("556") is not None


def test_the_outbox_is_taken_in_once_and_a_bad_line_is_put_aside():
    box = store.outbox()
    box.write_text("\n".join([
        json.dumps({"text": "จดตอนเลขาปิดอยู่", "tags": ["เลขา"], "at": "2026-11-06T09:00:00+07:00"}, ensure_ascii=False),
        "not json",
        json.dumps({"text": "อีกอัน"}, ensure_ascii=False),
    ]) + "\n", encoding="utf-8")
    assert store.import_outbox() == 2
    assert store.import_outbox() == 0  # nothing twice
    assert not box.exists() and box.with_name(box.name + ".bad").read_text().strip() == "not json"
    with session() as s:
        kept = {i.text: (i.source, i.tags, i.tagged) for i in s.scalars(select(Idea))}
    assert kept["จดตอนเลขาปิดอยู่"] == ("key", ["เลขา"], "you") and kept["อีกอัน"] == ("key", [], "")
    box.with_name(box.name + ".bad").unlink()


# ------------------------------------------------------------------ the round and the grown groups (step 3)
from app.core import actions  # noqa: E402
from app.core.config import get_config  # noqa: E402
from app.core.tables import Decision, Task  # noqa: E402
from app.features.ideas import groups  # noqa: E402
from app.features.projects.tables import Project  # noqa: E402


@pytest.fixture
def projects(tmp_path, monkeypatch):
    monkeypatch.setattr(get_config(), "projects_dir", tmp_path)
    with session() as s:
        s.execute(delete(Project))
        s.add(Project(name="Finance", path=str(tmp_path / "Finance"), status="active", progress={}))
    yield tmp_path
    with session() as s:
        s.execute(delete(Project))


def _round():
    return asyncio.run(groups.run())


def test_the_round_tags_what_nobody_tagged_and_groups_by_the_first_non_project_tag(projects):
    a = store.add("backtest หลายตลาดใน finance #backtest", source="discord", source_ref="1")
    b = store.add("finance: backtest คริปโตด้วย", source="discord", source_ref="2")  # no #tag: the rules find both
    c = store.add("จัดห้องทำงาน", source="web", tags=[])  # yours, empty: stays without a group
    line = _round()
    with session() as s:
        ideas = {i.id: i for i in s.scalars(select(Idea))}
        g = s.scalar(select(IdeaGroup).where(IdeaGroup.tag == "backtest"))
    assert ideas[b["id"]].tags == ["finance", "backtest"] and ideas[b["id"]].tagged == "rules"
    assert ideas[a["id"]].group_id == ideas[b["id"]].group_id == g.id and g.name == "backtest"  # not one big "finance" group
    assert ideas[c["id"]].group_id is None and ideas[c["id"]].tags == []
    assert line == "เข้ากลุ่ม 2 ไอเดีย · ยังไม่มีแท็ก 1"
    assert _round() is None  # nothing new: says nothing


def test_a_grown_group_is_asked_once_and_not_yet_asks_again_after_two_more(projects):
    for n in range(groups.GROWN):
        store.add(f"ไอเดีย {n} #podcast", source="web")
    _round()
    with session() as s:
        g = s.scalar(select(IdeaGroup).where(IdeaGroup.tag == "podcast"))
        d = s.get(Decision, g.decision_id)
        assert (g.status, d.kind, d.status, d.detail["size"]) == ("asked", "idea", "pending", groups.GROWN)
    store.add("อีกอัน #podcast", source="web")
    assert "กลุ่มที่โตพอ" not in (_round() or "")  # already waiting: not asked twice
    groups.later(g.id)
    with session() as s:
        assert s.get(Decision, g.decision_id).status == "rejected" and s.get(IdeaGroup, g.id).asked_size == groups.GROWN + 1
    store.add("หนึ่ง #podcast", source="web")
    assert "กลุ่มที่โตพอ" not in (_round() or "")
    store.add("สอง #podcast", source="web")
    assert "กลุ่มที่โตพอ 1" in _round()  # grown by AGAIN_AFTER since "ยังก่อน"


def test_make_it_a_task_and_undo(projects):
    for n in range(groups.GROWN):
        store.add(f"backtest ตลาด {n} ใน finance #backtest", source="web")
    _round()
    with session() as s:
        g = s.scalar(select(IdeaGroup).where(IdeaGroup.tag == "backtest"))
    task_id, action_id = groups.make_task(g.id)
    with session() as s:
        task = s.get(Task, task_id)
        assert (task.source, task.project, task.title) == ("idea", "Finance", "backtest")
        assert task.details.startswith("จากกลุ่มไอเดีย “backtest”:\n- backtest ตลาด 0")
        assert s.get(Decision, g.decision_id).status == "approved"
    with pytest.raises(groups.AnswerError):
        groups.make_task(g.id)  # not twice
    asyncio.run(actions.undo(action_id))
    with session() as s:
        assert s.get(Task, task_id).status == "dropped"
        assert s.get(IdeaGroup, g.id).status == "asked" and s.get(Decision, g.decision_id).status == "pending"


def test_open_a_project_makes_the_folder_from_the_ideas(projects):
    for n in range(groups.GROWN):
        store.add(f"สรุป paper {n} เป็นเสียง #podcast", source="discord", source_ref=f"p{n}")
    _round()
    with session() as s:
        g = s.scalar(select(IdeaGroup).where(IdeaGroup.tag == "podcast"))
    assert groups.suggested_folder(g.id) == "podcast"
    (projects / "taken").mkdir()
    for bad in ("", "../x", ".hidden", "a/b", "taken"):
        with pytest.raises(groups.AnswerError):
            groups.open_project(g.id, bad)
    project_id, _ = groups.open_project(g.id, "paper-podcast")
    folder = projects / "paper-podcast"
    readme, progress = (folder / "README.md").read_text(), (folder / "PROGRESS.md").read_text()
    assert "# paper-podcast" in readme and "- สรุป paper 0 เป็นเสียง #podcast (#ไอเดีย," in readme
    assert "- [ ] เขียนเป้าหมายใน README.md" in progress and "- [ ] ลองไอเดีย: สรุป paper 3 เป็นเสียง #podcast" in progress
    with session() as s:
        p = s.get(Project, project_id)
        assert (p.status, p.path, p.progress["next"]) == ("idea", str(folder), "เขียนเป้าหมายใน README.md")
        assert s.get(IdeaGroup, g.id).status == "project" and s.get(Decision, g.decision_id).answer == "project"


def test_tags_changed_on_the_page_move_the_idea_at_once(projects):
    i = store.add("แอปจดรายจ่าย", source="web", tags=[])
    out = store.set_tags(i["id"], ["#ส่วนตัว", "เงิน"])
    with session() as s:
        idea = s.get(Idea, i["id"])
        assert idea.tags == ["ส่วนตัว", "เงิน"] and s.get(IdeaGroup, idea.group_id).tag == "ส่วนตัว"
    assert out["group"]["name"] == "ส่วนตัว" and out["group"]["size"] == 1


def test_the_round_cards_say_where_ideas_went_and_ask_with_three_buttons(projects):
    for n in range(groups.GROWN):
        store.add(f"ไอเดียเสียง {n} #เสียง", source="web")
    r = groups.Round(placed=groups.place())
    r.asked = [(gid, groups.propose(gid)) for gid in groups.ripe()]
    card = cards.round_card(r)
    assert card.title == f"เข้ากลุ่มแล้ว {groups.GROWN} ไอเดีย" and "→ “เสียง” (4)" in card.description
    embed, view = cards.ripe_card(r.asked[0][0])
    assert embed.title == "เสียง · 4 ไอเดีย" and embed.author.name == "กลุ่มที่โตพอ"
    assert [c.item.label for c in view.children] == ["เปิดโปรเจค", "ทำเป็นงาน", "ยังก่อน"]
    assert [c.item.custom_id for c in view.children] == [f"idea:{r.asked[0][0]}:{a}" for a in ("project", "task", "later")]
