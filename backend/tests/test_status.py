"""The shell's status: the side menu's count next to People and email."""

import itertools
from datetime import timedelta

import pytest

from app.api import settings as api
from app.core import db
from app.core.db import now, session
from app.features.mail.tables import Email

_ids = itertools.count(1)


@pytest.fixture(scope="module", autouse=True)
def database():
    db.migrate()


def mail(level: str, *, ago: timedelta = timedelta(seconds=1), from_me: bool = False) -> None:
    n = next(_ids)
    with session() as s:
        s.add(Email(id=f"status-{n}", account="gmail", thread_id=f"st-{n}", sender=f"p{n}@example.com",
                    sent_at=now() - ago, level=level, from_me=from_me))


def test_the_people_count_is_todays_mail_from_important_people():
    before = api.status()["counts"]["people"]
    mail("important")
    mail("important")
    mail("interested")  # not important: not counted
    mail("important", from_me=True)  # you wrote it: not counted
    mail("important", ago=timedelta(days=2))  # not today
    assert api.status()["counts"]["people"] == before + 2
