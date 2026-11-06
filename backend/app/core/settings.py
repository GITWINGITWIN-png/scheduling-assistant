"""Small helpers for the `settings` table: your preferences and the secretary's saved state.

(Machine facts such as the Discord token live in config.py instead; see its docstring.)
Values are JSON, so a key can hold a number, a list or a whole dict.
"""

from typing import Any

from app.core.db import session
from app.core.tables import Setting


def get(key: str, default: Any = None) -> Any:
    """The stored value, or `default` if the key was never saved (or saved as null)."""
    with session() as s:
        row = s.get(Setting, key)
        return row.value if row is not None and row.value is not None else default


def put(key: str, value: Any) -> None:
    with session() as s:
        s.merge(Setting(key=key, value=value))
