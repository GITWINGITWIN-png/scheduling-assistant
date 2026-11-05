"""ตัวเลขทุกตัวของแผนที่นี้ — มาจากสองแหล่ง และ assert ทุกค่า

1. repos.json  — snapshot จาก GitHub API (ดาว · วันที่ push · archived · license) สร้างด้วย fetch_repos.py
2. โค้ดของ my_secretary เอง — อ่านตอน build (เวลา cron · จำนวน tool · อารมณ์ · พอร์ต TTS · ค่าของ planner)

ถ้า build ล้มที่ assert แปลว่าของจริงเปลี่ยน (repo ถูก archive · โค้ดเราเปลี่ยน) → แก้ข้อความใน spec.py
ให้ตรง แล้วค่อยแก้ค่าที่ assert · ห้ามลบ assert ทิ้งเพื่อให้ผ่าน
"""
import ast
import json
import re
from pathlib import Path

from repos import REPOS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                                   # docs/reference-map/ → รากของ repo my_secretary


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def const(rel: str, name: str):
    """ค่าคงที่ระดับบนสุดของไฟล์ Python (อ่านด้วย ast — ไม่ import โค้ดจริง)"""
    for node in ast.parse(read(rel)).body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            return ast.literal_eval(node.value)
    raise KeyError(f"{name} ไม่มีใน {rel}")


# ================================================================ 1 · GitHub snapshot
_SNAP = json.loads((HERE / "repos.json").read_text(encoding="utf-8"))
FETCHED_AT = _SNAP["fetched_at"]
R = _SNAP["repos"]
assert set(R) == set(REPOS), "repos.json ไม่ตรงกับ repos.py — รัน fetch_repos.py ใหม่"
assert all(R[k]["full_name"].lower() == REPOS[k].lower() for k in REPOS), "มี repo ย้ายชื่อ — ตรวจ repos.py"

# repo ที่ archive แล้ว (อ่านได้ แต่ไม่มีคนดูแล) — ข้อความใน spec พูดถึงสองตัวนี้ว่าเป็น "รุ่นก่อน"
ARCHIVED = sorted(k for k in R if R[k]["archived"])
assert ARCHIVED == ["cv", "eaia"], ARCHIVED

# ดาว: ใช้จัดลำดับความ "ผ่านการใช้งานจริง" อย่างหยาบ — ไม่ใช่ตัววัดคุณภาพโค้ด
assert R["oc"]["stars"] > 300_000 and R["ai"]["stars"] > 40_000 and R["tc"]["stars"] < 100


def stars(k: str) -> str:
    n = R[k]["stars"]
    return f"{n / 1000:.0f}k" if n >= 10_000 else f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def pushed(k: str) -> str:
    return R[k]["pushed"]


# license: GitHub API อ่านได้บางตัว (spdx) · ตัวที่ขึ้น NOASSERTION เปิดไฟล์ LICENSE อ่านเองเมื่อ 2026-11-04
LICENSE = {
    "oc": "MIT", "kh": "AGPL-3.0", "le": "MIT", "afs": "MIT", "eaia": "MIT", "tc": "AGPL-3.0", "sp": "MIT",
    "gw": "MIT", "am": "MIT", "cv": "MIT", "ai": "MIT",
    "ga": "PolyForm Noncommercial (ห้ามใช้เชิงพาณิชย์)",
    "iz": "AGPL-3.0 + ห้ามขาย · องค์กรต้องซื้อ license",
    "olv": "MIT (ยกเว้นโมเดล Live2D ตัวอย่าง)",
    "ea": "ไม่มี LICENSE ที่ราก (README ว่า MIT)",
}
assert set(LICENSE) == set(R)
for _k, _lic in LICENSE.items():   # ตัวที่ GitHub อ่าน spdx ได้ ต้องตรงกับที่เราเขียน
    if R[_k]["spdx"] not in ("-", "NOASSERTION"):
        assert _lic.startswith(R[_k]["spdx"]), (_k, R[_k]["spdx"], _lic)
assert {k for k in R if R[k]["spdx"] in ("-", "NOASSERTION")} == {"ga", "iz", "olv", "ea"}


# ================================================================ 2 · my_secretary (อ่านจากโค้ดจริง)
JOBS = [(jid, int(h), int(m)) for h, m, jid in
        re.findall(r'add_job\(\w+, "cron", hour=(\d+), minute=(\d+), id="(\w+)"\)', read("backend/app/scheduler.py"))]
assert JOBS == [("morning_brief", 7, 0), ("daily_mail_scan", 7, 10)], JOBS
T_BRIEF = f"{JOBS[0][1]:02d}:{JOBS[0][2]:02d}"
T_MAIL = f"{JOBS[1][1]:02d}:{JOBS[1][2]:02d}"

TOOLS = const("backend/app/agent/secretary.py", "_ALLOWED_TOOLS")
TOOL_SERVERS = list(dict.fromkeys(t.split("__")[1] for t in TOOLS))
assert len(TOOLS) == 10 and TOOL_SERVERS == ["calendar", "classroom", "planner", "gmail"], (TOOLS, TOOL_SERVERS)

EMOTIONS = const("backend/app/agent/persona.py", "EMOTIONS")
GESTURES = const("backend/app/agent/persona.py", "GESTURES")
assert (len(EMOTIONS), len(GESTURES)) == (6, 8)

TTS_PORT = int(re.search(r'tts_base_url: str = "http://127\.0\.0\.1:(\d+)"', read("backend/app/config.py")).group(1))
OLLAMA_MODEL = re.search(r'ollama_model: str = "([^"]+)"', read("backend/app/config.py")).group(1)
assert TTS_PORT == 8080 and OLLAMA_MODEL.startswith("scb10x/")

PLAN = const("backend/app/services/planner.py", "DEFAULTS")
assert PLAN == {"work_start": 9, "work_end": 21, "block_hours": 1.5, "max_hours_per_day": 3.0}, PLAN

# ซองปาก 3 ย่าน: ความถี่ตัดของ lowpass สองตัวใน audio.ts → ต่ำ (ou) · กลาง (aa) · สูง (ih)
LIP_CUTS = [int(x) for x in re.findall(r"lowpass\(data, sr, (\d+)\)", read("frontend/src/character/audio.ts"))]
assert LIP_CUTS == [500, 2000], LIP_CUTS

# ตอนนี้ agent ข้ามการขออนุญาต tool ทั้งหมด — ด่านอนุมัติของ M7 ยังไม่มี (ภาพ "ร่างก่อน ส่งทีหลัง" พูดถึงจุดนี้)
PERMISSION_MODE = re.search(r'permission_mode="(\w+)"', read("backend/app/agent/secretary.py")).group(1)
assert PERMISSION_MODE == "bypassPermissions", PERMISSION_MODE

# อารมณ์ + ท่าที่ใช้ในทัวร์ (ต้องมีอยู่จริงใน persona.py)
TOUR_MOOD = ("concerned", "point")
assert TOUR_MOOD[0] in EMOTIONS and TOUR_MOOD[1] in GESTURES

# วันที่อ่าน README / เอกสารสถาปัตยกรรมของแต่ละ repo เพื่อเขียนคำอธิบาย (ต่างจาก FETCHED_AT ที่เปลี่ยนทุกครั้งที่ดึงตัวเลขใหม่)
CONTENT_READ = "2026-11-04"

# งานที่วางแผนไว้ใน feature.md (ยังไม่เริ่ม) — ใช้ชื่อช่องทางตามที่ผู้ใช้เขียน
FEATURE_CHANNELS = re.findall(r"-\s*(gmail|line|discord)", read("feature.md"))
assert FEATURE_CHANNELS == ["gmail", "line", "discord"], FEATURE_CHANNELS
