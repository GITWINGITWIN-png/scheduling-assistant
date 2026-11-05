"""facts.py — ตัวเลขและรายการทุกตัวบนแผนที่ อ่านจากโค้ดจริงของ my_secretary ตอน build

ทำไมต้องอ่านจากโค้ด: แผนที่นี้จะถูกเปิดซ้ำระหว่างพัฒนา ถ้าพิมพ์ตัวเลขเอง (เช่น TTL 600 วินาที) แล้ววันหนึ่งโค้ดเปลี่ยน
แผนที่จะโกหกเงียบๆ · ที่นี่ทุกค่าอ่านจากไฟล์ต้นทาง แล้ว assert กับค่าที่ตรวจด้วยตาแล้ว (ณ 2026-11-04)
→ ถ้า build ล้มที่ assert แปลว่าโค้ดเปลี่ยน: แก้คำอธิบายใน spec.py ให้ตรงก่อน แล้วค่อยแก้ค่าใน assert

ไม่ import โค้ดของแอป (ต้องใช้ venv ของ backend และจะไปเปิด OAuth) — อ่านเป็นข้อความด้วย ast / regex แทน
ยกเว้นฟังก์ชันบริสุทธิ์ใน planner.py กับ pins.py ที่ดึงออกมารันจริง เพื่อวาดภาพจำลองด้วยอัลกอริทึมตัวจริง
"""
from __future__ import annotations

import __future__ as _future
import ast
import re
import subprocess
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # docs/map/ → รากของ repo


# ---------------------------------------------------------------- เครื่องมืออ่านโค้ด
def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def loc(rel: str) -> int:
    """จำนวนบรรทัดของไฟล์ — เปลี่ยนตามโค้ดทุกวัน จึงไม่ assert"""
    return len(read(rel).splitlines())


def _tree(rel: str) -> ast.Module:
    return ast.parse(read(rel))


def const(rel: str, name: str):
    """ค่าคงที่ระดับโมดูลที่เป็น literal (ตัวเลข สตริง list dict set tuple)"""
    for node in _tree(rel).body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        else:
            continue
        if name in names:
            return ast.literal_eval(node.value)
    raise KeyError(f"{name} ไม่มีใน {rel}")


def class_defaults(rel: str, cls: str) -> dict:
    """ค่าเริ่มของ field ใน class (เช่น Settings ของ pydantic-settings)"""
    for node in _tree(rel).body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            out = {}
            for st in node.body:
                if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and st.value is not None:
                    try:
                        out[st.target.id] = ast.literal_eval(st.value)
                    except ValueError:
                        pass
            return out
    raise KeyError(cls)


def func_defaults(rel: str, func: str) -> dict:
    """ค่าเริ่มของพารามิเตอร์ฟังก์ชัน เช่น pending(limit=20, max_age_hours=12)"""
    for node in ast.walk(_tree(rel)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func:
            args = node.args.args[-len(node.args.defaults):] if node.args.defaults else []
            return {a.arg: ast.literal_eval(d) for a, d in zip(args, node.args.defaults)}
    raise KeyError(func)


def grab(rel: str, pattern: str, group: int = 1, cast=str):
    m = re.search(pattern, read(rel))
    if not m:
        raise KeyError(f"/{pattern}/ ไม่เจอใน {rel}")
    return cast(m.group(group))


def has(rel: str, snippet: str) -> bool:
    return snippet in read(rel)


def run_funcs(rel: str, names: set[str], env: dict) -> dict:
    """ดึงฟังก์ชันบริสุทธิ์ออกจากไฟล์ (ตาม ast) แล้ว exec ใน env ที่ให้ — ได้อัลกอริทึมตัวจริงโดยไม่ import โมดูล"""
    text = read(rel)
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            code = compile(ast.get_source_segment(text, node), f"{rel}:{node.name}", "exec",
                           flags=_future.annotations.compiler_flag, dont_inherit=True)
            exec(code, env)  # noqa: S102 — โค้ดของโปรเจกต์นี้เอง
    missing = names - env.keys()
    assert not missing, f"ไม่พบฟังก์ชัน {missing} ใน {rel}"
    return env


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=10,
                              check=True).stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


# ---------------------------------------------------------------- เส้นทาง HTTP (router + /healthz)
ROUTER_FILES = ["chat", "events", "tts", "proactive", "calendar", "projects", "mail", "academic"]
ROUTES: dict[str, list[tuple[str, str]]] = {}
for _r in ROUTER_FILES:
    _txt = read(f"backend/app/routers/{_r}.py")
    _m = re.search(r'APIRouter\((?:prefix="([^"]*)")?', _txt)
    _prefix = (_m.group(1) or "") if _m else ""
    ROUTES[_r] = [(meth.upper(), _prefix + path) for meth, path in
                  re.findall(r'@router\.(get|post|patch|delete)\("([^"]*)"', _txt)]
ROUTE_COUNT = {k: len(v) for k, v in ROUTES.items()}
assert ROUTE_COUNT == dict(chat=2, events=4, tts=2, proactive=3, calendar=3, projects=8, mail=9, academic=6), ROUTE_COUNT
N_ROUTERS = len(ROUTES)
N_ROUTES = sum(ROUTE_COUNT.values()) + has("backend/app/main.py", '@app.get("/healthz")')
assert (N_ROUTERS, N_ROUTES) == (8, 38)
CORS_ORIGINS = re.findall(r'"(http://[^"]+)"', read("backend/app/main.py"))
assert CORS_ORIGINS == ["http://localhost:5173", "http://127.0.0.1:5173"]

# ---------------------------------------------------------------- agent: เครื่องมือ · persona · mood
TOOLS = const("backend/app/agent/secretary.py", "_ALLOWED_TOOLS")
TOOL_SERVERS: dict[str, list[str]] = {}
for _t in TOOLS:
    _, _srv, _name = _t.split("__")
    TOOL_SERVERS.setdefault(_srv, []).append(_name)
assert len(TOOLS) == 10 and list(TOOL_SERVERS) == ["calendar", "classroom", "planner", "gmail"]
assert TOOL_SERVERS["calendar"] == ["list_events", "create_event", "update_event", "delete_event"]
CAL_WRITE_TOOLS = [t for t in TOOL_SERVERS["calendar"] if t != "list_events"]

EMOTIONS = list(const("backend/app/agent/persona.py", "EMOTIONS"))
GESTURES = list(const("backend/app/agent/persona.py", "GESTURES"))
assert len(EMOTIONS) == 6 and len(GESTURES) == 8

# ฝั่งเบราว์เซอร์ต้องรู้จักคำชุดเดียวกัน — ถ้าไม่ตรง ตัวละครจะตกไปที่ neutral/idle เงียบๆ
_proto = "frontend/src/character/protocol.ts"
def _ts_set(rel: str, name: str) -> list[str]:
    body = re.search(rf"const {name} = new Set<string>\(\[(.*?)\]\)", read(rel), re.S).group(1)
    return re.findall(r"'(\w+)'", body)


TS_EMOTIONS = _ts_set(_proto, "EMOTIONS")
TS_GESTURES = _ts_set(_proto, "GESTURES")
assert TS_EMOTIONS == EMOTIONS and TS_GESTURES == GESTURES, "persona.py กับ protocol.ts ใช้คำ mood ไม่ตรงกัน"
NARRATION = dict(re.findall(r"(mcp__\w+): '([^']*)'", read(_proto)))
assert set(NARRATION) == set(TOOLS), "TOOL_NARRATION ต้องมีครบทุก tool ที่ agent ใช้ได้"

# ---------------------------------------------------------------- เหตุการณ์ (AgentEvent) ที่ตัวละครรายงาน
KIND_MOOD = const("backend/app/services/events.py", "_KIND_MOOD")
EMITTED = sorted(set(re.findall(r'events\.emit\(\s*"([a-z.]+)"',
                                "".join(read(p.relative_to(ROOT).as_posix())
                                        for p in (ROOT / "backend/app").rglob("*.py")))))
assert EMITTED == ["brief.failed", "brief.ready", "mail.autopinned", "mail.failed", "mail.scanned"], EMITTED
UNUSED_KINDS = sorted(set(KIND_MOOD) - set(EMITTED))
assert UNUSED_KINDS == ["chat.error", "deadline.warning"]           # มีสีหน้าไว้แล้ว แต่ยังไม่มีใคร emit
QUEUE_MAX = const("backend/app/services/events.py", "_QUEUE_MAX")
PENDING = func_defaults("backend/app/services/events.py", "pending")
SSE_PING = grab("backend/app/routers/events.py", r"ping=(\d+)", cast=int)
assert (QUEUE_MAX, PENDING, SSE_PING) == (100, {"limit": 20, "max_age_hours": 12}, 15)
# frontend ยืนยัน "delivered" ทันทีที่รับ — ไม่ได้รอให้พูดจบ (eventId ไม่ถูกใช้หลังเล่น)
ACK_ON_RECEIVE = (has("frontend/src/character/useAgentEvents.ts", "void acknowledge([payload.id])")
                  and "eventId" not in read("frontend/src/character/queue.ts")
                  and "eventId" not in read("frontend/src/character/Character.tsx"))
assert ACK_ON_RECEIVE

# ---------------------------------------------------------------- scheduler (นาฬิกาของงานเชิงรุก)
JOBS = [(jid, int(h), int(m)) for fn, h, m, jid in
        re.findall(r'add_job\((\w+), "cron", hour=(\d+), minute=(\d+), id="(\w+)"\)', read("backend/app/scheduler.py"))]
assert JOBS == [("morning_brief", 7, 0), ("daily_mail_scan", 7, 10)]
T_BRIEF = f"{JOBS[0][1]:02d}:{JOBS[0][2]:02d}"
T_MAIL = f"{JOBS[1][1]:02d}:{JOBS[1][2]:02d}"

# ---------------------------------------------------------------- แคช: snapshot ใน DB (ข้ามรีสตาร์ต) + แคชในหน่วยความจำ
TTL_CAL = const("backend/app/routers/calendar.py", "_CALENDAR_TTL")
TTL_MAIL = const("backend/app/routers/mail.py", "_MAIL_TTL")
TTL_ASSIGN = const("backend/app/routers/academic.py", "_ASSIGNMENTS_TTL")
MEM_GMAIL = const("backend/app/services/gmail.py", "_CACHE_TTL_SECONDS")
MEM_CLASS = const("backend/app/services/classroom.py", "_CACHE_TTL_SECONDS")
assert (TTL_CAL, TTL_MAIL, TTL_ASSIGN, MEM_GMAIL, MEM_CLASS) == (120, 600, 1800, 120, 300)
assert has("backend/app/services/calendar.py", '_CACHE_PREFIX = "calendar:"')
CACHE_ROWS = [  # (key ใน snapshots, ใครใช้, TTL วินาที)
    ("calendar:<start>:<end>", "GET /calendar/range", TTL_CAL),
    ("mail:unread · mail:today", "GET /mail/unread · /mail/today", TTL_MAIL),
    ("assignments:True", "GET /academic/assignments", TTL_ASSIGN),
]
MEM_ROWS = [("gmail._recent_cache", "ต่อ query ของ Gmail", MEM_GMAIL),
            ("classroom._assignments_cache", "งานทุกวิชา (ใช้โดย nudges · tool list_todo)", MEM_CLASS)]


def mins(sec: int) -> str:
    return f"{sec // 60} นาที" if sec % 60 == 0 else f"{sec} วินาที"


# ---------------------------------------------------------------- planner (แกนกำหนดได้ ไม่ใช้ token)
PLAN = const("backend/app/services/planner.py", "DEFAULTS")
assert PLAN == {"work_start": 9, "work_end": 21, "block_hours": 1.5, "max_hours_per_day": 3.0}
SLOT_DAYS = grab("backend/app/agent/planner_tools.py", r'days = int\(args\.get\("days_ahead"\) or (\d+)\)', cast=int)
assert SLOT_DAYS == 14

_plan_env = run_funcs("backend/app/services/planner.py", {"_busy_intervals", "_free_intervals", "plan_blocks", "free_slots"},
                      {"datetime": datetime, "time": time, "timedelta": timedelta})
TZ = timezone(timedelta(hours=7))                  # Asia/Bangkok — เวลาท้องถิ่นของผู้ใช้


def _at(day: int, hh: float) -> datetime:
    base = datetime(2026, 11, 9, tzinfo=TZ)        # จันทร์ 9 พ.ย. 2026 (วันสมมติของภาพจำลอง)
    return base + timedelta(days=day, hours=hh)


# ภาพจำลอง: นัดสมมติ 3 วัน แต่ใช้ plan_blocks() ตัวจริงจาก planner.py
SIM_NOW = _at(0, 8)
SIM_DEADLINE = _at(2, 18)
SIM_HOURS = 12.0
SIM_BUSY_EVENTS = [  # (วัน, เริ่ม, จบ, ชื่อ) — สมมติขึ้นเพื่อให้เห็นช่องว่าง
    (0, 10, 12, "เรียน Data Mining"), (0, 13, 14.5, "ประชุมกลุ่ม"),
    (1, 9, 12, "แล็บ"), (1, 15, 16, "นัดอาจารย์"),
    (2, 9.5, 11, "เรียน Datacom"),
]
SIM_EVENTS = [{"start": {"dateTime": _at(d, a).isoformat()}, "end": {"dateTime": _at(d, b).isoformat()}, "summary": s}
              for d, a, b, s in SIM_BUSY_EVENTS]
SIM_BUSY = _plan_env["_busy_intervals"](SIM_EVENTS, TZ)
SIM = _plan_env["plan_blocks"]("my_secretary", SIM_HOURS, SIM_DEADLINE, SIM_BUSY, now=SIM_NOW, **PLAN)
SIM_BLOCKS = [(datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"])) for b in SIM["blocks"]]
assert len(SIM_BLOCKS) == 6 and SIM["hours_scheduled"] == 9.0 and SIM["hours_unscheduled"] == 3.0, SIM
assert [b[0].strftime("%a %H:%M") for b in SIM_BLOCKS] == ["Mon 14:30", "Mon 16:00", "Tue 12:00", "Tue 13:30",
                                                           "Wed 11:00", "Wed 12:30"]
SIM_SLOTS = _plan_env["free_slots"](SIM_NOW, _at(2, 21), SIM_BUSY, work_start=PLAN["work_start"],
                                    work_end=PLAN["work_end"], block_hours=PLAN["block_hours"])
assert len(SIM_SLOTS) == 15                        # เมนูเวลาจริงที่ get_free_slots จะยื่นให้ agent ใน 3 วันนี้

# ---------------------------------------------------------------- อีเมล → หมุด → ปฏิทิน
AUTO_PIN_TYPES = sorted(const("backend/app/services/pins.py", "_AUTO_PIN_TYPES"))
assert AUTO_PIN_TYPES == ["deadline", "event", "meeting"]
_pin_env = run_funcs("backend/app/services/pins.py", {"_qualifies"}, {"_AUTO_PIN_TYPES": set(AUTO_PIN_TYPES)})
qualifies = _pin_env["_qualifies"]
# กฎสองข้อที่อยู่กลางฟังก์ชัน async (ดึงมารันตรงๆ ไม่ได้) — assert ว่าบรรทัดนั้นยังอยู่ แล้วใช้กฎเดียวกัน
assert has("backend/app/services/mail_extract.py", 'if it.get("type", "other") == "other" and not it.get("datetime"):')
assert has("backend/app/services/pins.py", 'if len(date) <= 10:  # "YYYY-MM-DD" → all-day')
assert has("backend/app/services/pins.py", "start + timedelta(hours=1)")


def mail_fate(item: dict) -> str:
    """ชะตาของรายการหนึ่งที่โมเดลในเครื่องดึงออกมา — ตามกฎใน mail_extract + pins"""
    if not item.get("title") or (item.get("type", "other") == "other" and not item.get("datetime")):
        return "ทิ้งตั้งแต่ตอนสกัด"
    if not qualifies(item):
        return "ไม่ปักหมุด"
    d = item.get("datetime")
    if not d:
        return "ปักหมุด · ไม่ลงปฏิทิน"
    return "ปักหมุด + นัดทั้งวัน" if len(d) <= 10 else "ปักหมุด + นัด 1 ชั่วโมง"


MAIL_EXAMPLES = [  # รายการสมมติที่ "โมเดลอาจตอบมา" — ผลคำนวณด้วยกฎจริงข้างบน
    ("ส่งรายงานกลุ่ม", dict(type="deadline", title="ส่งรายงานกลุ่ม", datetime="2026-11-20T16:30")),
    ("งานสัปดาห์วิชาการ", dict(type="event", title="งานสัปดาห์วิชาการ", datetime="2026-11-27")),
    ("ประชุมชมรม (ยังไม่มีวัน)", dict(type="meeting", title="ประชุมชมรม", datetime=None)),
    ("ลดราคาสุดสัปดาห์นี้", dict(type="other", title="ลดราคา", datetime=None)),
    ("กิจกรรมชมรม (type แปลก)", dict(type="activity", title="กิจกรรมชมรม", datetime=None)),
]
MAIL_FATES = {name: mail_fate(it) for name, it in MAIL_EXAMPLES}
assert list(MAIL_FATES.values()) == ["ปักหมุด + นัด 1 ชั่วโมง", "ปักหมุด + นัดทั้งวัน", "ปักหมุด · ไม่ลงปฏิทิน",
                                     "ทิ้งตั้งแต่ตอนสกัด", "ไม่ปักหมุด"]
# รายการที่รอดจากตัวกรองตอนสกัดเข้าเกณฑ์ปักหมุดเสมอ ยกเว้นโมเดลตอบ type นอก 4 แบบที่ prompt ให้ไว้
SCAN_TYPES = re.findall(r'\\"(\w+)\\"', re.search(r"`type` is one of (.*?);", read("backend/app/services/mail_extract.py")).group(1))
assert SCAN_TYPES == ["deadline", "meeting", "event", "other"], SCAN_TYPES
MAX_BODY = const("backend/app/services/mail_extract.py", "_MAX_BODY_CHARS")
DEEP_BODY = const("backend/app/services/mail_extract.py", "_DEEP_BODY_CHARS")
assert (MAX_BODY, DEEP_BODY) == (4000, 8000)

# ---------------------------------------------------------------- โมเดลในเครื่อง · เสียง
SETTINGS = class_defaults("backend/app/config.py", "Settings")
OLLAMA_MODEL = SETTINGS["ollama_model"]
OLLAMA_PORT = int(SETTINGS["ollama_base_url"].rsplit(":", 1)[1])
TTS_PORT = int(SETTINGS["tts_base_url"].rsplit(":", 1)[1])
TTS_VOICE = SETTINGS["tts_voice"]
assert (OLLAMA_MODEL, OLLAMA_PORT, TTS_PORT, TTS_VOICE) == ("scb10x/llama3.1-typhoon2-8b-instruct", 11434, 8080, "af_heart")
assert SETTINGS["tts_engine"] == "kokoro" and SETTINGS["database_url"] == "sqlite:///./secretary.db"
LLM_TIMEOUT = grab("backend/app/services/local_llm.py", r"_TIMEOUT = httpx\.Timeout\(([\d.]+)", cast=float)
TTS_TIMEOUT = grab("backend/app/services/tts.py", r"_TIMEOUT = httpx\.Timeout\(([\d.]+)", cast=float)
assert (LLM_TIMEOUT, TTS_TIMEOUT) == (180.0, 60.0)
BACKEND_PORT = grab("run.sh", r'PORT="\$\{PORT:-(\d+)\}"', cast=int)
assert BACKEND_PORT == 8000 and grab("run.sh", r'TTS_PORT="\$\{TTS_PORT:-(\d+)\}"', cast=int) == TTS_PORT
SIDECAR_PY = grab("backend/tts_sidecar/pyproject.toml", r'requires-python = "==([\d.]+)\.\*"')
BACKEND_PY = grab("backend/pyproject.toml", r'requires-python = ">=([\d.]+)"')
assert (SIDECAR_PY, BACKEND_PY) == ("3.13", "3.11")
KOKORO_MODEL = grab("backend/tts_sidecar/main.py", r'"KOKORO_MODEL", "([^"]+)"')
assert KOKORO_MODEL == "kokoro-v1.0.fp16.onnx"
# วัดบนเครื่องนี้ (บันทึกไว้ใน PROGRESS.md — ไม่ได้คำนวณ แต่ตรวจว่ายังเขียนไว้แบบนั้น)
assert has("PROGRESS.md", "**RTF ~0.20**") and has("PROGRESS.md", "model load 0.7s")
assert has("PROGRESS.md", "from ~1.0s into ~0.001s")
RTF, LOAD_S, MISS_S, HIT_S = 0.20, 0.7, 1.0, 0.001

# ---------------------------------------------------------------- ปากขยับ (audio.ts) · ร่าง (vrmScene / gestures) · ตัวละคร
_audio = "frontend/src/character/audio.ts"
FPS = int(grab(_audio, r"const FPS = (\d+)"))
LOOKAHEAD = int(grab(_audio, r"const LOOKAHEAD_FRAMES = (\d+)"))
CUT_LOW = int(grab(_audio, r"const low = lowpass\(data, sr, (\d+)\)"))
CUT_MID = int(grab(_audio, r"const lowMid = lowpass\(data, sr, (\d+)\)"))
ATTACK = float(grab(_audio, r"const ATTACK = ([\d.]+)"))
RELEASE = float(grab(_audio, r"const RELEASE = ([\d.]+)"))
assert (FPS, LOOKAHEAD, CUT_LOW, CUT_MID, ATTACK, RELEASE) == (60, 3, 500, 2000, 0.6, 0.15)
LOOKAHEAD_MS = round(1000 * LOOKAHEAD / FPS)
assert LOOKAHEAD_MS == 50

_gest = read("frontend/src/character/gestures.ts")
CLIP_SECONDS = {n: float(s) for n, s in re.findall(r"clip\('(\w+)', ([\d.]+)", _gest)}
assert list(CLIP_SECONDS) == GESTURES                       # ทุกท่าที่ protocol รู้จัก มีคลิปจริง
_vrm = read("frontend/src/character/vrmScene.ts")
_emap = re.search(r"const EMOTION_MAP[^{]*\{(.*?)\n\}", _vrm, re.S).group(1)
EMOTION_BLEND = {e: re.findall(r"\['(\w+)', ([\d.]+)\]", body)
                 for e, body in re.findall(r"^\s*(\w+): \[(.*)\],\s*$", _emap, re.M)}
assert list(EMOTION_BLEND) == EMOTIONS
assert EMOTION_BLEND["thinking"] == [("relaxed", "0.4"), ("lookUp", "0.3")] and EMOTION_BLEND["concerned"] == [("sad", "0.55")]
SILENT_WAIT_MS = grab("frontend/src/character/Character.tsx", r"setTimeout\(r, (\d+)\)", cast=int)
CANVAS = (grab("frontend/src/character/Character.tsx", r"CANVAS_W = (\d+)", cast=int),
          grab("frontend/src/character/Character.tsx", r"CANVAS_H = (\d+)", cast=int))
assert SILENT_WAIT_MS == 2500 and CANVAS == (300, 400)

# ---------------------------------------------------------------- ฐานข้อมูล secretary.db (ทุกตาราง จาก models.py)
TABLES: dict[str, list[str]] = {}
TABLE_CLASS: dict[str, str] = {}
for _node in _tree("backend/app/models.py").body:
    if isinstance(_node, ast.ClassDef):
        _tname, _cols = None, []
        for _st in _node.body:
            if isinstance(_st, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in _st.targets):
                _tname = ast.literal_eval(_st.value)
            elif isinstance(_st, ast.AnnAssign) and isinstance(_st.target, ast.Name):
                if "relationship" not in ast.unparse(_st.value or ast.Constant(None)):
                    _cols.append(_st.target.id)
        if _tname:
            TABLES[_tname], TABLE_CLASS[_tname] = _cols, _node.name
assert list(TABLES) == ["projects", "daily_briefs", "ignored_assignments", "pinned_emails", "daily_mail_scans",
                        "snapshots", "tasks", "agent_events"]
assert "calendar_event_id" in TABLES["pinned_emails"] and "dedupe_key" in TABLES["agent_events"]

# ---------------------------------------------------------------- Google: บัญชี · scope
CAL_SCOPES = const("backend/app/services/calendar.py", "SCOPES")
GMAIL_SCOPE = const("backend/app/services/gmail.py", "GMAIL_READONLY")
CLASS_SCOPES = const("backend/app/services/classroom.py", "SCOPES")
ACCOUNTS = {m: const(f"backend/app/services/{m}.py", "ACCOUNT") for m in ("calendar", "gmail", "classroom")}
assert ACCOUNTS == {"calendar": "personal", "gmail": "personal", "classroom": "school"}
assert GMAIL_SCOPE.endswith("gmail.readonly") and all(s.endswith(".readonly") for s in CLASS_SCOPES)
assert not any("courseworkmaterials" in s for s in CLASS_SCOPES)    # ตั้งใจไม่ขอเอกสารประกอบวิชา
SCOPE_SHORT = lambda s: s.rsplit("/", 1)[1]                          # noqa: E731

# ---------------------------------------------------------------- dependency ทางอ้อม (import ตรงแต่ไม่ได้ประกาศ)
_deps = read("backend/pyproject.toml")
_lock = read("backend/uv.lock")
_mcp = re.search(r'\[\[package\]\]\nname = "mcp"\n.*?\n\n', _lock, re.S).group(0)
_sdk = re.search(r'\[\[package\]\]\nname = "claude-agent-sdk"\n.*?\n\n', _lock, re.S).group(0)
IMPLICIT_DEPS = [d for d in ("sse-starlette", "httpx") if d not in _deps and f'{{ name = "{d}" }}' in _mcp]
assert IMPLICIT_DEPS == ["sse-starlette", "httpx"] and '{ name = "mcp" }' in _sdk
assert has("backend/app/routers/events.py", "from sse_starlette.sse import EventSourceResponse")

# ---------------------------------------------------------------- การตั้งค่า · git (ค่าที่เปลี่ยนได้ทุกวัน — ไม่ assert)
ENV_EXAMPLE_IGNORED = ".env.example" in read(".gitignore").splitlines()
ENV_EXAMPLE_TRACKED = bool(git("ls-files", "backend/.env.example"))
ENV_EXAMPLE_HAS_TTS = has("backend/.env.example", "TTS_")
HEAD = git("log", "-1", "--format=%h %s")
_porc = git("status", "--porcelain").splitlines()
DIRTY_MODIFIED = sum(1 for ln in _porc if ln[:2].strip() == "M")
DIRTY_UNTRACKED = sum(1 for ln in _porc if ln.startswith("??"))
WAV_CACHED = len(list((ROOT / "backend/.tts_cache").glob("*.wav"))) if (ROOT / "backend/.tts_cache").is_dir() else 0
BUILT_AT = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")

# ---------------------------------------------------------------- ใครเขียน Google Calendar ได้ (นอก calendar.py)
_writes = []
for _p in sorted((ROOT / "backend/app").rglob("*.py")):
    _rel = _p.relative_to(ROOT / "backend/app").as_posix()
    if _rel == "services/calendar.py":
        continue
    for _fn in re.findall(r"(?:cal|calendar)\.(create_event|create_all_day_event|update_event|delete_event)\(", _p.read_text("utf-8")):
        _writes.append((_rel, _fn))
CAL_WRITERS = sorted(set(_writes))
assert CAL_WRITERS == [("agent/tools.py", "create_event"), ("agent/tools.py", "delete_event"), ("agent/tools.py", "update_event"),
                       ("routers/calendar.py", "create_event"), ("routers/projects.py", "create_event"),
                       ("services/pins.py", "create_all_day_event"), ("services/pins.py", "create_event"),
                       ("services/pins.py", "delete_event")], CAL_WRITERS
# POST /calendar/events กับ GET /calendar/upcoming เหลือจาก M0 — ไม่มีหน้าไหนเรียก
_front = "".join(p.read_text("utf-8") for p in (ROOT / "frontend/src").rglob("*.ts*"))
assert "/calendar/events" not in _front and "/calendar/upcoming" not in _front
SENDCHAT_UNUSED = _front.count("sendChat(") == 1                     # มีแต่นิยาม — แชทใช้ streamChat แล้ว
assert SENDCHAT_UNUSED

# ---------------------------------------------------------------- จุดที่ใช้ Claude · สิทธิ์ของ agent · ความจำ
CLAUDE_CALLERS = sorted(p.relative_to(ROOT / "backend/app").as_posix() for p in (ROOT / "backend/app").rglob("*.py")
                        if "query(prompt" in p.read_text("utf-8"))
assert CLAUDE_CALLERS == ["agent/brief.py", "agent/secretary.py"]
assert all(has(f"backend/app/{f}", 'permission_mode="bypassPermissions"') for f in CLAUDE_CALLERS)
assert has("backend/app/agent/brief.py", "allowed_tools=[],") and has("backend/app/agent/secretary.py", "setting_sources=[],")
CHAT_STATELESS = "resume" not in read("backend/app/agent/secretary.py")
assert CHAT_STATELESS
SLOTS_CAP = grab("backend/app/agent/planner_tools.py", r"slots\[:(\d+)\]", cast=int)
SLOT_BLOCK = grab("backend/app/agent/planner_tools.py", r'block_hours = float\(args\.get\("block_hours"\) or ([\d.]+)\)', cast=float)
assert (SLOTS_CAP, SLOT_BLOCK) == (60, 1.5)

# ---------------------------------------------------------------- ตาราง tasks มีโครงแต่ยังไม่มีโค้ดไหนใช้
TASKS_UNUSED = not any(re.search(r"\bTask\b", p.read_text("utf-8")) for p in (ROOT / "backend/app").rglob("*.py")
                       if p.name != "models.py")
assert TASKS_UNUSED

# ---------------------------------------------------------------- หน้าเว็บกับ server พอร์ตเดียว
assert has("frontend/src/main.tsx", "<HashRouter>") and has("backend/app/main.py", 'app.mount("/", StaticFiles(')
assert has(".gitignore", "frontend/public/character/") and has(".gitignore", "backend/tts_sidecar/models/")

# ---------------------------------------------------------------- งาน M8 ที่ยังไม่ commit (เปลี่ยนทุกวัน — ไม่ assert)
_all = git("status", "--porcelain", "--untracked-files=all").splitlines()
DIRTY_NEW = sum(1 for ln in _all if ln.startswith("??") and not ln[3:].startswith("docs/"))

# ---------------------------------------------------------------- ใคร emit เหตุการณ์ชนิดไหน · ความสูงของโมเดล
EMITTERS: dict[str, list[str]] = {k: [] for k in KIND_MOOD}
for _p in sorted((ROOT / "backend/app").rglob("*.py")):
    for _k in re.findall(r'events\.emit\(\s*"([a-z.]+)"', _p.read_text("utf-8")):
        EMITTERS.setdefault(_k, []).append(_p.relative_to(ROOT / "backend/app").as_posix())
assert EMITTERS["mail.autopinned"] == ["services/mail_store.py"] and EMITTERS["brief.ready"] == ["scheduler.py"]
MODEL_HEIGHT = grab("frontend/src/character/vrmScene.ts", r"this one is ([\d.]+)m tall", cast=float)
assert MODEL_HEIGHT == 1.18
