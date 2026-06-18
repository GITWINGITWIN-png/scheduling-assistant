"""Minimal check that the Agent SDK talks to Claude on the Pro login.

No tools, no Google — just proves the SDK can reach Claude through the
logged-in `claude` CLI (your Pro subscription). Run from backend/:

    uv run python scripts/smoke_agent.py
"""

import asyncio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query


async def main() -> None:
    options = ClaudeAgentOptions(
        system_prompt="You are a terse assistant.",
        allowed_tools=[],
        setting_sources=[],
    )
    async for message in query(
        prompt="Reply with exactly: M1 connection OK", options=options
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)


if __name__ == "__main__":
    asyncio.run(main())
