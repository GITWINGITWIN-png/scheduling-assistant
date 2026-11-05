"""วัดความกว้างข้อความด้วยฟอนต์จริง — หัวใจของการตรวจ "ข้อความล้นกล่อง / ป้ายทับกัน" ก่อนเปิดดูด้วยตา

ทำไมต้องวัดจริง: ภาษาไทยมีสระและวรรณยุกต์ที่ไม่กินที่ในแนวนอน การนับจำนวนตัวอักษรจึงคลาดมาก
ใช้ Sarabun (มีทั้งไทยและละตินในไฟล์เดียว) ผ่าน Pillow + raqm ซึ่งจัดรูปอักษรไทยแบบเดียวกับเบราว์เซอร์

หาไฟล์ฟอนต์จาก: $SUBMAP_FONT_DIR → ~/.fonts/Sarabun → ~/.local/share/fonts(/Sarabun) → โฟลเดอร์ระบบ → fc-match
ถ้าไม่เจอ: ใช้ค่าประมาณและบันทึกคำเตือนไว้ใน WARNINGS (build จะพิมพ์ออกมา) — ติดตั้งได้จาก
https://fonts.google.com/specimen/Sarabun (วางไฟล์ Sarabun-Regular/SemiBold/Bold.ttf ไว้ที่ ~/.fonts/Sarabun)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import unicodedata
from functools import lru_cache
from pathlib import Path

FAMILY = "Sarabun"
FILES = {400: "Sarabun-Regular.ttf", 600: "Sarabun-SemiBold.ttf", 700: "Sarabun-Bold.ttf"}
SEARCH = [os.environ.get("SUBMAP_FONT_DIR", ""), "~/.fonts/Sarabun", "~/.local/share/fonts/Sarabun",
          "~/.local/share/fonts", "~/.fonts", "/usr/share/fonts/truetype/sarabun", "/usr/share/fonts/truetype/thai",
          "/usr/local/share/fonts", "~/Library/Fonts", "/Library/Fonts"]
WARNINGS: list[str] = []


def _warn(msg: str) -> None:
    if msg not in WARNINGS:
        WARNINGS.append(msg)


def _find(weight: int) -> Path | None:
    name = FILES[weight]
    for d in SEARCH:
        if d:
            p = Path(d).expanduser() / name
            if p.exists():
                return p
    if shutil.which("fc-match"):
        try:
            out = subprocess.run(["fc-match", "-f", "%{file}", f"{FAMILY}:weight={dict([(400, 80), (600, 180), (700, 200)])[weight]}"],
                                 capture_output=True, text=True, timeout=5).stdout.strip()
            if out and Path(out).name == name:
                return Path(out)
        except (OSError, subprocess.SubprocessError):
            pass
    return None


@lru_cache(maxsize=None)
def _font(weight: int):
    try:
        from PIL import ImageFont, features
    except ImportError:
        _warn("ไม่มี Pillow → วัดความกว้างข้อความด้วยค่าประมาณ (pip install pillow แล้ว build ใหม่)")
        return None
    path = _find(weight)
    if path is None:
        _warn(f"ไม่พบฟอนต์ {FILES[weight]} → ใช้ค่าประมาณ (ติดตั้ง Sarabun ไว้ที่ ~/.fonts/Sarabun แล้ว build ใหม่)")
        return None
    layout = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC
    if layout is not ImageFont.Layout.RAQM:
        _warn("Pillow ไม่มี raqm → ความกว้างภาษาไทยอาจคลาดเล็กน้อย (เผื่อที่ในกล่องเพิ่ม)")
    # วัดที่ 100px แล้วสเกลลง — ได้ค่าทศนิยมละเอียดกว่าวัดที่ขนาดจริง
    return ImageFont.truetype(str(path), 100, layout_engine=layout)


def _estimate(s: str, size: float, weight: int) -> float:
    """ค่าประมาณเมื่อไม่มีฟอนต์: ไม่นับสระ/วรรณยุกต์ที่ซ้อนบนล่าง (combining) · เผื่อไว้กว้างกว่าจริงเล็กน้อย"""
    units = 0.0
    for ch in s:
        if unicodedata.combining(ch) or ch in "ัิีึืฺุู็่้๊๋์ํ๎":
            continue
        units += 0.32 if ch == " " else (0.58 if ord(ch) < 0x80 else 0.6)
    return units * size * (1.06 if weight >= 600 else 1.0)


def text_w(s: str, size: float, weight: int = 400) -> float:
    """ความกว้างของข้อความ (หน่วย SVG = px ที่ซูม 100%) เมื่อแสดงด้วย Sarabun ขนาด size"""
    w = weight if weight in FILES else (700 if weight > 600 else 600 if weight > 400 else 400)
    f = _font(w)
    if f is None:
        return _estimate(str(s), size, w)
    return f.getlength(str(s)) * size / 100
