"""A scripted stand-in for ClaudeSDKClient, so the runner can be tested without Claude.

It plays a script the way the CLI does: each tool call is first sent as an AssistantMessage (with
the call's usage), then the permission question goes to the runner's can_use_tool (except reads
inside the folder, which Claude Code allows by itself), then the tool runs for real in the job's
folder: Write writes the file, Bash runs the command. interrupt() ends the script early, like
the real one, with an error result.

Script steps:
  ("tool", name, input, usage)  a tool call; usage = tokens of that model call (int)
  ("text", words, usage)        the model's words
  ("wait", seconds)             nothing happens for a while (a long test run)
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from claude_agent_sdk import AssistantMessage, PermissionResultAllow, ResultMessage, TextBlock, ToolUseBlock


class FakeClient:
    script: list = []
    last: "FakeClient | None" = None

    def __init__(self, options):
        self.options = options
        self.root = Path(options.cwd)
        self.interrupted = False
        self.denied: list[tuple[str, str]] = []
        self.ran: list[str] = []
        self.prompt = ""
        self.total = 0
        FakeClient.last = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def query(self, prompt: str) -> None:
        self.prompt = prompt

    async def interrupt(self) -> None:
        self.interrupted = True

    def _usage(self, tokens: int) -> dict:
        return {"input_tokens": tokens - 100, "output_tokens": 100}

    async def receive_response(self):
        for n, step in enumerate(self.script):
            if self.interrupted:
                break
            if step[0] == "wait":
                for _ in range(int(step[1] / 0.01)):
                    if self.interrupted:
                        break
                    await asyncio.sleep(0.01)
                continue
            if step[0] == "text":
                self.total += step[2]
                yield AssistantMessage(content=[TextBlock(step[1])], model="claude-sonnet-5-5", usage=self._usage(step[2]),
                                       message_id=f"m{n}")
                continue
            _, name, data, tokens = step
            self.total += tokens
            yield AssistantMessage(content=[ToolUseBlock(id=f"t{n}", name=name, input=data)], model="claude-sonnet-5-5",
                                   usage=self._usage(tokens), message_id=f"m{n}")
            if self.interrupted:
                break
            path = data.get("file_path")
            asks = not (name in ("Read", "Glob", "Grep") and (not path or (self.root / path).resolve().is_relative_to(self.root.resolve())))
            if asks:
                answer = await self.options.can_use_tool(name, data, None)
                if not isinstance(answer, PermissionResultAllow):
                    self.denied.append((name, answer.message))
                    continue
            if name == "Write":
                target = self.root / data["file_path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(data["content"])
            elif name == "Bash":
                self.ran.append(data["command"])
                subprocess.run(data["command"], shell=True, cwd=self.root, capture_output=True, timeout=60)
        yield ResultMessage(subtype="error_during_execution" if self.interrupted else "success", duration_ms=10, duration_api_ms=10,
                            is_error=self.interrupted, num_turns=len(self.script), session_id="fake",
                            usage=None if self.interrupted else self._usage(self.total),  # the real one has none after an interrupt
                            result=None if self.interrupted else "ทำครบตามแผน")
