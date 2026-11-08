"""Where the secretary's work on a project goes on from (B5, decided after the check, 2026-11-06).

All of the secretary's work on a project is on one branch, `secretary/<project>`: every job adds
its commits there, so the next job sees what the last one did, and you merge it once when you
like. (First it was a branch per job, each from your HEAD; unmerged, the next job couldn't see
the last one's work and did the same step again: slugify three times in the sandbox.)

- No such branch yet, or you merged it (all its commits are in your HEAD): the next job starts
  from your HEAD, and the branch is (re)made there.
- Its work isn't merged yet: the next job goes on from the branch's tip. When your HEAD has
  commits the branch hasn't, the runner merges them into the secretary's branch first (main is
  never touched); if they clash, the job stops and asks you to merge it yourself.

What a job is about to do is read from the same place: the next step in PROGRESS.md at the
branch (where the done steps are ticked), and the files the planner looks at.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.features.projects import progress


def slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.").lower()[:40] or "project"


def branch_name(project: str) -> str:
    return f"secretary/{slug(project)}"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30)


@dataclass(frozen=True)
class Base:
    branch: str  # secretary/<project>
    ref: str  # the commit the next job starts from
    on_branch: bool  # True: the secretary's unmerged work goes on · False: from your HEAD
    head: str  # your HEAD
    head_name: str  # your current branch ("main")
    ahead: int  # the secretary's commits not in your HEAD
    behind: int  # your commits the secretary's branch hasn't (merged in when the job starts)

    def words(self) -> str:
        """For the planner and the job's result."""
        if not self.on_branch:
            return f"{self.head_name} ({self.head[:7]})"
        more = f" · {self.head_name} มี commit ใหม่ {self.behind} อัน จะรวมเข้ามาก่อนเริ่ม" if self.behind else ""
        return f"{self.branch}: งานของเลขาที่ยังไม่ได้รวม {self.ahead} commit{more}"


def find(root: Path, project: str) -> Base:
    """Where the next job of this project starts (git only, no change)."""
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    head_name = _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "HEAD"
    branch = branch_name(project)
    tip = _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}^{{commit}}").stdout.strip()
    if not tip or not head or _git(root, "merge-base", "--is-ancestor", tip, head).returncode == 0:
        return Base(branch, head, False, head, head_name, 0, 0)
    ahead = int(_git(root, "rev-list", "--count", f"{head}..{tip}").stdout.strip() or 0)
    behind = int(_git(root, "rev-list", "--count", f"{tip}..{head}").stdout.strip() or 0)
    return Base(branch, tip, True, head, head_name, ahead, behind)


def next_step(root: Path, project: str) -> tuple[str, Base]:
    """The next unchecked step in PROGRESS.md where the next job starts. -> (step or "", base)."""
    b = find(root, project)
    return (progress.read_at(root, b.ref).get("next", "") if b.ref else ""), b
