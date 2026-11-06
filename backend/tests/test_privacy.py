"""B6's privacy filter (P12), the test agreed at the plan: nothing on the blocklist may reach the log.

Checked through the real read (pull.read) with a fake ActivityWatch, plus the rules on their own,
awatcher's config written from them, the pause, and the recorder's switches (systemctl faked)."""

import asyncio
import tomllib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.connectors import activitywatch as aw
from app.core import clock, db, settings
from app.core.db import session
from app.features.time import privacy, pull, recorder
from app.features.time.tables import HIDDEN, Activity, PrivacyRule

T0 = datetime(2026, 11, 6, 2, 0, tzinfo=timezone.utc)  # 09:00 in Bangkok


@pytest.fixture(scope="module", autouse=True)
def _db():
    db.migrate()


@pytest.fixture(autouse=True)
def _fresh(monkeypatch, tmp_path):
    with session() as s:
        s.execute(delete(Activity))
        s.execute(delete(PrivacyRule))
    settings.put(privacy.SEEDED_KEY, None)
    settings.put(privacy.PAUSES_KEY, [])
    settings.put(pull.STATE_KEY, {})
    privacy.seed()
    monkeypatch.setattr(privacy, "awatcher_config_path", lambda: tmp_path / "awatcher" / "config.toml")


def m(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def fake_aw(monkeypatch, windows: list[tuple[int, int, str, str]], present=None):
    """ActivityWatch with these windows (start min, end min, app, title), cut to what's asked."""
    def active(start, end):
        out = [aw.Window(max(m(a), start), min(m(b), end), app, title) for a, b, app, title in windows]
        return [w for w in out if w.end > w.start]

    def here(start, end):
        spans = present if present is not None else [(m(a), m(b)) for a, b, _, _ in windows]
        return [(max(a, start), min(b, end)) for a, b in spans if min(b, end) > max(a, start)]

    monkeypatch.setattr(aw, "active_windows", active)
    monkeypatch.setattr(aw, "present", here)


def kept() -> list[tuple[str, str, int]]:
    with session() as s:
        return [(r.app, r.title, int((r.end - r.start).total_seconds() // 60))
                for r in s.scalars(select(Activity).order_by(Activity.start))]


# ------------------------------------------------------------------ the rules
@pytest.mark.parametrize(("app", "title", "verdict"), [
    ("KeePassXC", "Passwords.kdbx - KeePassXC", "drop"),  # a password manager
    ("org.gnome.World.Secrets", "Secrets", "drop"),
    ("firefox", "K PLUS - Kasikornbank — Mozilla Firefox", "drop"),  # a bank, by its title
    ("firefox", "SCB Easy | หน้าหลัก — Mozilla Firefox", "drop"),
    ("google-chrome", "PayPal: Summary - Google Chrome", "drop"),
    ("firefox", "(3) WhatsApp — Mozilla Firefox", "drop"),  # private chat on the web
    ("line", "LINE", "drop"),  # and as an app
    ("firefox", "Gmail — Mozilla Firefox Private Browsing", "drop"),  # a private window
    ("google-chrome", "New Tab - Google Chrome (Incognito)", "drop"),
    ("firefox", "หน้าใหม่ — การท่องเว็บแบบส่วนตัวของ Mozilla Firefox", "drop"),
    ("firefox", "ตั้งรหัสผ่านใหม่ — Mozilla Firefox", "hide"),  # a word: kept, title hidden
    ("google-chrome", "Enter your OTP - Google Chrome", "hide"),
    ("code", "password_reset.py - my_secretary - Visual Studio Code", "keep"),  # password_ is one word with the _
    ("firefox", "Password reset — Mozilla Firefox", "hide"),
    ("code", "PROGRESS.md - my_secretary - Visual Studio Code", "keep"),
    ("org.gnome.Ptyxis", "user@pc: ~/Projects/scbx-report", "keep"),  # "scb" isn't in "scbx"
    ("firefox", "Command Line Tools — Mozilla Firefox", "keep"),  # "line" is an app rule, not a title one
])
def test_the_default_rules(app, title, verdict):
    assert privacy.rules().verdict(app, title) == verdict


def test_thai_values_are_found_inside_words_and_latin_ones_stand_alone():
    assert privacy.found("ธนาคาร", "เปิดบัญชีธนาคารออนไลน์")
    assert privacy.found("otp", "Your OTP: 1234") and not privacy.found("otp", "hotpot recipes")
    assert privacy.found("k plus", "K  PLUS mobile") is False  # two spaces aren't one: values are matched as typed
    assert privacy.found("k plus", "K PLUS mobile")


# ------------------------------------------------------------------ the real read
def test_nothing_on_the_blocklist_reaches_the_log(monkeypatch):
    fake_aw(monkeypatch, [
        (0, 30, "code", "pull.py - my_secretary - Visual Studio Code"),
        (30, 35, "KeePassXC", "Passwords.kdbx - KeePassXC"),
        (35, 40, "firefox", "K PLUS - Kasikornbank — Mozilla Firefox"),
        (40, 45, "firefox", "ตั้งรหัสผ่านใหม่ — Mozilla Firefox"),
        (45, 60, "firefox", "GitHub — Mozilla Firefox"),
    ])
    r = pull.read(m(60))
    assert (r.kept, r.skipped, r.hidden) == (3, 2, 1)
    log = kept()
    assert log == [("code", "pull.py - my_secretary - Visual Studio Code", 30), ("firefox", HIDDEN, 5),
                   ("firefox", "GitHub — Mozilla Firefox", 15)]
    text = " ".join(f"{a} {t}" for a, t, _ in log).lower()
    assert "keepass" not in text and "kasikorn" not in text and "รหัสผ่าน" not in text


def test_reading_again_never_counts_twice_and_the_window_youre_in_grows(monkeypatch):
    windows = [(0, 50, "code", "a.py - x - Visual Studio Code"), (55, 65, "firefox", "docs")]
    fake_aw(monkeypatch, windows)
    pull.read(m(65))
    windows[1] = (55, 80, "firefox", "docs")  # you stayed in it
    pull.read(m(80))  # starts 30 minutes back: the docs window is read again, whole
    pull.read(m(80))
    assert sum(n for _, _, n in kept()) == 50 + 25


def test_a_pause_cuts_out_whatever_was_recorded_during_it(monkeypatch):
    privacy.add_pause(m(10), m(40))
    fake_aw(monkeypatch, [(0, 60, "code", "a.py - x - Visual Studio Code")])
    r = pull.read(m(60))
    assert [n for _, _, n in kept()] == [10, 20] and sum((b - a for a, b in r.present), timedelta()) == timedelta(minutes=30)


def test_a_rule_added_later_cleans_what_was_kept_and_rewrites_awatchers_config(monkeypatch):
    restarts = []
    monkeypatch.setattr(recorder, "restart_if_running", lambda: restarts.append(1))
    fake_aw(monkeypatch, [(0, 20, "firefox", "Shopee | ช้อปออนไลน์ — Mozilla Firefox"), (20, 30, "code", "a.py")])
    pull.read(m(30))
    asyncio.run(privacy.add("title", "Shopee", "ช้อปปิ้ง"))
    assert kept() == [("code", "a.py", 10)] and restarts == [1]
    assert "shopee" in privacy.awatcher_config_path().read_text()


# ------------------------------------------------------------------ awatcher's config (the first line)
def test_awatchers_config_drops_first_then_hides():
    text = privacy.awatcher_config(privacy.rules())
    conf = tomllib.loads(text)  # it must be valid TOML, or awatcher won't start
    filters = conf["awatcher"]["filters"]
    assert conf["server"] == {"port": 5600, "host": "127.0.0.1"}
    first_hide = next(i for i, f in enumerate(filters) if "replace-title" in f)
    assert all("replace-title" not in f for f in filters[:first_hide])  # awatcher stops at the first match
    assert all(f["replace-title"] == HIDDEN for f in filters[first_hide:])
    r = privacy.rules()
    assert [f["match-app-id"] for f in filters if "match-app-id" in f] == [privacy.pattern(v) for v in r.apps]  # every one
    assert [f["match-title"] for f in filters if "replace-title" not in f and "match-title" in f] == [privacy.pattern(v) for v in r.titles]
    assert [f["match-title"] for f in filters if "replace-title" in f] == [privacy.pattern(v) for v in r.words]
    assert {"match-app-id": r"(?i).*\bkeepassxc\b.*"} in filters
    assert {"match-title": "(?i).*รหัสผ่าน.*", "replace-title": HIDDEN} in filters
    assert {"match-title": r"(?i).*\bline\.me\b.*"} in filters  # the dot escaped
    for f in filters:  # the same patterns, read by Python's regex, decide the same as the filter
        for key in ("match-app-id", "match-title"):
            if key in f:
                assert f[key].startswith("(?i).*") and f[key].endswith(".*")


# ------------------------------------------------------------------ the recorder's switches
@pytest.fixture
def systemd(monkeypatch, tmp_path):
    calls, state = [], {"active": False, "enabled": False}

    def systemctl(*args):
        calls.append(("systemctl", *args))
        if args[0] == "is-active":
            return type("R", (), {"returncode": 0 if state["active"] else 3, "stdout": "", "stderr": ""})()
        if args[0] == "is-enabled":
            return type("R", (), {"returncode": 0 if state["enabled"] else 1, "stdout": "", "stderr": ""})()
        if args[:2] == ("enable", "--now"):
            state.update(active=True, enabled=True)
        if args[:2] == ("disable", "--now"):
            state.update(active=False, enabled=False)
        if args[0] == "stop" and args[1] == recorder.UNIT:
            state["active"] = False
        if args[0] == "start" and args[1] == recorder.UNIT:
            state["active"] = True
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    def run(*args):
        calls.append(args)
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(recorder, "_systemctl", systemctl)
    monkeypatch.setattr(recorder, "_run", run)
    monkeypatch.setattr(recorder, "installed", lambda: True)
    return calls, state


def test_switching_on_writes_the_config_first_and_turns_the_round_on(systemd):
    calls, state = systemd
    recorder.set_on(True)
    assert privacy.awatcher_config_path().exists() and state["enabled"] and clock.enabled("activity")
    assert ("systemctl", "enable", "--now", recorder.UNIT) in calls
    recorder.set_on(False)
    assert not state["enabled"] and not clock.enabled("activity")


def test_a_pause_stops_the_recorder_and_a_timer_starts_it_again(systemd):
    calls, state = systemd
    recorder.set_on(True)
    until, _ = recorder.pause(60)
    assert not state["active"] and privacy.paused_until(until - timedelta(minutes=1)) == until
    timer = next(c for c in calls if c[0] == "systemd-run")
    assert "--on-active=3600" in timer and timer[-4:] == ("systemctl", "--user", "start", recorder.UNIT)
    recorder.resume()
    assert state["active"] and privacy.paused_until(until - timedelta(minutes=1)) is None
    with pytest.raises(recorder.RecorderError):
        recorder.pause(7)  # 15, 60 or 180
    recorder.set_on(False)
