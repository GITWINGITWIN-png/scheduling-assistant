"""The recorder: awatcher on this computer (ActivityWatch's server, web page and window watcher in
one program), run by systemd as the user service "awatcher". desktop/activitywatch.py installs it.

The time page's switch and pause button drive it from here:
- on: write awatcher's config from the blocklist, then `systemctl --user enable --now awatcher`,
  and switch the secretary's "activity" round on (it reads ActivityWatch every 15 minutes);
- off: the round off, and `disable --now`, so nothing is recorded, also after a restart;
- pause (หยุดบันทึก 1 ชั่วโมง): stop awatcher now, and let a one-off systemd timer start it again
  when the pause ends. The timer still fires if the secretary isn't running. The pause is also
  written down, so whatever was recorded during it is never kept (privacy.cut_pauses).

Every switch is in สิ่งที่เลขาทำ. Recording starts off: you switch it on (the rule for every
new round).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from app.core import actions, clock
from app.core.db import now
from app.core.timefmt import local
from app.features.time import privacy

log = logging.getLogger(__name__)

UNIT = "awatcher.service"
RESUME = "my-secretary-awatcher-resume"  # the one-off timer of a pause (.timer and .service)
EXTENSION = "focused-window-dbus@flexagoon.com"
PAUSE_MINUTES = (15, 60, 180)


def binary() -> Path:
    return Path.home() / ".local" / "bin" / "awatcher"


def unit_file() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / UNIT


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    """`systemctl --user …` (the seam tests replace)."""
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=20)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True, timeout=20)


def installed() -> bool:
    return binary().exists() and unit_file().exists()


def running() -> bool:
    return _systemctl("is-active", "--quiet", UNIT).returncode == 0


def enabled() -> bool:
    return _systemctl("is-enabled", "--quiet", UNIT).returncode == 0


def extension_state() -> str:
    """on (GNOME shows the focused window to awatcher) · after_login (installed, GNOME loads it at
    your next login) · missing. Asks whether the D-Bus object exists, never what window you're in."""
    if shutil.which("gdbus"):
        probe = _run("gdbus", "introspect", "--session", "--dest", "org.gnome.Shell",
                     "--object-path", "/org/gnome/shell/extensions/FocusedWindow")
        if probe.returncode == 0 and "FocusedWindow" in probe.stdout:
            return "on"
    folder = Path.home() / ".local" / "share" / "gnome-shell" / "extensions" / EXTENSION
    return "after_login" if folder.is_dir() else "missing"


def status() -> dict:
    at = now()
    until = privacy.paused_until(at)
    return {"installed": installed(), "running": running() if installed() else False,
            "enabled": enabled() if installed() else False, "extension": extension_state(),
            "round_on": clock.enabled("activity"), "paused_until": until.isoformat() if until else None,
            "web": "http://localhost:5600", "pause_minutes": list(PAUSE_MINUTES)}


class RecorderError(RuntimeError):
    """Why the recorder couldn't be switched, in your words."""


def _must(result: subprocess.CompletedProcess, what: str) -> None:
    if result.returncode != 0:
        raise RecorderError(f"{what}ไม่สำเร็จ: {(result.stderr or result.stdout).strip()[:300]}")


def _cancel_resume() -> None:
    _systemctl("stop", f"{RESUME}.timer")  # no pause timer: systemctl says so, nothing to do


def set_on(on: bool, *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    """The time page's บันทึกกิจกรรม switch. -> action id."""
    if on and not installed():
        raise RecorderError("ยังไม่ได้ติดตั้ง ActivityWatch · ดู docs/setup/ideas-and-time.md")
    was = {"recorder": enabled() if installed() else False, "round": clock.enabled("activity")}
    if on:
        privacy.write_awatcher_config()
        _must(_systemctl("enable", "--now", UNIT), "เปิดตัวบันทึก")
    else:
        _cancel_resume()
        if installed():
            _must(_systemctl("disable", "--now", UNIT), "ปิดตัวบันทึก")
        privacy.end_pause(now())
    clock.set_enabled("activity", on, via=via)
    return actions.record("activity.switch", "เปิดบันทึกกิจกรรม" if on else "ปิดบันทึกกิจกรรม",
                          "ActivityWatch + รอบอ่านทุก 15 นาที", source_label=via[0], source_url=via[1], undo=was)


async def _undo_switch(undo: dict) -> None:
    if undo["recorder"]:
        privacy.write_awatcher_config()
        _systemctl("enable", "--now", UNIT)
    elif installed():
        _systemctl("disable", "--now", UNIT)
    clock.set_enabled("activity", undo["round"], via=("ปุ่มย้อนกลับ", ""))


actions.register_undo("activity.switch", _undo_switch)


def pause(minutes: int = 60, *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> tuple[datetime, int]:
    """หยุดบันทึก: stop the recorder for `minutes`, then it starts again by itself. -> (until, action id)."""
    if minutes not in PAUSE_MINUTES:
        raise RecorderError(f"หยุดได้ {', '.join(map(str, PAUSE_MINUTES))} นาที")
    at = now()
    until = at + timedelta(minutes=minutes)
    privacy.add_pause(at, until)  # written first: even if stopping fails, nothing from now on is kept
    if installed() and running():
        _cancel_resume()
        _must(_systemctl("stop", UNIT), "หยุดตัวบันทึก")
        _must(_run("systemd-run", "--user", f"--unit={RESUME}", f"--on-active={minutes * 60}", "--timer-property=AccuracySec=1s",
                   "--description=my_secretary: เปิดบันทึกกิจกรรมต่อหลังหยุดพัก", "--collect",
                   "systemctl", "--user", "start", UNIT), "ตั้งเวลาเปิดตัวบันทึกต่อ")
    action_id = actions.record("activity.pause", f"หยุดบันทึกกิจกรรม {minutes} นาที", f"ถึง {local(until):%H:%M}",
                               source_label=via[0], source_url=via[1])
    return until, action_id


def resume(*, via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    """บันทึกต่อเลย: end the pause now."""
    privacy.end_pause(now())
    _cancel_resume()
    if installed() and enabled() and not running():
        _must(_systemctl("start", UNIT), "เปิดตัวบันทึก")
    return actions.record("activity.resume", "บันทึกกิจกรรมต่อ", "ก่อนครบเวลาหยุด", source_label=via[0], source_url=via[1])


def restart_if_running() -> None:
    """The blocklist changed: awatcher reads its config only when it starts."""
    if installed() and running():
        _systemctl("try-restart", UNIT)
