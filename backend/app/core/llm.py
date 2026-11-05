"""The one way the secretary calls Claude: model + effort per task, tokens recorded every time.

Everything goes through `run()`, so three rules hold everywhere:

1. **Your Pro subscription, never the paid API.** The Claude Agent SDK drives
   the Claude Code CLI that ships inside the package, logged in with your
   account (~/.claude). If ANTHROPIC_API_KEY were in the environment, the CLI
   would bill the paid API instead, so it is removed from this process below.
2. **Model and effort come from the task** ("ask", "plan", ...): the defaults
   are in DEFAULT_TASKS, and the settings page can change them (settings key
   "llm.tasks"). On the current models effort is the only thinking control:
   low = quick and cheap, high/xhigh/max = deeper and more tokens.
3. **Every call leaves a row in llm_usage** (task, model, effort, tokens, time),
   failed ones included. That's the evidence for tuning.
4. **One voice** (VOICE, added to every system prompt): the secretary calls you "คุณ"
   and itself "ฉัน". Prompts call you "เจ้าของ" in their instructions, because inside a
   prompt "คุณ" already means the model.

Each call runs isolated: no built-in tools (no Bash, no file access), no
~/.claude settings, hooks, plugins or CLAUDE.md, and only the tools the caller
passes in (in-process functions, see features/ask.py). The secretary's chat
answers then depend only on what this code gives it.
"""

import logging
import os
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SdkMcpTool,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
)

from app.core import actions
from app.core.config import get_config
from app.core.db import session
from app.core.tables import LLMUsage, Setting

log = logging.getLogger(__name__)

if os.environ.pop("ANTHROPIC_API_KEY", None):
    log.warning("ANTHROPIC_API_KEY was set; removed so Claude runs on the Pro subscription, not the paid API")

Effort = Literal["low", "medium", "high", "xhigh", "max"]
EFFORTS: tuple[Effort, ...] = ("low", "medium", "high", "xhigh", "max")
MODELS = ("sonnet", "opus")  # CLI aliases: always the newest Sonnet / Opus on your plan

# What each task uses unless you change it on the settings page (W10).
# The labels are what the settings page shows.
DEFAULT_TASKS: dict[str, dict[str, str]] = {
    "ask": {"model": "sonnet", "effort": "low", "label": "ถามตอบในแชท"},
    "ask_deep": {"model": "opus", "effort": "high", "label": "ให้ Opus คิดต่อ"},
    "plan": {"model": "opus", "effort": "high", "label": "วางแผน · สั่งงาน"},
    "mail": {"model": "opus", "effort": "medium", "label": "อ่านอีเมลทุกระดับ"},  # B2: you asked for no weak model on mail
}

TOOL_SERVER = "secretary"  # tools appear to the model as mcp__secretary__<name>


@dataclass
class Reply:
    text: str
    model: str  # the model that actually answered, e.g. "claude-sonnet-5-5"
    effort: str
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    tools_used: list[str] = field(default_factory=list)  # names of the tools it called: the "sources"

    @property
    def model_name(self) -> str:
        """"Sonnet" / "Opus" for display."""
        for name in ("opus", "sonnet", "haiku", "fable"):
            if name in self.model.lower():
                return name.capitalize()
        return self.model

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out


class LLMError(RuntimeError):
    """The call failed (CLI not logged in, quota reached, network...). The message says why."""


def task_settings(task: str) -> dict[str, str]:
    """Model and effort for `task`: your settings over the defaults."""
    with session() as s:
        row = s.get(Setting, "llm.tasks")
        saved = (row.value if row else None) or {}
    return {**DEFAULT_TASKS.get(task, DEFAULT_TASKS["ask"]), **saved.get(task, {})}


# How the secretary talks to you, in every call. The user's decision (2026-11-05):
# "อย่าเรียกฉันว่าเจ้านาย ใช้ คุณ/ฉัน ก็พอ". Before, the mail prompts said เจ้านาย and the
# summaries copied it.
VOICE = ('การใช้คำ: ทุกข้อความที่คุณเขียนคือการพูดกับเจ้าของโดยตรง เรียกเจ้าของว่า "คุณ" '
         'ถ้าต้องพูดถึงตัวเองให้ใช้ "ฉัน" ห้ามเรียกเจ้าของว่า เจ้านาย นาย บอส ท่าน เจ้าของ หรือ ผู้ใช้')


async def run(
    task: str,
    prompt: str,
    *,
    system: str,
    tools: Sequence[SdkMcpTool] = (),
    model: str | None = None,
    effort: Effort | None = None,
    on_text: Callable[[str], Awaitable[None]] | None = None,
    max_turns: int = 8,
) -> Reply:
    """Ask Claude once (it may call `tools` several times) and return its final text.

    `on_text` receives each piece of text as it arrives, for streaming to the web page.
    """
    chosen = task_settings(task)
    model = model or chosen["model"]
    effort = effort or chosen["effort"]  # type: ignore[assignment]

    options = ClaudeAgentOptions(
        model=model,
        effort=effort,
        system_prompt=f"{system}\n\n{VOICE}",
        tools=[],  # no built-in tools at all
        setting_sources=[],  # don't load ~/.claude settings, hooks, plugins, CLAUDE.md
        skills=[],
        mcp_servers={TOOL_SERVER: create_sdk_mcp_server(TOOL_SERVER, tools=list(tools))} if tools else {},
        # Only the servers above. Without this, the CLI also loads the claude.ai connectors on
        # your account (Gmail, Drive, Canva...) and their instructions: measured on 2026-11-05,
        # a one-tool question went from ~43k input tokens to ~2k with this on.
        strict_mcp_config=True,
        allowed_tools=[f"mcp__{TOOL_SERVER}__{t.name}" for t in tools],
        permission_mode="dontAsk",  # anything not allowed above is refused, never prompted
        max_turns=max_turns,
        cwd=str(get_config().data_dir),  # not inside a project, so no project files get picked up
    )

    texts: list[str] = []
    used: list[str] = []
    answered_by = model
    result: ResultMessage | None = None
    started = time.monotonic()
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                answered_by = message.model or answered_by
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text:
                        texts.append(block.text)
                        if on_text:
                            await on_text(block.text)
                    elif isinstance(block, ToolUseBlock):
                        used.append(block.name.removeprefix(f"mcp__{TOOL_SERVER}__"))
            elif isinstance(message, ResultMessage):
                result = message
    except Exception as exc:  # the CLI failed to start or died: record it, then surface it
        _record(task, model, effort, {}, int((time.monotonic() - started) * 1000), ok=False)
        raise LLMError(f"เรียก Claude ไม่สำเร็จ: {exc}") from exc

    usage = (result.usage if result else None) or {}
    duration = result.duration_ms if result else int((time.monotonic() - started) * 1000)
    failed = result is None or result.is_error
    _record(task, answered_by, effort, usage, duration, ok=not failed)
    if failed:
        why = (result.errors or [result.subtype]) if result else ["no result"]
        raise LLMError(f"Claude ตอบไม่สำเร็จ: {'; '.join(map(str, why))}")

    # The final answer is the text after the last tool call. ResultMessage.result has exactly that.
    final = (result.result if result and result.result else "\n".join(texts)).strip()
    tokens_in, tokens_out = _tokens(usage)
    return Reply(final, answered_by, effort, tokens_in, tokens_out, duration, used)


def _tokens(usage: dict) -> tuple[int, int]:
    """Input counts everything the model read, cached or not, because all of it uses quota."""
    tokens_in = sum(int(usage.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return tokens_in, int(usage.get("output_tokens") or 0)


def _record(task: str, model: str, effort: str, usage: dict, duration_ms: int, ok: bool) -> None:
    tokens_in, tokens_out = _tokens(usage)
    with session() as s:
        s.add(LLMUsage(task=task, model=model, effort=effort, tokens_in=tokens_in,
                       tokens_out=tokens_out, duration_ms=duration_ms, ok=ok))


# ------------------------------------------------------------------ changing it from the settings page
def set_task(task: str, model: str, effort: str) -> int:
    """Save a task's model and effort; logged with undo. Returns the action id."""
    if task not in DEFAULT_TASKS or model not in MODELS or effort not in EFFORTS:
        raise ValueError("งาน โมเดล หรือ effort ไม่ถูกต้อง")
    old = {k: task_settings(task)[k] for k in ("model", "effort")}
    with session() as s:
        row = s.get(Setting, "llm.tasks")
        saved = dict(row.value) if row and row.value else {}
        saved[task] = {"model": model, "effort": effort}
        s.merge(Setting(key="llm.tasks", value=saved))
    label = DEFAULT_TASKS[task]["label"]
    return actions.record("settings.llm", f"เปลี่ยนโมเดล: {label}",
                          f"{old['model']}/{old['effort']} → {model}/{effort}",
                          source_label="หน้าตั้งค่า", undo={"task": task, "old": old})


async def _undo_set_task(data: dict) -> None:
    with session() as s:
        row = s.get(Setting, "llm.tasks")
        saved = dict(row.value) if row and row.value else {}
        saved[data["task"]] = data["old"]
        s.merge(Setting(key="llm.tasks", value=saved))


actions.register_undo("settings.llm", _undo_set_task)
