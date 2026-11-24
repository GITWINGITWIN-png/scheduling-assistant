"""The project registry (2.1): every folder directly under ~/Projects, rescanned every morning.

From each folder the scan reads only what's cheap and local: whether it's a git repo, when it
last changed (the last commit, or the folder's own time when there's no git), how many commits
the last 14 days had, and its PROGRESS.md (progress.py). No network, no model.

The first scan meets everything at once (40-odd folders here, backups and copies among them),
so it records them quietly: potential C, urgency 2, and the status from recent activity (a
change in the last 14 days: active, otherwise paused). You set the levels, or hide what isn't a
project, on the projects page (the user's choice at the B5 plan). A folder that appears after
that is asked about in #approvals (D5 ⑥); until you answer it works with C, 2.

my_secretary itself is listed like any project, but the secretary never works on it in the
background: it would be changing its own code while it runs.
"""

from __future__ import annotations

import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.core import settings
from app.core.config import REPO_DIR, get_config
from app.core.db import now, session
from app.core.tables import Decision
from app.features.projects import progress
from app.features.projects.tables import DEFAULT_POTENTIAL, DEFAULT_URGENCY, Project

ACTIVE_DAYS = 14  # a change within this many days: in progress on the first scan
STATE_KEY = "state.projects"  # {"first_scan": when}: after it, a new folder is asked about

# Called with (project id, decision id) when a new project's levels are asked (cards.py posts it).
ASKED: list[Callable[[int, int], Awaitable[None]]] = []


def is_self(path: str | Path) -> bool:
    """my_secretary's own folder: listed, never worked on in the background."""
    return Path(path).resolve() == REPO_DIR.resolve()


def _git(path: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=10, check=True)
        return out.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


@dataclass
class Seen:
    path: Path
    is_git: bool
    last_activity: datetime | None
    commits_14d: int
    progress: dict = field(default_factory=dict)


def look(path: Path) -> Seen:
    """What one folder shows right now."""
    is_git = (path / ".git").exists()
    last, recent = None, 0
    if is_git:
        if iso := _git(path, "log", "-1", "--format=%cI"):
            last = datetime.fromisoformat(iso)
        count = _git(path, "rev-list", "--count", f"--since={ACTIVE_DAYS}.days", "HEAD")
        recent = int(count) if count and count.isdigit() else 0
    if last is None:
        last = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return Seen(path, is_git, last, recent, progress.read(path))


def folders(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))


@dataclass
class Scan:
    first: bool
    total: int
    new: list[tuple[int, int]] = field(default_factory=list)  # (project id, decision id) asked about
    gone: list[str] = field(default_factory=list)

    def line(self) -> str | None:
        if self.first:
            return f"จดโปรเจคที่มีอยู่ {self.total} โฟลเดอร์ · ระดับ C · 2 ไปก่อน ตั้งเองได้ในหน้าโปรเจค"
        parts = [f"โปรเจคใหม่ {len(self.new)}"] if self.new else []
        if self.gone:
            parts.append(f"โฟลเดอร์หายไป {len(self.gone)}: {', '.join(self.gone)}")
        return " · ".join(parts) or None


def scan(root: Path | None = None, at: datetime | None = None) -> Scan:
    """Bring the registry up to date with ~/Projects (blocking: git calls)."""
    root = root or get_config().projects_dir
    at = at or now()
    seen = [look(p) for p in folders(root)]
    first = not (settings.get(STATE_KEY, {}) or {}).get("first_scan")
    with session() as s:
        known = {p.path: p for p in s.scalars(select(Project))}
        result = Scan(first=first, total=len(seen))
        for f in seen:
            row = known.get(str(f.path))
            if row is None:
                active = f.last_activity is not None and f.last_activity >= at - timedelta(days=ACTIVE_DAYS)
                row = Project(name=f.path.name, path=str(f.path), status="active" if active else "paused",
                              potential=DEFAULT_POTENTIAL, urgency=DEFAULT_URGENCY, first_seen=at)
                s.add(row)
                s.flush()
                if not first:
                    d = Decision(kind="project_level", title=row.name,
                                 detail={"project_id": row.id, "path": row.path, "is_git": f.is_git})
                    s.add(d)
                    s.flush()
                    result.new.append((row.id, d.id))
            row.is_git, row.last_activity, row.commits_14d, row.progress = f.is_git, f.last_activity, f.commits_14d, f.progress
            row.missing, row.scanned_at = False, at
        found = {str(f.path) for f in seen}
        for path, row in known.items():
            if path not in found and not row.missing:
                row.missing = True
                result.gone.append(row.name)
    if first:
        settings.put(STATE_KEY, {"first_scan": at.isoformat()})
    return result


def set_levels(decision_id: int, potential: str, urgency: int, *,
               via: tuple[str, str] = ("หน้าเว็บ", "")) -> tuple[Decision, int]:
    """You answered "Set the project level again" (in #approvals, on the web, or in the chat). -> (it, action id)."""
    from app.core import actions
    from app.features.projects.tables import POTENTIALS

    if potential not in POTENTIALS or not 0 <= urgency <= 5:
        raise ValueError("potential S–F และความเร่งด่วน 0–5")
    with session() as s:
        d = s.get(Decision, decision_id)
        if d is None or d.kind != "project_level":
            raise ValueError("ไม่พบคำถามนี้")
        if d.status != "pending":
            raise ValueError("ตั้งระดับไปแล้ว")
        p = s.get(Project, d.detail["project_id"])
        old = {"potential": p.potential, "urgency": p.urgency, "level_set": p.level_set}
        p.potential, p.urgency, p.level_set = potential, urgency, True
        d.status, d.answered_at = "approved", now()
        name = p.name
        s.expunge(d)
    action_id = actions.record("project.level", f"ตั้งระดับโปรเจค {name}", f"{potential} · เร่งด่วน {urgency}",
                               source_label=via[0], source_url=via[1],
                               undo={"project_id": d.detail["project_id"], "decision_id": decision_id, "old": old})
    return d, action_id


async def run() -> str | None:
    """The "projects" round (06:30): rescan, ask about new folders."""
    import asyncio

    result = await asyncio.to_thread(scan)
    for project_id, decision_id in result.new:
        for hook in ASKED:
            await hook(project_id, decision_id)
    return result.line()


async def _undo_level(undo: dict) -> None:
    with session() as s:
        if p := s.get(Project, undo["project_id"]):
            for k, v in undo["old"].items():
                setattr(p, k, v)
        if d := s.get(Decision, undo["decision_id"]):
            d.status, d.answered_at = "pending", None


def setup() -> None:
    from app.core import actions, clock

    clock.attach("projects", run)
    actions.register_undo("project.level", _undo_level)
