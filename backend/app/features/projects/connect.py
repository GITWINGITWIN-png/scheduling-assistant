"""เชื่อมโปรเจคกับเลขา (B10, feature 2.5): a note in each project that tells Claude Code working
there to send its progress to the secretary, with the `secretary-news` command
(desktop/secretary_news.py, which writes docs/CONNECT.md's JSON into the inbox).

Where the note goes, and why (the user's answer: "ให้ไปเขียนในโปรเจคอื่นๆ"):
- The project's CLAUDE.local.md. Claude Code reads it in the folder it starts in and in every folder
  above, so a session started in a subfolder (job-search/ai-job-search) reads it too.
- CLAUDE.local.md is for personal notes that aren't committed, which this one is: the inbox exists
  only on this computer. In a git repo the file goes into .git/info/exclude, so it never shows up
  to commit, and the project's own CLAUDE.md is never touched.
- A project that relies on AGENTS.md gets "@AGENTS.md" in the note: any CLAUDE.local.md stops
  Claude Code from reading AGENTS.md on its own.

The note sits between two markers, so connecting again rewrites only it, and undo takes back
exactly what connecting changed: the note (and the file, if it was made for it) and the exclude
line it added. Whatever else you write in CLAUDE.local.md stays.
"""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import select

from app.core import actions
from app.core.config import get_config
from app.core.db import session
from app.features.projects import inbox
from app.features.projects.scan import is_self
from app.features.projects.tables import Project

Via = tuple[str, str]
FILE = "CLAUDE.local.md"
START = "<!-- secretary:connect"
END = "<!-- /secretary:connect -->"
IGNORE = ["# my_secretary: its note to this project (เชื่อมกับเลขา), only on this computer", f"/{FILE}"]


def note(name: str, agents: bool = False) -> str:
    """The note for one project. The markers are HTML comments, which Claude Code strips before
    reading, so they cost nothing; the rest is what Claude in that project reads every session."""
    guide = str(inbox.inbox_dir() / "CONNECT.md").replace(str(Path.home()), "~", 1)
    lines = [
        f"{START} · เขียนโดยเลขา (my_secretary) · เลิกเชื่อมได้ที่หน้าโปรเจคของเลขา -->",
        *(["@AGENTS.md", ""] if agents else []),
        "## ส่งข่าวให้เลขา",
        "",
        "ผู้ใช้มีเลขาส่วนตัว (my_secretary) ที่รวมความคืบหน้าของทุกโปรเจคไว้ในสรุปเช้าและหน้าเว็บของเลขา",
        f"โปรเจคนี้ชื่อ `{name}` ในทะเบียนของเลขา · เมื่อมีเรื่องที่ผู้ใช้ควรรู้ ส่งด้วยคำสั่ง `secretary-news`"
        " (หัวข้อภาษาไทย บรรทัดเดียว สั้น):",
        "",
        '- จบขั้นใน PROGRESS.md หรือถึง milestone: `secretary-news report "เสร็จ: <อะไร>" --body "ขั้นต่อไป: <อะไร>"`'
        " (มีลิงก์ให้ดู ใส่ `--link`)",
        "- ติดอยู่ หรือต้องให้ผู้ใช้ตัดสินหรือตรวจ: เพิ่ม `--needs-you`",
        '- เจอกำหนดส่งหรือเดดไลน์: `secretary-news schedule "<งาน>" --due 2026-11-13T17:00 --minutes 90`'
        " (เลขาจองเวลาในตารางให้)",
        '- งานที่รันเอง (feed, backtest, สคริปต์ตามเวลา) จบหรือล้ม: `secretary-news status "<งาน>" --state done`'
        ' หรือ `--state failed --body "<สาเหตุ>"` · สคริปต์ในโปรเจคเรียกคำสั่งนี้ได้เหมือนกัน',
        "",
        "ส่งเฉพาะเรื่องที่มีความหมาย ไม่ต้องส่งทุกครั้งที่แก้ไฟล์ · ห้ามใส่รหัสผ่าน token หรือข้อมูลลับ"
        f" · รูปแบบทั้งหมด: `{guide}`",
        END,
    ]
    return "\n".join(lines) + "\n"


def _split(text: str) -> tuple[str, str | None]:
    """(the file's text without the note, the note) — the note is None when there's none."""
    start = text.find(START)
    if start < 0:
        return text, None
    end = text.find(END, start)
    end = len(text) if end < 0 else end + len(END)
    rest = [part for part in (text[:start].rstrip(), text[end:].strip()) if part]
    return ("\n\n".join(rest) + "\n" if rest else ""), text[start:end] + "\n"


def connected(path: str | Path) -> bool:
    try:
        return START in (Path(path) / FILE).read_text()
    except OSError:
        return False


def why_not(p: Project) -> str:
    """Why this project gets no note ("" when it can have one)."""
    if is_self(p.path):
        return "นี่คือตัวเลขาเอง"
    if p.hidden:
        return "ซ่อนไว้ (ไม่ใช่โปรเจค)"
    if p.missing or not Path(p.path).is_dir():
        return "ไม่พบโฟลเดอร์"
    return ""


def _uses_agents(path: Path) -> bool:
    return (path / "AGENTS.md").is_file() and not any((path / f).is_file() for f in ("CLAUDE.md", ".claude/CLAUDE.md"))


def _exclude(path: Path, add: bool) -> bool:
    """Keep the note's file out of git, on this computer only (.git/info/exclude). Adds nothing
    when git already ignores it (your global ignore, say). -> whether the exclude file changed."""
    git = path / ".git"
    if not git.is_dir():  # not a repo (or a worktree, whose .git is a file): nothing to hide from
        return False
    f = git / "info" / "exclude"
    lines = f.read_text().splitlines() if f.is_file() else []
    if not add:
        kept = [ln for ln in lines if ln not in IGNORE]
        if kept == lines:
            return False
        f.write_text("\n".join(kept) + ("\n" if kept else ""))
        return True
    if IGNORE[1] in lines or subprocess.run(["git", "-C", str(path), "check-ignore", "-q", FILE],
                                            capture_output=True).returncode == 0:
        return False
    f.parent.mkdir(exist_ok=True)
    f.write_text("\n".join([*lines, *IGNORE]) + "\n")
    return True


@dataclass
class Done:
    """What connecting one project changed, so undo can take back exactly that."""
    path: str
    created: bool  # the file was made for the note
    excluded: bool  # the exclude lines were added
    before: str | None  # the note that was there before (connecting again rewrote it), or None


def connect(p: Project) -> Done | None:
    """Write (or rewrite) the note in one project. -> what changed, or None if it was there as it is."""
    path = Path(p.path)
    f = path / FILE
    text = f.read_text() if f.is_file() else ""
    rest, before = _split(text)
    new = (rest.rstrip() + "\n\n" if rest.strip() else "") + note(p.name, _uses_agents(path))
    if new == text:
        return None
    created = not f.exists()
    f.write_text(new)
    return Done(str(path), created, _exclude(path, True), before)


def disconnect(path: str | Path, done: Done | None = None) -> bool:
    """Take the note out (undo passes what connecting did: an older note comes back instead).
    -> whether anything changed."""
    path = Path(path)
    f = path / FILE
    if not f.is_file():
        return False
    rest, mine = _split(f.read_text())
    if mine is None:
        return False
    if done is not None and done.before:
        f.write_text((rest.rstrip() + "\n\n" if rest.strip() else "") + done.before)
        return True
    if rest.strip() or (done is not None and not done.created):
        f.write_text(rest)
    else:
        f.unlink()
    if done is None or done.excluded:
        _exclude(path, False)
    return True


def _record(kind: str, summary: str, target: str, via: Via, undo: dict) -> int:
    return actions.record(kind, summary, target, source_label=via[0], source_url=via[1], undo=undo)


def connect_all(via: Via = ("หน้าโปรเจค", ""), root: Path | None = None) -> tuple[list[str], list[str], int | None]:
    """เชื่อมทุกโปรเจค: the note in every project under ~/Projects that can have one (rewritten where
    it changed). A folder that can't be written to is skipped and said, and the rest still goes ahead.
    -> (the projects written to, "name: why" for the ones skipped, the action id or None)."""
    root = (root or get_config().projects_dir).resolve()
    with session() as s:
        projects = [p for p in s.scalars(select(Project).order_by(Project.name))
                    if not why_not(p) and Path(p.path).resolve().is_relative_to(root)]
        s.expunge_all()
    done: list[tuple[str, Done]] = []
    failed: list[str] = []
    for p in projects:
        try:
            if (d := connect(p)) is not None:
                done.append((p.name, d))
        except OSError as exc:
            failed.append(f"{p.name}: {exc.strerror or exc}")
    if not done:
        return [], failed, None
    names = [name for name, _ in done]
    action_id = _record("project.connect", f"เชื่อมโปรเจคกับเลขา {len(done)} โปรเจค", " · ".join(names), via,
                        {"done": [asdict(d) for _, d in done]})
    return names, failed, action_id


def _one(project_id: int) -> Project:
    with session() as s:
        p = s.get(Project, project_id)
        if p is None:
            raise ValueError("ไม่พบโปรเจคนี้")
        s.expunge(p)
    if why := why_not(p):
        raise ValueError(f"เชื่อม {p.name} ไม่ได้: {why}")
    return p


def connect_one(project_id: int, via: Via = ("หน้าโปรเจค", "")) -> int | None:
    p = _one(project_id)
    if (d := connect(p)) is None:
        return None  # connected already, with this very note
    return _record("project.connect", f"เชื่อม {p.name} กับเลขา", p.path, via, {"done": [asdict(d)]})


def disconnect_one(project_id: int, via: Via = ("หน้าโปรเจค", "")) -> int | None:
    p = _one(project_id)
    if not disconnect(p.path):
        return None
    return _record("project.disconnect", f"เลิกเชื่อม {p.name} กับเลขา", p.path, via, {"project_id": project_id})


async def _undo_connect(undo: dict) -> None:
    for d in undo["done"]:
        disconnect(d["path"], Done(**d))


async def _undo_disconnect(undo: dict) -> None:
    connect(_one(undo["project_id"]))


actions.register_undo("project.connect", _undo_connect)
actions.register_undo("project.disconnect", _undo_disconnect)
