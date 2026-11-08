#!/usr/bin/python3
"""Install ActivityWatch for the secretary (B6), or take it off again. No sudo: all in your home.

    /usr/bin/python3 desktop/activitywatch.py install [--from DIR]
    /usr/bin/python3 desktop/activitywatch.py uninstall
    /usr/bin/python3 desktop/activitywatch.py            # what is installed

Why these two pieces (GNOME 50 on Wayland, checked at the B6 plan):
- ActivityWatch's own window watcher can't see windows on GNOME Wayland. awatcher can, and its
  "bundle" is ActivityWatch's server, web page (http://localhost:5600) and the watchers in one
  file. AppImage and Flatpak builds can't see Wayland windows, so it's the plain binary.
- GNOME doesn't tell programs which window is in front, so awatcher needs the GNOME extension
  "Focused Window D-Bus" (it only answers that over D-Bus; its code was read before using it).

What `install` does:
1. downloads both (or takes them from --from DIR), and refuses unless their SHA-256 match the
   pinned ones below;
2. puts awatcher in ~/.local/bin;
3. installs the extension for your user and turns it on for your next login (GNOME on Wayland
   loads a new extension only at login);
4. writes the systemd user unit awatcher.service, but doesn't enable or start it. Recording
   stays off until you switch it on at the time page, which also writes awatcher's config from
   your blocklist first.

`uninstall` stops and removes all of it. What ActivityWatch recorded stays in
~/.local/share/activitywatch until you delete that folder.
"""

from __future__ import annotations

import ast
import hashlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

BUNDLE_URL = "https://github.com/2e3s/awatcher/releases/download/v0.4.0/awatcher-bundle.zip"
BUNDLE_SHA256 = "5d4d307ecfc9f0d46983ada7be66680e800acc5ea0b1b75617ab6dff524faf00"  # as GitHub lists it for v0.4.0
EXT_UUID = "focused-window-dbus@flexagoon.com"
EXT_URL = f"https://extensions.gnome.org/download-extension/{EXT_UUID}.shell-extension.zip?version_tag=76809"  # v12, GNOME 49–51
EXT_SHA256 = "8b499f72027d7d13e0e311a84fcb36760cf920f9d5ac9fc2f764bcfb601608b5"

HOME = Path.home()
BIN = HOME / ".local" / "bin" / "awatcher"
UNIT = HOME / ".config" / "systemd" / "user" / "awatcher.service"
EXT_DIR = HOME / ".local" / "share" / "gnome-shell" / "extensions" / EXT_UUID

UNIT_TEXT = """# ActivityWatch for my_secretary (B6): awatcher's bundle, server + web page + watchers in one.
# Written by desktop/activitywatch.py. Switched on and off from the secretary's time page.
[Unit]
Description=awatcher (ActivityWatch) for my_secretary
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
# The desktop needs a moment after login before the GNOME extension answers.
ExecStartPre=/bin/sleep 5
# No tray icon: the secretary's time page shows whether it records, and its switch turns it off.
ExecStart=%h/.local/bin/awatcher --no-tray
Restart=on-failure
RestartSec=10

[Install]
WantedBy=graphical-session.target
"""


def sh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True, check=check)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(url: str, name: str, want: str, folder: Path, given: Path | None) -> Path:
    """The file from --from DIR if it's there, else downloaded; refused unless its SHA-256 matches."""
    path = given / name if given and (given / name).exists() else folder / name
    if not path.exists():
        print(f"ดาวน์โหลด {url}")
        urllib.request.urlretrieve(url, path)
    got = sha256(path)
    if got != want:
        sys.exit(f"SHA-256 ของ {name} ไม่ตรง ({got}) · ไม่ติดตั้ง")
    return path


def enabled_extensions() -> list[str]:
    raw = sh("gsettings", "get", "org.gnome.shell", "enabled-extensions").stdout.strip()
    return [] if raw.startswith("@as") else list(ast.literal_eval(raw))


def install(given: Path | None) -> None:
    with tempfile.TemporaryDirectory(prefix="awatcher-") as tmp:
        work = Path(tmp)
        bundle = fetch(BUNDLE_URL, "awatcher-bundle.zip", BUNDLE_SHA256, work, given)
        ext = fetch(EXT_URL, "focused-window-dbus.zip", EXT_SHA256, work, given)
        out = work / "bundle"
        sh("unzip", "-o", "-q", str(bundle), "-d", str(out))
        BIN.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out / "awatcher", BIN)
        BIN.chmod(0o755)
        print(f"ติดตั้ง awatcher แล้ว: {BIN}")
        sh("gnome-extensions", "install", "--force", str(ext))
    if EXT_UUID not in (on := enabled_extensions()):  # at your next login; GNOME on Wayland can't load it sooner
        sh("gsettings", "set", "org.gnome.shell", "enabled-extensions", str(on + [EXT_UUID]))
    print(f"ติดตั้งส่วนเสริม GNOME แล้ว: {EXT_UUID} (เริ่มทำงานหลังล็อกเอาต์แล้วล็อกอินใหม่)")
    UNIT.parent.mkdir(parents=True, exist_ok=True)
    UNIT.write_text(UNIT_TEXT)
    sh("systemctl", "--user", "daemon-reload")
    print(f"เขียน {UNIT} แล้ว (ยังไม่เปิด: เปิดที่หน้าการใช้เวลาของเลขา)")
    print("\nต่อไป: ล็อกเอาต์แล้วล็อกอินใหม่ 1 ครั้ง แล้วเปิด “บันทึกกิจกรรม” ที่หน้าการใช้เวลา")


def uninstall() -> None:
    sh("systemctl", "--user", "disable", "--now", "awatcher.service", check=False)
    sh("systemctl", "--user", "stop", "my-secretary-awatcher-resume.timer", check=False)
    for path in (UNIT, BIN):
        if path.exists():
            path.unlink()
            print(f"ลบ {path}")
    sh("systemctl", "--user", "daemon-reload", check=False)
    on = enabled_extensions()
    if EXT_UUID in on:
        on.remove(EXT_UUID)
        sh("gsettings", "set", "org.gnome.shell", "enabled-extensions", str(on) if on else "@as []")
    if EXT_DIR.exists():
        sh("gnome-extensions", "uninstall", EXT_UUID, check=False)
        if EXT_DIR.exists():
            shutil.rmtree(EXT_DIR)
        print(f"ลบส่วนเสริม {EXT_UUID}")
    print("ข้อมูลที่ ActivityWatch บันทึกไว้ยังอยู่ใน ~/.local/share/activitywatch (ลบเองได้ถ้าไม่ใช้แล้ว)")


def show() -> None:
    active = sh("systemctl", "--user", "is-active", "awatcher.service", check=False).stdout.strip()
    print(f"awatcher: {'มี' if BIN.exists() else 'ไม่มี'} ({BIN})")
    print(f"systemd unit: {'มี' if UNIT.exists() else 'ไม่มี'} · {active}")
    print(f"ส่วนเสริม GNOME: {'มี' if EXT_DIR.exists() else 'ไม่มี'} · {'เปิดไว้' if EXT_UUID in enabled_extensions() else 'ปิด'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "install":
        given = Path(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else None
        install(given)
    elif cmd == "uninstall":
        uninstall()
    else:
        show()
