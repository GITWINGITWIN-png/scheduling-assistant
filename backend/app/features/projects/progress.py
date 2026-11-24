"""Reading a project's PROGRESS.md (2.4): how far it is, and the next step.

The background work takes "where a project is stuck" from here only (the user's choice at the
B5 plan: not Claude Code's own logs). Checkbox lines are the plan: "- [ ] …" to do, "- [x] …"
done. The next step is the first unchecked item; when it has unchecked items under it, the
first of those, so "B5 (Projects) › 1. Project registry" rather than the whole phase. An unchecked
item under one already checked (a check left for later) is not the next step.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

ITEM = re.compile(r"^(\s*)[-*+]\s+\[([ xX])\]\s+(.*\S)")
NAMES = ("PROGRESS.md", "progress.md", "Progress.md")


def find(folder: Path) -> Path | None:
    for name in NAMES:
        if (folder / name).is_file():
            return folder / name
    return None


def plain(text: str) -> str:
    """"**B5 (Projects)** (major task): …" -> "B5 (Projects) (major task)" (markdown and the trailing notes dropped)."""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]*)\*\*|__([^_]*)__", lambda m: m.group(1) or m.group(2), text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.split(": ")[0] if len(text) > 80 else text  # "title: a long explanation" -> the title
    return " ".join(text.split())[:160]


def _under_done(items: list[tuple[int, bool, str]]) -> list[bool]:
    """For each item: is it under an item already checked? (a check left for later, a note)"""
    out, stack = [], []  # stack: (indent, checked) of the items above
    for indent, checked, _ in items:
        while stack and stack[-1][0] >= indent:
            stack.pop()
        out.append(any(c for _, c in stack))
        stack.append((indent, checked))
    return out


def parse(text: str) -> dict:
    items = [(len(m.group(1).replace("\t", "    ")), m.group(2) != " ", plain(m.group(3)))
             for line in text.splitlines() if (m := ITEM.match(line))]
    done = sum(1 for _, checked, _ in items if checked)
    leftover = _under_done(items)
    path: list[str] = []
    # the next step: the first unchecked item that isn't a leftover under something already done
    i = next((k for k, (_, checked, _) in enumerate(items) if not checked and not leftover[k]), None)
    while i is not None:
        indent, _, title = items[i]
        path.append(title)
        child = None
        for k in range(i + 1, len(items)):
            if items[k][0] <= indent:
                break
            if not items[k][1] and items[k][0] > indent:
                child = k
                break
        i = child
    return {"done": done, "todo": len(items) - done, "next": " › ".join(path[:3])}


def read(folder: Path) -> dict:
    """{} when there's no PROGRESS.md; else {"done", "todo", "next", "updated"}."""
    f = find(folder)
    if f is None:
        return {}
    try:
        text = f.read_text(errors="replace")
    except OSError:
        return {}
    updated = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
    return {**parse(text), "file": f.name, "updated": updated.isoformat()}


def read_at(folder: Path, ref: str) -> dict:
    """The same, from a commit instead of the folder (B5: the secretary's own branch, where the
    steps its jobs did are ticked). {} when that commit has no PROGRESS.md."""
    import subprocess

    for name in NAMES:
        out = subprocess.run(["git", "-C", str(folder), "show", f"{ref}:{name}"], capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            return {**parse(out.stdout), "file": name}
    return {}
