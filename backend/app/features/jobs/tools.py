"""What the background planner may look at in a project (B5.6): three read-only tools that never
leave the project's folder. List the files git knows (tracked and new, not ignored), read one
text file a slice at a time, search the text. No writes, no other folder, no network, and no
secret files (.env, keys, tokens): the planner reads only enough to plan, and returns only the plan.

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


def inside(root: Path, rel: str) -> Path:
    """`rel` under the project, refusing anything that leaves it (.., an absolute path, a link out)."""
    base = root.resolve()
    target = (base / rel).resolve()
    if target != base and base not in target.parents:
        raise Outside("อยู่นอกโฟลเดอร์โปรเจค")
    if SECRET.search(target.relative_to(base).as_posix()):
        raise Outside("ไฟล์ลับ (.env กุญแจ โทเคน) ไม่อ่าน")
    return target


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=20)
    return out.stdout


def list_files(root: Path, pattern: str = "") -> str:
    names = [n for n in _git(root, "ls-files", "-co", "--exclude-standard").splitlines() if n and not SECRET.search(n)]
    if pattern:
        names = [n for n in names if fnmatch.fnmatch(n, pattern) or fnmatch.fnmatch(Path(n).name, pattern)]
    more = len(names) - MAX_FILES
    return "\n".join(names[:MAX_FILES]) + (f"\n... อีก {more} ไฟล์ (ใส่ pattern ให้แคบลง)" if more > 0 else "") if names else "(ไม่พบไฟล์)"


def read_file(root: Path, path: str, start: int = 1, lines: int = MAX_LINES) -> str:
    try:
        target = inside(root, path)
    except Outside as exc:
        return f"อ่านไม่ได้: {exc}"
    if not target.is_file():
        return "อ่านไม่ได้: ไม่มีไฟล์นี้"
    data = target.read_bytes()
    if b"\0" in data[:8192]:
        return "อ่านไม่ได้: ไฟล์ binary"
    text = data.decode("utf-8", errors="replace").splitlines()
    start = max(1, start)
    chunk = text[start - 1:start - 1 + max(1, min(lines, MAX_LINES))]
    end = start + len(chunk) - 1
    tail = f"\n... (บรรทัด {start}–{end} จาก {len(text)} · อ่านต่อด้วย start={end + 1})" if end < len(text) else ""
    return "\n".join(f"{start + i}: {line}" for i, line in enumerate(chunk)) + tail


def search(root: Path, pattern: str) -> str:
    if not pattern.strip():
        return "ใส่คำที่จะค้นก่อน"
    hits = [h for h in _git(root, "grep", "-n", "-I", "-F", "-e", pattern, "--", ".").splitlines()
            if not SECRET.search(h.split(":", 1)[0])]
    more = len(hits) - MAX_HITS
    return "\n".join(hits[:MAX_HITS]) + (f"\n... อีก {more} บรรทัด" if more > 0 else "") if hits else "(ไม่พบ)"


def _text(value: str) -> dict:
    return {"content": [{"type": "text", "text": value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)}]}


def project_tools(root: Path) -> list[SdkMcpTool]:
    """The three tools, bound to one project's folder."""

    @tool("list_files", "รายชื่อไฟล์ในโปรเจค (ที่ git รู้จัก) · pattern เช่น *.py หรือ src/*", {"pattern": Annotated[str, "glob หรือเว้นว่าง"]})
    async def _list(args: dict) -> dict:
        return _text(list_files(root, str(args.get("pattern") or "")))

    @tool("read_file", "อ่านไฟล์ข้อความในโปรเจคทีละช่วง (สูงสุด 400 บรรทัด)",
          {"path": Annotated[str, "path จากรากโปรเจค"], "start": Annotated[int, "บรรทัดแรก เริ่ม 1"]})
    async def _read(args: dict) -> dict:
        return _text(read_file(root, str(args.get("path") or ""), int(args.get("start") or 1)))

    @tool("search", "ค้นข้อความในไฟล์ของโปรเจค (ตรงตัว) ได้ไฟล์:บรรทัด", {"text": Annotated[str, "ข้อความที่ค้น"]})
    async def _search(args: dict) -> dict:
        return _text(search(root, str(args.get("text") or "")))

    return [_list, _read, _search]
