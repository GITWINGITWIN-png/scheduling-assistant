"""Read project progress from local git repos (M4).

The headline feature plans around what's *actually* happening, not just what you
typed. The cheapest reliable signal is your git history: when you last committed
and how much recent activity there is. We read that with plain `git` calls — no
network, no Claude tokens.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path


def _git(repo_path: str, *args: str) -> str | None:
    """Run a git command inside `repo_path`; return stdout, or None on failure."""
    try:
        out = subprocess.run(
            ["git", "-C", repo_path, *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def is_git_repo(path: str) -> bool:
    return (Path(path) / ".git").exists()


def last_commit_at(repo_path: str) -> datetime | None:
    """Datetime of the most recent commit (committer date), or None."""
    iso = _git(repo_path, "log", "-1", "--format=%cI")
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return None


def read_progress(repo_path: str) -> dict:
    """A small snapshot of recent git activity for one repo."""
    last = last_commit_at(repo_path)
    count = _git(repo_path, "rev-list", "--count", "HEAD")
    recent = _git(repo_path, "rev-list", "--count", "--since=14.days", "HEAD")
    subjects = _git(repo_path, "log", "-5", "--format=%s") or ""
    return {
        "last_commit_at": last.isoformat() if last else None,
        "commit_count": int(count) if count and count.isdigit() else 0,
        "commits_last_14d": int(recent) if recent and recent.isdigit() else 0,
        "recent_subjects": [s for s in subjects.splitlines() if s],
    }


def discover_repos(root: str) -> list[dict]:
    """Find git repos directly under `root` (one level deep).

    Returns {name, path, last_commit_at} per repo. Staying one level deep keeps
    it fast and avoids walking into node_modules/.venv — point it at the folder
    that holds your projects.
    """
    root_path = Path(root).expanduser()
    if not root_path.is_dir():
        return []

    repos: list[dict] = []
    for child in sorted(root_path.iterdir()):
        if child.is_dir() and is_git_repo(str(child)):
            last = last_commit_at(str(child))
            repos.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "last_commit_at": last.isoformat() if last else None,
                }
            )
    return repos
