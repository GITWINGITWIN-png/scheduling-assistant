"""Who starts at which level, and what may alert you (watch.py's rules).

These go through watch._store, the same door every new email passes, against a
throwaway database (conftest.py points the data folder at a temp dir).
"""

import itertools
from datetime import datetime, timedelta, timezone

import pytest

from app.connectors.gmail import Header
from app.core import db
from app.core.db import session
from app.features.mail import people, watch
from app.features.mail.tables import Person


@pytest.fixture(scope="module", autouse=True)
def database():
    db.migrate()


_ids = itertools.count(1)  # each test email gets its own message id


def mail(sender: str, *labels: str, subject: str = "สวัสดี", at: datetime | None = None) -> Header:
    i = next(_ids)
    return Header(id=f"m{i}", thread_id=f"t{i}", sender=sender, sender_name="", to=["me@example.com"], subject=subject,
                  snippet="", sent_at=at or datetime(2026, 11, 5, tzinfo=timezone.utc), labels={"INBOX", *labels})


def level_of(address: str) -> tuple[str, str]:
    with session() as s:
        p = people.find(s, address)
        return p.level, p.level_source


@pytest.mark.parametrize("tab", ["CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_FORUMS"])
def test_new_sender_from_a_bulk_tab_starts_ignored(tab):
    watch._store("gmail", mail(f"shop-{tab}@example.com", tab))
    assert level_of(f"shop-{tab}@example.com") == ("ignored", "bulk_tab")


@pytest.mark.parametrize("labels", [(), ("CATEGORY_PERSONAL",), ("CATEGORY_UPDATES",)])
def test_new_sender_elsewhere_starts_interested(labels):
    address = f"person-{'-'.join(labels) or 'inbox'}@example.com"
    watch._store("gmail", mail(address, *labels))
    assert level_of(address) == ("interested", "first_mail")


def test_someone_set_in_advance_keeps_their_level_even_from_a_bulk_tab():
    people.add("advisor@example.com", "อาจารย์", days=90)
    row = watch._store("gmail", mail("advisor@example.com", "CATEGORY_PROMOTIONS"))
    assert level_of("advisor@example.com")[0] == "important"
    assert row.flagged == "important"


def test_a_later_mail_doesnt_change_a_known_sender():
    watch._store("gmail", mail("club@example.com"))  # first mail in the main inbox: interested
    watch._store("gmail", mail("club@example.com", "CATEGORY_FORUMS"))
    assert level_of("club@example.com") == ("interested", "first_mail")


def test_keyword_alerts_skip_ignored_senders():
    row = watch._store("gmail", mail("sale@example.com", "CATEGORY_PROMOTIONS", subject="ด่วน! ลดราคา 50%"))
    assert row.flagged == ""


def test_keyword_alerts_still_work_for_interested_senders():
    row = watch._store("gmail", mail("office@example.com", subject="ด่วน: เลื่อนสอบ"))
    assert row.flagged == "keyword:ด่วน"


def test_a_reply_you_await_alerts_even_from_someone_ignored():
    assert watch.flag(level="ignored", subject="", snippet="", awaiting=True) == "awaiting"


def test_no_person_is_created_twice():
    watch._store("gmail", mail("twice@example.com"))
    watch._store("gmail", mail("TWICE@example.com"))
    with session() as s:
        assert s.query(Person).filter(Person.name == "twice").count() == 1


def test_first_run_handles_mail_that_arrived_while_waiting_for_it(monkeypatch):
    """The 2026-11-05 check: watch switched on 18:40, a test email at 18:42, first run 18:45.
    The test email must alert; last week's mail is filed quietly."""
    people.add("earth@example.com", "Earth", days=90)
    just_now = datetime.now(timezone.utc) - timedelta(minutes=3)
    last_week = datetime.now(timezone.utc) - timedelta(days=2)
    headers = [mail("earth@example.com", subject="ประชุมแผนงาน", at=just_now),
               mail("earth@example.com", subject="เรื่องเก่า", at=last_week)]
    monkeypatch.setattr(watch, "_new_headers", lambda account: (headers, True))  # True: the account's first run
    monkeypatch.setattr(watch, "after_sync", lambda account, headers: None)
    count, flagged = watch.sync("gmail")
    assert count == 2
    assert flagged == [headers[0].id]
