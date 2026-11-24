#!/usr/bin/python3
"""Bind Super+I to the idea popup (K1, B6), or take the binding off again.

    /usr/bin/python3 desktop/idea_key.py on      # Super+I opens desktop/idea_popup.py
    /usr/bin/python3 desktop/idea_key.py off     # back as it was
    /usr/bin/python3 desktop/idea_key.py         # what is bound now

It is one GNOME "custom shortcut" (the same as Settings → Keyboard → Custom Shortcuts, where
you can see and change it too), under its own path, so `off` removes exactly this one and
nothing of yours. `on` refuses if Super+I already does something else.

Run it again after moving the repo: the shortcut points at this folder.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/my-secretary-idea/"
ONE = f"{SCHEMA}.custom-keybinding:{PATH}"
BINDING = "<Super>i"
POPUP = Path(__file__).resolve().with_name("idea_popup.py")
COMMAND = f"/usr/bin/python3 {POPUP}"


def gs(*args: str) -> str:
    return subprocess.run(["gsettings", *args], capture_output=True, text=True, check=True).stdout.strip()


def bound() -> list[str]:
    """The custom shortcuts' paths ("@as []" is GVariant for an empty list)."""
    raw = gs("get", SCHEMA, "custom-keybindings")
    return [] if raw.startswith("@as") else list(ast.literal_eval(raw))


def taken_by() -> str | None:
    """Whatever else already uses Super+I, if anything."""
    for line in gs("list-recursively").splitlines():
        if BINDING.lower() in line.lower() and PATH not in line:
            schema, key, value = (line.split(" ", 2) + ["", ""])[:3]
            if f"'{BINDING.lower()}'" in value.lower():
                return f"{schema} {key}"
    for path in bound():
        if path != PATH and gs("get", f"{SCHEMA}.custom-keybinding:{path}", "binding").strip("'").lower() == BINDING.lower():
            return f"your own shortcut {gs('get', f'{SCHEMA}.custom-keybinding:{path}', 'name')}"
    return None


def on() -> None:
    other = taken_by()
    if other:
        sys.exit(f"Super+I is already taken by {other}; nothing was changed")
    paths = bound()
    if PATH not in paths:
        gs("set", SCHEMA, "custom-keybindings", str(paths + [PATH]))
    gs("set", ONE, "name", "จดไอเดีย (เลขา)")
    gs("set", ONE, "command", COMMAND)
    gs("set", ONE, "binding", BINDING)
    print(f"Super+I is bound: {COMMAND}\nTo remove it: /usr/bin/python3 {Path(__file__).resolve()} off")


def off() -> None:
    paths = bound()
    if PATH in paths:
        paths.remove(PATH)
        gs("set", SCHEMA, "custom-keybindings", str(paths) if paths else "@as []")
    gs("reset-recursively", ONE)
    print("Removed the secretary's Super+I shortcut")


def show() -> None:
    if PATH in bound():
        print(f"Super+I → {gs('get', ONE, 'command')}")
    else:
        print("Not bound yet. Bind it with: /usr/bin/python3 " + str(Path(__file__).resolve()) + " on")


if __name__ == "__main__":
    {"on": on, "off": off}.get(sys.argv[1] if len(sys.argv) > 1 else "", show)()
