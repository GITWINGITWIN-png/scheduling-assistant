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


def test_the_group_is_the_first_tag_that_isnt_a_project():
    projects = {"finance": "Finance"}
    assert store.primary(["finance", "backtest"], projects) == "backtest"
    assert store.primary(["finance"], projects) == "finance"
    assert store.primary([], projects) is None


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
    assert rows[typed["id"]] == (["backtest"], "you")
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
