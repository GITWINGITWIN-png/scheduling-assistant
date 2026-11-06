"""The gate for other projects (2.5) and their news (2.3): JSON files in ~/.secretary/inbox.

A project writes `~/.secretary/inbox/<its folder name>/<anything>.json` (docs/CONNECT.md says
how; a copy sits in the inbox itself). The secretary only reads: each file becomes one news
row and moves to `read/`; a file it can't read moves to `bad/` and says so in the news.
Three kinds: report (news), schedule (a task with a due date, so the planner books time),
status (how an automatic run went). No model.

A failure or a question (failed / needs_you) from a project that matters, potential S–A or
urgency 4–5, goes to #ด่วน at once (URGENT hooks, cards.py); everything else waits for the
morning brief and the pages (the agreed rule, stage 1).
"""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.config import REPO_DIR, get_config
from app.core.db import now, session
from app.core.tables import Task
from app.features.projects.tables import Project, ProjectNews

log = logging.getLogger(__name__)

KINDS = ("report", "schedule", "status")
MAX_BYTES = 256 * 1024  # a news file, not a dataset

# Called with the news id when something urgent arrives (cards.py posts it to #ด่วน).
URGENT: list[Callable[[int], Awaitable[None]]] = []


def inbox_dir() -> Path:
    return get_config().data_dir / "inbox"


def ensure() -> Path:
    """The inbox and its CONNECT.md (a copy of docs/CONNECT.md, so a project finds the rules next to the door)."""
    d = inbox_dir()
    d.mkdir(parents=True, exist_ok=True)
    guide = REPO_DIR / "docs" / "CONNECT.md"
    if guide.is_file() and (not (d / "CONNECT.md").is_file() or (d / "CONNECT.md").read_text() != guide.read_text()):
        shutil.copyfile(guide, d / "CONNECT.md")
    return d


def matters(p: Project | None) -> bool:
    """A project whose failures and questions can't wait for the morning."""
    return p is not None and (p.potential in ("S", "A") or p.urgency >= 4)


def _when(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=get_config().tz)


def _move(f: Path, sub: str) -> None:
    target = f.parent / sub
    target.mkdir(exist_ok=True)
    dest = target / f.name
    n = 1
    while dest.exists():  # never overwrite an older file of the same name
        dest = target / f"{f.stem}-{n}{f.suffix}"
        n += 1
    f.rename(dest)


def read_one(f: Path, project: Project | None) -> int:
    """One file -> one news row (and maybe a task). -> the news id."""
    name = f.parent.name
    try:
        if f.stat().st_size > MAX_BYTES:
            raise ValueError(f"ไฟล์ใหญ่เกิน {MAX_BYTES // 1024} KB")
        data = json.loads(f.read_text())
        if not isinstance(data, dict) or data.get("kind") not in KINDS or not str(data.get("title", "")).strip():
            raise ValueError("ต้องมี kind (report · schedule · status) และ title")
    except (ValueError, OSError) as exc:
        with session() as s:
            row = ProjectNews(project_id=project.id if project else None, project=name, kind="bad",
                              title=f"อ่านไฟล์ {f.name} ไม่ได้", body=str(exc)[:300], file=f.name)
            s.add(row)
            s.flush()
            news_id = row.id
        _move(f, "bad")
        return news_id
    kind = data["kind"]
    failed = bool(data.get("failed")) or data.get("status") == "failed"
    needs_you = bool(data.get("needs_you"))
    with session() as s:
        p = s.get(Project, project.id) if project else None
        row = ProjectNews(project_id=p.id if p else None, project=name, kind=kind, title=str(data["title"]).strip()[:300],
                          body=str(data.get("body", "")).strip()[:2000], link=str(data.get("link", "")).strip()[:500],
                          at=_when(data.get("at")) or now(), failed=failed, needs_you=needs_you,
                          urgent=(failed or needs_you) and matters(p), file=f.name)
        s.add(row)
        s.flush()
        news_id = row.id
        if kind == "schedule" and (due := _when(data.get("due"))):
            minutes = data.get("minutes")
            s.add(Task(title=f"{name}: {row.title}", due_at=due, est_minutes=int(minutes) if isinstance(minutes, int) and minutes > 0 else None,
                       source="project", source_ref=str(news_id), project=name, details=row.body))
        if kind == "status" and p is not None and data.get("status") in ("running", "done", "failed", "paused") and p.status != "done":
            p.status = "auto"  # it reports its own runs: a project that runs by itself
    _move(f, "read")
    return news_id


def files() -> list[tuple[Path, str]]:
    """Every waiting file: (path, its project folder's name). Hidden names and sub-folders are skipped."""
    root = inbox_dir()
    if not root.is_dir():
        return []
    out = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        out += [(f, folder.name) for f in sorted(folder.glob("*.json")) if not f.name.startswith(".")]
    return out


async def run() -> str | None:
    """The "inbox" round (every 5 minutes): read what's new. -> a line, or None when nothing came."""
    waiting = files()
    if not waiting:
        return None
    with session() as s:
        projects = {p.name: p for p in s.scalars(select(Project))}
        s.expunge_all()
    read, bad, urgent = 0, 0, []
    for f, name in waiting:
        news_id = read_one(f, projects.get(name))
        with session() as s:
            row = s.get(ProjectNews, news_id)
            bad += row.kind == "bad"
            read += row.kind != "bad"
            if row.urgent:
                urgent.append(news_id)
    for news_id in urgent:
        for hook in URGENT:
            try:
                await hook(news_id)
            except Exception:
                log.exception("urgent project news %s couldn't be sent", news_id)
    parts = [f"ข่าวโปรเจค {read} เรื่อง"] + ([f"ด่วน {len(urgent)}"] if urgent else []) + ([f"อ่านไม่ได้ {bad}"] if bad else [])
    return " · ".join(parts)


def setup() -> None:
    from app.core import clock
    ensure()
    clock.attach("inbox", run)
