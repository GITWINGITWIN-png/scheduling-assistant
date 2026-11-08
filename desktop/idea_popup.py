#!/usr/bin/python3
"""จดไอเดีย (K1, B6): the small window Super+I opens over whatever you're doing.

Type, press Enter, and the idea goes to the secretary on this computer (POST /api/ideas on
localhost). The window then says which group it joins and closes itself. Shift+Enter starts a
new line, Esc closes without saving.

As you type, the secretary's rules suggest tags (no model). They are picked already, and a click
drops one; "+ แท็ก" adds your own. If the secretary isn't running, the idea is kept in
~/.secretary/ideas-outbox.jsonl and goes into the store the next time the secretary starts.

It runs on the system Python, because GTK 4 (PyGObject) comes with Ubuntu and not with the
backend's venv. Pressing Super+I again while it's open brings the same window back: one window,
never two (a GApplication with an id).

    /usr/bin/python3 desktop/idea_popup.py      # what Super+I runs (desktop/idea_key.py binds it)

SECRETARY_URL and SECRETARY_DATA_DIR change where it sends to and where the outbox is. The
logic is plain functions above `main()`, so tests can use them without a screen.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = os.environ.get("SECRETARY_URL", "http://127.0.0.1:8000").rstrip("/")
APP_ID = "local.mysecretary.IdeaPopup"
TIMEOUT = 4  # seconds: the secretary answers in milliseconds, or it isn't there


def data_dir() -> Path:
    return Path(os.environ.get("SECRETARY_DATA_DIR") or Path.home() / ".secretary")


# ------------------------------------------------------------------ talking to the secretary
class Down(Exception):
    """The secretary isn't answering (not running, or still starting)."""


class Refused(Exception):
    """The secretary answered no; the message says why, in its words."""

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


def _call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(URL + path, data=data, method=method,
                                 headers={"content-type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("detail")
        except (ValueError, AttributeError):
            detail = None
        raise Refused(detail if isinstance(detail, str) else f"เลขาตอบว่าไม่ได้ ({exc.code})", exc.code) from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise Down(str(exc)) from exc


def suggest(text: str) -> list[str]:
    """The rules' tags for what you've typed so far ([] when the secretary is down)."""
    try:
        return _call("GET", "/api/ideas/suggest?text=" + urllib.parse.quote(text)).get("tags", [])
    except (Down, Refused):
        return []


def chosen(suggested: list[str], dropped: set[str], extra: list[str]) -> list[str] | None:
    """The tags to send. None: nothing was suggested and you added none, so the round's rules
    decide later (they may know more by then). A list, even empty, is final."""
    tags = [t for t in suggested if t not in dropped] + [t for t in extra if t not in suggested]
    return tags if tags or suggested else None


def joined(group: dict | None) -> str:
    """What the window says after saving (K1 ③)."""
    if not group:
        return "บันทึกแล้ว · เลขาจัดกลุ่มให้รอบเที่ยงและเที่ยงคืน"
    if group.get("new"):
        return f"บันทึกแล้ว · เริ่มกลุ่มใหม่ “{group['name']}”"
    return f"บันทึกแล้ว · เข้ากลุ่ม “{group['name']}” ({group['size']})"


def keep_for_later(text: str, tags: list[str] | None) -> Path:
    """The secretary is down: keep the idea in the outbox (it takes it in when it starts)."""
    box = data_dir() / "ideas-outbox.jsonl"
    box.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"text": text, "tags": tags, "at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)
    with box.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return box


def save(text: str, tags: list[str] | None) -> tuple[str, bool]:
    """-> (what to say, whether the window may close)."""
    try:
        saved = _call("POST", "/api/ideas", {"text": text, "tags": tags, "source": "key"})
        return joined(saved.get("group")), True
    except Down:
        keep_for_later(text, tags)
        return "เลขาปิดอยู่ · เก็บไว้ก่อน จะเข้าคลังตอนเลขาเปิด", True
    except Refused as exc:
        if exc.code == 404 or exc.code >= 500:  # a secretary from before B6, or one that broke: don't lose it
            keep_for_later(text, tags)
            return "เลขายังรับไอเดียไม่ได้ · เก็บไว้ก่อน จะเข้าคลังตอนเลขารีสตาร์ท", True
        return str(exc), False


# ------------------------------------------------------------------ the window
# Every colour is spelled out (the K1 mockup's white card), not taken from the desktop's theme:
# Ubuntu's Yaru themes for GTK 4 don't define libadwaita's names (window_bg_color, view_bg_color),
# and a name a theme lacks paints as transparent, so the first version had no background at all
# on the user's desktop (found at B6's check, 2026-11-08).
CSS = """
window.idea { background-color: #FFFFFF; color: #17120E; }
.idea .head { padding: 14px 18px 4px 18px; }
.idea .title { font-weight: 700; font-size: 15pt; color: #17120E; }
.idea .head image { color: #17120E; }
.idea .kbd { font-family: monospace; font-size: 9pt; padding: 1px 6px; color: #4A433D; border: 1px solid #D4CFC9; border-radius: 5px; }
.idea .box { border: 1.5px solid #F25F0C; border-radius: 12px; padding: 10px 12px; background-color: #FFFFFF; }
.idea textview, .idea textview text { background-color: #FFFFFF; color: #17120E; caret-color: #17120E; font-size: 12pt; }
.idea textview text selection { background-color: #FFE9DB; color: #17120E; }
.idea .muted { color: #7A736C; font-size: 9.5pt; }
.idea button.chip { border-radius: 999px; padding: 1px 10px; min-height: 0; font-weight: 700; font-size: 9.5pt;
  background-color: #FFE9DB; background-image: none; color: #C2410C; border: none; box-shadow: none; }
.idea button.chip:hover { background-color: #FFD9BF; }
.idea button.chip.off { background-color: #FFFFFF; color: #7A736C; border: 1px solid #D4CFC9; text-decoration: line-through; }
.idea button.add { border-radius: 999px; padding: 1px 10px; min-height: 0; font-size: 9.5pt; background-color: #FFFFFF;
  background-image: none; color: #4A433D; border: 1px solid #D4CFC9; box-shadow: none; }
.idea button.add:hover { background-color: #F0EFEC; }
.idea button.save { border-radius: 999px; padding: 4px 16px; font-weight: 700; background-color: #F25F0C;
  background-image: none; color: #FFFFFF; border: none; box-shadow: none; }
.idea button.save:hover { background-color: #C2410C; }
.idea .done { color: #16A34A; font-weight: 700; }
.idea .bad { color: #DC2626; font-weight: 700; }
.idea entry.tag { border-radius: 999px; min-height: 0; padding: 0 10px; font-size: 9.5pt; background-color: #FFFFFF;
  color: #17120E; border: 1px solid #D4CFC9; }
"""


def main() -> int:
    import threading

    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, Gio, GLib, Gtk

    class Popup(Gtk.ApplicationWindow):
        def __init__(self, app: Gtk.Application) -> None:
            super().__init__(application=app, title="จดไอเดีย")
            self.add_css_class("idea")
            self.set_default_size(560, -1)
            self.set_resizable(False)
            self.suggested: list[str] = []
            self.dropped: set[str] = set()
            self.extra: list[str] = []
            self.timer = 0
            self.asked = 0  # the latest suggestion request, so an old answer can't overwrite a newer one
            self.busy = False

            head = Gtk.Box(spacing=8, css_classes=["head"])
            head.append(Gtk.Image(icon_name="dialog-information-symbolic"))
            head.append(Gtk.Label(label="จดไอเดีย", css_classes=["title"], hexpand=True, xalign=0))
            head.append(Gtk.Label(label="Super+I", css_classes=["kbd"]))
            self.set_titlebar(Gtk.WindowHandle(child=head))  # drag it by its top, as any window

            body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=18, margin_end=18,
                           margin_bottom=16, margin_top=6)
            self.text = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, accepts_tab=False, height_request=64)
            frame = Gtk.Box(css_classes=["box"])
            frame.append(self.text)
            self.text.set_hexpand(True)
            body.append(frame)

            self.chips = Gtk.Box(spacing=6)
            self.chips.append(Gtk.Label(label="แท็กที่น่าจะใช่:", css_classes=["muted"]))
            self.chip_box = Gtk.Box(spacing=6)
            self.chips.append(self.chip_box)
            self.add_button = Gtk.Button(label="+ แท็ก", css_classes=["add"])
            self.add_button.connect("clicked", self.on_add)
            self.chips.append(self.add_button)
            self.tag_entry = Gtk.Entry(placeholder_text="แท็ก", css_classes=["tag"], visible=False, width_chars=10)
            self.tag_entry.connect("activate", self.on_tag_done)
            self.chips.append(self.tag_entry)
            body.append(self.chips)

            foot = Gtk.Box(spacing=8)
            self.hint = Gtk.Label(label="Enter บันทึก · Shift+Enter ขึ้นบรรทัด · Esc ปิด", css_classes=["muted"],
                                  hexpand=True, xalign=0, wrap=True)
            foot.append(self.hint)
            save_button = Gtk.Button(label="บันทึก", css_classes=["save"])
            save_button.connect("clicked", lambda *_: self.on_save())
            foot.append(save_button)
            body.append(foot)
            self.set_child(body)

            keys = Gtk.EventControllerKey()
            keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)  # before the text view takes Enter
            keys.connect("key-pressed", self.on_key)
            self.add_controller(keys)
            self.text.get_buffer().connect("changed", self.on_changed)
            self.text.grab_focus()

        # -- typing
        def on_key(self, _ctrl, keyval, _code, state) -> bool:
            if keyval == Gdk.KEY_Escape:
                if self.tag_entry.get_visible():
                    self.tag_entry.set_visible(False)
                    self.text.grab_focus()
                else:
                    self.close()
                return True
            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and not state & Gdk.ModifierType.SHIFT_MASK:
                if self.tag_entry.has_focus():
                    return False  # the tag box takes its own Enter
                self.on_save()
                return True
            return False

        def current(self) -> str:
            buf = self.text.get_buffer()
            return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()

        def on_changed(self, _buf) -> None:
            if self.timer:
                GLib.source_remove(self.timer)
            self.timer = GLib.timeout_add(300, self.ask_tags)

        def ask_tags(self) -> bool:
            self.timer = 0
            text = self.current()
            self.asked += 1
            ticket = self.asked

            def work() -> None:
                tags = suggest(text) if text else []
                GLib.idle_add(self.show_tags, tags, ticket)

            threading.Thread(target=work, daemon=True).start()
            return False

        def show_tags(self, tags: list[str], ticket: int) -> bool:
            if ticket != self.asked:
                return False
            self.suggested = tags
            self.dropped &= set(tags)
            self.draw_chips()
            return False

        def draw_chips(self) -> None:
            while (child := self.chip_box.get_first_child()) is not None:
                self.chip_box.remove(child)
            for tag in self.suggested + [t for t in self.extra if t not in self.suggested]:
                chip = Gtk.Button(label="#" + tag, css_classes=["chip"] + (["off"] if tag in self.dropped else []))
                chip.connect("clicked", self.on_chip, tag)
                self.chip_box.append(chip)

        def on_chip(self, _button, tag: str) -> None:
            if tag in self.extra:
                self.extra.remove(tag)
            elif tag in self.dropped:
                self.dropped.discard(tag)
            else:
                self.dropped.add(tag)
            self.draw_chips()
            self.text.grab_focus()

        def on_add(self, _button) -> None:
            self.tag_entry.set_visible(True)
            self.tag_entry.grab_focus()

        def on_tag_done(self, entry) -> None:
            tag = entry.get_text().strip().lstrip("#").lower().replace(" ", "-")
            if tag and tag not in self.extra and tag not in self.suggested:
                self.extra.append(tag)
            self.dropped.discard(tag)
            entry.set_text("")
            entry.set_visible(False)
            self.draw_chips()
            self.text.grab_focus()

        # -- saving
        def on_save(self) -> None:
            text = self.current()
            if not text or self.busy:
                return
            self.busy = True
            tags = chosen(self.suggested, self.dropped, self.extra)
            self.hint.set_label("กำลังบันทึก…")

            def work() -> None:
                said, close = save(text, tags)
                GLib.idle_add(self.saved, said, close)

            threading.Thread(target=work, daemon=True).start()

        def saved(self, said: str, close: bool) -> bool:
            self.busy = False
            self.hint.set_label(("✓ " if close else "") + said)
            for c in ("done", "bad"):
                self.hint.remove_css_class(c)
            self.hint.add_css_class("done" if close else "bad")
            if close:
                self.text.set_editable(False)
                GLib.timeout_add(1400, lambda: (self.close(), False)[1])
            return False

    class App(Gtk.Application):
        def __init__(self) -> None:
            super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

        def do_startup(self) -> None:
            Gtk.Application.do_startup(self)
            css = Gtk.CssProvider()
            css.load_from_string(CSS)
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        def do_activate(self) -> None:
            win = self.get_active_window() or Popup(self)  # Super+I again: the same window comes back
            win.present()

    return App().run([])


if __name__ == "__main__":
    raise SystemExit(main())
