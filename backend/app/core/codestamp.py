"""Is the backend code on disk newer than the code that is running? (the shell's restart banner)

The service loads the backend once, when it starts, but the web page (frontend/dist) is read
from disk on every request. So after new code arrives (a pull, a branch switch, a build), the
page is already new while the backend is still the old one, and a field the old backend
doesn't know is dropped without any error. That happened on 2026-11-06: task details looked
saved but were never stored, because the service had started before they existed.

This module fingerprints the backend's code when the process starts and compares it with what
is on disk now. Cheap to ask often: file sizes and times are checked first, and the files are
read again only when one of them changed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # backend/
PATTERNS = ("app/**/*.py", "migrations/versions/*.py")


def _files() -> list[Path]:
    return sorted(p for pattern in PATTERNS for p in ROOT.glob(pattern))


def _signature() -> tuple:
    out = []
    for p in _files():
        try:
            st = p.stat()
        except FileNotFoundError:  # removed between the listing and now
            continue
        out.append((p.as_posix(), st.st_mtime_ns, st.st_size))
    return tuple(out)


def _content() -> str:
    h = hashlib.sha256()
    for p in _files():
        try:
            data = p.read_bytes()
        except FileNotFoundError:
            continue
        h.update(p.relative_to(ROOT).as_posix().encode() + b"\0" + data)
    return h.hexdigest()


STARTED = _content()  # the code this process is running
_last = (_signature(), STARTED)


def stale() -> bool:
    """True when the code on disk differs from the code this process started with."""
    global _last
    signature = _signature()
    if signature != _last[0]:  # something was touched: compare contents (a touch alone isn't a change)
        _last = (signature, _content())
    return _last[1] != STARTED
