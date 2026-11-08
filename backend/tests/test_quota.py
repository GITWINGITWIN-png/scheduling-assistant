"""B5's quota watcher: the CLI's rate-limit report -> what's left of the week (and of 5 hours)."""

from datetime import timedelta

import pytest

from app.core import db
from app.core.db import now, session
from app.features.jobs import quota
from app.features.jobs.tables import QuotaReading

# What the CLI really sent on 2026-11-06 (RateLimitEvent.rate_limit_info.raw)
RAW = {"status": "allowed", "resetsAt": 1793952000, "rateLimitType": "five_hour", "overageStatus": "rejected",
       "unifiedWindows": {"five_hour": {"utilization": 0.2, "resetsAt": 1793952000, "status": "allowed"},
                          "seven_day": {"utilization": 0.27, "resetsAt": 1794268800, "status": "allowed"}}}


@pytest.fixture(scope="module", autouse=True)
def database():
    db.migrate()


def test_the_report_says_what_is_left_of_the_week_and_of_five_hours():
    n = quota.parse(RAW)
    assert (n["week_left"], n["five_left"]) == (73.0, 80.0)
    assert n["week_resets_at"].isoformat() == "2026-11-10T00:00:00+00:00"


def test_a_report_without_the_weekly_window_is_not_a_reading():
    assert quota.parse({"status": "allowed", "rateLimitType": "five_hour"}) is None


def test_the_same_numbers_move_the_reading_time_and_a_change_is_a_new_reading(monkeypatch):
    with session() as s:
        before = s.query(QuotaReading).count()
    quota.observe(RAW)
    with session() as s:
        first = s.query(QuotaReading).order_by(QuotaReading.id.desc()).first()
        first.at, first_id = now() - timedelta(minutes=5), first.id
    quota.observe(RAW)  # the same numbers 5 minutes later: no new row, but read just now
    latest = quota.latest()
    assert latest.id == first_id and now() - latest.at < timedelta(seconds=5)
    changed = {**RAW, "unifiedWindows": {**RAW["unifiedWindows"], "seven_day": {"utilization": 0.31, "resetsAt": 1794268800}}}
    quota.observe(changed)  # a change is a new reading
    with session() as s:
        assert s.query(QuotaReading).count() == before + 2
    assert quota.latest().week_left == 69.0


def test_an_old_reading_doesnt_count_as_fresh():
    with session() as s:
        for r in s.query(QuotaReading).all():
            r.at = now() - timedelta(hours=3)
    assert quota.latest() is None  # too old for the background work: it reads again first
    assert quota.latest(max_age=None).week_left == 69.0  # the page still shows it, with its time
