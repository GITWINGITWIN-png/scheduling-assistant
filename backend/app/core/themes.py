"""The six colour themes agreed in stage 2 (W11): one shape, different colours.

The web page holds the full colour sets (frontend/src/themes.css). The backend
only needs each theme's name and its accent, because the Discord bot colours
the bar beside its messages with the current theme's accent.
"""

from app.core.db import session
from app.core.tables import Setting

THEME_KEY = "ui.theme"
DEFAULT_THEME = "cs"

# id: (name, one-line description, accent colour)
THEMES: dict[str, tuple[str, str, int]] = {
    "c": ("อิฐนุ่ม", "C เดิม · ครีมกับส้มอิฐ", 0xDD5F3A),
    "cs": ("ส้มสด", "ค่าเริ่ม · ขาวกับส้มสด", 0xF25F0C),
    "cb": ("ฟ้า", "ขาวกับฟ้าสด", 0x2563EB),
    "cg": ("เขียว", "ขาวกับเขียวมรกต", 0x059669),
    "cp": ("ม่วง", "ขาวกับม่วง", 0x7C3AED),
    "cd": ("มืด", "พื้นมืด ส้มสด", 0xFF7A3D),
}


def current_theme() -> str:
    with session() as s:
        row = s.get(Setting, THEME_KEY)
    return row.value if row and row.value in THEMES else DEFAULT_THEME


def accent() -> int:
    return THEMES[current_theme()][2]
