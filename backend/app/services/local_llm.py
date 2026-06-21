"""Local LLM via Ollama (M6).

Some jobs don't need Claude. Pulling structured schedule items out of a few
emails is short, repetitive, and privacy-sensitive — a perfect fit for a small
model running locally on the user's GPU. Offloading it here keeps the Claude Pro
budget for the interactive chat, and means email bodies never leave the machine.

We talk to Ollama's HTTP API directly (no extra dependency — httpx is already
in the venv via the Agent SDK). The model is configurable in settings, so it can
be swapped (Typhoon, Qwen, Llama…) without touching this code.

Design choices worth knowing:
  - We serialize calls behind a single lock. Even an 8B model wants the GPU to
    itself; two concurrent generations would thrash VRAM (and a bigger model
    could OOM). Extraction isn't latency-critical, so one-at-a-time is fine.
  - We ask Ollama for JSON mode (`format="json"`) AND describe the shape in the
    prompt, then parse defensively — small models occasionally wrap JSON in
    prose or stray tokens.
  - Failures raise a clear OllamaError so callers can degrade gracefully (the
    Mail page still browses; only the "scan for deadlines" button needs this).
"""

from __future__ import annotations

import asyncio
import json

import httpx

from app.config import settings

# One generation at a time — see module docstring.
_lock = asyncio.Lock()

# Background extraction can be slow on a busy GPU; be patient rather than flaky.
_TIMEOUT = httpx.Timeout(180.0, connect=5.0)


class OllamaError(RuntimeError):
    """Raised when the local model is unreachable or returns nothing usable."""


async def is_up() -> bool:
    """True if the Ollama server answers — used to show a friendly UI hint."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            return r.status_code == 200
    except httpx.HTTPError:
        return False


async def chat_json(system: str, user: str) -> dict | list:
    """Run one JSON-returning completion on the local model and parse it.

    `system`/`user` are the two prompt halves. We force Ollama's JSON mode and
    temperature 0 (deterministic extraction), then parse the reply. Raises
    OllamaError if the server is down or the output can't be salvaged as JSON.
    """
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "format": "json",  # constrain the decoder to valid JSON
        "stream": False,
        "options": {"temperature": 0},
    }

    async with _lock:  # keep the GPU to ourselves for this generation
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/chat", json=payload
                )
                resp.raise_for_status()
        except httpx.HTTPError as e:
            raise OllamaError(
                f"Local model unreachable at {settings.ollama_base_url} "
                f"({settings.ollama_model}). Is `ollama serve` running? [{e}]"
            ) from e

    content = resp.json().get("message", {}).get("content", "")
    return _parse_json(content)


def _parse_json(text: str) -> dict | list:
    """Parse the model's reply as JSON, tolerating a little surrounding noise."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Small models sometimes add a sentence before/after the JSON. Fall back
        # to the outermost {...} or [...] span.
        for open_ch, close_ch in (("{", "}"), ("[", "]")):
            start, end = text.find(open_ch), text.rfind(close_ch)
            if 0 <= start < end:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    continue
        raise OllamaError(f"Local model did not return JSON: {text[:200]!r}")
