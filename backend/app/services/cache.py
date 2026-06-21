"""Database-backed snapshot cache with stale-while-revalidate (M6+).

The goal: skimming a page should never wait on Google. We persist the last fetch
of each expensive read in the `snapshots` table and serve it instantly. When the
snapshot is older than a TTL we still serve it immediately, but kick a background
refresh so the *next* visit is fresh — the classic "stale-while-revalidate".

Usage from a router (sync path operation):

    @router.get("/things")
    def things(background_tasks: BackgroundTasks, refresh: bool = False):
        return cache.serve("things", fetch_things, ttl=600,
                           refresh=refresh, add_task=background_tasks.add_task)

`serve` returns an envelope: {"data": ..., "fetched_at": iso, "stale": bool}.
The fetcher is any zero-arg callable returning JSON-serializable data.

Writes elsewhere can invalidate a family of keys with `clear_prefix("calendar:")`
so the next read re-fetches (e.g. after the user creates a calendar event).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import Snapshot

log = logging.getLogger(__name__)


def _now() -> datetime:
    """Current UTC time, naive (SQLite stores naive datetimes)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_iso(dt: datetime) -> str:
    """Render a stored (naive UTC) datetime as an explicit-UTC ISO string."""
    return dt.replace(tzinfo=timezone.utc).isoformat()


def get(key: str) -> tuple[Any, datetime] | None:
    """Return (data, fetched_at) for `key`, or None if not cached."""
    with SessionLocal() as db:
        row = db.get(Snapshot, key)
        if row is None:
            return None
        return json.loads(row.content), row.fetched_at


def set(key: str, data: Any) -> datetime:
    """Store `data` under `key` and return the fetch time."""
    now = _now()
    content = json.dumps(data)
    with SessionLocal() as db:
        row = db.get(Snapshot, key)
        if row:
            row.content = content
            row.fetched_at = now
        else:
            db.add(Snapshot(key=key, content=content, fetched_at=now))
        db.commit()
    return now


def clear_prefix(prefix: str) -> int:
    """Delete every snapshot whose key starts with `prefix`. Returns the count.

    Used to invalidate a family of cached reads after a write (e.g. all
    "calendar:*" ranges once an event is created/edited/deleted).
    """
    with SessionLocal() as db:
        keys = db.scalars(select(Snapshot.key).where(Snapshot.key.startswith(prefix))).all()
        if keys:
            db.execute(delete(Snapshot).where(Snapshot.key.startswith(prefix)))
            db.commit()
        return len(keys)


def _refresh_safe(key: str, fetcher: Callable[[], Any]) -> None:
    """Re-fetch and store in the background; never raise (it's best-effort)."""
    try:
        set(key, fetcher())
    except Exception:
        log.exception("background refresh failed for %s", key)


def serve(
    key: str,
    fetcher: Callable[[], Any],
    *,
    ttl: float,
    refresh: bool = False,
    add_task: Callable[..., None] | None = None,
) -> dict:
    """Serve `key` from cache, refreshing per stale-while-revalidate.

    - `refresh=True` or a cold cache → fetch synchronously now (and store).
    - cached & fresh (age <= ttl) → return it as-is.
    - cached & stale (age > ttl) → return it immediately, but schedule a
      background refresh via `add_task` (if provided) so the next read is fresh.
    """
    snap = None if refresh else get(key)

    if snap is None:
        data = fetcher()
        fetched = set(key, data)
        return {"data": data, "fetched_at": _to_iso(fetched), "stale": False}

    data, fetched = snap
    age = (_now() - fetched).total_seconds()
    stale = age > ttl
    if stale and add_task is not None:
        add_task(_refresh_safe, key, fetcher)
    return {"data": data, "fetched_at": _to_iso(fetched), "stale": stale}
