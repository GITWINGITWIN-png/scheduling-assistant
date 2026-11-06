"""What the background planner may look at in a project (B5.6): three read-only tools that never
leave the project. They read the commit the job will start from (base.py: the secretary's own
branch when its work isn't merged yet, else your HEAD), through git, so the planner sees what
the job will have, not your folder's unsaved state: list the files, read one text file a slice
at a time, search the text. No writes, no network, no secret files (.env, keys, tokens).

Each tool is a plain function first (what the tests call), wrapped for the model by
`project_tools(root)`.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from pathlib import Path
from typing import Annotated

from claude_agent_sdk import SdkMcpTool, tool

MAX_FILES = 300
MAX_LINES = 400  # one read
MAX_HITS = 80
SECRET = re.compile(r"(^|/)(\.env(\..*)?|.*\.pem|.*\.key|id_(rsa|ed25519|ecdsa)(\.pub)?|credentials.*\.json|token.*\.json|\.netrc|\.pgpass)$",
                    re.IGNORECASE)


class Outside(ValueError):
    """The path would leave the project's folder, or is a secret file."""


def inside(root: Path, rel: str) -> str:
    """`rel` as a path inside the project (posix, from its root), refusing anything that leaves it
    (.., an absolute path) and secret files."""
    base = root.resolve()
    target = (base / rel).resolve()
    if target != base and base not in target.parents:
        raise Outside("อยู่นอกโฟลเดอร์โปรเจค")
    clean = target.relative_to(base).as_posix()
    if SECRET.search(clean):
        raise Outside("ไฟล์ลับ (.env กุญแจ โทเคน) ไม่อ่าน")
    return clean


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=20)


def list_files(root: Path, ref: str, pattern: str = "") -> str:
    """The files of the commit the job starts from (what the job will have)."""
    out = _git(root, "ls-tree", "-r", "--name-only", "-z", ref).stdout.decode("utf-8", errors="replace")
    names = [n for n in out.split("\0") if n and not SECRET.search(n)]
    if pattern:
        names = [n for n in names if fnmatch.fnmatch(n, pattern) or fnmatch.fnmatch(Path(n).name, pattern)]
    more = len(names) - MAX_FILES
    return "\n".join(names[:MAX_FILES]) + (f"\n... อีก {more} ไฟล์ (ใส่ pattern ให้แคบลง)" if more > 0 else "") if names else "(ไม่พบไฟล์)"


def read_file(root: Path, ref: str, path: str, start: int = 1, lines: int = MAX_LINES) -> str:
    try:
        rel = inside(root, path)
    except Outside as exc:
        return f"อ่านไม่ได้: {exc}"
    out = _git(root, "show", f"{ref}:{rel}")
    if out.returncode or _git(root, "cat-file", "-t", f"{ref}:{rel}").stdout.strip() != b"blob":
        return "อ่านไม่ได้: ไม่มีไฟล์นี้"
    data = out.stdout
    if b"\0" in data[:8192]:
        return "อ่านไม่ได้: ไฟล์ binary"
    text = data.decode("utf-8", errors="replace").splitlines()
    start = max(1, start)
    chunk = text[start - 1:start - 1 + max(1, min(lines, MAX_LINES))]
    end = start + len(chunk) - 1
    tail = f"\n... (บรรทัด {start}–{end} จาก {len(text)} · อ่านต่อด้วย start={end + 1})" if end < len(text) else ""
    return "\n".join(f"{start + i}: {line}" for i, line in enumerate(chunk)) + tail


def search(root: Path, ref: str, pattern: str) -> str:
    if not pattern.strip():
        return "ใส่คำที่จะค้นก่อน"
    out = _git(root, "grep", "-n", "-I", "-F", "-e", pattern, ref, "--").stdout.decode("utf-8", errors="replace")
    hits = [h.removeprefix(f"{ref}:") for h in out.splitlines()]
    hits = [h for h in hits if not SECRET.search(h.split(":", 1)[0])]
    more = len(hits) - MAX_HITS
    return "\n".join(hits[:MAX_HITS]) + (f"\n... อีก {more} บรรทัด" if more > 0 else "") if hits else "(ไม่พบ)"


def _text(value: str) -> dict:
    return {"content": [{"type": "text", "text": value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)}]}


def project_tools(root: Path, ref: str) -> list[SdkMcpTool]:
    """The three tools, bound to one project and the commit its next job starts from."""

    @tool("list_files", "รายชื่อไฟล์ในโปรเจค (ที่ git รู้จัก) · pattern เช่น *.py หรือ src/*", {"pattern": Annotated[str, "glob หรือเว้นว่าง"]})
    async def _list(args: dict) -> dict:
        return _text(list_files(root, ref, str(args.get("pattern") or "")))

    @tool("read_file", "อ่านไฟล์ข้อความในโปรเจคทีละช่วง (สูงสุด 400 บรรทัด)",
          {"path": Annotated[str, "path จากรากโปรเจค"], "start": Annotated[int, "บรรทัดแรก เริ่ม 1"]})
    async def _read(args: dict) -> dict:
        return _text(read_file(root, ref, str(args.get("path") or ""), int(args.get("start") or 1)))

    @tool("search", "ค้นข้อความในไฟล์ของโปรเจค (ตรงตัว) ได้ไฟล์:บรรทัด", {"text": Annotated[str, "ข้อความที่ค้น"]})
    async def _search(args: dict) -> dict:
        return _text(search(root, ref, str(args.get("text") or "")))

    return [_list, _read, _search]
