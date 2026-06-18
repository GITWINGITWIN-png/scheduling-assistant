"""Terminal REPL to talk to the secretary (M1 smoke test).

Run from backend/:  uv run python scripts/chat.py

Calendar requests ("what's my day look like?", "add gym at 6 tomorrow") need
your Google credentials set up first (see README → Setup step 2). Without them,
the calendar tools will report an error but the chat itself still works.
"""

import asyncio
import sys
from pathlib import Path

# Running a script puts scripts/ on the import path, not the project root —
# so add backend/ so `app` is importable however this is launched.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.secretary import ask  # noqa: E402  (import after sys.path tweak)


async def main() -> None:
    print("Secretary ready. Type a message (Ctrl-C or empty line + Ctrl-D to quit).")
    while True:
        try:
            msg = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return
        if not msg:
            continue
        reply = await ask(msg)
        print(f"\nsecretary> {reply}")


if __name__ == "__main__":
    asyncio.run(main())
