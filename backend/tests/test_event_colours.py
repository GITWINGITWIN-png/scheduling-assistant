"""Event colours: a colour you give an event in Google Calendar shows on the today and schedule
pages (instead of the red of นัด), and recolouring many events is one action whose undo gives each
one its old colour back. Google is faked: nothing here reaches it."""

import asyncio
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.api import schedule as api
from app.api import today as api_today
from app.connectors import gcal
from app.core import actions, db
from app.core.config import get_config
from app.core.db import now, session
from app.core.tables import Action, Event
from app.features.briefs import day
from app.features.schedule import events, sync


@pytest.fixture(scope="module", autouse=True)
def _db():
    db.migrate()


@pytest.fixture
def google(monkeypatch):
    """Google's side of recolouring: {gcal id: colorId}. "gone" was deleted there by hand."""
    colours: dict[str, str] = {}

    def recolor(event_id, color_id, *, calendar="primary"):
        if event_id == "gone":
            return False
        colours[event_id] = color_id
        return True
    monkeypatch.setattr(gcal, "recolor", recolor)
    return colours


def _placed(title: str, gcal_id: str, color: str = "", start: datetime | None = None) -> int:
    start = start or now() + timedelta(days=2)
    with session() as s:
        ev = Event(title=title, starts_at=start, ends_at=start + timedelta(hours=1), source="you", status="placed",
                   gcal_id=gcal_id, color=color)
        s.add(ev)
        s.flush()
        return ev.id


def test_recolouring_many_is_one_action_and_undo_gives_each_its_old_colour(google):
    drawing = _placed("co-วาด", "co-ga")
    sculpting = _placed("co-ปั้น", "co-gb", color="#039be5")  # Peacock already
    deleted = _placed("co-ลบแล้วใน Google", "gone")
    action_id = asyncio.run(events.recolor([drawing, sculpting, deleted], "6"))
    assert google == {"co-ga": "6", "co-gb": "6"}
    with session() as s:
        assert [s.get(Event, i).color for i in (drawing, sculpting, deleted)] == ["#f4511e", "#f4511e", ""]
        act = s.get(Action, action_id)
        assert (act.summary, act.target) == ("เปลี่ยนสี 2 กิจกรรม", "เป็นสีส้ม")
    asyncio.run(actions.undo(action_id))
    assert google == {"co-ga": "", "co-gb": "7"}  # each one back to its own colour
    with session() as s:
        assert [s.get(Event, i).color for i in (drawing, sculpting)] == ["", "#039be5"]


def test_the_page_refuses_a_colour_google_doesnt_have(google):
    event = _placed("co-สีแปลก", "co-gc")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api.color_events(api.ColorIn(event_ids=[event], color="99")))
    assert exc.value.status_code == 400 and google == {}
    assert asyncio.run(api.color_events(api.ColorIn(event_ids=[event], color="3")))["action_id"]


def test_a_colour_set_in_google_is_copied_in_and_reaches_both_pages(monkeypatch):
    tz = get_config().tz
    start = datetime(2027, 3, 15, 10, 30, tzinfo=tz)  # far from every other test's data
    painted = gcal.CalEvent(id="co-gd", title="co-ลงสีใน Procreate", start=start, end=start + timedelta(hours=2),
                            all_day=False, location="", link="", mark="", busy=True, recurring=False, color="#8e24aa")
    monkeypatch.setattr(gcal, "window", lambda lo, hi, calendar="primary": [painted] if calendar == "primary" else [])
    monkeypatch.setattr(gcal, "blocks_calendar", lambda create=False: "co-blocks")
    sync.refresh_calendar(start - timedelta(hours=1), start + timedelta(days=1))
    week = api.week("2027-03-15T00:00", "2027-03-16T00:00")
    assert [(e["title"], e["color"]) for e in week["events"] if e["title"].startswith("co-")] == [("co-ลงสีใน Procreate", "#8e24aa")]
    items = [i for i in day.agenda(start.date()) if i.title.startswith("co-")]
    assert [(i.kind, i.color) for i in items] == [("meet", "#8e24aa")]
    monkeypatch.setattr(day, "agenda", lambda d: items)  # the today page's rows, as that day's
    assert [(i["title"], i["color"]) for i in api_today.today_page()["plan"]] == [("co-ลงสีใน Procreate", "#8e24aa")]
