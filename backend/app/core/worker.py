"""One secretary at a time does the background work: the clock and the Discord bot.

The secretary can run twice on one machine, e.g. the always-on service on :8000 and
`uvicorn --port 8001` while trying something. Both would log in as the same Discord bot,
so every DM got two different answers (it happened on 2026-11-05). Both would also run
the clock, so every round would run twice, and from B2 every alert would arrive twice.

So the first process to start takes a lock on ~/.secretary/worker.lock and becomes the
"worker": it runs the clock and the bot. Any other process serves only the web page and
the API. They share one database, so every page shows the same data. If the worker
stops, another process takes over within LOCK_RETRY seconds.

Why flock and not a "pid file": the kernel drops the lock as soon as its process ends,
even on a crash or `kill -9`. A stale file can never block the secretary from starting.
"""

import fcntl
import os
from pathlib import Path
from typing import IO

from app.core.config import get_config

LOCK_RETRY = 30  # seconds between tries, for a process waiting to take over

_held: IO[str] | None = None  # the open lock file; closing it (or exiting) releases the lock


def lock_path() -> Path:
    return get_config().data_dir / "worker.lock"


def claim() -> bool:
    """Try to become the worker. Never waits: returns False at once if another process holds it."""
    global _held
    if _held is not None:
        return True
    f = open(lock_path(), "a+")  # "a+" creates it if missing and doesn't wipe the holder's pid
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return False
    f.truncate(0)
    f.write(f"{os.getpid()}\n")  # only so the other process can say who holds it
    f.flush()
    _held = f
    return True


def holder() -> str:
    """The pid of the process that holds the lock (for messages), or "?"."""
    try:
        return lock_path().read_text().strip() or "?"
    except OSError:
        return "?"


def is_worker() -> bool:
    return _held is not None
