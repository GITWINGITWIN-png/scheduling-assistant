"""The planner (features/schedule/planner.py): pure, so these need no database or Google.

The clock is fixed at Monday 9 Nov 2026, 08:00 Bangkok time, with the default rules:
09:00–22:00, blocks 30–120 min on quarter hours, 15 min around busy time, at most
3 h per task per day, early tasks in the earliest free time.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.features.schedule.planner import Placed, Rules, Work, free_time, plan

BKK = ZoneInfo("Asia/Bangkok")
NOW = datetime(2026, 11, 9, 8, 0, tzinfo=BKK)  # a Monday


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """A time in the test week: day 9 = Monday 9 Nov."""
    return datetime(2026, 11, day, hour, minute, tzinfo=BKK)


def minutes(blocks, task_id=None) -> int:
    return sum(b.minutes for b in blocks if task_id is None or b.task_id == task_id)


def assert_no_overlaps(blocks, busy=()):
    spans = sorted([(b.start, b.end) for b in blocks] + list(busy))
    for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
        assert e1 <= s2, f"{s1:%a %H:%M}-{e1:%H:%M} overlaps {s2:%a %H:%M}-{e2:%H:%M}"


# ------------------------------------------------------------------ free time
def test_free_time_is_inside_the_day_window_and_keeps_a_gap_around_busy_time():
    busy = [(at(9, 10), at(9, 11))]
    free = free_time(busy, now=NOW, rules=Rules(horizon_days=1), tz=BKK)
    assert free == [(at(9, 9), at(9, 9, 45)), (at(9, 11, 15), at(9, 22))]


def test_free_time_starts_at_the_next_quarter_hour_after_now():
    free = free_time([], now=at(9, 13, 7), rules=Rules(horizon_days=1), tz=BKK)
    assert free[0][0] == at(9, 13, 15)


# ------------------------------------------------------------------ early (the default)
def test_early_task_starts_today_and_is_done_a_day_before_it_is_due():
    p = plan([Work(1, 180, due=at(12, 17))], [], now=NOW)
    assert minutes(p.blocks) == 180
    assert p.blocks[0].start == at(9, 9)
    assert all(b.end <= at(11, 17) for b in p.blocks)
    assert not p.short


def test_blocks_are_at_most_two_hours_and_on_quarter_hours():
    p = plan([Work(1, 170, due=at(13, 17))], [], now=at(9, 8, 5))
    assert [b.minutes for b in p.blocks] == [120, 50]
    assert all(b.start.minute % 15 == 0 for b in p.blocks)


def test_one_task_gets_at_most_three_hours_a_day():
    p = plan([Work(1, 360, due=at(14, 17))], [], now=NOW)
    per_day = {}
    for b in p.blocks:
        per_day[b.start.date()] = per_day.get(b.start.date(), 0) + b.minutes
    assert max(per_day.values()) == 180
    assert len(per_day) == 2


def test_a_task_can_set_its_own_block_length_and_daily_limit():
    # 4 hours, in 1-hour blocks, at most 2 hours a day: two days of two blocks each.
    p = plan([Work(1, 240, due=at(14, 17), max_block=60, per_day=120)], [], now=NOW)
    assert [b.minutes for b in p.blocks] == [60, 60, 60, 60]
    assert sorted({b.start.date() for b in p.blocks}) == [at(9, 0).date(), at(10, 0).date()]


def test_a_block_length_under_the_rules_minimum_still_places_work():
    # The rules say 30 minutes at least; a task that asks for 15-minute pieces gets them.
    p = plan([Work(1, 45, due=at(9, 17), max_block=15)], [], now=NOW)
    assert [b.minutes for b in p.blocks] == [15, 15, 15]


def test_per_task_limits_do_not_change_other_tasks():
    p = plan([Work(1, 240, due=at(14, 17), per_day=60), Work(2, 240, due=at(14, 18))], [], now=NOW)
    first_day = [b for b in p.blocks if b.start.date() == at(9, 0).date()]
    assert minutes(first_day, 1) == 60 and minutes(first_day, 2) == 180


def test_a_kept_block_counts_towards_its_days_limit():
    # A block that already runs 09:00-10:00 today stays (sync keeps it): with 2 hours a day,
    # only one more hour goes on today, and the rest moves to tomorrow.
    kept = [Placed(1, at(9, 9), at(9, 10))]
    busy = [(at(9, 9), at(9, 10))]  # sync passes a kept block's time as busy too
    p = plan([Work(1, 180, due=at(14, 17), max_block=60, per_day=120)], busy, now=NOW, kept=kept)
    assert minutes([b for b in p.blocks if b.start.date() == at(9, 0).date()]) == 60
    assert minutes(p.blocks) == 180


@pytest.mark.parametrize("mode", ["early", "late"])
def test_blocks_of_one_task_have_a_break_between_them(mode):
    p = plan([Work(1, 180, due=at(9, 21), mode=mode, max_block=60)], [], now=NOW)
    spans = sorted((b.start, b.end) for b in p.blocks)
    assert [int((b[0] - a[1]).total_seconds() // 60) for a, b in zip(spans, spans[1:])] == [15, 15]


def test_early_task_uses_the_last_day_only_when_it_must():
    # due Tuesday 12:00: "a day before" is Monday 12:00, but Monday morning is busy
    busy = [(at(9, 9), at(9, 12))]
    p = plan([Work(1, 120, due=at(10, 12))], busy, now=NOW)
    assert minutes(p.blocks) == 120
    assert all(b.end <= at(10, 12) for b in p.blocks)
    assert_no_overlaps(p.blocks, busy)


# ------------------------------------------------------------------ late (on request)
def test_late_task_goes_as_close_to_the_due_time_as_it_fits():
    p = plan([Work(1, 120, due=at(13, 17), mode="late")], [], now=NOW)
    assert [(b.start, b.end) for b in p.blocks] == [(at(13, 15), at(13, 17))]


def test_late_block_ends_on_a_quarter_hour_before_an_odd_due_time():
    p = plan([Work(1, 60, due=at(13, 16, 59), mode="late")], [], now=NOW)
    assert (p.blocks[0].start, p.blocks[0].end) == (at(13, 15, 45), at(13, 16, 45))


# ------------------------------------------------------------------ several tasks
def test_the_task_due_first_gets_the_earliest_time():
    p = plan([Work(1, 120, due=at(16, 17)), Work(2, 120, due=at(11, 17))], [], now=NOW)
    first = p.blocks[0]
    assert first.task_id == 2 and first.start == at(9, 9)
    assert_no_overlaps(p.blocks)


def test_tasks_without_a_due_date_get_what_is_left():
    p = plan([Work(1, 60), Work(2, 180, due=at(11, 17))], [], now=NOW)
    no_due = [b for b in p.blocks if b.task_id == 1]
    assert minutes(no_due) == 60
    assert min(b.start for b in p.blocks if b.task_id == 2) < no_due[0].start


def test_blocks_never_overlap_busy_time_or_each_other():
    busy = [(at(9, 10), at(9, 12)), (at(9, 13), at(9, 16)), (at(10, 9), at(10, 12))]
    work = [Work(1, 300, due=at(12, 17)), Work(2, 240, due=at(13, 9)), Work(3, 90)]
    p = plan(work, busy, now=NOW)
    gap = timedelta(minutes=15)
    assert_no_overlaps(p.blocks, [(s - gap, e + gap) for s, e in busy])


# ------------------------------------------------------------------ what doesn't fit
def test_work_that_does_not_fit_before_the_due_date_is_reported_not_placed_late():
    p = plan([Work(1, 600, due=at(9, 18))], [], now=NOW)  # only 9:00-18:00 today, 3 h cap
    assert minutes(p.blocks) == 180
    assert p.short == {1: 420}
    assert all(b.end <= at(9, 18) for b in p.blocks)


def test_an_overdue_task_is_reported_short():
    p = plan([Work(1, 60, due=at(8, 17))], [], now=NOW)
    assert p.blocks == [] and p.short == {1: 60}


def test_a_short_gap_is_skipped_for_big_work_but_fits_a_short_leftover():
    busy = [(at(9, 9, 15), at(9, 22))]  # leaves only 09:00-09:15 on Monday; Tuesday is free
    rules = Rules(gap=0)
    p = plan([Work(1, 20, due=at(9, 23))], [(at(9, 9, 20), at(9, 22))], now=NOW, rules=rules)
    assert [(b.start, b.end) for b in p.blocks] == [(at(9, 9), at(9, 9, 20))]
    p = plan([Work(1, 120, due=at(11, 17))], busy, now=NOW, rules=rules)
    assert p.blocks[0].start == at(10, 9)  # the 15 minutes on Monday morning were too short


@pytest.mark.parametrize("mode", ["early", "late"])
def test_nothing_is_placed_before_now(mode):
    p = plan([Work(1, 240, due=at(10, 20), mode=mode)], [], now=at(9, 15, 40))
    assert all(b.start >= at(9, 15, 45) for b in p.blocks)


# ------------------------------------------------------------------ B7: your schedule rules
from datetime import time  # noqa: E402

TUE_AFTERNOON = (1, time(12, 0), time(17, 0))
FOCUS = (time(9, 0), time(11, 30))


def test_avoided_hours_are_never_booked_on_that_weekday():
    rules = Rules(avoid=(TUE_AFTERNOON,), horizon_days=3)
    free = free_time([], now=NOW, rules=rules, tz=BKK)
    assert (at(10, 9), at(10, 12)) in free and (at(10, 17), at(10, 22)) in free  # Tuesday 10 Nov, around 12:00–17:00
    assert (at(9, 9), at(9, 22)) in free and (at(11, 9), at(11, 22)) in free  # Monday and Wednesday untouched
    out = plan([Work(1, 13 * 60 * 2, per_day=13 * 60, max_block=120)], [], now=NOW, rules=rules, tz=BKK)
    tuesday = [b for b in out.blocks if b.start.date() == at(10, 0).date()]
    assert tuesday and all(b.end <= at(10, 12) or b.start >= at(10, 17) for b in tuesday)


def test_focus_hours_go_first_within_a_day_but_never_push_work_to_a_later_day():
    busy = [(at(9, 9), at(9, 12))]  # Monday morning is taken, focus hours included
    rules = Rules(focus=FOCUS, horizon_days=3)
    out = plan([Work(1, 60)], busy, now=NOW, rules=rules, tz=BKK)
    assert out.blocks[0].start == at(9, 12, 15)  # still Monday: not moved to Tuesday's focus hours
    out = plan([Work(2, 60)], [], now=at(9, 7), rules=rules, tz=BKK)
    assert out.blocks[0].start == at(9, 9)
    afternoon = at(9, 13)
    out = plan([Work(3, 90)], [], now=afternoon, rules=rules, tz=BKK)
    assert out.blocks[0].start == at(9, 13)  # today's focus hours are gone: the rest of today, not tomorrow


def test_with_two_tasks_the_first_takes_the_focus_hours_and_email_work_never_does():
    rules = Rules(focus=FOCUS, horizon_days=2)
    day = at(9, 7)
    out = plan([Work(1, 60, due=at(9, 18)), Work(2, 60, due=at(9, 20))], [], now=day, rules=rules, tz=BKK)
    starts = {b.task_id: b.start for b in out.blocks}
    assert starts[1] == at(9, 9) and at(9, 9) < starts[2] < at(9, 11, 30)  # both fit the focus hours, in order
    mail = plan([Work(1, 60, focus=False)], [(at(9, 9), at(9, 9, 30))], now=day, rules=rules, tz=BKK)
    assert mail.blocks[0].start == at(9, 9, 45)  # earliest free time, as before the rule


def test_a_task_never_gets_two_blocks_back_to_back_at_the_focus_hours_edge():
    rules = Rules(focus=FOCUS, horizon_days=1, gap=15, max_block=150)
    out = plan([Work(1, 5 * 60, max_block=150, per_day=5 * 60)], [], now=at(9, 7), rules=rules, tz=BKK)
    spans = sorted((b.start, b.end) for b in out.blocks)
    assert spans[0] == (at(9, 9), at(9, 11, 30)) and minutes(out.blocks) == 5 * 60  # the focus hours exactly, then a break
    for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
        assert s2 - e1 >= timedelta(minutes=15), f"{e1:%H:%M} then {s2:%H:%M}"


def test_late_tasks_use_focus_hours_first_on_their_last_days():
    rules = Rules(focus=FOCUS, horizon_days=3)
    out = plan([Work(1, 60, due=at(11, 20), mode="late")], [], now=at(9, 7), rules=rules, tz=BKK)
    # the due day's focus hours, as late in them as fits ("late"), not the due day's evening
    assert (out.blocks[0].start, out.blocks[0].end) == (at(11, 10, 30), at(11, 11, 30))
