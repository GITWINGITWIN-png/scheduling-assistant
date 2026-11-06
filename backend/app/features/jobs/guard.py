"""What a background job may do while it runs (3.2, B5.7): the guard, the budget and the loop check.
Plain functions and small classes, no Claude, so the tests can try every case (B5.8).

The guard (`judge`) sees every Bash command, every write, and every read or search outside the
job's folder (Claude Code asks about those; reads inside the folder it allows by itself):

- files: read and write only inside the job's folder (its git worktree), and never a secret
  file (.env, keys, tokens);
- never, whatever was approved: push, switching branches, rewriting history or git's settings,
  sudo, the secretary's own data (~/.secretary), the keys in your home folder;
- the high-risk kinds that show in a command (installing or downloading, deleting in bulk,
  uploading or deploying, sending messages) only when this job was approved by you with that
  kind in its plan: an approval covers what the plan said, nothing more;
- the web tools count as downloading; any tool not listed here is refused.

The budget (`Budget`) adds up the tokens of each model call once (a call's usage arrives with
each of its content blocks, and in the stream's own events as it's written), the way
core/llm.py counts them: everything read, cached or not, plus everything written. The loop check (`Loop`) catches the same call repeated: 3 times in a
row, or 5 times in all.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.features.jobs.tools import SECRET

# A command name at the start of a command: the line's start, after ; && || | ( $( or a backtick,
# or after a wrapper (sudo, env, xargs...). So "curl" counts, "fix curl parsing" in a message doesn't.
CMD = r"(?:^|[;&|(`\n]\s*|\$\(\s*|\b(?:sudo|env|xargs|exec|nohup|time|command)\s+)"

NEVER: tuple[tuple[str, str], ...] = (
    (r"\bgit\s+push\b", "ห้าม push: งานอยู่บน branch ในเครื่องเท่านั้น"),
    (r"\bgit\s+(switch|worktree|config|remote|filter-branch|update-ref|rebase)\b", "ห้ามสลับ branch หรือแก้ประวัติและการตั้งค่า git"),
    (r"\bgit\s+checkout\s+(?!--(\s|$))(-[bB]\s+)?[\w./-]+\s*($|[;&|)])", "ห้ามสลับ branch"),
    (r"\bgit\s+branch\s+-[dDmMcC]\b|\bgit\s+tag\s+-d\b", "ห้ามลบหรือย้าย branch"),
    (CMD + r"(sudo|su|doas|pkexec)\b", "ห้ามใช้ sudo"),
    (r"\.secretary\b", "ห้ามแตะข้อมูลของเลขา"),
    (r"(~|\$HOME|\$\{HOME\}|/home/[^/\s]+)/\.(ssh|gnupg|aws|netrc|docker|kube|config/gcloud|claude)\b", "ห้ามแตะกุญแจและรหัสผ่านในเครื่อง"),
)

KIND_COMMANDS: dict[str, tuple[str, ...]] = {  # the high-risk kinds a command can show
    "download": (r"\b(pip3?|pipx|conda)\s+install\b", r"\buv\s+(add|pip\s+install|tool\s+install)\b", r"\bpoetry\s+add\b",
                 r"\bnpm\s+(i|install|add)\b[^;&|\n]*\s[^-\s;&|]", r"\b(yarn|pnpm)\s+add\b", CMD + r"(npx|curl|wget|gdown|apt|apt-get|brew)\b",
                 r"\bgit\s+(clone|fetch|pull|submodule)\b", r"\bcargo\s+(add|install)\b", r"\bgo\s+(get|install)\b",
                 r"huggingface-cli|\bhf\s+download\b"),
    "delete": (r"\brm\s+(-\w*[rRf]\w*|--recursive|--force)\b", r"\bgit\s+(reset\s+--hard|clean)\b", r"\bfind\b.*\s-delete\b",
               CMD + r"(shred|truncate|mkfs\S*|dd)\b", r"\bdrop\s+(table|database|schema)\b"),
    "push": (CMD + r"(scp|rsync|sftp|ssh|vercel|netlify|heroku|flyctl)\b", r"\bgh\s+(pr|release|repo|gist)\b",
             r"\bnpm\s+publish\b", r"\btwine\s+upload\b", r"\bdocker\s+push\b", r"\bkubectl\s+(apply|create|delete)\b"),
    "message": (CMD + r"(mail|mailx|sendmail|mutt|msmtp)\b", r"\bgh\s+(issue|pr)\s+comment\b", r"\bsmtplib\b"),
}
_NEVER = [(re.compile(p, re.IGNORECASE), why) for p, why in NEVER]
_KINDS = {k: [re.compile(p, re.IGNORECASE) for p in ps] for k, ps in KIND_COMMANDS.items()}
KIND_WORDS = {"download": "โหลดหรือติดตั้งของจากภายนอก", "delete": "ลบหรือเขียนทับแบบล้างทั้งหมด", "push": "ส่งขึ้นที่อื่นหรือ deploy",
              "message": "ส่งข้อความหาคนอื่น"}
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\b", re.DOTALL)
_MESSAGE = re.compile(r"(\s(?:-m|--message)(?:=|\s+))(\"(?:[^\"\\]|\\.)*\"|'[^']*'|\S+)")


_INNER = re.compile(r"(?:\b(?:ba|z|da)?sh\s+-c|\beval)\s+('([^']*)'|\"((?:[^\"\\]|\\.)*)\")")


def expand(command: str) -> str:
    """The scripts inside bash -c '...', sh -c "..." and eval, added as commands of their own."""
    inner = [m.group(2) if m.group(2) is not None else m.group(3) for m in _INNER.finditer(command)]
    return "\n".join([command, *(expand(i) for i in inner)])


def without_messages(command: str) -> str:
    """A git commit's message taken out (Claude Code writes it as -m "$(cat <<'EOF' ... EOF)"), so the
    words in it aren't read as commands. Only for git commit and git tag: elsewhere a heredoc may be
    a script, and that is read."""
    if not re.search(r"\bgit\s+(commit|tag)\b", command):
        return command
    return _MESSAGE.sub(r"\1MSG", _HEREDOC.sub("<<MSG", command))


FILE_TOOLS = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path",
              "Read": "file_path", "Glob": "path", "Grep": "path"}
WEB_TOOLS = ("WebFetch", "WebSearch")
QUIET_TOOLS = ("TodoWrite",)  # harmless bookkeeping


def command_kinds(command: str) -> list[str]:
    """The high-risk kinds a shell command shows (in KIND_COMMANDS order)."""
    command = expand(without_messages(command))
    return [k for k, ps in _KINDS.items() if any(p.search(command) for p in ps)]


def _inside(root: Path, value: str) -> bool:
    base = root.resolve()
    target = (base / value).resolve() if value else base
    return target == base or base in target.parents


def judge(tool: str, data: dict, *, root: Path, allowed: set[str]) -> str:
    """"" when the call may go ahead, else why not (told to the model, kept in the job's result).
    allowed: the high-risk kinds you approved for this job."""
    if tool in QUIET_TOOLS:
        return ""
    if tool in FILE_TOOLS:
        value = str(data.get(FILE_TOOLS[tool]) or "")
        if not _inside(root, value):
            return "ทำได้เฉพาะในโฟลเดอร์ของงานนี้"
        rel = (root.resolve() / value).resolve().relative_to(root.resolve()).as_posix()
        if SECRET.search(rel):
            return "ไฟล์ลับ (.env กุญแจ โทเคน) ห้ามแตะ"
        return ""
    if tool in WEB_TOOLS:
        return "" if "download" in allowed else "ใช้เว็บได้เมื่อคุณอนุมัติงานนี้พร้อม “โหลดของจากภายนอก” เท่านั้น"
    if tool == "Bash":
        command = str(data.get("command") or "")
        for pattern, why in _NEVER:
            if pattern.search(expand(without_messages(command))):
                return why
        for kind in command_kinds(command):
            if kind not in allowed:
                return f"{KIND_WORDS[kind]} เป็นงานเสี่ยงสูง ทำได้เมื่อคุณอนุมัติแผนที่มีงานนี้เท่านั้น"
        return ""
    return f"งานเบื้องหลังใช้ {tool} ไม่ได้"


class Budget:
    """Tokens so far, counting each model call once."""

    KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")

    def __init__(self, limit: int):
        self.limit = limit
        self._calls: dict[str, dict] = {}

    @classmethod
    def tokens(cls, usage: dict | None) -> int:
        return sum(int((usage or {}).get(k) or 0) for k in cls.KEYS)

    def add(self, call_id: str, usage: dict | None) -> int:
        """Part of a call's usage. The same call is reported several times and in pieces (its
        start with what it read, then what it wrote as it writes): each number keeps its largest.
        -> the total."""
        if usage:
            mine = self._calls.setdefault(call_id, dict.fromkeys(self.KEYS, 0))
            for k in self.KEYS:
                mine[k] = max(mine[k], int(usage.get(k) or 0))
        return self.used

    @property
    def used(self) -> int:
        return sum(self.tokens(u) for u in self._calls.values())

    @property
    def usage(self) -> dict:
        """All the calls' usage added up, in the CLI's own keys."""
        return {k: sum(u[k] for u in self._calls.values()) for k in self.KEYS}

    @property
    def over(self) -> bool:
        return self.used > self.limit


class Loop:
    """The same tool call again and again: going round in circles."""

    IN_A_ROW, IN_ALL = 3, 5

    def __init__(self):
        self._last: str | None = None
        self._row = 0
        self._all: dict[str, int] = {}

    def see(self, tool: str, data: dict) -> bool:
        """True once the call has repeated too often."""
        key = tool + json.dumps(data, sort_keys=True, ensure_ascii=False)
        self._row = self._row + 1 if key == self._last else 1
        self._last = key
        self._all[key] = self._all.get(key, 0) + 1
        return self._row >= self.IN_A_ROW or self._all[key] >= self.IN_ALL
