"""B6's Super+I popup, without a screen: which tags it sends, what it says, and that an idea is
never lost when the secretary is down or too old (desktop/idea_popup.py's plain functions)."""

import importlib.util
import json
from pathlib import Path

import pytest

POPUP = Path(__file__).resolve().parents[2] / "desktop" / "idea_popup.py"
spec = importlib.util.spec_from_file_location("idea_popup", POPUP)
popup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(popup)  # no GTK here: the window is only built inside main()


def test_the_tags_it_sends():
    assert popup.chosen(["เลขา", "เสียง"], set(), []) == ["เลขา", "เสียง"]
    assert popup.chosen(["เลขา", "เสียง"], {"เสียง"}, ["podcast"]) == ["เลขา", "podcast"]
    assert popup.chosen(["เลขา"], {"เลขา"}, []) == []  # you dropped them all: no tags, final
    assert popup.chosen([], set(), []) is None  # nothing to choose from: the round decides


def test_what_it_says_after_saving():
    assert popup.joined({"name": "เลขาพูดสรุปตอนเช้า", "size": 5, "new": False}) == "บันทึกแล้ว · เข้ากลุ่ม “เลขาพูดสรุปตอนเช้า” (5)"
    assert popup.joined({"name": "backtest", "size": 1, "new": True}) == "บันทึกแล้ว · เริ่มกลุ่มใหม่ “backtest”"


@pytest.fixture
def outbox(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRETARY_DATA_DIR", str(tmp_path))
    return tmp_path / "ideas-outbox.jsonl"


def test_a_secretary_that_isnt_running_gets_it_later(outbox, monkeypatch):
    monkeypatch.setattr(popup, "URL", "http://127.0.0.1:9")  # nothing listens on port 9
    said, close = popup.save("จดตอนเลขาปิด", ["เลขา"])
    assert close and "เก็บไว้ก่อน" in said
    kept = json.loads(outbox.read_text().splitlines()[0])
    assert kept["text"] == "จดตอนเลขาปิด" and kept["tags"] == ["เลขา"] and kept["at"].endswith("+00:00")


@pytest.mark.parametrize(("code", "kept"), [(404, True), (500, True), (422, False)])
def test_an_old_or_broken_secretary_keeps_it_and_a_refusal_is_shown(outbox, monkeypatch, code, kept):
    def answer(method, path, body=None):
        raise popup.Refused("ไอเดียว่างอยู่", code)

    monkeypatch.setattr(popup, "_call", answer)
    said, close = popup.save("ไอเดีย", None)
    assert close is kept and outbox.exists() is kept  # 404: before B6 · 500: broken · 422: its words, window stays
    if not kept:
        assert said == "ไอเดียว่างอยู่"
