"""spec ของ "แผนที่ my_secretary" — ทุกไฟล์ ทุก process และทุกบริการภายนอกของโปรเจกต์ วางบนภาพเดียว

แกนแนวตั้ง (ไกลจากคุณแค่ไหน): เบราว์เซอร์ → HTTP API → แกน backend → ในเครื่องนี้ → คลาวด์
    ข้ามแถบ = ข้ามขอบจริง: HTTP (fetch · NDJSON · SSE) → process/ไฟล์ในเครื่อง → อินเทอร์เน็ต + OAuth
แกนแนวนอน (ระบบย่อย): ① ตัวละคร · รายงาน  ② แชท · agent  ③ วันนี้ · ปฏิทิน · โปรเจกต์  ④ อีเมล  ⑤ การเรียน

ตัวเลขทุกตัวมาจาก facts.py ซึ่งอ่านโค้ดจริงตอน build แล้ว assert — ไม่มีเลขพิมพ์มือ
สร้างใหม่: python3 docs/map/build.py   (engine อยู่ใน docs/map/submap/ จาก skill subject-map)
"""
from facts import *  # noqa: F401,F403 — ตัวเลข/รายการที่อ่านจากโค้ด (ดู facts.py)
import facts as F
from submap import Conn, Draw, Edge as E, Graph, Node as N, esc

# ================================================================ หน้า
META = dict(
    title="แผนที่ my_secretary",
    eyebrow=f"สถานะ ณ {BUILT_AT} · M8 ตัวละครคู่หู · รวมงานที่ยังไม่ commit",
    lead=("เลขาส่วนตัวที่อยู่บน Google Calendar: แชทสั่งงานได้ ทำสรุปเช้าเอง อ่านอีเมลหานัด วางแผนเวลาทำโปรเจกต์ "
          "และ (ตั้งแต่ M8) มีตัวละครที่พูดรายงานให้ฟัง · แถบบนสุดคือสิ่งที่คุณเห็นในเบราว์เซอร์ ยิ่งลงล่างยิ่งไกลจากคุณ "
          "จนถึงบริการบนคลาวด์ · กดกล่องเพื่ออ่านว่ามันคืออะไรและต่อกับอะไร หรือกด “ถัดไป” เพื่อเดินตามหนึ่งวันของเลขา"),
    axes=dict(vertical="ไกลจากคุณแค่ไหน — เบราว์เซอร์ → HTTP API → แกน backend → ในเครื่องนี้ → คลาวด์",
              horizontal="ระบบย่อย — ① ตัวละคร · รายงาน ② แชท · agent ③ วันนี้ · ปฏิทิน · โปรเจกต์ ④ อีเมล ⑤ การเรียน"),
    tour_title="หนึ่งวันของเลขา ตั้งแต่เปิดเครื่องจนสั่งงานผ่านแชท",
    tour_intro=(f"กด ถัดไป เพื่อเริ่ม: run.sh → {T_BRIEF} สรุปเช้า → {T_MAIL} อ่านอีเมล → เปิดแอปแล้วตัวละครเล่าให้ฟัง → "
                "สั่งวางแผนผ่านแชท → ตรวจและย้อนสิ่งที่เลขาทำ"),
    footer=[f"วาดจาก working tree ณ {BUILT_AT} (HEAD `{HEAD.split()[0]}` + แก้ {DIRTY_MODIFIED} ไฟล์ · ใหม่ {DIRTY_NEW} ไฟล์ที่ยังไม่ commit) · "
            "แหล่ง: โค้ดใน backend/ frontend/ run.sh · README.md · PROGRESS.md",
            f"ตัวเลขทุกตัวอ่านจากโค้ดจริงตอน build (`docs/map/facts.py`) แล้ว assert — ถ้าโค้ดเปลี่ยน build จะล้มจนกว่าจะแก้แผนที่",
            "สร้างใหม่ด้วย `python3 docs/map/build.py` · engine จาก skill subject-map"],
)

TOPICS = [("char", "ตัวละคร · รายงาน", "teal"), ("chat", "แชท · agent", "blue"), ("day", "วันนี้ · ปฏิทิน · โปรเจกต์", "purple"),
          ("mail", "อีเมล", "amber"), ("acad", "การเรียน", "green"), ("infra", "พื้นฐานร่วม", "slate"),
          ("safe", "ด่านตรวจ", "red")]

# ================================================================ กริด (การ์ด 230 × 80 · เลน 310 · ระหว่างคอลัมน์ 370)
A1, A2 = 70, 380                 # ① ตัวละคร · รายงาน
B1 = 750                         # ② แชท · agent
C1, C2, C3 = 1120, 1430, 1740    # ③ วันนี้ · ปฏิทิน · โปรเจกต์
D1, D2, D3 = 2110, 2420, 2730    # ④ อีเมล
E1 = 3100                        # ⑤ การเรียน
U1, U2 = 100, 220                # เบราว์เซอร์
R1 = 375                         # HTTP API
K1, K2, K3, K4 = 525, 665, 790, 915   # แกน backend (แถว 1–2 ห่างกว่าเพื่อวาง badge)
L1, L2 = 1065, 1185              # ในเครื่อง
CL = 1330                        # คลาวด์
SIZE = (3370, 1450)

BANDS = [
    dict(id="web", y0=70, y1=330, name="เบราว์เซอร์", sub="React", chip="เบราว์เซอร์",
         note="สิ่งที่คุณเห็นและกดได้ — แอป React หน้าเดียว (HashRouter) ที่ backend เสิร์ฟจาก frontend/dist"),
    dict(id="api", y0=350, y1=497, name="HTTP API", sub="FastAPI", chip="HTTP API",
         note=f"ประตูของ backend: {N_ROUTERS} router · {N_ROUTES} เส้นทาง รวมใน main.py (ที่เดียวกับ lifespan · CORS · เสิร์ฟหน้าเว็บ)"),
    dict(id="core", y0=503, y1=1020, name="แกน BACKEND", sub="agent · services", chip="แกน backend",
         note="โค้ด Python ใน process เดียวกับ FastAPI — agent, บริการที่คุยกับ Google, ตัวจัดเวลา, ตัวคำนวณแผน"),
    dict(id="local", y0=1040, y1=1290, name="ในเครื่องนี้", sub="process · ไฟล์", chip="ในเครื่อง",
         note="process อื่นบนเครื่องเดียวกัน (claude CLI · Ollama · TTS sidecar) และไฟล์บนดิสก์ (SQLite · token)"),
    dict(id="cloud", y0=1310, y1=1430, name="คลาวด์", sub="", chip="คลาวด์",
         note="บริการนอกเครื่อง — ต้องมีอินเทอร์เน็ตและสิทธิ์ OAuth / Pro login"),
]
COLUMNS = [
    dict(x0=A1, x1=A2 + 230, head="① ตัวละคร · รายงาน", sub="เสียง · ร่าง · เหตุการณ์", tag="M8", topic="char"),
    dict(x0=B1, x1=B1 + 230, head="② แชท · AGENT", sub="", tag="M1", topic="chat"),
    dict(x0=C1, x1=C3 + 230, head="③ วันนี้ · ปฏิทิน · โปรเจกต์", sub="สรุปเช้า · ปฏิทิน · วางแผน", tag="M0 · M4 · M5",
         topic="day"),
    dict(x0=D1, x1=D3 + 230, head="④ อีเมล", sub="อ่านอย่างเดียว · โมเดลในเครื่อง", tag="M6", topic="mail"),
    dict(x0=E1, x1=E1 + 230, head="⑤ การเรียน", sub="Classroom", tag="M3", topic="acad"),
]
BOUNDARIES = [
    (340, 2260, "ขอบเบราว์เซอร์ ↔ server — fetch · NDJSON (แชท) · SSE (เหตุการณ์)"),
    (1030, 2245, "ขอบ process — HTTP ไป localhost · ไฟล์"),
    (1300, 2030, "ขอบเครื่อง — อินเทอร์เน็ต · OAuth (Google) · Pro login (Claude)"),
]

NODES = [
    # ① ตัวละคร · รายงาน
    N("vrm", A1, U1, "ร่าง VRM", "สีหน้า · 8 ท่า · ปากขยับ", "face", "char", q=("M8",)),
    N("stage", A2, U1, "คิวการแสดง", "ทีละบรรทัด · ฟองคำพูด", "queue", "char", q=("M8",)),
    N("voice", A1, U2, "เสียง · ปาก", "WAV → ซองปาก 3 ย่าน", "wave", "char", q=("M8", "L")),
    N("hook", A2, U2, "useAgentEvents", "ตามทันตอนเปิด + ฟังสด", "sse", "char", q=("M8",)),
    N("r_tts", A1, R1, "/tts", "ข้อความ → WAV · ไม่มีเสียง = 503", "wave", "char", q=("M8", "L")),
    N("r_events", A2, R1, "/events", "stream (SSE) · pending · delivered", "sse", "char", q=("M8",)),
    N("tts_svc", A1, K1, "tts.py", "แคช WAV บนดิสก์ · ล็อกของตัวเอง", "cache", "char", q=("M8", "L")),
    N("events_svc", A2, K1, "events.py", "emit → บันทึก + ส่งสด", "irq", "char", q=("M8", "W")),
    N("sidecar", A1, L1, "TTS sidecar", f"Kokoro บน CPU · :{TTS_PORT}", "term", "char", q=("M8", "L")),
    N("t_events", A2, L1, "agent_events", "สิ่งที่ทำ · ส่งแล้วหรือยัง", "journal", "char", q=("M8",)),
    N("run_sh", A1, L2, "run.sh", f"เปิด sidecar + backend :{BACKEND_PORT}", "script", "infra"),
    # ② แชท · agent
    N("chat_ui", B1, U1, "FloatingChat", "แชทเดียวทุกหน้า · อ่าน NDJSON", "chat", "chat", q=("Q",)),
    N("r_chat", B1, R1, "/chat/stream", "NDJSON ทีละ frame", "frames", "chat", q=("Q", "M8")),
    N("ask", B1, K1, "ask_stream()", "1 turn → tool · text · done", "pipeline", "chat", q=("Q", "W", "M8")),
    N("persona", B1, K2, "persona.py", "system prompt · แท็ก mood", "person", "chat", q=("Q", "M8")),
    N("tools", B1, K3, "เครื่องมือ MCP", f"{len(TOOL_SERVERS)} server · {len(TOOLS)} tool", "tools", "chat", q=("Q", "W")),
    N("cli", B1, L1, "claude CLI", "Agent SDK เปิดเป็น process ลูก", "term", "chat", q=("Q",)),
    N("claude", B1, CL, "Claude (Pro)", "คิด + เลือก tool · มีโควตา", "model", "chat", q=("Q",)),
    # ③ วันนี้ · ปฏิทิน · โปรเจกต์
    N("home", C1, U1, "หน้า Home", "ปฏิทินสัปดาห์ · สรุปเช้า · เส้นตาย", "browser", "day", q=("Q",)),
    N("projects_pg", C3, U1, "หน้า Projects", "ค้น repo · วางแผน · หมุดจากเมล", "folder", "day", q=("W",)),
    N("r_pro", C1, R1, "/brief · /nudges", "สรุปวันนี้ · ใกล้ครบกำหนด", "doc", "day", q=("Q",)),
    N("r_cal", C2, R1, "/calendar", f"range · snapshot {mins(TTL_CAL)}", "calendar", "day"),
    N("r_proj", C3, R1, "/projects", "CRUD · discover · plan → commit", "checklist", "day", q=("W",)),
    N("brief", C1, K1, "สรุปเช้า", "brief_store + brief.py · วันละครั้ง", "doc", "day", q=("Q",)),
    N("nudges", C1, K2, "nudges.py", "เลยกำหนด · ใกล้กำหนด · ไม่ใช้ token", "warning", "day", q=("L",)),
    N("sched", C1, K4, "scheduler", f"{T_BRIEF} สรุปเช้า · {T_MAIL} สแกนเมล", "clock", "day", q=("Q", "W", "M8")),
    N("cache", C2, K1, "cache.py", "snapshot ใน DB · stale-while-revalidate", "cache", "infra"),
    N("cal_svc", C2, K2, "calendar.py", "อ่าน/เขียน Google · เขียนแล้วล้างแคช", "calendar", "day", q=("W",)),
    N("repos", C3, K1, "repos.py", "อ่าน git log ของ repo", "git", "day", q=("L",)),
    N("planner", C3, K2, "planner.py", f"หาช่องว่าง {PLAN['work_start']:02d}–{PLAN['work_end']} น.", "sched", "day",
      q=("L", "W")),
    N("t_brief", C1, L1, "daily_briefs", "1 แถวต่อวัน", "table", "day"),
    N("t_proj", C3, L1, "projects · tasks", "เส้นตาย · ชั่วโมงที่เหลือ", "table", "day"),
    N("gcal", C2, CL, "Google Calendar", "บัญชีส่วนตัว · ที่อยู่จริงของนัด", "calendar", "day", q=("W",)),
    # ④ อีเมล
    N("mail_pg", D1, U1, "หน้า Mail", "ค้น · สแกน · ปักหมุด", "mail", "mail"),
    N("r_mail", D1, R1, "/mail", "unread · today · search · scan · pins", "mail", "mail"),
    N("mail_store", D1, K1, "mail_store.py", "สแกนวันละครั้ง + ปักหมุดเอง", "loop", "mail", q=("W", "L", "M8")),
    N("pins", D1, K2, "pins.py", "ปักหมุด · มีวันที่ → ลงปฏิทิน", "pin", "mail", q=("W",)),
    N("extract", D2, K1, "mail_extract.py", "อีเมลละ 1 ครั้ง → รายการนัด", "magnifier", "mail", q=("L",)),
    N("gmail", D2, K2, "gmail.py", f"อ่านอย่างเดียว · แคช {mins(MEM_GMAIL)}", "mail", "mail"),
    N("llm", D3, K1, "local_llm.py", "JSON mode · ทีละงาน (ล็อก GPU)", "lock", "mail", q=("L",)),
    N("t_pins", D1, L1, "pinned_emails", "หมุด + id นัดในปฏิทิน", "table", "mail", q=("W",)),
    N("ollama", D3, L1, "Ollama", f":{OLLAMA_PORT} · typhoon2 8B บน GPU", "model", "mail", q=("L",)),
    N("oauth", D3, L2, "OAuth · token", "google_auth.py · token ต่อบัญชี", "key", "infra"),
    N("gmail_api", D2, CL, "Gmail", SCOPE_SHORT(GMAIL_SCOPE), "mail", "mail"),
    # ⑤ การเรียน
    N("acad_pg", E1, U1, "หน้า Academic", "งานค้าง 3 กลุ่ม · นับถอยหลัง", "book", "acad"),
    N("r_acad", E1, R1, "/academic", f"assignments · snapshot {mins(TTL_ASSIGN)}", "book", "acad"),
    N("classroom", E1, K2, "classroom.py", "บัญชีโรงเรียน · ~2 call ต่อวิชา", "book", "acad"),
    N("t_ignored", E1, L1, "งานที่สั่งข้าม", "ignored_assignments", "table", "acad"),
    N("gclass", E1, CL, "Google Classroom", "อ่านอย่างเดียว · ไม่ขอ materials", "book", "acad"),
    # ด่านตรวจ
    N("b_allow", 690, 767, f"{len(TOOLS)} tool เท่านั้น", "allowed_tools", kind="badge", topic="safe", q=("Q",)),
    N("b_preview", 1700, 490, "ดูก่อนจอง", "plan → commit", kind="badge", topic="safe", q=("W",)),
    N("b_qualify", 2225, 635, "ปักหมุดเอง?", "มีวันที่ หรือ นัด/เส้นตาย", kind="badge", topic="safe", q=("W",)),
    N("b_dedupe", 495, 885, "ประกาศครั้งเดียว", "dedupe_key", kind="badge", topic="safe", lab="l", q=("M8",)),
]

EDGES = [
    # ① ตัวละคร
    E("e_say", "stage", "voice", "speak(text)", sp="w@0.75", dp="e@0.3"),
    E("e_pose", "stage", "vrm", "สีหน้า · ท่า", sp="w@0.3", dp="e@0.3"),
    E("e_mouth", "voice", "vrm", "mouthRef 60 fps", kind="data"),
    E("e_tts", "voice", "r_tts", "POST /tts"),
    E("e_push", "hook", "stage", "push(Performance)", kind="data"),
    E("e_poll", "hook", "r_events", "pending · delivered", sp="s@0.25", dp="n@0.25", lside="l"),
    E("e_sse", "r_events", "hook", "SSE event: agent", kind="data", sp="n@0.75", dp="s@0.75"),
    E("e_synth", "r_tts", "tts_svc", "synthesize()"),
    E("e_kokoro", "tts_svc", "sidecar", "POST /synth", sp="s@0.5", dp="n@0.5"),
    E("e_live", "events_svc", "r_events", "subscribe · pending", kind="data"),
    E("e_row", "events_svc", "t_events", "INSERT · delivered_at", kind="data"),
    E("e_start_tts", "run_sh", "sidecar", f"เปิด :{TTS_PORT}"),
    # ② แชท
    E("e_send", "chat_ui", "r_chat", "POST message", sp="s@0.25", dp="n@0.25", lside="l"),
    E("e_frames", "r_chat", "chat_ui", "frame ทีละบรรทัด", kind="data", sp="n@0.75", dp="s@0.75"),
    E("e_reply", "chat_ui", "stage", "คำตอบ + mood", kind="data", sp="w@0.5", dp="e@0.5"),
    E("e_ask", "r_chat", "ask", "ask_stream(msg)"),
    E("e_persona", "ask", "persona", "prompt · parse_mood"),
    E("e_tools", "ask", "tools", "เรียก tool", sp="w@0.5", dp="w@0.5", via=(("x", 690),), lseg=1, lside="r", lt=0.25),
    E("e_query", "ask", "cli", "query()", sp="e@0.75", dp="n@0.7", via=(("x", 1000), ("y", 1047)), lseg=2),
    E("e_cloud", "cli", "claude", "HTTPS · Pro login"),
    E("t_cal", "tools", "cal_svc", "ปฏิทิน ×4 tool", sp="e@0.3", dp="s@0.5", via=(("x", 1545),),
      lxy=(1330, 806, "middle")),
    E("t_plan", "tools", "planner", "get_free_slots", sp="e@0.75", dp="s@0.3", via=(("x", 1809),), lseg=0, lt=0.8),
    # ③ วันนี้ · ปฏิทิน · โปรเจกต์
    E("e_home_pro", "home", "r_pro", "brief · nudges"),
    E("e_home_cal", "home", "r_cal", "สัปดาห์ที่เห็น", sp="e@0.5", dp="n@0.5"),
    E("e_proj_ui", "projects_pg", "r_proj", "discover · plan"),
    E("e_proj_pins", "projects_pg", "r_mail", "หมุดจากเมล", sp="s@0.85", dp="n@0.15", via=(("y", 305),), lseg=1),
    E("e_get_brief", "r_pro", "brief", "get_or_create_today"),
    E("e_get_nudges", "r_pro", "nudges", "compute_nudges", sp="w@0.5", dp="w@0.3", via=(("x", 1060),), lseg=1, lt=0.3,
      lside="l", lw=70),
    E("e_brief_n", "brief", "nudges", "ดึง nudges", kind="data", sp="s@0.5", dp="n@0.5", lside="l"),
    E("e_brief_cal", "brief", "cal_svc", "ปฏิทินวันนี้", kind="data", sp="s@0.85", dp="n@0.2", via=(("y", 635),),
      lseg=1),
    E("e_brief_ai", "brief", "cli", "เขียนสรุป", sp="w@0.25", dp="e@0.75", via=(("x", 1030),),
      lxy=(1038, 1112, "start")),
    E("e_brief_row", "brief", "t_brief", "เก็บวันละแถว", kind="data", sp="e@0.5", dp="e@0.5", via=(("x", 1390),),
      lt=0.8, lside="r", lw=60),
    E("e_cron_brief", "sched", "brief", f"{T_BRIEF}", sp="w@0.5", dp="w@0.75", via=(("x", 1090),), lt=0.15, lside="l"),
    E("e_cron_emit", "sched", "events_svc", "emit brief.ready", sp="w@0.75", dp="s@0.85", lt=0.55),
    E("e_nudge_proj", "nudges", "t_proj", "โปรเจกต์ active", kind="data", sp="s@0.9", dp="n@0.9",
      via=(("y", 767), ("x", 1947)), lseg=1, lt=0.61, lside="b"),
    E("e_range", "r_cal", "cache", "serve(range)"),
    E("e_fetch", "cache", "cal_svc", "miss → ดึง", sp="s@0.45", dp="n@0.45", lside="r", lw=90),
    E("e_clear", "cal_svc", "cache", "เขียน → ล้าง", kind="sig", sp="n@0.8", dp="s@0.8", lside="r", lw=70),
    E("e_google", "cal_svc", "gcal", "events.list / insert / patch / delete", kind="data", sp="s@0.25", dp="n@0.25",
      lt=0.7, lw=110),
    E("e_cal_auth", "cal_svc", "oauth", "credentials (personal)", sp="s@0.75", dp="n@0.3", via=(("y", 1165),), lseg=1,
      lt=0.62),
    E("e_discover", "r_proj", "repos", "discover · progress"),
    E("e_plan", "r_proj", "planner", "plan (ดูก่อน)", sp="e@0.5", dp="e@0.5", via=(("x", 2010),), lside="r", lw=60),
    E("e_crud", "r_proj", "t_proj", "CRUD", kind="data", sp="e@0.8", dp="e@0.5", via=(("x", 2040),), lt=0.55,
      lside="r"),
    E("e_commit", "r_proj", "cal_svc", "commit", sp="w@0.5", dp="e@0.3", via=(("x", 1700),),
      lxy=(1712, 641, "start")),
    E("e_busy", "planner", "cal_svc", "ช่วงที่\nไม่ว่าง", kind="data", sp="w@0.7", dp="e@0.7", lside="b"),
    # ④ อีเมล
    E("e_mail_ui", "mail_pg", "r_mail", "unread · scan · pin"),
    E("e_scan_today", "r_mail", "mail_store", "scan/today"),
    E("e_scan_now", "r_mail", "extract", "scan?scope=unread", sp="e@0.3", dp="n@0.5", via=(("x", 2535),), lseg=0),
    E("e_pin_api", "r_mail", "pins", "หมุด GET·POST·DEL", sp="e@0.8", dp="e@0.5", via=(("x", 2380),),
      lxy=(2388, 646, "start")),
    E("e_daily", "mail_store", "extract", "scan(today)", sp="e@0.5", dp="w@0.5"),
    E("e_autopin", "mail_store", "pins", ""),
    E("e_list", "extract", "gmail", "list_today · unread", kind="data"),
    E("e_llm", "extract", "llm", "chat_json ทีละฉบับ", sp="e@0.5", dp="w@0.5", lxy=(2690, 513, "middle")),
    E("e_ollama", "llm", "ollama", "POST /api/chat · JSON", lt=0.3),
    E("e_gmail", "gmail", "gmail_api", "messages.list / get", kind="data", lt=0.75),
    E("e_gmail_auth", "gmail", "oauth", "credentials (personal)", sp="e@0.7", dp="w@0.5", via=(("x", 2690),), lt=0.32,
      lside="r", lw=60),
    E("e_pin_cal", "pins", "cal_svc", "มีวันที่ → สร้างนัด", sp="s@0.2", dp="s@0.62", via=(("y", 990),), lseg=1, lt=0.1),
    E("e_pin_row", "pins", "t_pins", "หมุด + event id", kind="data", lt=0.3),
    # ⑤ การเรียน
    E("e_acad_ui", "acad_pg", "r_acad", "assignments · ignore"),
    E("e_assign", "r_acad", "classroom", "list_assignments"),
    E("e_ignore", "r_acad", "t_ignored", "ignore / un-ignore", kind="data", sp="e@0.5", dp="e@0.5",
      via=(("x", 3350),), lt=0.82, lside="l", lw=60),
    E("e_class", "classroom", "gclass", "courses · coursework", kind="data", sp="w@0.3", dp="w@0.5",
      via=(("x", 3060),), lt=0.35, lside="l", lw=70),
    E("e_class_auth", "classroom", "oauth", "credentials (school)", sp="w@0.8", dp="e@0.5", via=(("x", 3030),), lt=0.6,
      lside="l", lw=70),
]
CONNS = [
    Conn("S", "S", "sched", "s@0.8", "mail_store", "n@0.85", f"→ {T_MAIL} สแกนเมล", "← scheduler", stub=14, lside_src="w"),
    Conn("A", "E", "mail_store", "s@0.15", "events_svc", "e@0.85", "→ ประกาศ", "← mail_store", stub=14,
         lside_src="w", lside_dst="s"),
    Conn("M", "M", "tools", "s@0.3", "gmail", "e@0.25", "→ gmail", "← tools", stub=14),
    Conn("C", "C", "tools", "w@0.85", "classroom", "n@0.2", "→ classroom", "← tools", stub=14, lside_src="s"),
    Conn("N", "N", "nudges", "s@0.2", "classroom", "n@0.8", "→ classroom", "← nudges", stub=14),
]
ALLOW = (("e_tools", "b_allow"), ("e_commit", "b_preview"), ("e_autopin", "b_qualify"), ("e_row", "b_dedupe"))
EDGE_KINDS = {"ctl": "สั่ง / เรียกใช้", "data": "ข้อมูลไหล", "sig": "แจ้งย้อนกลับ / ล้างแคช", "rel": "เป็นส่วนของ"}
MAP_LEGEND_AT = None

FOCUS = [
    dict(id="W", label="เขียนปฏิทิน", topic="safe", title="ทุกทางที่ไปแก้ Google Calendar ได้", points="",
         where="tools · /projects commit · pins"),
    dict(id="Q", label="ใช้โควตา Claude", topic="chat", title="จุดที่จ่ายด้วย Claude Pro", points="", where="แชท · สรุปเช้า"),
    dict(id="L", label="ฟรี · ในเครื่อง", topic="mail", title="งานที่ไม่ใช้ token เลย", points="",
         where="Ollama · Kokoro · planner · nudges"),
    dict(id="M8", label="ใหม่ใน M8", topic="char", title="ชิ้นที่ M8 เพิ่ม (ยังไม่ commit)", points="",
         where="frontend/src/character · events · tts"),
]

# ================================================================ ไอคอนของโปรเจกต์นี้ (กรอบ 56 × 56)
ICONS = {
    "sse": ('<circle class="i-A" cx="13" cy="28" r="5"/>'
           '<path class="i-sA" d="M19.4,20.3 A10,10 0 0 1 19.4,35.7 M23.9,15.0 A17,17 0 0 1 23.9,41.0 M28.4,9.6 A24,24 0 0 1 28.4,46.4" style="stroke-width:2.4"/>'
           '<rect class="i-b" x="37" y="34" width="16" height="14" rx="2"/>'
           '<path class="i-s" d="M40,39 H50 M40,43 H47"/>'),
    "frames": "".join(f'<rect class="i-b" x="6" y="{y}" width="44" height="10" rx="2"/>'
                      f'<rect class="{c}" x="6" y="{y}" width="9" height="10" rx="2"/>'
                      f'<line class="i-s" x1="19" y1="{y + 5}" x2="{x2}" y2="{y + 5}"/>'
                      for y, c, x2 in ((8, "i-a", 40), (21, "i-A", 44), (34, "i-a", 36)))
              + '<path class="i-sA" d="M28,47 V53 M24.5,50 L28,53.5 L31.5,50"/>',
    # 4 server × จำนวน tool จริงของแต่ละ server (จุด) — อ่านจาก _ALLOWED_TOOLS
    "tools": "".join(f'<rect class="i-a" x="{x}" y="{y}" width="21" height="21" rx="4"/>'
                     + "".join(f'<circle class="i-A" cx="{x + 6 + 9 * (k % 2)}" cy="{y + 6 + 9 * (k // 2)}" r="2.6"/>'
                               for k in range(len(TOOL_SERVERS[srv])))
                     for (x, y), srv in zip(((6, 6), (29, 6), (6, 29), (29, 29)), TOOL_SERVERS)),
    "chat": ('<path class="i-b" d="M5,9 H37 V31 H17 L9,39 V31 H5 Z"/>'
             '<path class="i-a" d="M20,22 H51 V43 H46 V51 L38,43 H20 Z"/>'
             '<line class="i-s" x1="10" y1="16" x2="31" y2="16"/><line class="i-s" x1="10" y1="23" x2="15" y2="23"/>'
             '<circle class="i-A" cx="28" cy="33" r="2.2"/><circle class="i-A" cx="35" cy="33" r="2.2"/>'
             '<circle class="i-A" cx="42" cy="33" r="2.2"/>'),
    "calendar": ('<rect class="i-b" x="6" y="10" width="44" height="40" rx="4"/>'
                 '<path class="i-A" d="M6,14 a4,4 0 0 1 4,-4 H46 a4,4 0 0 1 4,4 V20 H6 Z"/>'
                 '<rect class="i-a" x="28" y="29" width="11" height="10"/>'
                 '<path class="i-s" d="M6,29 H50 M6,39 H50 M17,20 V50 M28,20 V50 M39,20 V50"/>'
                 '<path class="i-s" d="M17,5 V14 M39,5 V14" style="stroke-width:2.2"/>'),
    "mail": ('<rect class="i-b" x="5" y="13" width="46" height="32" rx="3"/>'
             '<path class="i-s" d="M6,15 L28,32 L50,15"/><path class="i-s" d="M6,44 L22,29 M50,44 L34,29"/>'
             '<circle class="i-A" cx="47" cy="13" r="5"/>'),
    "face": ('<path class="i-b" d="M12,52 C13,44 20,40 28,40 C36,40 43,44 44,52 Z"/>'
             '<circle class="i-a" cx="28" cy="25" r="16"/>'
             '<path class="i-A" d="M11,24 C11,12 19,7 28,7 C38,7 45,13 45,24 C40,17 33,15 28,17 C22,15 15,18 11,24 Z"/>'
             '<circle class="i-k" cx="22" cy="27" r="2.4"/><circle class="i-k" cx="34" cy="27" r="2.4"/>'
             '<path class="i-s" d="M23,33 Q28,37 33,33"/>'),
    "wave": "".join(f'<rect class="{"i-A" if 2 <= i <= 7 else "i-a"}" x="{6 + i * 4.6:.1f}" y="{28 - h / 2:.1f}" '
                    f'width="3" height="{h}" rx="1.5"/>'
                    for i, h in enumerate((6, 12, 22, 34, 18, 40, 26, 14, 20, 8))),
    "term": ('<rect class="i-b" x="5" y="9" width="46" height="38" rx="4"/>'
             '<path class="i-a" d="M5,13 a4,4 0 0 1 4,-4 H47 a4,4 0 0 1 4,4 V17 H5 Z"/>'
             '<path class="i-sA" d="M12,25 L19,30 L12,35" style="stroke-width:2.4"/>'
             '<line class="i-s" x1="23" y1="37" x2="35" y2="37" style="stroke-width:2"/>'),
    "browser": ('<rect class="i-b" x="5" y="8" width="46" height="40" rx="4"/><path class="i-s" d="M5,17 H51"/>'
                '<circle class="i-A" cx="10.5" cy="12.5" r="1.7"/><circle class="i-A" cx="16" cy="12.5" r="1.7"/>'
                '<circle class="i-A" cx="21.5" cy="12.5" r="1.7"/><rect class="i-a" x="10" y="22" width="17" height="21" rx="2"/>'
                '<path class="i-s" d="M31,25 H46 M31,31 H46 M31,37 H41"/>'),
    "git": ('<path class="i-s" d="M17,9 V47 M17,21 C17,31 39,25 39,36 V41" style="stroke-width:2"/>'
            '<circle class="i-A" cx="17" cy="9" r="4.5"/><circle class="i-a" cx="17" cy="28" r="4.5"/>'
            '<circle class="i-A" cx="17" cy="47" r="4.5"/><circle class="i-a" cx="39" cy="41" r="4.5"/>'),
    "pin": ('<path class="i-A" d="M19,6 H37 L34,12 V22 L42,31 H14 L22,22 V12 Z"/>'
            '<line class="i-s" x1="28" y1="31" x2="28" y2="51" style="stroke-width:2.2"/>'),
}


# ================================================================ คำอธิบายรายกล่อง (แผงข้าง + แค็ตตาล็อก)
def cols(table: str) -> str:
    return " · ".join(f"`{c}`" for c in TABLES[table])


def writers_in(path: str) -> str:
    return ", ".join(fn for f, fn in CAL_WRITERS if f == path)


DESC = {
    # ---------------- ① ตัวละคร · รายงาน
    "vrm": dict(
        what="ร่าง 3 มิติของตัวละคร (ไฟล์ VRM 1.0) ที่ three.js วาดลงแคนวาสโปร่งใสมุมซ้ายล่าง — ทุกอย่างที่ตัวละครแสดงออกมารวมที่นี่",
        does=[f"ทุกเฟรม: ท่าจาก AnimationMixer → สีหน้า ({len(EMOTIONS)} แบบ ผสมจาก expression ของ VRM) → ปาก 3 รูป (ou · aa · ih) → "
              "กะพริบตาแบบสุ่ม → หายใจ → มองตามเมาส์ → `vrm.update()` ท้ายสุด",
              f"gesture เล่นครั้งเดียวแล้ว crossfade กลับ idle — {len(GESTURES)} ท่าเขียนเป็น keyframe เอง (ไม่ใช้ Mixamo)",
              "three.js + three-vrm ถูก import แบบ dynamic เป็น chunk แยก (~800 KB) หน้าแรกจึงไม่ต้องรอ"],
        look=f"แคนวาส {CANVAS[0]}×{CANVAS[1]} px · กล้องคำนวณจากตำแหน่งหัวและสะโพกของโมเดลจริง (โมเดลนี้สูง {MODEL_HEIGHT} m)",
        exam=["โมเดลโหลดไม่ได้หรือ WebGL ตาย → ตกไปเป็นวงกลมของ Stage 0 — เสียงและฟองคำพูดยังทำงาน",
              "ลำดับใน `tick()` สำคัญ: mixer ก่อน → offset หายใจ → `vrm.update()` ท้ายสุด · offset ต้องลบค่าของเฟรมก่อนออก "
              "ไม่งั้นสะโพกหมุนสะสมไปเรื่อยๆ",
              "`model.vrm` ถูก git-ignore (หามาเอง) → clone ใหม่จะเห็นวงกลมแทนตัวละคร"],
        read="frontend/src/character/CharacterCanvas.tsx · vrmScene.ts (`createScene` · `tick`) · gestures.ts"),
    "stage": dict(
        what="คิวกลางของทุกอย่างที่ตัวละครจะพูด — คำตอบจากแชทและเหตุการณ์จาก backend ถูกแปลงเป็น `Performance` "
             "{text, emotion, gesture, speak} ก่อนเข้าคิว ร่างจึงไม่ต้องรู้ว่าแต่ละบรรทัดมาจากไหน",
        does=[f"`drain()` เล่นทีละรายการ: speak → รอเสียงจบ · ไม่พูด → แสดงฟองไว้ {SILENT_WAIT_MS / 1000:g} วินาที",
              "บรรทัดที่เล่นพลาดไม่ทำให้คิวค้าง (try/catch ต่อบรรทัด)",
              "React อ่านผ่าน `useSyncExternalStore` · ตัวนับ `seq` เพิ่มทุกบรรทัด → ท่าเดิมซ้ำก็เล่นใหม่ได้",
              "ฟองคำพูดขึ้นเสมอ แม้ไม่มีเสียงหรือไม่มีร่าง · มี “+N more” เมื่อมีคิวรอ"],
        look="store ระดับโมดูล (queue.ts) ไม่ใช่ useState — loop 60 Hz อ่านได้โดยไม่เจอ stale closure · Character.tsx ตั้ง runner",
        exam=["ทีละบรรทัดโดยตั้งใจ: ตอนเช้าที่เหตุการณ์มาเป็นชุด ตัวละครจะไม่พูดทับตัวเอง",
              "เบราว์เซอร์ยังไม่อนุญาตเสียง (ยังไม่มีการคลิก) → บรรทัดแรกรอจนคุณคลิก และขึ้น “click anywhere to enable sound”"],
        read="frontend/src/character/queue.ts · Character.tsx · protocol.ts"),
    "voice": dict(
        what="เสียงของตัวละคร: ขอ WAV จาก /tts แล้วเล่นผ่าน Web Audio พร้อมคำนวณ “ซองปาก” ล่วงหน้าทั้งประโยค",
        does=["`synthesize(text)` → POST /tts → ArrayBuffer · ได้ 503 = ไม่มีเสียง → เงียบแล้วไปต่อ (ไม่ใช่ error)",
              f"`buildVisemeEnvelope`: แยก 3 ย่านด้วย low-pass {CUT_LOW} / {CUT_MID} Hz → RMS ทุก 1/{FPS} วินาที → "
              f"ปรับตามความดังของประโยคนั้น → เปิดเร็ว ({ATTACK}) ปิดช้า ({RELEASE})",
              f"`playWithEnvelope`: เขียน [ou, aa, ih] ลง mouthRef ทุกเฟรม นำหน้าเสียง {LOOKAHEAD} เฟรม (~{LOOKAHEAD_MS} ms) "
              "เพราะปากจริงขยับก่อนเสียงออก"],
        look="mouthRef เป็น ref ไม่ใช่ state — ถ้าเป็น state จะ re-render ทั้ง dashboard (รวม FullCalendar) 60 ครั้งต่อวินาที",
        exam=["ปากรูปเดียว ('aa') ทำให้ดูเหมือนปลา — 3 ย่านคือสิ่งที่ทำให้อ่านออกว่าเป็นคำพูด",
              "AudioContext เกิดมาแบบ suspended จนกว่าจะมีการคลิก — มี listener กลางที่ resume ให้"],
        read="frontend/src/character/useSpeech.ts · audio.ts"),
    "hook": dict(
        what="ตัวรับรายงานจาก backend ฝั่งเบราว์เซอร์ — สองแหล่ง ลงคิวเดียว",
        does=[f"ตอนเปิดหน้า: GET /events/pending (ยังไม่ส่ง ≤ {PENDING['limit']} รายการ · อายุ ≤ {PENDING['max_age_hours']} ชม.) → "
              "เข้าคิวตามลำดับ → POST /events/delivered",
              "จากนั้นเปิด EventSource('/events/stream') ฟังสด · ได้ event `agent` → เข้าคิว → ยืนยัน delivered ทันที",
              "EventSource ต่อใหม่เองเมื่อ backend รีสตาร์ต (uvicorn --reload) — ไม่ต้องเขียน retry"],
        look="hook ที่ Character.tsx เรียก · มี ref กันเปิดสองสายตอน StrictMode mount ซ้ำ",
        exam=["**delivered = เบราว์เซอร์ได้รับ ไม่ใช่ตัวละครพูดจบ** — ปิดแท็บตอนคิวยังเหลือ บรรทัดที่เหลือจะไม่กลับมาอีก "
              "(eventId ถูกพกมาใน Performance แต่ไม่ได้ใช้ยืนยันหลังเล่น)",
              "ไม่มีแท็บเปิดตอน 07:00 → เหตุการณ์รอใน DB แล้วถูกเล่าตอนเปิดครั้งถัดไป (ถ้ายังไม่เกิน 12 ชม.)"],
        read="frontend/src/character/useAgentEvents.ts"),
    "r_tts": dict(
        what="ประตูเสียงของ backend: รับข้อความ คืน WAV",
        does=["GET /tts/status → {enabled, up, engine, voice} ให้หน้าเว็บบอกว่าเสียงหาย",
              "POST /tts {text ≤ 5000 ตัว} → audio/wav · Cache-Control 1 ชม. (ประโยคซ้ำในแท็บเดียวไม่ต้องขอใหม่)",
              "sidecar ล่ม → 503 ไม่ใช่ 500 → ตัวละครแค่เงียบ"],
        look=f"routers/tts.py · {ROUTE_COUNT['tts']} เส้นทาง",
        exam=["ลืมเปิด sidecar คือพลาดที่ง่ายที่สุด: ทุกอย่างยังทำงาน แค่ตัวละครเงียบ — ดู /tts/status"],
        read="backend/app/routers/tts.py"),
    "r_events": dict(
        what="ช่องรายงานสดของตัวละคร",
        does=[f"GET /events/stream → SSE event `agent` · ping ทุก {SSE_PING} วินาที (ทำให้รู้ว่าแท็บปิดแล้ว ไม่งั้น subscriber ค้าง)",
              "GET /events/pending → ตามทัน · POST /events/delivered → ยืนยัน",
              "POST /events/test → ยิงเหตุการณ์ปลอม (demo-character.sh ใช้ไล่ทุกสีหน้าและท่า)"],
        look=f"routers/events.py · {ROUTE_COUNT['events']} เส้นทาง · `sse_starlette.EventSourceResponse`",
        exam=["SSE ถูกที่ตรงนี้เพราะ reconnect เอง = ได้สิ่งที่พลาดไป — แต่ห้ามใช้กับแชท (ดูคู่ที่มักสับสน)",
              f"`{IMPLICIT_DEPS[0]}` ไม่ได้ประกาศใน pyproject — มาทางอ้อมผ่าน claude-agent-sdk → mcp"],
        read="backend/app/routers/events.py"),
    "tts_svc": dict(
        what="client ฝั่ง backend ที่คุยกับ TTS sidecar — โครงเดียวกับ local_llm.py ที่คุยกับ Ollama",
        does=["ดูแคชบนดิสก์ก่อนเข้าล็อก: `.tts_cache/<sha256(เสียง|ความเร็ว|ข้อความ)>.wav`",
              f"ไม่เจอ → เข้าล็อก (ทีละประโยค) → POST /synth (timeout {TTS_TIMEOUT:.0f} s) → ตรวจว่าขึ้นต้นด้วย `RIFF`",
              "เขียนลง `.part` แล้ว rename — ล่มกลางทางจะไม่ทิ้ง WAV ครึ่งๆ ไว้ในแคชตลอดไป"],
        look=f"services/tts.py · ตอน build มี WAV ในแคช {WAV_CACHED} ไฟล์",
        exam=["ล็อกนี้แยกจากของ local_llm โดยตั้งใจ (CPU vs GPU) — ใช้ล็อกร่วมแล้วการสแกนเมล 180 วินาทีจะบล็อกทุกคำพูด",
              f"**backend ห้าม import kokoro_onnx** — ทันทีที่ import เพดาน Python {SIDECAR_PY} จะลามมาที่ backend"],
        read="backend/app/services/tts.py · config.py (`tts_*`)"),
    "events_svc": dict(
        what="สมุดบันทึกของเลขา: สิ่งที่ทำหรือสังเกตเห็นถูกเขียนเป็นแถว แล้วส่งสดให้ทุกแท็บที่เปิดอยู่",
        does=["`emit(kind, title, …)`: เลือกสีหน้า/ท่าจาก `_KIND_MOOD` (ไม่ใช้ LLM) → dedupe_key ซ้ำ = เงียบ → INSERT → ใส่คิวของทุก subscriber",
              f"หนึ่งคิวต่อแท็บ จำกัด {QUEUE_MAX} รายการ (แท็บที่หลับไม่กินหน่วยความจำ server)",
              "`pending()` และ `mark_delivered()` สำหรับการตามทัน"],
        look="services/events.py · title เป็นประโยคภาษาอังกฤษที่พูดออกเสียงได้ ไม่ใช่ log",
        exam=[f"มีสีหน้าเตรียมไว้ให้ {' และ '.join(UNUSED_KINDS)} แต่ยังไม่มีโค้ดไหน emit",
              "emit จาก worker thread ที่ไม่มี event loop → บันทึกอย่างเดียว ไม่ส่งสด (mail_store จึง emit หลัง to_thread กลับมา)",
              "**process เดียวเท่านั้น** — subscriber อยู่ในหน่วยความจำ รัน `uvicorn --workers 2` แล้วแท็บจะพลาดเหตุการณ์ของอีก worker"],
        read="backend/app/services/events.py"),
    "sidecar": dict(
        what=f"process แยกที่รัน Kokoro TTS บน CPU ด้วย Python {SIDECAR_PY} — เพราะ kokoro-onnx ต้องการ Python ต่ำกว่า 3.14 แต่ backend ใช้ 3.14",
        does=["โหลดโมเดลครั้งเดียวตอนเริ่ม (lifespan) ไม่ใช่ตอนคำขอแรก",
              "POST /synth {text, voice, speed, lang} → WAV 24 kHz mono 16-bit (เขียนด้วย `wave` ของ stdlib ไม่ต้องลง libsndfile)",
              "GET /healthz · GET /voices"],
        look=f"backend/tts_sidecar/ · โมเดล `{KOKORO_MODEL}` + `voices-v1.0.bin` · เสียงเริ่มต้น `{TTS_VOICE}`",
        exam=[f"วัดบนเครื่องนี้: โหลด {LOAD_S} s · RTF ~{RTF:.2f} (เร็วกว่าเวลาจริง 5 เท่า)",
              "รันบน CPU โดยตั้งใจ: GPU 8 GB ถูกโมเดล 8B ของ Ollama ใช้ไปราว 5 GB แล้ว",
              "bind 127.0.0.1 เท่านั้น — เครื่องอยู่บน Tailscale และ sidecar ไม่มี auth",
              "ไฟล์โมเดลถูก git-ignore → clone ใหม่ต้องดาวน์โหลดตาม README ของ sidecar"],
        read="backend/tts_sidecar/main.py · README.md"),
    "t_events": dict(
        what="ตาราง `agent_events` ใน secretary.db — ความจำระยะยาวของสิ่งที่ตัวละครต้องเล่า",
        does=["หนึ่งแถว = หนึ่งเหตุการณ์ · `dedupe_key` กันประกาศซ้ำ · `delivered_at` บอกว่าส่งแล้ว"],
        look=f"คอลัมน์: {cols('agent_events')}",
        exam=["**คอลัมน์ถือว่าตายตัวแล้ว**: `create_all` เพิ่มตารางใหม่ได้แต่ไม่ ALTER และไม่มี Alembic · ลบ DB = หมุดลืม event id → "
              "นัดใน Google Calendar กลายเป็นกำพร้า · ของใหม่ใส่ใน `detail` (JSON)"],
        read="backend/app/models.py · class AgentEvent"),
    "run_sh": dict(
        what="สคริปต์เปิดระบบ — เปิด process ที่โปรเจกต์นี้เป็นเจ้าของสองตัว",
        does=[f"มีไฟล์โมเดล → เปิด TTS sidecar ที่ 127.0.0.1:{TTS_PORT}",
              f"เปิด backend (`uvicorn app.main:app`) ที่ :{BACKEND_PORT} · `HOST=0.0.0.0` เพื่อเข้าผ่าน Tailscale",
              "พอร์ตถูกจอง → บอก pid ที่ถืออยู่ (อาจเป็นโค้ดเก่า) · `--force` ปิดให้ · Ctrl-C ปิดทั้งกลุ่ม"],
        look=f"run.sh ที่รากโปรเจกต์ · Ollama (:{OLLAMA_PORT}) ต้องเปิดแยกเอง",
        exam=["backend ที่ค้างจากรอบก่อนยังเป็นโค้ดเก่า → route ใหม่ 404 · ใช้ `./run.sh --force`"],
        read="run.sh · PROGRESS.md (Running it)"),
    # ---------------- ② แชท · agent
    "chat_ui": dict(
        what="หน้าต่างแชทลอยมุมขวาล่าง — mount ครั้งเดียวใน App.tsx จึงเป็นบทสนทนาเดียวกันทุกหน้า",
        does=["`streamChat()` ส่งข้อความแล้วอ่าน NDJSON ทีละบรรทัด (เก็บเศษบรรทัดที่ขาดไว้ต่อรอบหน้า)",
              f"frame `tool` → ขึ้นข้อความชั่วคราวจาก TOOL_NARRATION เช่น “{NARRATION['mcp__planner__get_free_slots']}”",
              "frame `text` → แทนที่ข้อความชั่วคราว แล้วส่งต่อเข้าคิวการแสดงพร้อม emotion/gesture",
              "frame `error` ชนิด rate_limit → “I've hit my Claude limit for now”"],
        look="ซ่อนด้วย CSS เมื่อปิด (ไม่ unmount) ประวัติจึงไม่หาย",
        exam=["**ประวัติบนจอ ≠ ความจำของ agent** — ทุกข้อความเป็น `query()` ใหม่ agent ไม่รู้ว่าเมื่อกี้คุยอะไร",
              "`sendChat()` (POST /chat แบบรอทั้งก้อน) ยังอยู่ใน api.ts แต่ไม่มีใครเรียกแล้ว"],
        read="frontend/src/components/Chat.tsx · api.ts (`streamChat`)"),
    "r_chat": dict(
        what="ประตูแชท: POST /chat/stream ส่งผลทีละ frame แบบ NDJSON (JSON หนึ่งบรรทัดต่อ frame)",
        does=["วน `ask_stream(message)` แล้วส่ง `json + \\n` ทีละ frame",
              "พังหลังเริ่มส่งแล้ว → ส่ง frame error + done แทน HTTP 500 (header ออกไปแล้ว)",
              "header `X-Accel-Buffering: no` กัน proxy รวมทุกอย่างเป็นก้อนเดียว"],
        look=f"routers/chat.py · {ROUTE_COUNT['chat']} เส้นทาง (POST /chat แบบเก่ายังอยู่)",
        exam=["**ไม่ใช่ SSE โดยตั้งใจ**: EventSource เป็น GET (ส่งข้อความไม่ได้) และ reconnect เองเมื่อสายขาด — บนแชทนั่นคือรัน agent ซ้ำ "
              "เผาโควตา Pro และอาจเขียนปฏิทินซ้ำ"],
        read="backend/app/routers/chat.py"),
    "ask": dict(
        what="หัวใจของแชท: หนึ่งข้อความ = หนึ่ง turn ของ Agent SDK แปลงเป็น frame ที่แชทและตัวละครเข้าใจ",
        does=[f"สร้าง options ใหม่ทุกครั้ง (วันที่ใน prompt จะได้ถูก) · ลงทะเบียน {len(TOOL_SERVERS)} MCP server ในโปรเซส",
              "AssistantMessage: ToolUseBlock → `tool` · TextBlock → `parse_mood` → `text` · message.error → `error`",
              "UserMessage ที่มี ToolResultBlock → `tool_result` (จังหวะที่ตัวละครเลิกทำท่าคิด)",
              "ResultMessage → `done` {session_id, turns}"],
        look="agent/secretary.py · `ask()` เดิมเหลือเป็น wrapper ที่เก็บเฉพาะ text",
        exam=["ไม่ใช่ระดับ token — เสียงต้องการประโยคเต็มก่อนสังเคราะห์",
              "`setting_sources=[]` → เลขาไม่เห็น CLAUDE.md หรือ settings ของคุณ รู้เฉพาะสิ่งที่ prompt บอก"],
        read="backend/app/agent/secretary.py (`ask_stream` · `_options`)"),
    "persona": dict(
        what="ตัวตนของเลขาในไฟล์เดียว: system prompt + คำศัพท์อารมณ์ + ตัวแกะแท็ก mood",
        does=["`system_prompt()`: ใส่วันที่วันนี้ · ตอบอังกฤษเสมอแม้ถามไทย (เสียงพูดอังกฤษ) · 1–3 ประโยค ไม่มี markdown · "
              "กติกาการใช้ tool และการวางแผน",
              f"`mood_instruction()`: ให้ปิดท้ายด้วย `<mood>emotion:gesture</mood>` จาก {len(EMOTIONS)} อารมณ์ × {len(GESTURES)} ท่า",
              "`parse_mood()`: แกะแท็กท้ายข้อความ · ตัดแท็กที่หลงอยู่ทุกที่ · ค่าผิด → neutral/idle"],
        look="agent/persona.py — คำศัพท์ชุดเดียวกับ protocol.ts ฝั่งเบราว์เซอร์ (build ของแผนที่ตรวจว่าตรงกัน)",
        exam=["แท็กผิดรูปไม่ใช่ error: หน้าเรียบดีกว่า 500",
              "แก้ EMOTIONS/GESTURES ต้องแก้ protocol.ts + EMOTION_MAP + gestures.ts ด้วย ไม่งั้นเบราว์เซอร์ตกไปที่ค่าเริ่ม"],
        read="backend/app/agent/persona.py · frontend/src/character/protocol.ts"),
    "tools": dict(
        what=f"เครื่องมือ {len(TOOLS)} ตัวใน {len(TOOL_SERVERS)} MCP server ที่รันในโปรเซสเดียวกับ FastAPI — ทั้งหมดที่ Claude ทำได้",
        does=[f"**{srv}**: " + " · ".join(f"`{n}`" for n in names) for srv, names in TOOL_SERVERS.items()]
             + ["`allowed_tools` = รายชื่อนี้เท่านั้น → ไม่มี bash ไฟล์ หรือเว็บ"],
        look="agent/tools.py · planner_tools.py · gmail_tools.py · classroom_tools.py — ทุกตัวคืน {content: [{type: text}]}",
        exam=["`permission_mode=bypassPermissions` → tool รันทันที ไม่มีด่านยืนยันในโค้ด · “ยืนยันก่อนลบ” อยู่ใน system prompt เท่านั้น",
              f"`get_free_slots` คืนช่องว่างจริงไม่เกิน {SLOTS_CAP} ช่อง ({SLOT_DAYS} วัน · {SLOT_BLOCK} ชม.) — agent เลือกจากเมนูนี้ ไม่ประดิษฐ์เวลาเอง",
              "`list_events` ใส่ event id ให้ เพื่อให้ update/delete อ้างถึงได้"],
        read="backend/app/agent/*_tools.py · secretary.py (`_ALLOWED_TOOLS`)"),
    "cli": dict(
        what="Agent SDK ไม่ได้ยิง API เอง — มันเปิด claude CLI เป็น process ลูกที่ล็อกอินด้วยบัญชี Claude Pro ของคุณ",
        does=["`query()` → subprocess claude → stream ข้อความกลับ", "tool ของเรา (SDK MCP) ถูกเรียกกลับเข้ามาในโปรเซส FastAPI"],
        look="login เดียวกับ Claude Code · ไม่มี ANTHROPIC_API_KEY ใน .env",
        exam=["ตั้ง ANTHROPIC_API_KEY = เปลี่ยนไปจ่ายแบบ API ที่คิดเงินแยก (จึงตั้งใจเว้นว่าง)",
              f"ใช้แค่ {len(CLAUDE_CALLERS)} จุด: แชท และสรุปเช้า"],
        read=".env.example · README (Architecture)"),
    "claude": dict(
        what="สมองของแชทและคนเขียนสรุปเช้า — Claude บน subscription Pro",
        does=["แชท: อ่าน system prompt → เลือก tool → อ่านผล → ตอบ + mood", "สรุปเช้า: เขียนจากข้อความที่ยื่นให้ ไม่มี tool"],
        look="บริการคลาวด์ของ Anthropic ที่เข้าผ่าน claude CLI",
        exam=["ชนเพดานของ Pro เป็นเรื่องปกติ → frame `error` (rate_limit) → แชทบอกให้รอ ไม่ใช่ 500",
              "งานจำนวนมากหรือข้อมูลส่วนตัว (อ่านอีเมล) ถูกย้ายไปโมเดลในเครื่อง เพื่อเก็บโควตาไว้ให้แชท"],
        read="README · Architecture & key decisions"),
    # ---------------- ③ วันนี้ · ปฏิทิน · โปรเจกต์
    "home": dict(
        what="หน้าแรก: ปฏิทินสัปดาห์ (FullCalendar) + การ์ดสรุปเช้า + การ์ดเส้นตาย",
        does=["ปฏิทินขอ /calendar/range ตามช่วงที่มองเห็น และขอใหม่เมื่อเลื่อนสัปดาห์",
              "สรุปเช้า: GET /brief/today · ปุ่ม Refresh = POST /brief/regenerate (เรียก Claude ใหม่)",
              "เส้นตาย: GET /nudges (เลยกำหนด · ใกล้กำหนด · คำแนะนำให้วางแผน)"],
        look="pages/Home.tsx · ปฏิทินด้านบน การ์ดสองใบด้านล่าง · ทั้งแอปเป็น HashRouter (/#/academic) ที่ backend เสิร์ฟจาก dist",
        exam=["Refresh สรุปเช้าใช้โควตา Claude ทุกครั้ง — nudges ไม่ใช้"],
        read="frontend/src/pages/Home.tsx · main.tsx (HashRouter)"),
    "projects_pg": dict(
        what="หน้าโปรเจกต์: repo ที่ค้นเจอ + แผนงาน + หมุดจากอีเมล",
        does=["Discover: สแกนโฟลเดอร์หา git repo แล้ว upsert เป็นโปรเจกต์",
              "แก้ deadline · ชั่วโมง · สถานะในการ์ด (Ignore = สถานะ dropped)",
              "Plan now → ดูบล็อกก่อน → Add to calendar", "ส่วน From email: หมุดจาก /mail/pins + ปุ่มถอนหมุด"],
        look="pages/Projects.tsx · การ์ดต่อโปรเจกต์ + การ์ดหมุดแยกส่วน",
        exam=["หมุดอยู่หน้านี้แต่ไม่ใช่โปรเจกต์ — planner และ nudges มองไม่เห็น"],
        read="frontend/src/pages/Projects.tsx"),
    "r_pro": dict(
        what="ประตูของงานเชิงรุก",
        does=["GET /brief/today → `get_or_create_today()` (สร้างครั้งแรกของวัน)", "POST /brief/regenerate → force",
              "GET /nudges?days=7 → `compute_nudges()`"],
        look=f"routers/proactive.py · {ROUTE_COUNT['proactive']} เส้นทาง",
        exam=[f"server ปิดตอน {T_BRIEF} ก็ไม่เป็นไร: คนแรกที่เปิด Home ทำให้สรุปถูกสร้างตอนนั้น (lazy)"],
        read="backend/app/routers/proactive.py"),
    "r_cal": dict(
        what="ประตูปฏิทินของหน้า Home",
        does=[f"GET /calendar/range?start&end → `cache.serve('calendar:<start>:<end>', ttl={TTL_CAL})`",
              "ตอบเป็นซอง {data, fetched_at, stale}"],
        look=f"routers/calendar.py · {ROUTE_COUNT['calendar']} เส้นทาง",
        exam=["GET /calendar/upcoming และ POST /calendar/events เหลือจาก M0 — ไม่มีหน้าไหนเรียก แต่ POST ยังเขียนปฏิทินได้จริง",
              "แต่ละช่วงวันที่เป็น snapshot แยกกัน · เขียนผ่าน calendar.py เมื่อไรก็ล้างทั้งตระกูล `calendar:*`"],
        read="backend/app/routers/calendar.py"),
    "r_proj": dict(
        what="ประตูของโปรเจกต์และการวางแผนแบบกดปุ่ม",
        does=["CRUD: GET/POST /projects · PATCH/DELETE /projects/{id}",
              "POST /projects/discover → `discover_repos(root)` แล้ว upsert ตาม repo_path (ไม่แตะ goal/deadline/ชั่วโมงที่คุณใส่)",
              "POST /projects/{id}/plan → `make_plan()` (อ่านอย่างเดียว)", "POST /projects/{id}/plan/commit → สร้างนัดตามบล็อกที่ส่งมา"],
        look=f"routers/projects.py · {ROUTE_COUNT['projects']} เส้นทาง",
        exam=["plan กับ commit แยกกันโดยตั้งใจ — เป็นทางเดียวที่คุณได้ดูก่อนเลขาเขียนปฏิทิน",
              "ลบโปรเจกต์ไม่แตะ repo จริง ลบแค่ระเบียนของเรา"],
        read="backend/app/routers/projects.py"),
    "brief": dict(
        what="สรุปเช้า = brief_store.py (วันละครั้ง) + agent/brief.py (Claude เขียน)",
        does=["`get_or_create_today()`: มีแถวของวันนี้ใน daily_briefs แล้ว → คืนเลย · ยังไม่มีหรือ force → สร้าง",
              "`_gather()`: ปฏิทินที่เหลือของวันนี้ + nudges 7 วัน → ข้อความธรรมดา",
              "`generate_brief()`: `query()` ด้วย `allowed_tools=[]` (เขียนอย่างเดียว) แล้วเก็บผล"],
        look="ข้อความธรรมดา: ทักทาย 1 บรรทัดแล้วตามด้วย bullet แบบขีด (ไม่มี markdown)",
        exam=["นี่คือการใช้ token ตามตารางเวลาเพียงจุดเดียวของแอป",
              "งาน Classroom ที่สั่งข้ามไม่เข้ามาในสรุป (ถูกกรองตั้งแต่ nudges)"],
        read="backend/app/services/brief_store.py · agent/brief.py"),
    "nudges": dict(
        what="ตัวคำนวณ “อะไรต้องสนใจ” แบบไม่ใช้ token — เรียกบ่อยแค่ไหนก็ได้",
        does=["งาน Classroom: เลยกำหนด และครบกำหนดภายใน 7 วัน (ตัดงานที่สั่งข้าม)",
              "โปรเจกต์ active: deadline ผ่านแล้ว = เลยกำหนด · ภายใน 7 วัน = ใกล้กำหนด",
              "โปรเจกต์ใกล้กำหนดที่ยังเหลือชั่วโมง → ข้อความแนะนำ “ask the chat to plan it” (replan แบบแนะนำ ไม่แก้ปฏิทิน)"],
        look="{overdue: [...], due_soon: [...], suggestions: [...]}",
        exam=[f"ใช้แคชในหน่วยความจำของ classroom.py ({mins(MEM_CLASS)}) ไม่ใช่ snapshot {mins(TTL_ASSIGN)} ของหน้า Academic — สองที่อาจเห็นไม่ตรงกันชั่วครู่",
              "หมุดจากเมลไม่อยู่ในนี้"],
        read="backend/app/services/nudges.py"),
    "sched": dict(
        what="นาฬิกาของงานเชิงรุก (APScheduler) — เริ่มใน lifespan ของ main.py พร้อม `init_db()`",
        does=[f"{T_BRIEF} morning_brief → สร้างสรุปเช้า → emit brief.ready (พลาด → brief.failed)",
              f"{T_MAIL} daily_mail_scan → `mail_store.get_or_create_today(force=True)` → ปักหมุด/สร้างนัด → emit (พลาด → mail.failed)",
              "dedupe_key ผูกกับวันที่ → retry หรือ --reload ไม่ทำให้ประกาศซ้ำ"],
        look="scheduler.py · AsyncIOScheduler ใน event loop เดียวกับ FastAPI",
        exam=["รันเฉพาะตอน backend เปิด — ปิดเครื่องข้ามคืน = สรุปถูกสร้างแบบ lazy ตอนเปิด Home",
              f"งาน {T_MAIL} คือการเขียนปฏิทินครั้งเดียวที่ไม่มีใครกด — M8 จึงให้มันประกาศเสมอ",
              "nightly replan ไม่มีงานจริง — เป็นข้อความแนะนำใน nudges"],
        read="backend/app/scheduler.py · main.py (lifespan)"),
    "cache": dict(
        what="แคช snapshot ในตาราง `snapshots` ของ SQLite แบบ stale-while-revalidate: เปิดหน้าไม่ต้องรอ Google",
        does=["`serve(key, fetcher, ttl)`: ไม่มี snapshot หรือ refresh=true → ดึงสดแล้วเก็บ",
              "มีและยังสด → คืนเลย · เก่ากว่า TTL → คืนของเก่าทันที + ตั้งงาน refresh เบื้องหลัง (BackgroundTasks)",
              "`clear_prefix('calendar:')` เมื่อมีการเขียนปฏิทิน"],
        look="ซอง {data, fetched_at, stale} → หน้าเว็บแสดง “updated 4m ago · Refresh”",
        exam=["รอดการรีสตาร์ต ต่างจากแคชในหน่วยความจำของ gmail.py / classroom.py",
              "นัดที่แก้ใน Google Calendar โดยตรง (มือถือ) จะเห็นหลัง TTL เท่านั้น"],
        read="backend/app/services/cache.py"),
    "cal_svc": dict(
        what="จุดเดียวที่คุยกับ Google Calendar — ทุกคนที่อ่านหรือเขียนปฏิทินผ่านที่นี่",
        does=["`list_events` · `create_event` · `create_all_day_event` · `update_event` (patch) · `delete_event`",
              "ทุกการเขียน → `_invalidate_cache()` → `clear_prefix('calendar:')`",
              "`_rfc3339()`: datetime ที่ไม่มีโซนเวลาถือว่าเป็น UTC"],
        look=f"services/calendar.py · บัญชี {ACCOUNTS['calendar']} · scope `{', '.join(SCOPE_SHORT(s) for s in CAL_SCOPES)}` (อ่าน+เขียน)",
        exam=[f"ถูกเรียกเขียนจาก {len({w[0] for w in CAL_WRITERS})} ไฟล์: " + " · ".join(sorted({w[0] for w in CAL_WRITERS})),
              "delete ย้อนไม่ได้ — ระวังเป็นพิเศษใน tool ของแชท"],
        read="backend/app/services/calendar.py"),
    "repos": dict(
        what="อ่านความคืบหน้าจาก git ในเครื่อง — ไม่ใช้เน็ต ไม่ใช้ token",
        does=["`discover_repos(root)`: โฟลเดอร์ชั้นเดียวใต้ root ที่มี .git → {name, path, last_commit_at}",
              "`read_progress(path)`: commit ล่าสุด · จำนวน commit · ใน 14 วัน · หัวข้อ 5 commit ล่าสุด"],
        look="เรียก `git -C <path>` ผ่าน subprocess (timeout 10 s)",
        exam=["ลงไปชั้นเดียวโดยตั้งใจ (ไม่เดินเข้า node_modules / .venv) — ชี้ไปที่โฟลเดอร์ที่รวมโปรเจกต์",
              "last_commit_at ถูกเก็บในตาราง projects ตอน discover เพื่อให้หน้าโหลดเร็ว"],
        read="backend/app/services/repos.py"),
    "planner": dict(
        what="แกนวางแผนแบบกำหนดได้ (deterministic): หาช่องว่างจริงในปฏิทิน แล้ววางบล็อกงานก่อน deadline",
        does=[f"วันละช่วง {PLAN['work_start']:02d}:00–{PLAN['work_end']}:00 · บล็อกละ {PLAN['block_hours']} ชม. · "
              f"ไม่เกิน {PLAN['max_hours_per_day']:g} ชม./วัน/โปรเจกต์",
              "`_busy_intervals`: นัดที่มีเวลา = ไม่ว่าง (นัดทั้งวันไม่นับ)",
              "`plan_blocks` → {blocks, hours_scheduled, hours_unscheduled} · `free_slots` → เมนูช่องว่างให้ agent"],
        look="services/planner.py · ฟังก์ชันบริสุทธิ์ (แผนที่นี้ดึงไปรันจริงในภาพ “หาช่องว่าง”)",
        exam=["ไม่เขียนอะไรเลย — คืนแค่ข้อเสนอ",
              "ชั่วโมงเกินที่วางได้ → บอกส่วนที่วางไม่ได้ตรงๆ (hours_unscheduled) ไม่ยัดเกินเพดาน",
              "นัดทั้งวันจากหมุดเมลไม่บล็อกเวลา"],
        read="backend/app/services/planner.py"),
    "t_brief": dict(
        what="ตาราง `daily_briefs` — สรุปเช้าหนึ่งแถวต่อวัน (for_date ไม่ซ้ำ)",
        does=["brief_store เขียน/ทับ · /brief/today อ่าน"], look=f"คอลัมน์: {cols('daily_briefs')}",
        read="backend/app/models.py · class DailyBrief"),
    "t_proj": dict(
        what="ตาราง `projects` (+ `tasks`) — สมองของการวางแผน",
        does=["/projects เขียน (CRUD · discover)", "planner (`make_plan`) · tool `list_projects` · nudges อ่าน"],
        look=f"projects: {cols('projects')} · tasks: {cols('tasks')}",
        exam=["ตาราง tasks มีโครงแล้วแต่ยังไม่มีโค้ดไหนอ่านหรือเขียน — ชั่วโมงที่เหลือใช้ `projects.estimated_hours`",
              "status `dropped` = Ignore บนหน้า Projects (ไม่ถูกเตือน ไม่ถูกวางแผน)"],
        read="backend/app/models.py · class Project · class Task"),
    "gcal": dict(
        what="ที่อยู่จริงของนัดทั้งหมด — SQLite ไม่เคยเก็บนัด เก็บแค่สิ่งที่เลขาคิด",
        does=["ถูกอ่านทุกครั้งที่หน้า Home เปลี่ยนช่วง (ผ่าน snapshot)", "ถูกเขียนจากแชท · Add to calendar · หมุดเมล"],
        look=f"Google Calendar API v3 · calendarId=`{SETTINGS['calendar_id']}`",
        exam=["403 accessNotConfigured = ยังไม่ได้เปิด API ในโปรเจกต์ Google Cloud (ไม่ใช่ปัญหา scope)"],
        read="README · Setup"),
    # ---------------- ④ อีเมล
    "mail_pg": dict(
        what="หน้าอีเมล: อ่าน · ค้น · สแกนหานัด · ปักหมุด",
        does=[f"ดู Unread หรือ Today (snapshot {mins(TTL_MAIL)}) · ค้นด้วย Gmail syntax (สด)",
              "สแกน: unread = POST /mail/scan สดทุกครั้ง · today = ผลรายวันที่เก็บไว้ (force = สแกนใหม่)",
              "📌 บนรายการที่สกัดได้ (พาวันที่ไปด้วย) หรือบนอีเมล (ไม่มีวันที่ → backend อ่านลึกหาเอง)",
              "เตือนก่อนสแกนถ้า Ollama ไม่ทำงาน (/mail/local-status)"],
        look="pages/Mail.tsx · จำสถานะหน้าไว้ในตัวแปรระดับโมดูล กลับมาหน้านี้ไม่ต้องโหลดใหม่",
        exam=["การสแกนปักหมุดให้เองและอาจสร้างนัดทันที — ไม่ต้องการก็ถอนหมุดที่หน้า Projects"],
        read="frontend/src/pages/Mail.tsx"),
    "r_mail": dict(
        what="ประตูอีเมล — ฝั่ง Gmail อ่านอย่างเดียวทั้งหมด",
        does=[f"GET /mail/unread · /mail/today → snapshot {mins(TTL_MAIL)} · GET /mail/search → สด",
              "POST /mail/scan → สกัดด้วยโมเดลในเครื่อง → ปักหมุดเอง (ใน worker thread) → ตอบพร้อมธง pinned",
              "GET /mail/scan/today → mail_store (วันละครั้ง)",
              f"GET/POST/DELETE /mail/pins · POST ที่ไม่มีวันที่ → `deep_extract` อ่านลึก {DEEP_BODY:,} ตัวอักษรก่อนปัก"],
        look=f"routers/mail.py · {ROUTE_COUNT['mail']} เส้นทาง",
        exam=["Ollama ล่ม → 503 พร้อมข้อความบอกวิธีแก้ (ไม่ใช่ 500)",
              "สแกนแบบกดปุ่มไม่ emit เหตุการณ์ (คุณเห็นผลบนจออยู่แล้ว) — ประกาศเฉพาะสแกนรายวัน"],
        read="backend/app/routers/mail.py"),
    "mail_store": dict(
        what="สแกนอีเมลวันละครั้ง (แบบเดียวกับสรุปเช้า) แล้วปักหมุดสิ่งที่เข้าเกณฑ์ และประกาศให้ตัวละครเล่า",
        does=["มีแถวของวันนี้ใน daily_mail_scans และไม่ force → คืนเลย",
              "`scan(scope='today')` → `auto_pin_items` ใน worker thread (เรียก Google แบบ blocking)",
              "กลับมาที่ event loop แล้ว emit mail.autopinned (พูด) หรือ mail.scanned (ไม่พูด)",
              "เก็บผลเป็น JSON ใน daily_mail_scans"],
        look="services/mail_store.py",
        exam=["emit ตรงนี้ ไม่ใช่ใน `pins.auto_pin_items` เพราะนั่นอยู่ใน worker thread ซึ่งส่งสดไม่ได้",
              "dedupe_key ผูกกับวัน → สแกนซ้ำในวันเดียวกันจะไม่ประกาศซ้ำ"],
        read="backend/app/services/mail_store.py"),
    "pins": dict(
        what="หมุด = ยกอีเมลขึ้นมาเป็นรายการบนหน้า Projects · มีวันที่ → สร้างนัดใน Google Calendar ด้วย",
        does=["`auto_pin_items`: เข้าเกณฑ์ (`_qualifies`) → ปักหมุด · หนึ่งหมุดต่ออีเมล (รายการที่มีวันที่มาก่อน) · ปักแล้วข้าม",
              "`pin()`: วันที่ล้วน → นัดทั้งวัน · มีเวลา → นัด 1 ชั่วโมง · เก็บ calendar_event_id",
              "`unpin()`: ลบนัดที่สร้างไว้ด้วย แล้วลบหมุด"],
        look=f"services/pins.py · ชื่อนัดขึ้นต้นด้วย 📧 · เรียก {writers_in('services/pins.py')}",
        exam=["Gmail ยังอ่านอย่างเดียว — หมุดเป็นสถานะในเครื่องล้วน",
              "ปฏิทินพังไม่ทำให้ปักไม่ได้ (หมุดยังเกิด แค่ไม่มีนัด)"],
        read="backend/app/services/pins.py"),
    "extract": dict(
        what="ตัวสกัดนัดจากอีเมลด้วยโมเดลในเครื่อง — ให้แค่ข้อเสนอ ไม่เขียนอะไรเอง",
        does=[f"`scan()`: อ่านอีเมล (unread หรือ today) ทีละฉบับ · เนื้อหาไม่เกิน {MAX_BODY:,} ตัวอักษร",
              "prompt: ไทยหรืออังกฤษ · ห้ามเดาวันที่ · ข้ามโปรโมชันและจดหมายข่าว",
              "ทิ้งรายการ type=other ที่ไม่มีวันที่ (ที่ที่ขยะโฆษณามักตกค้าง)",
              f"`deep_extract()`: อ่านฉบับเดียวแบบละเอียด {DEEP_BODY:,} ตัวอักษร → {{date, type, summary}}"],
        look="{type, title, datetime, note, email_id, email_subject, email_from, link}",
        exam=["หนึ่งฉบับต่อหนึ่งการเรียกโมเดล — หลายสิบฉบับใช้เวลาเป็นนาที (รับได้สำหรับงานเบื้องหลัง)"],
        read="backend/app/services/mail_extract.py"),
    "gmail": dict(
        what="จุดเดียวที่คุยกับ Gmail — อ่านอย่างเดียว",
        does=["`list_messages(query)`: list แล้ว get ทีละฉบับ → {id, from, subject, date, snippet, body, unread, link}",
              "`list_unread` · `list_today` (after:<วันนี้>) · `get_message` (สำหรับหมุด)",
              "ดึงข้อความจาก text/plain ก่อน · ไม่มีค่อยลอก HTML"],
        look=f"services/gmail.py · scope `{SCOPE_SHORT(GMAIL_SCOPE)}` · แคชในหน่วยความจำ {mins(MEM_GMAIL)} ต่อ query",
        exam=["ขอ scope รวม (calendar + gmail.readonly) เพราะใช้ token.json ร่วมกับปฏิทิน — ไม่งั้นสองฝั่งแย่งกันขอ consent ใหม่",
              "ทำเครื่องหมายอ่านแล้วก็ทำไม่ได้ — การส่งเมลคือ M7 และต้องอนุมัติทุกครั้ง"],
        read="backend/app/services/gmail.py"),
    "llm": dict(
        what="client ของ Ollama: ส่ง prompt สองส่วน ได้ JSON กลับ",
        does=["`chat_json(system, user)`: format='json' · temperature 0 · stream=false",
              f"ล็อกเดียวทั้งแอป → GPU ทำทีละงาน · timeout {LLM_TIMEOUT:.0f} s",
              "`_parse_json`: โมเดลพูดเกิน → ตัดเอาช่วง {...} หรือ [...] นอกสุด"],
        look=f"services/local_llm.py · ใช้ `{IMPLICIT_DEPS[1]}` ที่มากับ SDK (ไม่ได้ประกาศเอง)",
        exam=["Ollama ล่ม → OllamaError → 503 พร้อมคำแนะนำ “Is `ollama serve` running?”"],
        read="backend/app/services/local_llm.py"),
    "t_pins": dict(
        what="ตาราง `pinned_emails` — หนึ่งแถวต่ออีเมลที่ปัก",
        does=["pins.py เขียน/ลบ · /mail/pins อ่าน (หน้า Projects)",
              f"(ผลสแกนรายวันอยู่อีกตาราง: `daily_mail_scans` = {cols('daily_mail_scans')})"],
        look=f"คอลัมน์: {cols('pinned_emails')}",
        exam=["`calendar_event_id` คือสายเดียวที่ทำให้ถอนหมุดลบนัดได้ — ลบ DB = นัดกำพร้า"],
        read="backend/app/models.py · class PinnedEmail · class DailyMailScan"),
    "ollama": dict(
        what="เซิร์ฟเวอร์โมเดลภาษาในเครื่อง (process แยกที่เปิดเอง) — ใช้แค่สกัดนัดจากอีเมล",
        does=[f"โมเดล `{OLLAMA_MODEL}` (ไทย/อังกฤษ 8B พอดี GPU 8 GB)", "POST /api/chat · GET /api/tags (ใช้เช็กว่าเปิดอยู่)"],
        look=f"http://localhost:{OLLAMA_PORT}",
        exam=["run.sh ไม่ได้เปิดให้ — ต้อง `ollama serve` เอง", "เปลี่ยนโมเดลได้ที่ OLLAMA_MODEL โดยไม่แก้โค้ด"],
        read="backend/app/config.py · README (Tech stack)"),
    "oauth": dict(
        what="สิทธิ์เข้า Google ต่อบัญชี: google_auth.py จัดการไฟล์ token บนดิสก์",
        does=["`get_credentials(account, scopes)`: personal → token.json · school → token_school.json",
              "token ได้ scope ไม่ครบ → เปิดเบราว์เซอร์ขอ consent ใหม่ · หมดอายุ → refresh",
              "โหลดด้วย scope รวม (ที่ขอ ∪ ที่เคยได้) → refresh แล้ว scope ของอีกฝั่งไม่หด",
              "`OAUTHLIB_RELAX_TOKEN_SCOPE` + ตาราง scope ทดแทน (Google เปลี่ยนชื่อ scope ของ Classroom)"],
        look="credentials.json (ตัวตนของแอป) + token*.json (สิทธิ์ของแต่ละบัญชี) — ถูก git-ignore ทั้งหมด",
        exam=["ห้าม commit `.env` · `credentials.json` · `token*.json` · `*.db`"]
             + ([".env.example ก็ถูก git-ignore ไปด้วย (อยู่ในหมวด secrets ของ .gitignore) — clone ใหม่จะทำตาม README "
                 "ที่ให้ `cp .env.example .env` ไม่ได้"] if ENV_EXAMPLE_IGNORED and not ENV_EXAMPLE_TRACKED else [])
             + (["`.env.example` ยังไม่มีคีย์ OLLAMA_* และ TTS_*"] if not ENV_EXAMPLE_HAS_TTS else []),
        read="backend/app/services/google_auth.py · .gitignore"),
    "gmail_api": dict(
        what="Gmail ของบัญชีส่วนตัว", does=["users.messages.list(q) + get(format=full)"], look="Gmail API v1",
        exam=[f"อ่านได้อย่างเดียว (`{SCOPE_SHORT(GMAIL_SCOPE)}`) — การส่งรอ M7"], read="README · Setup"),
    # ---------------- ⑤ การเรียน
    "acad_pg": dict(
        what="หน้าการเรียน: งานที่ยังไม่ส่ง + ทุกวิชา",
        does=["fetch เดียว (/academic/assignments) ป้อนทั้งสองส่วน",
              "ด้านบน: เลยกำหนด · กำลังจะถึง · ไม่มีกำหนด · ✕ = สั่งข้าม",
              "ด้านล่าง: ทุกวิชาพร้อมสถานะการส่ง และนับถอยหลังทุกนาที"],
        look="pages/Academic.tsx · “updated Nm ago · Refresh”", read="frontend/src/pages/Academic.tsx"),
    "r_acad": dict(
        what="ประตูการเรียน (Classroom อ่านอย่างเดียว)",
        does=[f"GET /academic/assignments → snapshot {mins(TTL_ASSIGN)} (เรียก classroom แบบข้ามแคชในหน่วยความจำ) แล้วแปะธง ignored ทุกครั้ง",
              "GET /courses · /todo · /ignored · POST /ignore · DELETE /ignore/{id}"],
        look=f"routers/academic.py · {ROUTE_COUNT['academic']} เส้นทาง",
        exam=["สั่งข้ามมีผลทันทีโดยไม่ต้องดึง Classroom ใหม่ (ธงถูกแปะทับ snapshot)"],
        read="backend/app/routers/academic.py"),
    "classroom": dict(
        what="จุดเดียวที่คุยกับ Google Classroom — บัญชีโรงเรียน อ่านอย่างเดียว",
        does=["`list_courses` → ทุกวิชาที่ ACTIVE",
              "`list_assignments`: ต่อวิชาเรียก coursework + submission ของฉัน (~2 call ต่อวิชา) → {due, state, submitted, overdue}",
              "`list_todo_grouped` → overdue · upcoming · no_deadline"],
        look="services/classroom.py · scope " + " · ".join(f"`{SCOPE_SHORT(s)}`" for s in CLASS_SCOPES) + f" · แคช {mins(MEM_CLASS)}",
        exam=["ไม่ขอ courseworkmaterials โดยตั้งใจ — เอกสารประกอบวิชาเป็นงานของอีกโปรเจกต์",
              "ส่งแล้ว = TURNED_IN หรือ RETURNED · มีวันแต่ไม่มีเวลา = 23:59 UTC ของวันนั้น",
              "ACCESS_TOKEN_SCOPE_INSUFFICIENT ถูกโยนต่อ (ไม่กลืนเป็น “0 งาน”)"],
        read="backend/app/services/classroom.py"),
    "t_ignored": dict(
        what="ตาราง `ignored_assignments` — งาน Classroom ที่สั่งว่าไม่ต้องเตือน (Classroom เองแก้ไม่ได้)",
        does=["/academic/ignore เขียน", "หน้า Academic · nudges · สรุปเช้า · tool `list_todo` กรองออก"],
        look=f"คอลัมน์: {cols('ignored_assignments')}", read="backend/app/models.py · services/dismissed.py"),
    "gclass": dict(
        what="Google Classroom ของบัญชีโรงเรียน (Workspace for Education)",
        does=["courses.list · courseWork.list · studentSubmissions.list (userId=me)"], look="Classroom API v1",
        exam=["ผู้ดูแลของโรงเรียนบล็อกแอปภายนอกได้ — ทดสอบตอน M3 แล้วผ่าน (go/no-go: GREEN)"], read="README · M3"),
    # ---------------- ด่านตรวจ
    "b_allow": dict(
        what="ด่าน allowed_tools: Claude ใช้ได้เฉพาะ tool ในรายชื่อ",
        does=[f"{len(TOOLS)} tool จาก {len(TOOL_SERVERS)} server · ไม่มี bash ไฟล์ หรือเว็บ"], look="secretary.py · `_ALLOWED_TOOLS`",
        exam=["ด่านนี้จำกัดว่า “ทำอะไรได้” ไม่ได้จำกัดว่า “ทำเมื่อไร” — ทุก tool รันทันที (bypassPermissions)"],
        read="backend/app/agent/secretary.py"),
    "b_preview": dict(
        what="ด่าน “ดูก่อนจอง” ของการวางแผนแบบกดปุ่ม",
        does=["POST /plan คืนบล็อกที่เสนอโดยไม่เขียนอะไร", "POST /plan/commit สร้างนัดเฉพาะบล็อกที่ส่งกลับมา"],
        exam=["เป็นทางเขียนปฏิทินทางเดียวที่มีการดูก่อน — ทางอื่นเขียนทันที"], read="backend/app/routers/projects.py"),
    "b_qualify": dict(
        what="ด่านเกณฑ์ปักหมุดอัตโนมัติ (`_qualifies`)",
        does=[f"ผ่านเมื่อมีวันที่ หรือ type เป็น {' / '.join(AUTO_PIN_TYPES)}", "ผ่าน + มีวันที่ → สร้างนัดในปฏิทินด้วย"],
        exam=["ตั้งใจหลวม: ปักไว้ก่อนให้คุณถอนเอง ดีกว่าพลาดเส้นตาย",
              "รายการที่รอดตัวกรองตอนสกัดเข้าเกณฑ์เสมอ — ด่านนี้คัดออกได้เฉพาะเมื่อโมเดลตอบ type นอกที่ prompt กำหนด"],
        read="backend/app/services/pins.py (`_qualifies` · `auto_pin_items`)"),
    "b_dedupe": dict(
        what="ด่านกันประกาศซ้ำ",
        does=["emit ที่มี dedupe_key ซ้ำกับแถวเดิม → คืน None และไม่ส่งอะไร",
              "scheduler และ mail_store ใช้ `kind:<วันที่>` เช่น brief.ready:" + BUILT_AT[:10]],
        exam=["retry แบบ best-effort ของ scheduler และ uvicorn --reload คือเหตุผลที่ต้องมีด่านนี้"],
        read="backend/app/services/events.py (`emit`)"),
}


# ================================================================ อธิบายละเอียด (ตาราง/ตัวเลขคำนวณจาก facts)
_WRAPS = {"list_events": "calendar.list_events (ใส่ event id)", "create_event": "calendar.create_event",
          "update_event": "calendar.update_event (patch)", "delete_event": "calendar.delete_event",
          "list_todo": "classroom.list_todo_grouped − งานที่สั่งข้าม", "list_courses": "classroom.list_courses",
          "list_projects": "ตาราง projects", "get_free_slots": f"calendar.list_events + planner.free_slots (≤ {SLOTS_CAP})",
          "search_email": "gmail.list_messages(q, 15)", "recent_unread_email": "gmail.list_unread(15)"}
assert set(_WRAPS) == {n for names in TOOL_SERVERS.values() for n in names}
_ROUTER_NODE = dict(chat="r_chat", events="r_events", tts="r_tts", proactive="r_pro", calendar="r_cal", projects="r_proj",
                    mail="r_mail", academic="r_acad")
_day = lambda d: d.strftime("%a %d %b %H:%M")  # noqa: E731

DEEP = {
    "tools": dict(blocks=[
        ("table", f"{len(TOOLS)} tool ที่ Claude ใช้ได้", ["server", "tool", "ห่อของจริง", "เขียน?", "แชทขึ้นว่า"],
         [[srv, f"`{n}`", _WRAPS[n], "✏️ เขียน" if n in CAL_WRITE_TOOLS else "อ่าน", NARRATION[f"mcp__{srv}__{n}"]]
          for srv, names in TOOL_SERVERS.items() for n in names]),
        ("trap", ["“ยืนยันก่อนลบ” อยู่ใน system prompt ไม่ใช่ในโค้ด — แชทไม่มีความจำ ถ้าเลขาถามยืนยันแล้วคุณตอบ “yes” "
                  "turn ใหม่จะไม่รู้ว่า yes หมายถึงอะไร"]),
    ]),
    "events_svc": dict(blocks=[
        ("table", "ชนิดเหตุการณ์ → สีหน้า · ท่า (ไม่ใช้ LLM)", ["kind", "emotion", "gesture", "ใคร emit"],
         [[f"`{k}`", e, g, ", ".join(EMITTERS[k]) or "— (ยังไม่มี)"] for k, (e, g) in KIND_MOOD.items()]),
        ("p", "ทำไมต้องมีทั้งแถวใน DB และการส่งสด",
         "แถวทำให้ “ระหว่างที่คุณไม่อยู่ ฉันทำ…” รอดทั้งการรีสตาร์ตและการปิดแท็บ · การส่งสดทำให้แท็บที่เปิดอยู่ได้ยินทันที "
         "สองครึ่งนี้คือสิ่งที่ M8 Stage 1 (event backbone) เพิ่มเข้ามา"),
    ]),
    "vrm": dict(blocks=[
        ("table", "อารมณ์ของเรา → expression ของ VRM (น้ำหนักบวกทุกเฟรม)", ["emotion", "ผสมจาก"],
         [[e, " + ".join(f"{n} {w}" for n, w in EMOTION_BLEND[e]) or "— (หน้าปกติ)"] for e in EMOTIONS]),
        ("table", "ท่าทาง → ความยาวคลิป (keyframe เขียนเอง)", ["gesture", "วินาที"],
         [[g, f"{CLIP_SECONDS[g]:g}" + (" (วน)" if g == "idle" else "")] for g in GESTURES]),
    ]),
    "voice": dict(blocks=[
        ("calc", "ซองปากของประโยคหนึ่ง (audio.ts)",
         [f"แบ่งเสียงเป็นเฟรมละ 1/{FPS} วินาที → ที่ 24 kHz = {24000 // FPS} sample ต่อเฟรม",
          f"ย่านต่ำ < {CUT_LOW} Hz → ou · ย่านกลาง {CUT_LOW}–{CUT_MID} Hz → aa · ย่านสูง > {CUT_MID} Hz → ih",
          "RMS ต่อย่านต่อเฟรม → หารด้วยค่าสูงสุดของประโยค (ประโยคเบาก็ยังขยับปาก)",
          f"กรองไม่สมมาตร: เป้าสูงขึ้น → ขยับ {ATTACK:.0%} ของระยะ · ต่ำลง → {RELEASE:.0%} (ปากเปิดเร็ว ปิดช้า)",
          f"ตอนเล่น อ่านเฟรมล่วงหน้า {LOOKAHEAD} เฟรม = {LOOKAHEAD} × 1000/{FPS} ≈ **{LOOKAHEAD_MS} ms**"]),
    ], figs=["f-voice"]),
    "planner": dict(blocks=[
        ("calc", "ตัวอย่างจากภาพจำลอง (รัน plan_blocks ตัวจริง)",
         [f"ต้องการ {SIM_HOURS:g} ชม. · ตอนนี้ {_day(SIM_NOW)} · deadline {_day(SIM_DEADLINE)}",
          f"เพดาน {PLAN['max_hours_per_day']:g} ชม./วัน ÷ บล็อก {PLAN['block_hours']} ชม. = วันละ {int(PLAN['max_hours_per_day'] // PLAN['block_hours'])} บล็อก",
          f"3 วัน × {PLAN['max_hours_per_day']:g} ชม. = {3 * PLAN['max_hours_per_day']:g} ชม. → วางได้ **{SIM['hours_scheduled']:g}** · "
          f"วางไม่ได้ **{SIM['hours_unscheduled']:g}** ชม.",
          "บล็อก: " + " · ".join(b[0].strftime("%a %H:%M") for b in SIM_BLOCKS)]),
    ], figs=["f-plan"]),
    "sched": dict(blocks=[
        ("table", "งานตามเวลา", ["id", "เวลา", "ทำอะไร", "ประกาศ"],
         [[JOBS[0][0], T_BRIEF, "brief_store.get_or_create_today()", "brief.ready / brief.failed"],
          [JOBS[1][0], T_MAIL, "mail_store.get_or_create_today(force=True)", "mail.autopinned / mail.scanned / mail.failed"]]),
    ]),
    "oauth": dict(blocks=[
        ("table", "สองบัญชี หนึ่ง OAuth client", ["บัญชี", "ไฟล์ token", "ใช้โดย", "scope"],
         [["personal", "token.json", "calendar.py · gmail.py",
           " · ".join(f"`{SCOPE_SHORT(s)}`" for s in CAL_SCOPES + [GMAIL_SCOPE])],
          ["school", "token_school.json", "classroom.py", " · ".join(f"`{SCOPE_SHORT(s)}`" for s in CLASS_SCOPES)]]),
        ("p", "ทำไม gmail ขอ scope ของปฏิทินด้วย",
         "สองบริการใช้ token.json ไฟล์เดียว ถ้าต่างคนต่างขอเฉพาะของตัวเอง ทุกครั้งที่ฝั่งหนึ่ง refresh จะเขียนทับจนอีกฝั่งต้อง "
         "consent ใหม่ — วนแบบนี้ทุกชั่วโมง การขอ scope รวม และโหลดด้วย “ที่ขอ ∪ ที่เคยได้” ตัดวงจรนี้"),
    ]),
    "cache": dict(blocks=[
        ("table", "snapshot ใน SQLite (รอดการรีสตาร์ต)", ["key", "ใช้โดย", "TTL"],
         [[f"`{k}`", who, mins(t)] for k, who, t in CACHE_ROWS]),
        ("table", "แคชในหน่วยความจำ (หายเมื่อ process ตาย)", ["ตัวแปร", "เก็บอะไร", "อายุ"],
         [[f"`{k}`", what, mins(t)] for k, what, t in MEM_ROWS]),
    ], figs=["f-cache"]),
    "cal_svc": dict(blocks=[
        ("table", "ใครเรียกฟังก์ชันเขียนของ calendar.py (นับจากโค้ดตอน build)", ["ไฟล์", "ฟังก์ชัน"],
         [[f, f"`{fn}`"] for f, fn in CAL_WRITERS]),
    ]),
    "persona": dict(blocks=[
        ("ul", "สิ่งที่ system prompt สั่ง (ย่อ)",
         ["ตอบอังกฤษเสมอ · 1–3 ประโยค · ไม่มี markdown/emoji · พูดตัวเลขแบบคนพูด",
          "แก้/ลบนัด: list_events หา id ก่อน · แก้เฉพาะช่องที่ขอ · ลบต้องยืนยัน",
          "อีเมลอ่านได้อย่างเดียว · จะใส่ลงปฏิทินต้องยืนยันรายละเอียดก่อน",
          "วางแผน: list_projects → get_free_slots → เลือกตามเงื่อนไข → สร้าง “Work: <project>” · "
          "วางใหม่ = ลบบล็อกเดิมของโปรเจกต์นั้นก่อน · ห้ามแตะโปรเจกต์ที่สั่งให้เว้น",
          "แชทไม่มีความจำ → คำสั่งชัดให้ทำจบใน turn เดียว แล้วรายงานว่าเพิ่ม/ลบอะไร",
          "เวลาแบบ “พรุ่งนี้ 6 โมง” ต้องแปลงเป็น ISO 8601 ก่อนเรียก tool · นัดยาว 1 ชม. ถ้าไม่บอก"]),
    ]),
    **{_ROUTER_NODE[r]: dict(blocks=[("table", "เส้นทางทั้งหมด", ["method", "path"], [[m, f"`{p}`"] for m, p in rs])])
       for r, rs in ROUTES.items() if r not in ("tools",)},
}

# ================================================================ ทัวร์: หนึ่งวันของเลขา
TOUR = [
    dict(act="เปิดระบบ", t="run.sh เปิด TTS sidecar และ backend", n=["run_sh", "sidecar"], e=["e_start_tts"],
         x=f"sidecar ฟังที่ :{TTS_PORT} · backend ที่ :{BACKEND_PORT} · Ollama (:{OLLAMA_PORT}) ต้องเปิดแยกเอง · "
           "ลืม sidecar ทุกอย่างยังทำงาน แค่ตัวละครไม่มีเสียง (/tts/status บอกว่าขาดอะไร)"),
    dict(act="เปิดระบบ", t="lifespan ของ FastAPI: สร้างตาราง แล้วตั้งนาฬิกา", n=["sched", "t_events", "t_brief", "t_proj"],
         x=f"init_db() = create_all (เพิ่มตารางใหม่ได้ แต่ไม่แก้ตารางเดิม) · start_scheduler() ตั้งงาน {T_BRIEF} กับ {T_MAIL} · "
           "backend ยังเสิร์ฟหน้าเว็บจาก frontend/dist ที่พอร์ตเดียวกัน"),
    dict(act=f"{T_BRIEF} สรุปเช้า", t="scheduler เรียก brief_store", n=["sched", "brief"], e=["e_cron_brief"],
         x="มีแถวของวันนี้แล้วก็คืนเลย (วันละครั้ง) · ยังไม่มีก็สร้าง — จุดเดียวที่ใช้ Claude ตามตารางเวลา"),
    dict(act=f"{T_BRIEF} สรุปเช้า", t="รวมข้อมูล: ปฏิทินที่เหลือของวันนี้ + nudges", n=["brief", "cal_svc", "nudges", "classroom", "t_proj"],
         e=["e_brief_cal", "e_brief_n", "e_nudge_proj"], c=["N"],
         x="nudges ไม่ใช้ token: งาน Classroom ที่เลยหรือใกล้กำหนด (ตัดงานที่สั่งข้าม) + โปรเจกต์ active ที่ deadline ใกล้"),
    dict(act=f"{T_BRIEF} สรุปเช้า", t="Claude เขียนสรุปผ่าน claude CLI — ไม่มี tool เลย", n=["brief", "cli", "claude", "t_brief"],
         e=["e_brief_ai", "e_cloud", "e_brief_row"],
         x="allowed_tools=[] → เขียนจากข้อมูลที่ยื่นให้เท่านั้น ไม่มีทางไปแตะปฏิทิน · เก็บลง daily_briefs วันละแถว"),
    dict(act=f"{T_BRIEF} สรุปเช้า", t="ประกาศ brief.ready ลง agent_events", n=["sched", "events_svc", "b_dedupe", "t_events"],
         e=["e_cron_emit", "e_row"],
         x="dedupe_key = brief.ready:<วันที่> → retry หรือ --reload ไม่ทำให้พูดซ้ำ · ไม่มีแท็บเปิด = เหตุการณ์รออยู่ใน DB"),
    dict(act=f"{T_MAIL} อ่านอีเมล", t="scheduler สั่ง mail_store สแกนอีเมลของวันนี้", n=["sched", "mail_store"], c=["S"],
         x="scope 'today' = ทุกฉบับที่เข้ามาวันนี้ อ่านแล้วหรือยังก็ได้ — ฟรีเพราะใช้โมเดลในเครื่อง"),
    dict(act=f"{T_MAIL} อ่านอีเมล", t="gmail.py ดึงอีเมล (อ่านอย่างเดียว)", n=["mail_store", "extract", "gmail", "oauth", "gmail_api"],
         e=["e_daily", "e_list", "e_gmail", "e_gmail_auth"],
         x="ใช้ token.json ของบัญชีส่วนตัวร่วมกับปฏิทิน · ขอ scope รวมกันเพื่อไม่ต้อง consent สลับไปมา"),
    dict(act=f"{T_MAIL} อ่านอีเมล", t="Ollama อ่านทีละฉบับ แล้วตอบเป็นรายการนัด (JSON)", n=["extract", "llm", "ollama"],
         e=["e_llm", "e_ollama"],
         x=f"เนื้อหาตัดที่ {MAX_BODY:,} ตัวอักษร · ล็อกให้ GPU ทำทีละงาน · timeout {LLM_TIMEOUT:.0f} วินาที · เนื้อหาไม่ออกนอกเครื่อง"),
    dict(act=f"{T_MAIL} อ่านอีเมล", t="เข้าเกณฑ์ → ปักหมุดเอง · มีวันที่ → สร้างนัดใน Google Calendar",
         n=["mail_store", "b_qualify", "pins", "cal_svc", "gcal", "t_pins"], e=["e_autopin", "e_pin_cal", "e_google", "e_pin_row"],
         x="นี่คือการเขียนปฏิทินครั้งเดียวที่ไม่มีใครกด · วันที่ล้วน → นัดทั้งวัน · มีเวลา → 1 ชั่วโมง · "
           "เก็บ event id ไว้ให้ถอนหมุดแล้วลบนัดได้"),
    dict(act=f"{T_MAIL} อ่านอีเมล", t="calendar.py เขียนเสร็จแล้วล้าง snapshot calendar:*", n=["cal_svc", "cache"], e=["e_clear"],
         x="ครั้งหน้าที่เปิดหน้า Home จะเห็นนัดใหม่ทันที ไม่ต้องรอ TTL"),
    dict(act=f"{T_MAIL} อ่านอีเมล", t="ประกาศ mail.autopinned", n=["mail_store", "events_svc", "t_events"], e=["e_row"], c=["A"],
         x="emit บน event loop (หลัง to_thread กลับมา) จึงส่งสดได้ · ไม่มีอะไรเข้าเกณฑ์ → mail.scanned แบบไม่พูด"),
    dict(act="เปิดแอป", t="เปิดเบราว์เซอร์ → หน้า Home", n=["home", "r_pro", "r_cal", "cache", "brief"],
         e=["e_home_pro", "e_home_cal", "e_range", "e_get_brief"],
         x="ปฏิทินมาจาก snapshot ทันที · สรุปเช้ามาจาก DB (ไม่เรียก Claude ซ้ำ) · URL เป็น /#/… เพราะ HashRouter "
           "หน้าเว็บกับ API จึงไม่ชนกัน"),
    dict(act="เปิดแอป", t="useAgentEvents ขอ /events/pending แล้วเปิดสายสด", n=["hook", "r_events", "events_svc", "t_events"],
         e=["e_poll", "e_live", "e_sse"],
         x=f"ได้เหตุการณ์ที่ยังไม่ส่ง ไม่เกิน {PENDING['limit']} รายการ อายุไม่เกิน {PENDING['max_age_hours']} ชม. · แล้วเปิด EventSource ฟังต่อ"),
    dict(act="เปิดแอป", t="ยืนยัน delivered ทันที แล้วเข้าคิวการแสดง", n=["hook", "stage", "r_events"], e=["e_push", "e_poll"],
         x="POST /events/delivered เกิดตอนรับ ไม่ใช่ตอนพูดจบ — ปิดแท็บกลางคิว บรรทัดที่เหลือจะหายไป"),
    dict(act="เปิดแอป", t="คิวส่งทีละบรรทัด → ขอเสียงจาก /tts", n=["stage", "voice", "r_tts", "tts_svc"], e=["e_say", "e_tts", "e_synth"],
         x="tts.py ดูแคชบนดิสก์ก่อน (sha256 ของเสียง|ความเร็ว|ข้อความ) ไม่เจอค่อยเข้าล็อก"),
    dict(act="เปิดแอป", t="Kokoro สังเคราะห์ WAV บน CPU", n=["tts_svc", "sidecar"], e=["e_kokoro"],
         x=f"RTF ~{RTF:.2f} (เร็วกว่าเวลาจริง 5 เท่า) · ประโยคเดิมครั้งหน้าใช้ ~{HIT_S} วินาทีจากแคช · sidecar ใช้ Python {SIDECAR_PY} แยกจาก backend"),
    dict(act="เปิดแอป", t="WAV → ซองปาก 3 ย่าน → ปากขยับ + สีหน้า + ท่าทาง", n=["voice", "vrm", "stage"], e=["e_mouth", "e_pose"],
         x=f"คำนวณ RMS ต่อ 1/{FPS} วินาทีล่วงหน้าทั้งประโยค · เปิดปากก่อนเสียง {LOOKAHEAD_MS} ms · brief.ready = "
           f"{'/'.join(KIND_MOOD['brief.ready'])}"),
    dict(act="สั่งงานผ่านแชท", t="พิมพ์: “plan my_secretary next week, mornings only”", n=["chat_ui", "r_chat", "ask"],
         e=["e_send", "e_ask"],
         x="POST /chat/stream (NDJSON) — ไม่ใช่ SSE เพราะ EventSource reconnect เอง ซึ่งบนแชทเท่ากับสั่ง agent ซ้ำและเผาโควตา"),
    dict(act="สั่งงานผ่านแชท", t="ask_stream ประกอบ prompt แล้วเปิด claude CLI", n=["ask", "persona", "cli", "claude"],
         e=["e_persona", "e_query", "e_cloud"],
         x="system prompt สร้างใหม่ทุกครั้ง (มีวันที่วันนี้) · ตอบอังกฤษสั้นๆ เพราะต้องพูดออกเสียง · ไม่มีความจำข้ามข้อความ"),
    dict(act="สั่งงานผ่านแชท", t="Claude เรียก list_projects แล้ว get_free_slots", n=["ask", "b_allow", "tools", "planner", "cal_svc", "t_proj"],
         e=["e_tools", "t_plan", "e_busy"],
         x=f"ใช้ได้แค่ {len(TOOLS)} tool ที่อนุญาต · get_free_slots คืนช่องว่างจริงจาก planner ({SLOT_DAYS} วัน · บล็อก {SLOT_BLOCK} ชม.) "
           "agent จึงเลือกจากเมนูเวลาจริง ไม่เดาเอง"),
    dict(act="สั่งงานผ่านแชท", t=f"ระหว่างรอ แชทขึ้น “{NARRATION['mcp__planner__get_free_slots']}”", n=["r_chat", "chat_ui"], e=["e_frames"],
         x="frame tool ถูกแปลเป็นข้อความชั่วคราวด้วย TOOL_NARRATION แล้วถูกแทนด้วยคำตอบจริง"),
    dict(act="สั่งงานผ่านแชท", t="create_event ทีละบล็อก “Work: my_secretary”", n=["tools", "cal_svc", "gcal", "cache"],
         e=["t_cal", "e_google", "e_clear"],
         x="bypassPermissions — tool รันทันที ไม่มีด่านยืนยันในโค้ด (คำสั่งใน system prompt คือด่านเดียว) · เขียนแล้วล้างแคชเหมือนทุกทาง"),
    dict(act="สั่งงานผ่านแชท", t="คำตอบ + <mood> → ฟองแชท + ตัวละครพูด", n=["ask", "persona", "chat_ui", "stage", "vrm"],
         e=["e_frames", "e_reply", "e_pose"],
         x="parse_mood ตัดแท็กออกก่อนแสดง · แท็กผิดรูป → neutral/idle ไม่ใช่ error"),
    dict(act="ตรวจและย้อน", t="หน้า Projects: ดูหมุดจากเมล แล้วถอนหมุดที่ไม่ต้องการ", n=["projects_pg", "r_mail", "pins", "cal_svc", "t_pins"],
         e=["e_proj_pins", "e_pin_api", "e_pin_cal"],
         x=f"unpin ลบนัดที่สร้างไว้ด้วย (ใช้ event id ที่เก็บไว้) — ทางย้อนของการเขียนตอน {T_MAIL}"),
    dict(act="ตรวจและย้อน", t="Plan now: ดูแผนก่อน แล้วค่อยจอง", n=["projects_pg", "r_proj", "planner", "b_preview", "cal_svc"],
         e=["e_proj_ui", "e_plan", "e_commit"],
         x="POST /plan ไม่เขียนอะไร · POST /plan/commit จึงสร้างนัด — ทางเดียวที่คุณได้ดูก่อนเลขาเขียน"),
]

# ================================================================ คู่ที่มักสับสน
PAIRS = [
    ("/chat/stream (NDJSON)", "/events/stream (SSE)", ["r_chat", "r_events"],
     "แชทเป็น **POST ที่ไม่ต่อใหม่เอง** (ต่อใหม่ = รัน agent ซ้ำ เขียนปฏิทินซ้ำ) · เหตุการณ์เป็น **SSE ที่ต่อใหม่เอง** "
     "(ต่อใหม่ = ได้สิ่งที่พลาดไป)"),
    ("Claude (Pro)", "Ollama", ["claude", "ollama"],
     "Claude **คิดและเลือก tool** ในแชท + เขียนสรุปเช้า (นับโควตา) · Ollama **สกัดนัดจากอีเมล** อย่างเดียว (ฟรี เนื้อหาไม่ออกนอกเครื่อง)"),
    ("snapshot (cache.py)", "แคชในหน่วยความจำ", ["cache", "gmail", "classroom"],
     f"snapshot อยู่ใน **SQLite รอดการรีสตาร์ต** และบอกได้ว่าเก่าแค่ไหน · แคชใน gmail.py/classroom.py **หายเมื่อ process ตาย** "
     f"({mins(MEM_GMAIL)} / {mins(MEM_CLASS)}) — หน้า Academic ข้ามแคชนี้ แต่ nudges ใช้"),
    ("หมุดจากเมล", "โปรเจกต์", ["t_pins", "t_proj", "projects_pg"],
     "อยู่หน้า Projects เหมือนกัน แต่หมุดอยู่ใน **pinned_emails** · planner, nudges และ list_projects อ่านแค่ **projects** — "
     "หมุดจึงไม่ถูกวางแผนหรือเตือน"),
    ("Plan now (ปุ่ม)", "วางแผนในแชท", ["r_proj", "planner", "tools"],
     "ปุ่มใช้ **plan_blocks + ดูก่อนจอง** ทีละโปรเจกต์ · แชทให้ Claude **เลือกจาก free_slots แล้วจองทันที** "
     "และรับเงื่อนไขภาษาคนได้ (เฉพาะเช้า · อย่าแตะโปรเจกต์ B)"),
    ("สรุปเช้า", "nudges", ["brief", "nudges"],
     "nudges **คำนวณสดทุกครั้ง ไม่ใช้ token** · สรุปเช้า **ใช้ Claude วันละครั้ง** แล้วเก็บไว้ — กด Refresh = เรียก Claude ใหม่"),
    ("delivered", "พูดจบแล้ว", ["hook", "stage", "t_events"],
     "delivered_at ถูกตั้ง **ตอนเบราว์เซอร์ได้รับ** ไม่ใช่ตอนตัวละครพูดจบ — ปิดแท็บตอนคิวยังเหลือ บรรทัดที่เหลือจะไม่ถูกเล่าอีก"),
    ("emotion", "gesture", ["vrm", "persona"],
     "emotion = **สีหน้าค้างไว้ตลอดบรรทัด** (ผสม expression ของ VRM) · gesture = **ท่าครั้งเดียว** แล้วกลับ idle — "
     "มาจากแท็ก <mood> อันเดียวกัน"),
    ("tts.py", "local_llm.py", ["tts_svc", "llm"],
     "ทั้งคู่เป็น HTTP client ไปหา process ในเครื่องและมี **ล็อกของตัวเอง** · แยกกันเพราะ Kokoro ใช้ CPU ส่วน Ollama ใช้ GPU — "
     f"ล็อกร่วมจะทำให้สแกนเมล {LLM_TIMEOUT:.0f} วินาทีบล็อกเสียงพูด"),
    ("token.json (ส่วนตัว)", "token_school.json", ["oauth", "gcal", "gclass"],
     "ส่วนตัว = **ปฏิทิน + Gmail ใช้ร่วมกัน** (scope รวม) · โรงเรียน = **Classroom อย่างเดียว** — OAuth client ตัวเดียว สองบัญชี"),
    ("ประวัติบนจอแชท", "ความจำของ agent", ["chat_ui", "ask"],
     "FloatingChat **เก็บข้อความไว้บนจอ** ทุกหน้า แต่แต่ละ turn เป็น query() ใหม่ — **agent ไม่รู้ว่าเมื่อกี้คุยอะไร** "
     "(Stage 7 วางแผนใช้ resume)"),
    ("สแกนแบบกดปุ่ม (unread)", f"สแกนรายวัน {T_MAIL} (today)", ["r_mail", "mail_store", "extract"],
     "ทั้งคู่ **ปักหมุดเองและอาจสร้างนัด** · แบบกดปุ่มรันสดทุกครั้งและ **ไม่ประกาศ** · แบบรายวันเก็บผลวันละครั้งและ "
     "**emit ให้ตัวละครพูด**"),
]

UI = dict(ch="", exam="จุดที่มักพลาด / ต้องรู้", read="อ่านต่อในโค้ด", nav_catalog="ทุกกล่อง",
          badge_legend="ด่านตรวจ / กฎที่เลขาต้องผ่าน",
          chapters_title="ภาพอธิบายรายเรื่อง",
          chapters_intro="ตัวเลขในภาพมาจากโค้ดจริงตอน build · ภาพจำลองระบุไว้ในคำบรรยาย · กด “ทีละขั้น” เพื่อดูทีละส่วน")


# ================================================================ ภาพรายเรื่อง
def chip(i, x, y, name, gloss="", w=220, h=54, topic="infra", steps=()):
    return N(i, x, y, name, gloss, kind="chip", topic=topic, w=w, h=h, steps=steps)


def fig_turn():
    """หนึ่ง turn ของแชท = frame 4 ชนิด · คอลัมน์ = frame ตามเวลา · แถว = แต่ละชั้นทำอะไรกับ frame นั้น"""
    d = Draw(1000, 400, topic="chat", aria="frame ทั้ง 4 ชนิดของหนึ่ง turn ในแชท")
    rows = [("Claude ทำอะไร", 62), ("ask_stream แปลงเป็น", 120), ("บรรทัด NDJSON", 178), ("FloatingChat", 236), ("ตัวละคร", 294)]
    cols = [(206, "tool"), (404, "tool_result"), (602, "text"), (800, "done")]
    allk = tuple(range(1, 5))
    for name, y in rows:
        d.text(16, y + 28, name, "ftB", s=allk)
    for k, (x, kind) in enumerate(cols, 1):
        d.step_badge(x + 14, 30, k)
        d.text(x + 32, 35, f"frame “{kind}”", "fh", s=(k,))
    cells = [
        ["เลือก tool\nget_free_slots", "ToolUseBlock → tool", '{"type":"tool",…}', f"ขึ้น “{NARRATION['mcp__planner__get_free_slots']}”",
         "— ยังไม่พูด"],
        ["รอผลจาก tool\n(รันในโปรเซสเรา)", "ToolResultBlock → ok", '{"type":"tool_result"}', "ข้อความชั่วคราวยังอยู่", "—"],
        ["ตอบ + แท็กท้าย\n<mood>proud:point</mood>", "parse_mood → text", '{"type":"text",…}', "แทนที่ด้วยคำตอบจริง",
         "push(proud · point)\n→ พูด + ชี้"],
        ["จบ turn\n(ResultMessage)", "→ done", '{"type":"done",…}', "หยุด “…thinking”", "—"],
    ]
    for k, ((x, _), col) in enumerate(zip(cols, cells), 1):
        for (_, y), t in zip(rows, col):
            mono = t.startswith("{")
            cls = "fcA" if (k == 3 and y >= 236) or mono else ("fcW" if t.startswith("—") else "fc")
            d.tbox(x, y, 186, 48, t, cls=cls, tcls="fmono" if mono else "ft", s=(k,))
    d.line([(206, 368), (986, 368)], cls="fld", head=True, s=allk)
    d.text(206, 392, "เวลา → (frame มาทีละบรรทัด ไม่ใช่ทีละ token)", "fsm", s=allk)
    return d


def fig_voice():
    """ข้อความ → แคช/Kokoro → WAV → ซองปาก → VRM"""
    nodes = [
        chip("v_text", 20, 30, "ข้อความ 1 บรรทัด", "จากคิวการแสดง", w=170, topic="char", steps=(1, 2)),
        chip("v_hit", 230, 30, "มีใน .tts_cache?", "sha256(เสียง|ความเร็ว|ข้อความ)", w=220, topic="char", steps=(1, 2)),
        chip("v_read", 500, 30, "อ่าน WAV จากดิสก์", f"~{HIT_S} วินาที", w=180, topic="infra", steps=(1,)),
        chip("v_lock", 230, 140, "รอล็อกของ TTS", "ทีละประโยค · ไม่ใช่ล็อก GPU", w=220, topic="char", steps=(2,)),
        chip("v_synth", 500, 140, "Kokoro /synth", f"CPU · RTF ~{RTF:.2f} · ≤ {TTS_TIMEOUT:.0f} s", w=180, topic="char", steps=(2,)),
        chip("v_wav", 740, 85, "WAV 24 kHz mono", ".part → rename → เข้าแคช", w=230, topic="char", steps=(1, 2, 3)),
        chip("v_dec", 740, 270, "decodeAudioData", "Web Audio ในเบราว์เซอร์", w=230, topic="char", steps=(3,)),
        chip("v_env", 500, 270, "ซองปาก 3 ย่าน", f"<{CUT_LOW} · {CUT_LOW}–{CUT_MID} · >{CUT_MID} Hz", w=200, topic="char", steps=(3, 4)),
        chip("v_smooth", 260, 270, "เปิดเร็ว ปิดช้า", f"attack {ATTACK} · release {RELEASE}", w=190, topic="char", steps=(4,)),
        chip("v_vrm", 20, 270, "ปาก VRM", f"ou · aa · ih · {FPS} fps", w=180, topic="char", steps=(4,)),
    ]
    edges = [
        E("v1", "v_text", "v_hit", steps=(1, 2)),
        E("v2", "v_hit", "v_read", "มี", steps=(1,)),
        E("v3", "v_hit", "v_lock", "ไม่มี", lside="r", steps=(2,)),
        E("v4", "v_lock", "v_synth", steps=(2,)),
        E("v5", "v_read", "v_wav", sp="e@0.5", dp="w@0.3", steps=(1,)),
        E("v6", "v_synth", "v_wav", sp="e@0.5", dp="w@0.8", steps=(2,)),
        E("v7", "v_wav", "v_dec", "ส่งกลับเบราว์เซอร์", kind="data", steps=(3,)),
        E("v8", "v_dec", "v_env", kind="data", steps=(3,)),
        E("v9", "v_env", "v_smooth", kind="data", steps=(4,)),
        E("v10", "v_smooth", "v_vrm", f"นำ {LOOKAHEAD_MS} ms", kind="data", steps=(4,)),
    ]
    return Graph(1000, 350, nodes, edges, aria="ทางของเสียงจากข้อความถึงปากของตัวละคร")


_FATE_LEAF = {"ทิ้งตั้งแต่ตอนสกัด": "m_drop", "ไม่ปักหมุด": "m_skip", "ปักหมุด · ไม่ลงปฏิทิน": "m_pin",
              "ปักหมุด + นัดทั้งวัน": "m_allday", "ปักหมุด + นัด 1 ชั่วโมง": "m_hour"}
_LEAF_PATH = {"m_drop": (["m_start", "m_q1"], ["a0", "a1"]),
              "m_skip": (["m_start", "m_q1", "m_q2"], ["a0", "a2", "a3"]),
              "m_pin": (["m_start", "m_q1", "m_q2", "m_q3"], ["a0", "a2", "a4", "a5"]),
              "m_allday": (["m_start", "m_q1", "m_q2", "m_q3", "m_q4"], ["a0", "a2", "a4", "a6", "a7"]),
              "m_hour": (["m_start", "m_q1", "m_q2", "m_q3", "m_q4"], ["a0", "a2", "a4", "a6", "a8"])}


def fig_mailpin():
    """ต้นไม้ตัดสินใจ: รายการหนึ่งจาก Ollama จะจบที่ไหน · ขั้น = ตัวอย่าง 5 รายการ (ผลคำนวณด้วยกฎจริงใน facts.py)"""
    steps_of: dict[str, set] = {}
    for k, (name, _) in enumerate(MAIL_EXAMPLES, 1):
        leaf = _FATE_LEAF[MAIL_FATES[name]]
        ns, es = _LEAF_PATH[leaf]
        for i in ns + es + [leaf]:
            steps_of.setdefault(i, set()).add(k)
    st = lambda i: tuple(sorted(steps_of.get(i, ())))  # noqa: E731
    nodes = [
        chip("m_start", 360, 16, "รายการหนึ่งจาก Ollama", "{type, title, datetime, note}", w=300, topic="mail", steps=st("m_start")),
        chip("m_q1", 360, 110, "ไม่มี title หรือ other ไร้วันที่?", "ตัวกรองใน _extract_one", w=300, topic="mail", steps=st("m_q1")),
        chip("m_drop", 760, 110, "ทิ้งตั้งแต่ตอนสกัด", "โปรโมชัน · จดหมายข่าว", w=210, topic="safe", steps=st("m_drop")),
        chip("m_q2", 360, 204, "มีวันที่ หรือเป็นนัด/เส้นตาย?", f"_qualifies: {' · '.join(AUTO_PIN_TYPES)}", w=300, topic="mail",
             steps=st("m_q2")),
        chip("m_skip", 760, 204, "ไม่ปักหมุด", "เห็นแค่ในผลสแกน", w=210, topic="infra", steps=st("m_skip")),
        chip("m_q3", 360, 298, "มีวันที่ไหม?", "datetime ไม่ว่าง", w=300, topic="mail", steps=st("m_q3")),
        chip("m_pin", 40, 298, "ปักหมุด · ไม่ลงปฏิทิน", "หน้า Projects · From email", w=250, topic="day", steps=st("m_pin")),
        chip("m_q4", 360, 392, "วันที่ล้วน (≤ 10 ตัวอักษร)?", "เช่น 2026-11-27", w=300, topic="mail", steps=st("m_q4")),
        chip("m_allday", 170, 490, "ปักหมุด + นัดทั้งวัน", "create_all_day_event", w=250, topic="day", steps=st("m_allday")),
        chip("m_hour", 600, 490, "ปักหมุด + นัด 1 ชั่วโมง", "create_event(start, +1h)", w=250, topic="day", steps=st("m_hour")),
    ]
    Y, No = "ใช่", "ไม่"
    edges = [
        E("a0", "m_start", "m_q1", steps=st("a0")),
        E("a1", "m_q1", "m_drop", Y, steps=st("a1")),
        E("a2", "m_q1", "m_q2", No, lside="r", steps=st("a2")),
        E("a3", "m_q2", "m_skip", No, steps=st("a3")),
        E("a4", "m_q2", "m_q3", Y, lside="r", steps=st("a4")),
        E("a5", "m_q3", "m_pin", No, steps=st("a5")),
        E("a6", "m_q3", "m_q4", Y, lside="r", steps=st("a6")),
        E("a7", "m_q4", "m_allday", Y, sp="s@0.25", dp="n@0.5", lside="l", lseg=0, steps=st("a7")),
        E("a8", "m_q4", "m_hour", No, sp="s@0.75", dp="n@0.5", lside="r", lseg=0, steps=st("a8")),
    ]
    return Graph(1000, 560, nodes, edges, aria="รายการนัดจากอีเมลหนึ่งรายการจะถูกทิ้ง ปักหมุด หรือสร้างนัด")


def fig_plan():
    """3 วันของภาพจำลอง: ช่วงทำงาน · นัดเดิม · บล็อกที่ plan_blocks() วาง (รันจริงตอน build)"""
    d = Draw(1000, 400, topic="day", aria="planner วางบล็อกงานลงช่องว่างของ 3 วัน")
    x0, px = 150, 60                                 # 09:00 อยู่ที่ x0 · 1 ชม. = px
    X = lambda h: x0 + (h - PLAN["work_start"]) * px  # noqa: E731
    days = ["จันทร์ 9 พ.ย.", "อังคาร 10 พ.ย.", "พุธ 11 พ.ย."]
    ys = [70, 160, 250]
    allk = tuple(range(1, 7))
    for h in range(PLAN["work_start"], PLAN["work_end"] + 1, 3):
        d.text(X(h), 54, f"{h:02d}:00", "fsm", anchor="middle", s=allk)
        d.line([(X(h), 62), (X(h), 312)], cls="fld", head=False, s=allk)
    dl_h = SIM_DEADLINE.hour + SIM_DEADLINE.minute / 60
    for i, (name, y) in enumerate(zip(days, ys)):
        d.text(16, y + 34, name, "ftB", s=allk)
        end = dl_h if i == 2 else PLAN["work_end"]
        d.rect(X(PLAN["work_start"]), y, X(end) - X(PLAN["work_start"]), 56, cls="fcW", s=(1,))
    for day, a, b, name in SIM_BUSY_EVENTS:
        d.rect(X(a), ys[day] + 6, X(b) - X(a), 44, cls="fcW", s=(2, 3, 4, 5))
        d.tbox(X(a), ys[day] + 6, X(b) - X(a), 44, name, cls="fcN", tcls="fsm", s=(2, 3, 4, 5))
    totals = {}
    for s_, e_ in SIM_BLOCKS:
        day = (s_.date() - SIM_NOW.date()).days
        hh = s_.hour + s_.minute / 60
        totals[day] = totals.get(day, 0) + (e_ - s_).total_seconds() / 3600
        d.tbox(X(hh), ys[day] + 6, PLAN["block_hours"] * px, 44, f"Work {PLAN['block_hours']} ชม.", cls="fcB", tcls="fsmW",
               s=(3 + day, 6))
    for day, tot in totals.items():
        d.text(X(PLAN["work_end"]) + 14, ys[day] + 34, f"{tot:g} ชม.", "fa", s=(3 + day, 6))
    d.line([(X(dl_h), ys[2] - 6), (X(dl_h), ys[2] + 62)], cls="flD", head=False, s=(5, 6))
    d.text(X(dl_h) + 6, ys[2] + 76, f"deadline {SIM_DEADLINE:%H:%M}", "fsm", s=(5, 6))
    d.text(16, 372, f"ต้องการ {SIM_HOURS:g} ชม. → วางได้ {SIM['hours_scheduled']:g} ชม. ({len(SIM_BLOCKS)} บล็อก) · "
                    f"วางไม่ได้ {SIM['hours_unscheduled']:g} ชม. — planner บอกตรงๆ ไม่ยัดเกินเพดาน", "fh", s=(6,))
    return d


def fig_cache():
    """serve(): ทางตัดสินใจของ snapshot · ขั้น = เหตุการณ์ 4 แบบ"""
    nodes = [
        chip("c_req", 360, 16, "คำขอ เช่น /calendar/range", "cache.serve(key, fetcher, ttl)", w=290, topic="infra", steps=(1, 2, 3)),
        chip("c_q1", 360, 110, "refresh=true?", "ปุ่ม Refresh บนหน้าเว็บ", w=290, topic="infra", steps=(1, 2, 3)),
        chip("c_q2", 360, 204, "มี snapshot ของ key นี้?", "ตาราง snapshots ใน SQLite", w=290, topic="infra", steps=(1, 2, 3, 4)),
        chip("c_q3", 360, 298, "อายุ ≤ TTL?", f"ปฏิทิน {mins(TTL_CAL)} · เมล {mins(TTL_MAIL)} · งาน {mins(TTL_ASSIGN)}", w=290,
             topic="infra", steps=(2, 3)),
        chip("c_fetch", 740, 157, "ดึงสดจาก Google แล้วเก็บ", "stale=false · ต้องรอ Google", w=240, topic="day", steps=(1, 4)),
        chip("c_fresh", 110, 400, "คืน snapshot ทันที", "stale=false", w=240, topic="day", steps=(2,)),
        chip("c_stale", 560, 400, "คืนของเก่าทันที + refresh เบื้องหลัง", "stale=true · ครั้งหน้าได้ของใหม่", w=330, topic="day",
             steps=(3,)),
        chip("c_write", 30, 157, "เขียนปฏิทิน (ทุกทาง)", "clear_prefix('calendar:')", w=250, topic="safe", steps=(4,)),
    ]
    edges = [
        E("k0", "c_req", "c_q1", steps=(1, 2, 3)),
        E("k1", "c_q1", "c_fetch", "ใช่", sp="e@0.5", dp="n@0.3", steps=()),
        E("k2", "c_q1", "c_q2", "ไม่", lside="r", steps=(1, 2, 3)),
        E("k3", "c_q2", "c_fetch", "ไม่มี", sp="e@0.5", dp="s@0.3", steps=(1, 4)),
        E("k4", "c_q2", "c_q3", "มี", lside="r", steps=(2, 3)),
        E("k5", "c_q3", "c_fresh", "ใช่", sp="s@0.25", dp="n@0.5", lside="l", lseg=0, steps=(2,)),
        E("k6", "c_q3", "c_stale", "ไม่", sp="s@0.75", dp="n@0.5", lside="r", lseg=0, steps=(3,)),
        E("k7", "c_write", "c_q2", "ลบ snapshot", kind="sig", sp="s@0.5", dp="w@0.5", steps=(4,)),
    ]
    return Graph(1000, 470, nodes, edges, aria="cache.serve ตัดสินใจคืน snapshot หรือดึงสด")


def _table(head, rows):
    th = "".join(f"<th>{h}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="dscroll"><table class="dtab"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def ttl_html():
    rows = [[f"<code>{esc(k)}</code>", esc(who), mins(t), "SQLite · รอดรีสตาร์ต"] for k, who, t in CACHE_ROWS]
    rows += [[f"<code>{esc(k)}</code>", esc(what), mins(t), "หน่วยความจำ · หายเมื่อรีสตาร์ต"] for k, what, t in MEM_ROWS]
    return _table(["แคช", "ใช้โดย", "อายุ", "อยู่ที่"], rows)


# ทุกทางที่ไปถึง Google Calendar ได้ (ช่องสุดท้าย = ไฟล์ที่เรียกฟังก์ชันเขียนจริง ตรวจกับ CAL_WRITERS)
WRITE_PATHS = [
    ("แชท: create / update / delete_event", "คุณพิมพ์สั่ง", "ไม่มี — รันทันที", "สั่งแชทแก้ หรือแก้ในปฏิทินเอง", "ไม่", "agent/tools.py"),
    ("Projects: Add to calendar", "คุณกด", "มี — POST /plan ก่อน", "ลบในปฏิทินเอง", "ไม่", "routers/projects.py"),
    ("Mail: 📌 ปักหมุดเอง", "คุณกด", "ไม่มี (ไม่มีวันที่ → อ่านลึกหาก่อน)", "ถอนหมุด = ลบนัด", "ไม่", "services/pins.py"),
    ("Mail: Scan (unread) → ปักหมุดเอง", "คุณกด Scan", "ไม่มี", "ถอนหมุด = ลบนัด", "ไม่", "services/pins.py"),
    (f"สแกนรายวัน {T_MAIL} → ปักหมุดเอง", "**ไม่มีใครกด**", "ไม่มี", "ถอนหมุด = ลบนัด", "mail.autopinned", "services/pins.py"),
    ("POST /calendar/events", "ไม่มีหน้าไหนเรียก (เหลือจาก M0)", "ไม่มี", "—", "ไม่", "routers/calendar.py"),
]
assert {w[-1] for w in WRITE_PATHS} == {f for f, _ in CAL_WRITERS}


def writes_html():
    return _table(["ทาง", "ใครเริ่ม", "ได้ดูก่อน?", "ย้อนอย่างไร", "ประกาศ?", "ไฟล์ที่เขียน"],
                  [[esc(a), b.replace("**", ""), esc(c), esc(d_), esc(e_), f"<code>{esc(f)}</code>"]
                   for a, b, c, d_, e_, f in WRITE_PATHS])


_TABLE_USE = {
    "projects": ("/projects (CRUD · discover)", "planner · tool list_projects · nudges"),
    "tasks": ("— (ยังไม่มี)", "— (ยังไม่มี)"),
    "daily_briefs": ("brief_store", "/brief/today"),
    "ignored_assignments": ("/academic/ignore", "หน้า Academic · nudges · tool list_todo"),
    "pinned_emails": ("pins.py (หมุดเอง · ปักเอง · ถอน)", "/mail/pins → หน้า Projects"),
    "daily_mail_scans": ("mail_store", "/mail/scan/today"),
    "snapshots": ("cache.py", "cache.py (/calendar/range · /mail/unread·today · /academic/assignments)"),
    "agent_events": ("events.emit (scheduler · mail_store · /events/test)", "/events/pending · /events/stream"),
}
assert set(_TABLE_USE) == set(TABLES)


def db_html():
    return _table(["ตาราง", "class", "คอลัมน์", "ใครเขียน", "ใครอ่าน"],
                  [[f"<code>{t}</code>", TABLE_CLASS[t], " · ".join(TABLES[t]), esc(_TABLE_USE[t][0]), esc(_TABLE_USE[t][1])]
                   for t in TABLES])


# ข้อสังเกตจากการอ่านโค้ด — แต่ละข้อมีเงื่อนไขจาก facts (แก้แล้ว ข้อนั้นจะหายจากหน้าเอง)
FINDINGS = [f for f in [
    (ACK_ON_RECEIVE, "delivered ตั้งตอนรับ ไม่ใช่ตอนพูดจบ", "useAgentEvents.ts",
     "ปิดแท็บตอนคิวยังเหลือ → บรรทัดที่เหลือไม่ถูกเล่าอีก (models.py เขียนว่าตั้งเมื่อ “ส่งถึงคน” แล้ว)",
     "ยืนยันใน runner ของคิวหลังพูดจบ โดยใช้ eventId ที่พกมาอยู่แล้ว"),
    (bool(UNUSED_KINDS), f"มีสีหน้ารอไว้ แต่ไม่มีใคร emit: {', '.join(UNUSED_KINDS)}", "services/events.py · _KIND_MOOD",
     "ตัวละครยังไม่เตือนเส้นตายเอง และไม่รายงานแชทที่พัง", "emit deadline.warning จาก nudges/scheduler · chat.error ใน /chat/stream"),
    (bool(IMPLICIT_DEPS), f"import ตรงแต่ไม่ได้ประกาศ: {', '.join(IMPLICIT_DEPS)}", "backend/pyproject.toml",
     "มาทางอ้อมผ่าน claude-agent-sdk → mcp · ถ้าวันหนึ่ง mcp เลิกพึ่ง backend จะพังตอน import", f"uv add {' '.join(IMPLICIT_DEPS)}"),
    (ENV_EXAMPLE_IGNORED and not ENV_EXAMPLE_TRACKED, ".env.example ถูก git-ignore", ".gitignore (หมวด secrets)",
     "README บอกให้ cp .env.example .env แต่ clone ใหม่ไม่มีไฟล์นี้ · ยังไม่มีคีย์ OLLAMA_* / TTS_*",
     "เอาออกจาก .gitignore แล้วเติมคีย์ที่ config.py รู้จัก"),
    (True, "tool ของแชทรันทันที (bypassPermissions)", "agent/secretary.py",
     "ยืนยันก่อนลบอยู่ใน prompt เท่านั้น และแชทไม่มีความจำ — “yes” ใน turn ถัดไปไม่รู้ว่ายืนยันอะไร",
     "ด่านยืนยันในโค้ดสำหรับ delete_event (แนวเดียวกับที่ M7 วางไว้สำหรับส่งเมล)"),
    (CHAT_STATELESS, "แชทไม่มีความจำข้ามข้อความ", "agent/secretary.py · ask_stream",
     "คำสั่งต่อเนื่องหลายข้อความใช้ไม่ได้ · ต้องสั่งให้จบในข้อความเดียว", "Stage 7: resume ด้วย session_id ที่ frame done ส่งมาอยู่แล้ว"),
    (TASKS_UNUSED, "ตาราง tasks ไม่มีใครใช้", "models.py · class Task", "ชั่วโมงที่เหลือมาจาก projects.estimated_hours ช่องเดียว",
     "ใช้แตกงานย่อย หรือเอาออกถ้าไม่ต้องการ (ระวัง: create_all ไม่ลบตาราง)"),
    (True, "แคช Classroom สองชั้นอายุต่างกัน", "classroom.py · routers/academic.py",
     f"หน้า Academic ใช้ snapshot {mins(TTL_ASSIGN)} · nudges/สรุปเช้าใช้แคชในหน่วยความจำ {mins(MEM_CLASS)} — อาจเห็นไม่ตรงกันชั่วครู่",
     "ยอมรับได้ หรือให้ nudges อ่าน snapshot เดียวกัน"),
    (True, "events ทำงานได้ใน process เดียวเท่านั้น", "services/events.py",
     "รัน uvicorn --workers 2 แล้วแท็บจะพลาดเหตุการณ์ของอีก worker", "คงไว้ process เดียว (แอปผู้ใช้คนเดียว) — run.sh ทำแบบนี้อยู่แล้ว"),
    (SENDCHAT_UNUSED, "โค้ดค้างจากรุ่นก่อน", "api.ts sendChat · /calendar/upcoming · POST /calendar/events",
     "ไม่มีหน้าไหนเรียก แต่ POST /calendar/events ยังเขียนปฏิทินได้", "ลบทิ้ง หรือเก็บไว้เป็นเครื่องมือ debug โดยรู้ตัว"),
] if f[0]]


def findings_html():
    return _table(["ข้อสังเกต", "อยู่ที่", "ผลที่ตามมา", "ทางที่เป็นไปได้"],
                  [[f"<b>{esc(a)}</b>", f"<code>{esc(b)}</code>", esc(c), esc(d_)] for _, a, b, c, d_ in FINDINGS])


GROUPS = [
    dict(id="g-talk", short="คุย", title="คุยกับเลขา", sub="แชท · เสียง · ตัวละคร", chapters=[
        dict(id="ch-turn", num="1", nav="หนึ่ง turn", title="แชทหนึ่งข้อความเดินทางอย่างไร", topic="chat", q=("Q", "M8"),
             thesis="คำตอบไม่ได้มาเป็นก้อนเดียว — มาเป็น frame ทีละบรรทัด แชทจึงบอกได้ว่ากำลังทำอะไร และตัวละครพูดได้ทันทีที่ได้ประโยค",
             figs=[dict(id="f-turn", title="frame 4 ชนิดของหนึ่ง turn (ตัวอย่าง: สั่งวางแผน)", draw=fig_turn,
                        caption="คอลัมน์ = frame ตามลำดับเวลา · แถว = แต่ละชั้นทำอะไรกับ frame นั้น · ช่องสีคือสิ่งที่คุณเห็นหรือได้ยิน",
                        steps=[("tool", "Claude เลือก get_free_slots → แชทขึ้นข้อความชั่วคราวทันที ไม่ต้องรอคำตอบ"),
                               ("tool_result", "tool รันในโปรเซส FastAPI ของเราเอง แล้วผลกลับไปให้ Claude อ่าน"),
                               ("text", "คำตอบจริงมาพร้อมแท็ก mood · parse_mood ตัดแท็กออก แล้วแชทกับตัวละครได้ข้อความเดียวกัน"),
                               ("done", "ResultMessage ปิด turn · session_id ถูกส่งมาแต่ยังไม่มีใครใช้ (แชทจึงไม่มีความจำ)")],
                        story=dict(
                            problem="POST /chat เดิมรอจนจบแล้วคืนข้อความก้อนเดียว — ระหว่าง tool ทำงานหลายวินาที ผู้ใช้เห็นแค่ “…thinking” "
                                    "และตัวละครไม่รู้ว่าจะทำท่าคิดตอนไหน",
                            think="ถ้าส่งต่อ “จังหวะ” ที่ Agent SDK มีอยู่แล้ว (เรียก tool · ผลกลับ · ข้อความ · จบ) หน้าเว็บจะตอบสนองได้ทันทีทุกจังหวะ",
                            choose="ask_stream แปลงข้อความของ SDK เป็น frame 5 ชนิด (รวม error) · ส่งแบบ NDJSON บน POST "
                                   "เพราะ EventSource ส่งข้อความไม่ได้และ reconnect เอง",
                            read="อ่านจากซ้ายไปขวาตามเวลา · อ่านจากบนลงล่างคือ frame เดียวกันผ่านแต่ละชั้น",
                            result=f"{len(TOOLS)} tool มีข้อความชั่วคราวครบทุกตัว (build ตรวจว่า TOOL_NARRATION ตรงกับ allowed_tools) · "
                                   "ไม่ใช่ระดับ token เพราะเสียงต้องการประโยคเต็ม",
                            mean="M8 Stage 2 ไม่ได้เปลี่ยน agent — เปลี่ยนแค่วิธีส่งผลออกมา ตัวละครเลยรู้จังหวะของงานโดยไม่ต้องเรียก LLM เพิ่ม"),
                        traps=["frame text มาได้หลายครั้งต่อ turn (ก่อนและหลัง tool) — มีแท็ก mood เฉพาะข้อความสุดท้าย ที่เหลือเป็น neutral/idle",
                               "พังกลางทาง → server ส่ง frame error + done แทน HTTP 500 เพราะ header ถูกส่งไปแล้ว"],
                        onmap=["chat_ui", "r_chat", "ask", "persona", "tools", "stage"])]),
        dict(id="ch-voice", num="2", nav="เสียง", title="จากข้อความเป็นเสียงและปากที่ขยับ", topic="char", q=("M8", "L"),
             thesis="เสียงสังเคราะห์ใน process แยกที่ Python คนละรุ่น แล้วเบราว์เซอร์คำนวณการขยับปากล่วงหน้าทั้งประโยค ไม่ต้องวิเคราะห์สด",
             figs=[dict(id="f-voice", title="ทางของเสียง: ข้อความ → WAV → ปาก", draw=fig_voice,
                        caption="แถวบนอยู่ใน backend และ sidecar · แถวล่างอยู่ในเบราว์เซอร์ (อ่านจากขวาไปซ้าย) · กดทีละขั้นเพื่อแยกทางแคชเจอกับไม่เจอ",
                        steps=[("แคชเจอ", f"ประโยคที่เคยพูดแล้วอ่านจากดิสก์ ~{HIT_S} วินาที ไม่ต้องรอล็อก"),
                               ("แคชไม่เจอ", f"รอล็อกของ TTS แล้วให้ Kokoro สังเคราะห์บน CPU (เคยวัดได้ ~{MISS_S:g} วินาที) · เขียน .part แล้ว rename"),
                               ("ซองปาก", f"decode แล้วแยก 3 ย่านความถี่ → RMS ทุก 1/{FPS} วินาที"),
                               ("ปากขยับ", f"เปิดเร็วปิดช้า แล้วอ่านเฟรมล่วงหน้า {LOOKAHEAD} เฟรม (~{LOOKAHEAD_MS} ms) ใส่ปาก VRM 3 รูป")],
                        story=dict(
                            problem=f"kokoro-onnx ต้องการ Python ต่ำกว่า 3.14 แต่ backend ใช้ 3.14 · และปากที่ขยับตามความดังอย่างเดียวดูเหมือนปลา",
                            think="แยก TTS ไปเป็น process ของตัวเองแบบเดียวกับ Ollama · ฝั่งปากให้ดูความถี่ ไม่ใช่แค่ความดัง",
                            choose=f"sidecar FastAPI บน Python {SIDECAR_PY} · แคช WAV ตาม hash · ซองปาก 3 ย่าน (ou/aa/ih) คำนวณล่วงหน้าทั้งประโยค "
                                   "แทน AnalyserNode สด เพราะมองล่วงหน้าได้และไม่กระตุก",
                            read="กล่องในแถวบนคือ backend · แถวล่างคือเบราว์เซอร์ · ลูกศรหนาคือข้อมูลเสียงที่ไหล",
                            result=f"RTF ~{RTF:.2f} บนเครื่องนี้ · ประโยคซ้ำ ~{MISS_S:g} s → ~{HIT_S} s · ตอน build มี WAV ในแคช {WAV_CACHED} ไฟล์",
                            mean="backend ไม่ต้องรู้จัก kokoro เลย และถ้า sidecar ล่ม ตัวละครแค่เงียบ — ฟองคำพูดยังขึ้นตามปกติ"),
                        traps=["ล็อกของ TTS แยกจากล็อก GPU ของ Ollama — ล็อกเดียวกันจะทำให้สแกนเมลบล็อกเสียงพูด",
                               "เบราว์เซอร์ไม่ให้เล่นเสียงจนกว่าจะคลิก — บรรทัดแรกของเช้าจะรอจนคุณแตะหน้าจอ"],
                        onmap=["stage", "voice", "r_tts", "tts_svc", "sidecar", "vrm"])]),
    ]),
    dict(id="g-auto", short="ทำเอง", title="งานที่เลขาทำเอง", sub="อีเมล → นัด · หาช่องว่าง", chapters=[
        dict(id="ch-mail", num="3", nav="หมุดเมล", title="อีเมลหนึ่งฉบับกลายเป็นนัดได้อย่างไร", topic="mail", q=("W", "L"),
             thesis="ทุกอย่างที่รอดตัวกรองตอนสกัดถูกปักหมุด และถ้ามีวันที่ก็กลายเป็นนัดจริงใน Google Calendar — โดยไม่มีหน้าจอให้ยืนยัน",
             figs=[dict(id="f-mailpin", title="ชะตาของรายการหนึ่งที่ Ollama ตอบมา (5 ตัวอย่าง)", draw=fig_mailpin,
                        caption="เริ่มจากบนสุด ตอบใช่/ไม่ลงไปจนถึงผล · ตัวอย่างเป็นรายการสมมติ แต่ผลคำนวณด้วยกฎจริงจาก mail_extract.py และ pins.py ตอน build",
                        steps=[(n, f"{it['type']} · datetime={it['datetime'] or 'ไม่มี'} → **{MAIL_FATES[n]}**") for n, it in MAIL_EXAMPLES],
                        story=dict(
                            problem="อีเมลมาเยอะ ส่วนใหญ่ไม่เกี่ยวกับตาราง แต่ที่เกี่ยว (เส้นตาย · ประชุม) หลุดง่ายมาก",
                            think="ให้โมเดลในเครื่องเสนอรายการ แล้วใช้กฎตายตัวตัดสินว่าจะทำอะไรต่อ — กฎตรวจได้ โมเดลตรวจไม่ได้",
                            choose="ตัดขยะตั้งแต่ตอนสกัด · เกณฑ์ปักหมุดตั้งใจหลวม (พลาดเส้นตายแย่กว่าปักเกิน) · มีวันที่จึงลงปฏิทิน · เก็บ event id ไว้ให้ถอนได้",
                            read="กล่องสีอีเมลคือคำถาม · สีม่วงคือผลที่ไปถึงหน้า Projects/ปฏิทิน · แดงคือถูกทิ้ง",
                            result=" · ".join(f"{n}: {MAIL_FATES[n]}" for n, _ in MAIL_EXAMPLES[:3]) + " …",
                            mean=f"การสแกน {T_MAIL} จึงเป็นการเขียนปฏิทินโดยไม่มีใครกด — M8 ให้มันประกาศเสมอ และทางย้อนคือถอนหมุด"),
                        traps=["รายการที่รอดตัวกรองเข้าเกณฑ์ปักหมุดเสมอ — ด่านปักหมุดคัดออกได้เฉพาะ type ที่อยู่นอกรายการของ prompt",
                               "หนึ่งอีเมลได้หนึ่งหมุด: รายการที่มีวันที่ได้ก่อน ปฏิทินจึงได้วันจริง",
                               "นัดทั้งวันจากหมุดไม่บล็อกเวลาของ planner"],
                        onmap=["mail_store", "extract", "llm", "pins", "b_qualify", "cal_svc"])]),
        dict(id="ch-plan", num="4", nav="วางแผน", title="planner หาช่องว่างและวางบล็อกอย่างไร", topic="day", q=("L", "W"),
             thesis="แกนวางแผนไม่ใช้ AI: หาช่องว่างจริง วางบล็อกเท่ากัน ไม่เกินเพดานต่อวัน — แชทเลือกจากเมนูเดียวกันนี้",
             figs=[dict(id="f-plan", title="งาน 12 ชั่วโมง ต้องเสร็จพุธ 18:00 (ภาพจำลอง)", draw=fig_plan,
                        caption="ภาพจำลอง — นัดสมมติ แต่บล็อกคำนวณด้วย plan_blocks() ตัวจริงจาก planner.py ตอน build · แกนนอนคือเวลาในวัน",
                        steps=[("ช่วงทำงาน", f"{PLAN['work_start']:02d}:00–{PLAN['work_end']}:00 ทุกวัน · วันสุดท้ายถูกตัดที่ deadline"),
                               ("นัดเดิม", "นัดที่มีเวลาคือช่วงไม่ว่าง (นัดทั้งวันไม่นับ)"),
                               ("จันทร์", f"ช่องว่างก่อนบ่ายยาวแค่ 1 ชม. ใส่บล็อก {PLAN['block_hours']} ชม. ไม่ได้ → บล็อกแรกเริ่มหลังประชุม"),
                               ("อังคาร", f"เต็มเพดาน {PLAN['max_hours_per_day']:g} ชม. แล้วหยุด แม้ยังมีที่ว่างตอนเย็น"),
                               ("พุธ", f"วางได้ถึง deadline {SIM_DEADLINE:%H:%M} เท่านั้น"),
                               ("ผล", f"วางได้ {SIM['hours_scheduled']:g} · ไม่ได้ {SIM['hours_unscheduled']:g} ชม.")],
                        story=dict(
                            problem="มีงานค้างหลายชั่วโมงก่อน deadline แต่ปฏิทินมีนัดกระจัดกระจาย จะวางเวลาทำงานตรงไหน",
                            think="ไม่ต้องให้ AI คิดเรื่องนี้ — เป็นปัญหาช่วงเวลาที่คำนวณตรงๆ ได้ ส่วน AI ไว้ตัดสินเงื่อนไขภาษาคน",
                            choose="plan_blocks: วันละช่วงทำงาน · บล็อกเท่ากัน · เพดานต่อวันให้งานกระจาย · ไม่ทับนัดเดิม · บอกส่วนที่วางไม่ได้ตรงๆ",
                            read="แถว = วัน · แกนนอน = เวลา · กล่องเส้นประ = นัดเดิม · กล่องทึบ = บล็อกที่วาง · ตัวเลขขวาคือชั่วโมงต่อวัน",
                            result=f"{len(SIM_BLOCKS)} บล็อก = {SIM['hours_scheduled']:g} ชม. · วางไม่ได้ {SIM['hours_unscheduled']:g} ชม. · "
                                   f"get_free_slots ช่วงเดียวกันจะยื่นเมนู {len(SIM_SLOTS)} ช่องให้ agent",
                            mean="ปุ่ม Plan now ใช้ผลนี้ตรงๆ (ดูก่อนจอง) · แชทใช้ free_slots เป็นเมนูแล้วให้ Claude เลือกตามเงื่อนไข"),
                        traps=["เพดานเป็นต่อโปรเจกต์ต่อวัน — สองโปรเจกต์อาจรวมกันเกิน 3 ชม./วัน",
                               "บล็อกเริ่มที่ต้นช่องว่างเสมอ ไม่เว้นช่วงพักหลังนัด"],
                        onmap=["planner", "cal_svc", "r_proj", "tools", "b_preview"])]),
    ]),
    dict(id="g-data", short="ข้อมูล", title="ข้อมูล · ความเร็ว · ความปลอดภัย", sub="แคช · ใครเขียนปฏิทิน · secretary.db", chapters=[
        dict(id="ch-cache", num="5", nav="แคช", title="ทำไมหน้าเว็บเปิดเร็ว: snapshot + ล้างเมื่อเขียน", topic="infra",
             thesis="เปิดหน้าไม่รอ Google: คืนของที่เก็บไว้ทันที แล้วค่อยเติมของใหม่เบื้องหลัง — และการเขียนปฏิทินทุกทางล้าง snapshot ให้เอง",
             figs=[dict(id="f-cache", title="cache.serve() ตัดสินใจอย่างไร", draw=fig_cache,
                        caption="เริ่มจากบนสุด · กดทีละขั้นเพื่อดู 4 สถานการณ์ · ทาง “ใช่” ของ refresh ไม่มีขั้นของตัวเอง (คือปุ่ม Refresh)",
                        steps=[("เปิดครั้งแรก", "ยังไม่มี snapshot → ดึงสดแล้วเก็บ (ช้าครั้งเดียว)"),
                               ("เปิดซ้ำภายใน TTL", "คืนจาก SQLite ทันที ไม่แตะ Google"),
                               ("เปิดหลัง TTL", "คืนของเก่าทันที + ตั้ง refresh เบื้องหลัง → ครั้งหน้าได้ของใหม่"),
                               ("หลังแชทสร้างนัด", "calendar.py ล้าง calendar:* → ครั้งหน้าดึงสด เห็นนัดใหม่ทันที")],
                        story=dict(
                            problem="Classroom ใช้ ~2 call ต่อวิชา · Gmail ใช้ 1 list + 1 get ต่อฉบับ — เปิดหน้าทีละหลายวินาที",
                            think="ผู้ใช้อยากกวาดตาดูเร็วๆ มากกว่าความสดระดับวินาที — ยอมให้เก่าได้นิดหน่อยถ้าบอกตรงๆ ว่าเก่าแค่ไหน",
                            choose="stale-while-revalidate บน SQLite (รอดรีสตาร์ต) · ซอง {data, fetched_at, stale} · ล้างตระกูล key เมื่อเขียน",
                            read="คำถามสามข้อเรียงจากบนลงล่าง · กล่องสีม่วงคือสิ่งที่หน้าเว็บได้กลับไป · กล่องแดงคือการเขียนที่ทำให้ snapshot หาย",
                            result=f"TTL: ปฏิทิน {mins(TTL_CAL)} · เมล {mins(TTL_MAIL)} · งาน {mins(TTL_ASSIGN)} · การค้นเมลไม่แคช",
                            mean="หน้า Home เปิดทันทีแม้ Google ช้า และนัดที่แชทสร้างขึ้นทันทีเพราะการล้างแคช ไม่ใช่เพราะ TTL สั้น"),
                        traps=["นัดที่แก้จากมือถือโดยตรงจะเห็นหลัง TTL เท่านั้น — การล้างแคชเกิดเฉพาะการเขียนผ่าน calendar.py"],
                        onmap=["cache", "r_cal", "cal_svc", "r_mail", "r_acad"]),
                   dict(id="f-ttl", title="แคชทั้งหมดในแอป", html=ttl_html,
                        caption="สองชั้น: snapshot ใน SQLite (บอกอายุบนหน้าเว็บได้) และแคชในหน่วยความจำของ service",
                        onmap=["cache", "gmail", "classroom", "nudges"])]),
        dict(id="ch-writes", num="6", nav="เขียนปฏิทิน", title="ใครเขียน Google Calendar ได้บ้าง", topic="safe", q=("W",),
             thesis=f"มี {len(WRITE_PATHS)} ทางที่ไปถึงปฏิทิน มีทางเดียวที่ได้ดูก่อน และมีทางเดียวที่ไม่มีใครกด — ซึ่งเป็นเหตุผลที่ M8 ให้มันประกาศ",
             figs=[dict(id="f-writes", title="ทุกทางที่ไปแก้ Google Calendar ได้", html=writes_html,
                        caption="ช่องสุดท้ายคือไฟล์ที่เรียกฟังก์ชันเขียนของ calendar.py จริง — build ตรวจกับโค้ดว่าครบทุกไฟล์",
                        onmap=["tools", "r_proj", "pins", "mail_store", "r_cal", "cal_svc"])]),
        dict(id="ch-db", num="7", nav="ฐานข้อมูล", title="secretary.db เก็บอะไรบ้าง", topic="infra",
             thesis="นัดอยู่ใน Google เสมอ · SQLite เก็บแค่ “สมอง”: โปรเจกต์ ความจำของวัน หมุด แคช และสิ่งที่ตัวละครต้องเล่า",
             figs=[dict(id="f-db", title=f"{len(TABLES)} ตารางใน secretary.db", html=db_html,
                        caption="รายชื่อตารางและคอลัมน์อ่านจาก models.py ตอน build · create_all เพิ่มตารางได้แต่ไม่แก้ตารางเดิม (ไม่มี Alembic)",
                        onmap=["t_proj", "t_brief", "t_ignored", "t_pins", "t_events", "cache"])]),
    ]),
    dict(id="g-next", short="ก่อนทำต่อ", title="ข้อสังเกตก่อนทำ Stage 6", sub="จากการอ่านโค้ดระหว่างทำแผนที่", chapters=[
        dict(id="ch-findings", num="8", nav="ข้อสังเกต", title="สิ่งที่ควรรู้ก่อนแก้ต่อ", topic="safe",
             thesis="ไม่มีข้อไหนทำให้แอปพังตอนนี้ แต่แต่ละข้อจะกลายเป็นบั๊กที่หาสาเหตุยากถ้าไม่รู้ล่วงหน้า",
             figs=[dict(id="f-findings", title=f"ข้อสังเกต {len(FINDINGS)} ข้อ", html=findings_html,
                        caption="แต่ละข้อมีเงื่อนไขที่ตรวจจากโค้ดตอน build — แก้แล้ว build ใหม่ ข้อนั้นจะหายจากตารางเอง",
                        onmap=["hook", "events_svc", "oauth", "tools", "ask", "t_proj"])]),
    ]),
]

for _f in FOCUS:   # ตัวเลขบนการ์ดกรอง คำนวณจาก facts
    _f["points"] = {"W": f"{len(WRITE_PATHS)} ทาง · 1 ทางไม่มีใครกด", "Q": f"{len(CLAUDE_CALLERS)} จุดเท่านั้น", "L": "ไม่ใช้ token",
                    "M8": f"แก้ {DIRTY_MODIFIED} · ใหม่ {DIRTY_NEW} ไฟล์"}[_f["id"]]

# ชื่อในโค้ดยาวๆ (เช่น mail_store.get_or_create_today(force=True)) ห้ามดันหน้าให้กว้างเกินจอมือถือ
EXTRA_CSS = ("code { overflow-wrap: anywhere; word-break: break-word; }\n"
             ".dtab code { overflow-wrap: normal; word-break: normal; white-space: nowrap; }")   # ตารางเลื่อนข้างในกรอบเองอยู่แล้ว
