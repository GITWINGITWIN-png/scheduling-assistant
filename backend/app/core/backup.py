"""The nightly backup round: a copy of secretary.db each day, the newest 14 kept.

Why SQLite's own backup API rather than copying the file: with WAL mode, the
latest changes may still sit in secretary.db-wal, and the bot or the web page
may be writing at that moment. `Connection.backup()` reads a consistent
snapshot through SQLite itself. A plain file copy can capture half a write.

Restoring: docs/setup/always-on.md ("กู้คืนจากไฟล์สำรอง").
"""

import asyncio
import sqlite3
from pathlib import Path

from app.core import clock
from app.core.config import get_config
from app.core.db import now
from app.core.timefmt import local

KEEP = 14


def backup_dir() -> Path:
    return get_config().data_dir / "backups"


def backup_now() -> Path:
    """Write today's backup (replacing an earlier one from today) and prune to the newest KEEP."""
    folder = backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"secretary-{local(now()):%Y-%m-%d}.db"
    tmp = dest.with_suffix(".db.part")  # never leave a half-written backup under the real name
    src = sqlite3.connect(get_config().db_path)
    dst = sqlite3.connect(tmp)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    tmp.replace(dest)
    for old in sorted(folder.glob("secretary-*.db"))[:-KEEP]:  # names sort by date
        old.unlink()
    return dest


async def run() -> str:
    path = await asyncio.to_thread(backup_now)  # file work off the event loop, so the bot keeps answering
    count = len(list(backup_dir().glob("secretary-*.db")))
    return f"{path.name} · {path.stat().st_size / 1024:.0f} KB · เก็บไว้ {count} ไฟล์"


def setup() -> None:
    """Give the clock's "backup" round its work (called before the clock starts)."""
    clock.attach("backup", run)
