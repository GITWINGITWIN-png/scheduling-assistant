"""spec ของ "แผนที่ผู้ช่วย AI โอเพนซอร์ส" — 15 repo ต้นแบบ วางเทียบกับ my_secretary บนภาพเดียว

แกนแนวนอน (ฟีเจอร์ของโปรเจกต์แนวนี้):
    ① ตัวละคร · เสียง  ② ช่องทาง · แจ้งเตือน  ③ แกน agent  ④ งานเชิงรุก  ⑤ อีเมล  ⑥ วางแผนเวลา
    เรียงให้ของที่ต่อกันอยู่ติดกัน: ช่องทางป้อนแกน agent · งานเชิงรุกปลุกทั้งแกน agent และอีเมล
แกนแนวตั้ง (ชั้นของระบบ): หน้าบ้าน → ประตูเข้า → ตัวตัดสินใจ → ตัวลงมือ → ฐาน
กล่องหนึ่งกล่อง = วิธีออกแบบของโปรเจกต์หนึ่ง ณ ฟีเจอร์ × ชั้นนั้น · สีกรอบ = กลุ่มโปรเจกต์ · ป้ายมุม = ชื่อโปรเจกต์
ปุ่มกรอง (FOCUS) หนึ่งปุ่มต่อหนึ่งโปรเจกต์ → เห็นโครงของตัวนั้นทั้งตัว

ตัวเลขทุกตัวมาจาก facts.py (GitHub snapshot ใน repos.json + โค้ดของ my_secretary) — ไม่มีเลขพิมพ์มือ
สร้างใหม่: python3 docs/reference-map/build.py   (ดึงตัวเลข GitHub ใหม่: python3 docs/reference-map/fetch_repos.py)
"""
from facts import (CONTENT_READ, EMOTIONS, FEATURE_CHANNELS, FETCHED_AT, GESTURES, JOBS, LICENSE, LIP_CUTS,
                   OLLAMA_MODEL, PERMISSION_MODE, PLAN, R, T_BRIEF, T_MAIL, TOOL_SERVERS, TOOLS, TOUR_MOOD, TTS_PORT,
                   pushed, stars)
from repos import REPOS
from submap import Conn, Draw, Edge as E, Graph, Node as N


def gh(k: str, path: str = "", tree: bool = False, ref: str = "HEAD") -> str:
    """ลิงก์ไปไฟล์/โฟลเดอร์ใน repo — เขียนเป็น `github.com/...` แล้ว EXTRA_JS ทำให้กดได้"""
    if not path:
        return f"`github.com/{REPOS[k]}`"
    return f"`github.com/{REPOS[k]}/{'tree' if tree else 'blob'}/{ref}/{path}`"


def lang(k: str) -> str:
    return {"TypeScript": "TS", "JavaScript": "JS", "Jupyter Notebook": "Python · notebook"}.get(
        R[k]["language"], R[k]["language"])


CH_LIST = " · ".join(FEATURE_CHANNELS)

# ================================================================ หน้า
META = dict(
    title="แผนที่ผู้ช่วย AI โอเพนซอร์ส",
    eyebrow=f"{len(REPOS)} repo ต้นแบบ เทียบกับ my_secretary · ข้อมูล GitHub ณ {FETCHED_AT}",
    lead=("แต่ละ **คอลัมน์** คือฟีเจอร์หนึ่งของโปรเจกต์แนวนี้ และแต่ละ **แถบ** คือชั้นของระบบ · กล่องหนึ่งกล่องคือวิธีออกแบบ"
          "ของโปรเจกต์หนึ่งในจุดนั้น — **สีกรอบ** บอกกลุ่ม **ชื่อมุมขวาล่าง** บอกว่าเป็นของใคร · กด **ปุ่มชื่อโปรเจกต์** "
          "เพื่อเหลือเฉพาะกล่องของตัวนั้น (เห็นโครงทั้งตัว) หรือกด “ถัดไป” เพื่อเดินตามอีเมลหนึ่งฉบับผ่านทุกแนวทาง · "
          "ตั้งใจให้เห็นแนวทาง ไม่ลงถึงโค้ดทีละบรรทัด — กล่องทุกกล่องมี “อ่านต่อ” ชี้ไฟล์จริงใน repo"),
    axes=dict(vertical="อยู่ชั้นไหน — หน้าบ้าน → ประตูเข้า → ตัวตัดสินใจ → ตัวลงมือ → ฐาน",
              horizontal="ฟีเจอร์ — ① ตัวละคร · เสียง ② ช่องทาง · แจ้งเตือน ③ แกน agent ④ งานเชิงรุก ⑤ อีเมล ⑥ วางแผนเวลา"),
    map_intro=("อ่านจากบนลงล่างคือจากสิ่งที่คุณเห็นลงไปถึงฐานของระบบ · อ่านซ้ายไปขวาคือฟีเจอร์ · "
               "กล่องสีเขียวอมฟ้าคือ my_secretary ที่วางไว้เทียบในทุกคอลัมน์ · กล่องเส้นประคือสิ่งที่ยังเป็นแผน"),
    tour_title="อีเมลหนึ่งฉบับ: จากกล่องเมลจนตัวละครพูด",
    tour_intro=("ตัวอย่าง: อาจารย์ส่งเมลว่า “ส่ง HW3 ภายในศุกร์นี้” · กด ถัดไป เพื่อดูว่าแต่ละโปรเจกต์ "
                "รู้ตัว → คัดแยก → ร่าง → ลงเวลา → แจ้งคุณ → เล่าให้ฟัง ต่างกันอย่างไร"),
    pairs_intro="แต่ละคู่คือสองวิธีแก้ปัญหาเดียวกัน — อ่านว่าต่างกันตรงไหน แล้วกด “ชี้บนแผนที่”",
    chapters_title="สามคำถามที่โปรเจกต์แนวนี้ต้องตอบ",
    chapters_intro="ภาพเทียบแนวทาง (ไม่ใช่โค้ดทีละบรรทัด) · กด “ทีละขั้น” ได้ทุกภาพ",
    footer=[f"ตัวเลขของ repo (ดาว · push ล่าสุด · archived) จาก GitHub API ณ {FETCHED_AT} — `docs/reference-map/repos.json` · "
            "ดึงใหม่ด้วย `python3 docs/reference-map/fetch_repos.py`",
            f"คำอธิบายแต่ละกล่องสรุปจาก README · เอกสารสถาปัตยกรรม · โครงโฟลเดอร์ของแต่ละ repo (อ่านเมื่อ {CONTENT_READ}) — "
            "โปรเจกต์พวกนี้เปลี่ยนเร็ว เปิดของจริงก่อนลอก",
            "ตัวเลขของ my_secretary อ่านจากโค้ดตอน build (`facts.py`) แล้ว assert · license ที่ GitHub อ่านไม่ออก เปิดไฟล์ LICENSE ดูเอง",
            "ดาวบอกแค่ว่ามีคนใช้มาก ไม่ได้บอกว่าโค้ดดี · สร้างหน้านี้ใหม่ด้วย `python3 docs/reference-map/build.py`"],
)

UI = dict(ch="", exam="ข้อคิดสำหรับ my_secretary", look="โครงสร้าง · ไฟล์ที่ควรเปิด", read="อ่านต่อ",
          focus_hint="ดูทั้งตัว",
          howto_focus="<b>ปุ่มชื่อโปรเจกต์</b> → เหลือเฉพาะกล่องของโปรเจกต์นั้น = เห็นโครงของมันทั้งตัว",
          focus_desc="กล่องของโปรเจกต์นี้ — กดชื่อเพื่ออ่านคำอธิบาย")

TOPICS = [("ours", "my_secretary (ของเรา)", "teal"), ("plat", "แพลตฟอร์มผู้ช่วย", "blue"), ("mail", "agent อีเมล", "amber"),
          ("time", "วางแผนเวลา", "purple"), ("tool", "ชั้นเครื่องมือ", "slate"), ("char", "ตัวละคร · เสียง", "green"),
          ("safe", "ด่านตรวจ", "red")]


def card(k: str, label: str, topic: str, title: str) -> dict:
    archived = " · archived" if R[k]["archived"] else ""
    return dict(id=k, label=label, topic=topic, title=title, points=f"★{stars(k)} · {lang(k)}{archived}",
                where=f"{LICENSE[k]} · push ล่าสุด {pushed(k)}")


FOCUS = [
    dict(id="ms", label="my_secretary", topic="ours", title="ของเรา — วางไว้เทียบในทุกคอลัมน์",
         points="M8 กำลังทำ", where="แผนที่ละเอียดของเราอยู่ที่ docs/map/"),
    card("oc", "OpenClaw", "plat", "ผู้ช่วยที่อยู่ในแอปแชทที่คุณใช้อยู่แล้ว · Gateway เดียวถือทุกอย่าง"),
    card("ga", "GAIA", "plat", "โครงใกล้เราที่สุด: FastAPI + agent สองชั้น + บอต + workflow"),
    card("kh", "Khoj", "plat", "สมองที่สอง · automation จากประโยค (APScheduler แบบเรา)"),
    card("le", "Leon", "plat", "รุ่น 2.0: ลูป agent 3 โหมด · pulse คิดงานเอง"),
    card("ea", "email-agent", "mail", "demo ทางการของ Claude Agent SDK ตัวเดียวกับเรา"),
    card("afs", "agents-from-scratch", "mail", "สอนทำ email assistant: triage → อนุมัติ → ความจำ"),
    card("eaia", "EAIA", "mail", "รุ่นก่อนของ agents-from-scratch — ปุ่มนี้ไฮไลต์กล่องที่รับแนวคิดมา"),
    card("iz", "Inbox Zero", "mail", "แอปอีเมล AI ใช้งานจริง: Gmail push + กฎภาษาคน"),
    card("tc", "taskcheck", "time", "ตัวจัดตารางไม่ใช้ AI บน Taskwarrior"),
    card("sp", "Super Productivity", "time", "to-do + timebox + จับเวลา · คนวางเอง"),
    card("gw", "workspace-mcp", "tool", "MCP server สำเร็จรูปของ Google Workspace"),
    card("am", "Amica", "char", "ตัวละคร VRM ในเบราว์เซอร์ · fork มาจาก ChatVRM"),
    card("cv", "ChatVRM", "char", "ต้นแบบของ Amica — ปุ่มนี้ไฮไลต์กล่องของ Amica ที่มาจากที่นี่"),
    card("ai", "AIRI", "char", "ตัวละครเต็มระบบ: Live2D + VRM · หลายช่องทาง · เล่นเกม"),
    card("olv", "Open-LLM-VTuber", "char", "ตัวละคร Live2D · backend Python + FastAPI แบบเรา"),
]
assert {f["id"] for f in FOCUS} == set(REPOS) | {"ms"}

# ================================================================ กริด (การ์ด 230 × 80 · เลน 310 · ระหว่างคอลัมน์ 370)
A, B, C = 70, 380, 690           # ① ตัวละคร · เสียง (3 เลน: ของเรา · Amica · AIRI + OLV)
D = 1060                         # ② ช่องทาง · แจ้งเตือน
E1, E2 = 1430, 1740              # ③ แกน agent (E1 = GAIA + workspace-mcp · E2 = ของเรา + OpenClaw + Leon + Khoj)
F = 2110                         # ④ งานเชิงรุก
G1, G2 = 2480, 2790              # ⑤ อีเมล (G1 = email-agent + ของเรา · G2 = Inbox Zero + agents-from-scratch)
H = 3160                         # ⑥ วางแผนเวลา
U1, U2 = 100, 210                # หน้าบ้าน
R1 = 376                         # ประตูเข้า (ลงมาให้ badge pairing วางเหนือ Gateway ได้)
K1, K2 = 510, 620                # ตัวตัดสินใจ
J1, J2 = 770, 880                # ตัวลงมือ
L1, L2, L3 = 1030, 1140, 1250    # ฐาน
SIZE = (3430, 1370)
W = 230                          # ความกว้างการ์ด
# ทางเดินเส้นตั้ง (กึ่งกลางช่องว่างระหว่างเลน) — เส้นที่ข้ามแถว/คอลัมน์เดินในช่องพวกนี้ ไม่ทะลุการ์ด
GAP_AB, GAP_BC, GAP_CD, GAP_DE, GAP_EE, GAP_EF, GAP_FG, GAP_GH = 340, 650, 990, 1360, 1700, 2040, 2410, 3090


def mid(x: int) -> int:
    return x + W // 2


BANDS = [
    dict(id="face", y0=70, y1=310, name="หน้าบ้าน", sub="สิ่งที่คุณเห็น", chip="หน้าบ้าน",
         note="สิ่งที่ผู้ใช้เห็นหรือแตะได้: ร่างตัวละคร หน้าเว็บ แอปแชทที่บอตอยู่"),
    dict(id="gate", y0=330, y1=460, name="ประตูเข้า", sub="", chip="ประตูเข้า",
         note="ทางที่ข้อความ เสียง หรือเหตุการณ์ไหลเข้าระบบ: gateway · webhook · proxy · ตัวนำเข้างาน"),
    dict(id="brain", y0=480, y1=720, name="ตัวตัดสินใจ", sub="LLM หรืออัลกอริทึม", chip="ตัวตัดสินใจ",
         note="ส่วนที่เลือกว่าจะทำอะไรต่อ — agent ที่ใช้ LLM หรืออัลกอริทึมธรรมดา (ตัววางแผนเวลาก็อยู่ชั้นนี้)"),
    dict(id="hands", y0=740, y1=980, name="ตัวลงมือ", sub="tool · กฎ · สคริปต์", chip="ตัวลงมือ",
         note="ของที่ทำงานจริงตามคำสั่ง: tool · กฎ · สคริปต์ที่ agent เขียน · คิวเสียง · ตัวกระจายแจ้งเตือน"),
    dict(id="base", y0=1000, y1=1350, name="ฐาน", sub="ความจำ · เวลา · runtime", chip="ฐาน",
         note="ความจำ ที่เก็บข้อมูล ตัวจับเวลา และ process ของโมเดล/เสียงที่ทำงานอยู่เบื้องหลัง"),
]
COLUMNS = [
    dict(x0=A, x1=C + W, head="① ตัวละคร · เสียง", sub="สีหน้า · เสียง · ปากขยับ", tag="M8", topic="base"),
    dict(x0=D, x1=D + W, head="② ช่องทาง", sub="LINE · Discord", tag="", topic="base"),   # คอลัมน์เลนเดียว — ข้อความสั้น
    dict(x0=E1, x1=E2 + W, head="③ แกน agent", sub="ใครคิด · ใช้ tool อะไร · จำอะไร", tag="M1", topic="base"),
    dict(x0=F, x1=F + W, head="④ งานเชิงรุก", sub="ใครปลุก agent", tag="M5", topic="base"),
    dict(x0=G1, x1=G2 + W, head="⑤ อีเมล", sub="รู้ตัว · คัด · ร่าง · อนุมัติ", tag="M6 · M7", topic="base"),
    dict(x0=H, x1=H + W, head="⑥ วางแผนเวลา", sub="", tag="M4", topic="base"),
]
MAP_LEGEND_AT = (2160, 96)

# ================================================================ ไอคอนที่วาดเพิ่ม (นำมาจาก docs/map/spec.py ให้สองแผนที่หน้าตาไปทางเดียวกัน)
ICONS = {
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
    "frames": "".join(f'<rect class="i-b" x="6" y="{y}" width="44" height="10" rx="2"/>'
                      f'<rect class="{c}" x="6" y="{y}" width="9" height="10" rx="2"/>'
                      f'<line class="i-s" x1="19" y1="{y + 5}" x2="{x2}" y2="{y + 5}"/>'
                      for y, c, x2 in ((8, "i-a", 40), (21, "i-A", 44), (34, "i-a", 36)))
              + '<path class="i-sA" d="M28,47 V53 M24.5,50 L28,53.5 L31.5,50"/>',
    # กล่อง MCP หลายตัว แต่ละตัวมี tool อยู่ข้างใน (จุด)
    "tools": "".join(f'<rect class="i-a" x="{x}" y="{y}" width="21" height="21" rx="4"/>'
                     f'<circle class="i-A" cx="{x + 6}" cy="{y + 10.5}" r="2.6"/>'
                     f'<circle class="i-A" cx="{x + 15}" cy="{y + 10.5}" r="2.6"/>'
                     for x, y in ((6, 6), (29, 6), (6, 29), (29, 29))),
    # หนึ่งเรื่องเข้า → กระจายออกหลายช่องทาง
    "fanout": ('<circle class="i-A" cx="14" cy="28" r="7"/>'
               '<path class="i-s" d="M21,28 H30 M30,28 L42,12 M30,28 H42 M30,28 L42,44" style="stroke-width:2"/>'
               '<rect class="i-a" x="42" y="6" width="10" height="11" rx="2"/>'
               '<rect class="i-a" x="42" y="22.5" width="10" height="11" rx="2"/>'
               '<rect class="i-a" x="42" y="39" width="10" height="11" rx="2"/>'),
}

# ================================================================ กล่อง
NODES = [
    # ① ตัวละคร · เสียง — เลน A ของเรา · B Amica · C AIRI + Open-LLM-VTuber
    N("ms_vrm", A, U1, "VRM ของเรา", f"ปาก 3 ย่าน · สีหน้า {len(EMOTIONS)} · ท่า {len(GESTURES)}", "face", "ours",
      ch="my_secretary", q=("ms",)),
    N("ms_mood", A, K1, "แท็ก <mood>", "agent ต่อท้ายคำตอบ · server ตัดออก", "code", "ours", ch="my_secretary", q=("ms",)),
    N("ms_tts", A, L1, "Kokoro sidecar", f"process แยก · Python 3.13 · :{TTS_PORT}", "term", "ours", ch="my_secretary",
      q=("ms",)),
    N("am_vrm", B, U1, "vrmViewer", "ปากขยับตามความดัง → aa ท่าเดียว", "face", "char", ch="Amica", q=("am", "cv")),
    N("am_life", B, K1, "amicaLife", "ผู้ใช้เงียบนาน → ทำอะไรเอง", "loop", "char", ch="Amica", q=("am",)),
    N("am_screen", B, K2, "screenplay", "แยกประโยค + [happy] ต่อประโยค", "frames", "char", ch="Amica", q=("am", "cv")),
    N("am_queue", B, J1, "คิวเสียงสองชั้น", "สร้างเสียงประโยคถัดไป ระหว่างที่พูด", "queue", "char", ch="Amica",
      q=("am", "cv")),
    N("ai_stage", C, U1, "Stage", "Live2D + VRM · ปากจากสระ AEIOU", "browser", "char", ch="AIRI", q=("ai",)),
    N("ai_unspeech", C, R1, "unspeech", "endpoint เดียวทั้ง ASR และ TTS", "socket", "char", ch="AIRI", q=("ai",)),
    N("olv_emo", C, K1, "emotionMap", "[joy] [sadness] ใส่ใน prompt", "table", "char", ch="Open-LLM-VTuber", q=("olv",)),
    N("olv_factory", C, J1, "factory โมดูล", "ASR · LLM · TTS เลือกใน conf.yaml", "gear", "char", ch="Open-LLM-VTuber",
      q=("olv",)),
    # ② ช่องทาง · แจ้งเตือน
    N("oc_channels", D, U1, "channel plugins", "20+ ช่องทาง รวม LINE · Discord", "chat", "plat", ch="OpenClaw", q=("oc",)),
    N("ga_bots", D, U2, "bot adapters", "หนึ่ง adapter ต่อแพลตฟอร์ม", "people", "plat", ch="GAIA", q=("ga",)),
    N("ai_server", D, R1, "server-runtime", "ส่งต่อเหตุการณ์ระหว่าง module", "nic", "char", ch="AIRI", q=("ai",)),
    N("ga_notif", D, J1, "notify router", "in-app · อีเมล · bot · push", "fanout", "plat", ch="GAIA", q=("ga",)),
    N("ms_notify_plan", D, J2, "รวมแจ้งเตือน", f"แผนใน feature.md · {CH_LIST}", "checklist", "ours", ch="my_secretary",
      q=("ms",)),
    N("oc_pair", mid(E2), 340, "pairing", "จับคู่ผู้ส่งก่อนคุย", kind="badge", topic="safe", lab="r", q=("oc",)),
    # ③ แกน agent — E1 GAIA + workspace-mcp + ความจำของ OpenClaw · E2 OpenClaw + Leon + ของเรา + Khoj
    N("ga_voice", E1, R1, "voice worker", "LiveKit: เสียง ↔ ข้อความ", "wave", "plat", ch="GAIA", q=("ga",)),
    N("ga_comms", E1, K1, "Comms agent", "คุยกับคุณ · tool น้อยโดยตั้งใจ", "person", "plat", ch="GAIA", q=("ga",)),
    N("ga_exec", E1, K2, "Executor", "tool ครบ · เปิด integration ตามงาน", "threads", "plat", ch="GAIA", q=("ga",)),
    N("gw_tiers", E1, J1, "tool tiers", "120+ tool · core / extended / complete", "tools", "tool", ch="workspace-mcp",
      q=("gw",)),
    N("gw_auth", E1, J2, "OAuth 2.1", "หลายผู้ใช้ · stateless · read-only", "key", "tool", ch="workspace-mcp", q=("gw",)),
    N("oc_mem", E1, L1, "MEMORY.md", "ความจำ = ไฟล์ Markdown", "doc", "plat", ch="OpenClaw", q=("oc",)),
    N("oc_gw", E2, R1, "Gateway", "daemon เดียว · WebSocket", "socket", "plat", ch="OpenClaw", q=("oc",)),
    N("le_loop", E2, K1, "agent loop", "3 โหมด · โหลด tool ทีละชุด", "loop", "plat", ch="Leon", q=("le",)),
    N("ms_agent", E2, K2, "ask_stream()", f"agent ตัวเดียว · {len(TOOLS)} tool", "model", "ours", ch="my_secretary",
      q=("ms",)),
    N("ms_mcp", E2, J1, "MCP ในตัว", f"{len(TOOL_SERVERS)} server · ขอ scope เท่าที่ใช้", "tools", "ours",
      ch="my_secretary", q=("ms",)),
    N("kh_search", E2, L3, "pgvector search", "ค้นเอกสารของคุณ ตามความหมาย", "rag", "plat", ch="Khoj", q=("kh",)),
    # ④ งานเชิงรุก
    N("le_pulse", F, K1, "pulse manager", "คิดเรื่องจะทำเอง · ทีละเรื่อง", "idea", "plat", ch="Leon", q=("le",)),
    N("ga_wf", F, J1, "workflows", "ตามเวลา หรือตามเหตุการณ์", "pipeline", "plat", ch="GAIA", q=("ga",)),
    N("ea_listen", F, J2, "listeners/*.ts", "สคริปต์เฝ้าเมล · agent เขียนเอง", "script", "mail", ch="email-agent",
      q=("ea",)),
    N("ms_sched", F, L1, "APScheduler", f"cron ตายตัว {T_BRIEF} · {T_MAIL}", "clock", "ours", ch="my_secretary",
      q=("ms",)),
    N("oc_auto", F, L2, "automations", "เวลา · webhook · Gmail PubSub", "timer", "plat", ch="OpenClaw", q=("oc",)),
    N("kh_auto", F, L3, "ประโยค → cron", "LLM แปลงคำขอเป็นงานตั้งเวลา", "loop", "plat", ch="Khoj", q=("kh",)),
    # ⑤ อีเมล — G1 email-agent + ของเรา · G2 Inbox Zero + agents-from-scratch (EAIA ไฮไลต์ร่วม)
    N("ea_sdk", G1, K1, "ccsdk session", "Agent SDK ตัวเดียวกับเรา", "model", "mail", ch="email-agent", q=("ea",)),
    N("ea_actions", G1, J1, "actions/*.ts", "ปุ่มกดครั้งเดียว เติมค่าครบแล้ว", "exe", "mail", ch="email-agent",
      q=("ea",)),
    N("ms_mail", G1, L1, "mail_extract", "Ollama ในเครื่อง · แนะนำเท่านั้น", "magnifier", "ours", ch="my_secretary",
      q=("ms",)),
    N("iz_push", G2, R1, "Gmail push", "Pub/Sub → webhook · ไม่ต้องวนถาม", "irq", "mail", ch="Inbox Zero", q=("iz",)),
    N("iz_rules", G2, K1, "AI rules", "กฎภาษาคน → AI เลือกกฎ", "balance", "mail", ch="Inbox Zero", q=("iz",)),
    N("afs_triage", G2, K2, "triage router", "ignore · notify · respond", "dispatch", "mail", ch="from-scratch",
      q=("afs", "eaia")),
    N("afs_hitl", G2, J1, "interrupt()", "หยุดรอคนอนุมัติก่อนส่ง", "person", "mail", ch="from-scratch",
      q=("afs", "eaia")),
    N("afs_store", G2, L1, "Store ความชอบ", "เรียนจากที่คนแก้ร่าง", "database", "mail", ch="from-scratch", q=("afs",)),
    N("afs_cron", G2, L2, "cron ingest", "ดึงเมลย้อนหลัง N นาที", "parcel", "mail", ch="from-scratch",
      q=("afs", "eaia")),
    # ⑥ วางแผนเวลา
    N("sp_ui", H, U1, "schedule view", "ไทม์ไลน์งานข้างนัดในปฏิทิน", "calendar", "time", ch="Super Productivity",
      q=("sp",)),
    N("sp_issue", H, R1, "issue providers", "ดึงงานจาก GitHub · Jira", "git", "time", ch="Super Productivity",
      q=("sp",)),
    N("ms_planner", H, K1, "planner.py", f"เติมช่องว่าง {PLAN['work_start']:02d}–{PLAN['work_end']} น.", "blocks", "ours",
      ch="my_secretary", q=("ms",)),
    N("tc_sched", H, K2, "taskcheck", "เรียงตาม urgency · due", "sched", "time", ch="taskcheck", q=("tc",)),
    N("tc_tw", H, L1, "Taskwarrior", "แหล่งความจริง · เขียนแผนกลับ", "table", "time", ch="taskcheck", q=("tc",)),
]

EDGES = [  # ctl สั่ง/ปลุก · data ข้อมูลไหล · sig แจ้งย้อนกลับ · rel แนวคิดเดียวกัน
    # ① ตัวละคร
    E("e_mood_vrm", "ms_mood", "ms_vrm", "สีหน้า + ท่า", kind="data", sp="n@0.3", dp="s@0.3"),
    E("e_tts_vrm", "ms_tts", "ms_vrm", "WAV → ซองปาก", kind="data", sp="e", dp="e@0.7", via=(("x", GAP_AB),), lw=60,
      lt=0.37),                  # ป้ายลงช่องว่างระหว่างแถบ ตัวตัดสินใจ / ตัวลงมือ (ไม่ทับการ์ดของ Amica)
    E("e_life_screen", "am_life", "am_screen", "ว่าง → หาเรื่องพูด"),
    E("e_screen_queue", "am_screen", "am_queue", "ประโยค + อารมณ์", kind="data"),
    E("e_queue_vrm", "am_queue", "am_vrm", "เสียง → ความดัง", kind="data", sp="e", dp="e@0.7", via=(("x", GAP_BC),),
      lw=60),
    E("e_uns_stage", "ai_unspeech", "ai_stage", "เสียงพูด", kind="data"),
    E("e_emo_fac", "olv_emo", "olv_factory", "ประโยค + [joy]", kind="data"),
    E("e_srv_stage", "ai_server", "ai_stage", "ข้อความจาก Discord · Telegram", kind="data", sp="w", dp="e@0.7",
      via=(("x", GAP_CD),), lw=110, lside="l"),
    # ② ช่องทาง
    E("e_ch_gw", "oc_channels", "oc_gw", "ข้อความเข้า", kind="data", sp="e", dp="n", via=(("x", mid(E2)),)),
    E("e_bots_comms", "ga_bots", "ga_comms", "ข้อความ → call_agent", kind="data", sp="e", dp="w",
      via=(("x", GAP_DE),), lw=110),
    E("e_exec_notif", "ga_exec", "ga_notif", "send_notification", sp="w", dp="e", via=(("x", GAP_DE),), lw=110),
    E("e_plan_notif", "ms_notify_plan", "ga_notif", "แบบเดียวกัน", kind="rel", arrow=False),
    # ③ แกน agent
    E("e_voice_comms", "ga_voice", "ga_comms", "ถอดเสียง", kind="data"),
    E("e_comms_exec", "ga_comms", "ga_exec", "call_executor"),
    E("e_tiers_auth", "gw_tiers", "gw_auth", "เรียกในนามผู้ใช้"),
    E("e_mem_gw", "oc_mem", "oc_gw", "โหลดต้น session", kind="data", sp="e", dp="w", via=(("x", GAP_EE),), lw=60),
    E("e_agent_mcp", "ms_agent", "ms_mcp", "เรียก tool", sp="s@0.7", dp="n@0.7"),
    E("e_pulse_loop", "le_pulse", "le_loop", "ส่งเรื่องเข้าลูปเดิม", lw=110),
    # ④ งานเชิงรุก
    E("e_sched_agent", "ms_sched", "ms_agent", f"{T_BRIEF} สรุปเช้า", sp="w", dp="e", via=(("x", GAP_EF),), lw=110),
    E("e_sched_mail", "ms_sched", "ms_mail", f"{T_MAIL} สแกนเมล", lw=110),
    E("e_kauto_search", "kh_auto", "kh_search", "ถามซ้ำตามเวลา", lw=110),
    E("e_sdk_listen", "ea_sdk", "ea_listen", "เขียนไฟล์ listener", sp="w", dp="e", via=(("x", GAP_FG),), lw=110),
    # ⑤ อีเมล
    E("e_sdk_actions", "ea_sdk", "ea_actions", "สร้างปุ่ม action"),
    E("e_push_rules", "iz_push", "iz_rules", "เมลใหม่ (history)", kind="data"),
    E("e_triage_hitl", "afs_triage", "afs_hitl", "respond → ร่าง → รอ"),
    E("e_hitl_store", "afs_hitl", "afs_store", "คนแก้ร่าง → จำ", kind="data"),
    E("e_cron_triage", "afs_cron", "afs_triage", "เมลย้อนหลัง N นาที", kind="data", sp="e", dp="e",
      via=(("x", GAP_GH),), lw=100, lside="l"),   # ซ้ายเส้น — ฝั่งขวาเป็นป้ายของ taskcheck
    # ⑥ วางแผนเวลา
    E("e_issue_ui", "sp_issue", "sp_ui", "นำเข้างาน", kind="data"),
    E("e_tw_sched", "tc_tw", "tc_sched", "งาน + estimated", kind="data", sp="n@0.3", dp="s@0.3", lside="l", lw=90),
    E("e_sched_tw", "tc_sched", "tc_tw", "เขียน scheduled กลับ", kind="data", sp="s@0.75", dp="n@0.75", lw=80),
]
ALLOW = (("e_ch_gw", "oc_pair"),)

CONNS = [  # เส้นที่ต้องพาดข้ามหลายคอลัมน์ → วงกลมตัวอักษรเดียวกันสองจุด
    Conn("cA", "A", "ms_mcp", "s", "ms_planner", "n", "get_free_slots", "จาก MCP ของเรา", stub=14),
    Conn("cB", "B", "ms_agent", "s@0.2", "ms_mood", "s", "แท็กท้ายคำตอบ", "จาก ask_stream()"),
    Conn("cC", "C", "oc_auto", "w", "oc_gw", "e", "ปลุก agent", "จาก automation"),
    Conn("cD", "D", "ga_wf", "n", "ga_exec", "s", "รัน workflow", "จาก workflow"),
]
EDGE_KINDS = {"ctl": "สั่ง / ปลุกให้ทำ", "data": "ข้อมูลหรือข้อความไหล", "sig": "แจ้งเหตุการณ์ย้อนกลับ",
              "rel": "แนวคิดเดียวกัน (ไม่มีการไหล)"}

# ================================================================ คำอธิบายรายกล่อง (แผงข้าง + แค็ตตาล็อก)
DESC = {
    # ---- ① ตัวละคร · เสียง
    "ms_vrm": dict(
        what="ร่าง VRM ของเลขาเรา — แสดงสีหน้า ท่าทาง และขยับปากตามเสียงจาก sidecar",
        does=[f"ปาก: คำนวณ “ซองปาก” จาก WAV **ล่วงหน้า** แบ่ง 3 ย่าน (<{LIP_CUTS[0]} Hz → ou · กลาง → aa · "
              f">{LIP_CUTS[1]} Hz → ih)",
              f"สีหน้า {len(EMOTIONS)} แบบ · ท่า {len(GESTURES)} ท่า มาจากแท็ก mood",
              "ถ้า WebGL หรือโมเดลพัง ถอยไปใช้วงกลม (Stage 0)"],
        look="`frontend/src/character/` — vrmScene.ts · audio.ts · gestures.ts · queue.ts",
        exam=["เทียบสามแบบ: Amica ใช้ความดังอย่างเดียว (ปากท่าเดียว) · AIRI ตรวจสระ AEIOU · ของเราอยู่ตรงกลาง — "
              "ถูกกว่าการตรวจสระ แต่ไม่อ้าปากแบบเดียวทั้งประโยค"],
        read="`docs/map/` (แผนที่ละเอียดของเรา) · `frontend/src/character/audio.ts`"),
    "ms_mood": dict(
        what="แท็ก `<mood>emotion:gesture</mood>` ที่ agent ต่อท้ายคำตอบ แล้ว server ตัดออกก่อนถึงคุณ",
        does=["system prompt (persona.py) ให้เลือกอารมณ์และท่าจากรายการที่กำหนด",
              "server แยกแท็กออก แล้วส่งเป็นเหตุการณ์ไปให้ตัวละคร",
              "ไม่มี LLM call เพิ่ม — ไม่เปลืองโควตา Pro"],
        look="`backend/app/agent/persona.py` — EMOTIONS · GESTURES · regex ที่ตัดแท็ก",
        exam=["Amica · ChatVRM · Open-LLM-VTuber ใช้แนวเดียวกัน (แท็กในเนื้อความ) แต่วางแท็ก **ต่อประโยค** "
              "จึงเปลี่ยนสีหน้ากลางคำตอบได้ — ของเราได้แท็กเดียวต่อคำตอบ"],
        read="`backend/app/agent/persona.py`"),
    "ms_tts": dict(
        what="เสียงของเลขา: Kokoro (ONNX) รันเป็น process แยกบน CPU",
        does=[f"backend เรียก HTTP ไปที่ :{TTS_PORT} แล้วได้ WAV กลับ",
              "แคช WAV บนดิสก์ ประโยคเดิมไม่ต้องสร้างใหม่",
              "แยก process เพราะ kokoro-onnx ต้องการ Python < 3.14 แต่ backend ใช้ 3.14"],
        look="`backend/tts_sidecar/main.py` · `backend/app/services/tts.py`",
        exam=["AIRI ทำชั้นนี้เป็น proxy กลาง (unspeech) · Open-LLM-VTuber ทำเป็น interface + factory — "
              "ถ้าวันหนึ่งอยากได้เสียงไทย สองแบบนี้ทำให้เปลี่ยนผู้ให้บริการได้โดยไม่แตะส่วนอื่น"],
        read="`backend/tts_sidecar/README.md`"),
    "am_vrm": dict(
        what="ตัวแสดงผล VRM ของ Amica (three.js + @pixiv/three-vrm) — ส่วนที่รับมาจาก ChatVRM",
        does=["ต่อเสียงเข้า AnalyserNode อ่านค่าสูงสุดของคลื่นทุกเฟรม",
              "บีบด้วย sigmoid แล้วใส่เป็นน้ำหนักของปาก `aa` ตัวเดียว",
              "autoBlink · autoLookAt ทำให้ดูมีชีวิตตอนเงียบ"],
        look="`src/features/vrmViewer/` · `lipSync/lipSync.ts` · `emoteController/`",
        exam=["วิธีนี้ง่ายและทำสด (ไม่ต้องคำนวณล่วงหน้า) แต่ได้ปากท่าเดียว — โค้ดของเราเขียนไว้ว่า "
              "“aa อย่างเดียวดูเหมือนปลา” จึงแบ่ง 3 ย่าน"],
        read=gh("am", "src/features/lipSync/lipSync.ts")),
    "am_life": dict(
        what="ระบบ “ชีวิตตอนว่าง” ของ Amica — เมื่อผู้ใช้เงียบนาน ตัวละครจะทำอะไรเอง",
        does=["สุ่มเหตุการณ์ว่าง 3 แบบ: ขยับท่า (VRMA) · พูดจาก prompt ชุด idle · subconscious",
              "subconscious = สรุปบทสนทนาย่อๆ เก็บไว้ใช้ต่อ (มีเพดาน token)",
              "ส่งข้อความเข้าแชทเดิม เหมือนผู้ใช้พิมพ์เอง"],
        look="`src/features/amicaLife/` — amicaLife.ts · eventHandler.ts",
        exam=["งานเชิงรุกแบบ “ตัวละคร”: ไม่ได้ตั้งเวลา แต่เริ่มเมื่อเงียบ — ถ้าจะทำต้องมีเพดาน ไม่งั้นเปลืองโควตา Pro"],
        read=gh("am", "src/features/amicaLife", tree=True)),
    "am_screen": dict(
        what="การแปลงคำตอบของ LLM เป็น “บท” (screenplay) ทีละประโยค พร้อมอารมณ์ของแต่ละประโยค",
        does=["แบ่งคำตอบเป็นประโยค",
              "อ่านแท็กหน้าประโยค เช่น `[happy]` `[sad]` → สีหน้าของประโยคนั้น",
              "ส่งบทเข้าคิวเสียง"],
        look="`src/features/chat/messages.ts` (textsToScreenplay) · `chat/chat.ts`",
        exam=["รูปแบบ “แท็กในข้อความ” เดียวกับ `<mood>` ของเรา แต่ละเอียดถึงระดับประโยค"],
        read=gh("am", "src/features/chat/messages.ts")),
    "am_queue": dict(
        what="คิวสองชั้นของ Amica: สร้างเสียงประโยคถัดไปไว้ก่อน ขณะที่ประโยคปัจจุบันกำลังพูด",
        does=["`ttsJobs` — ประโยคที่รอสังเคราะห์เสียง",
              "`speakJobs` — เสียงที่สร้างแล้ว รอเล่นพร้อมเปลี่ยนสีหน้า",
              "`interrupt()` ล้างทั้งสองคิวทันทีเมื่อผู้ใช้พูดแทรก"],
        look="`src/features/chat/chat.ts` — Queue<TTSJob> · Queue<Speak>",
        exam=["ถ้าเสียงของเรามีช่องว่างระหว่างบรรทัด การสร้างเสียงบรรทัดถัดไปไว้ก่อนแบบนี้ช่วยได้"],
        read=gh("am", "src/features/chat/chat.ts")),
    "ai_stage": dict(
        what="หน้าจอของ AIRI (Stage) มี 3 แบบ: เว็บ · desktop (Electron) · มือถือ — รองรับทั้ง Live2D และ VRM",
        does=["วาดตัวละครด้วย renderer แยกตามชนิดโมเดล",
              "ปาก: wLipSync ตรวจสระ AEIOU จากเสียง แล้วทำให้นิ่ง (เลือกตัวชนะ · ตรวจความเงียบ · smoothing)",
              "รับข้อความจาก module อื่นผ่าน server-runtime"],
        look="`apps/stage-web` · `apps/stage-tamagotchi` · `apps/stage-pocket` · `packages/model-driver-lipsync`",
        exam=["monorepo ใหญ่มาก (แพ็กเกจหลายสิบตัว) — สำหรับงานของเรา อ่าน `model-driver-lipsync` กับ "
              "`core-character` ก็พอ"],
        read=gh("ai", "packages/model-driver-lipsync", tree=True)),
    "ai_unspeech": dict(
        what="proxy กลางสำหรับเสียง — endpoint เดียวทั้ง `/audio/transcriptions` (ASR) และ `/audio/speech` (TTS) "
             "เหมือน LiteLLM แต่สำหรับเสียง",
        does=["แอปเรียก endpoint เดียว ไม่ต้องรู้ว่าข้างหลังเป็นเจ้าไหน",
              "สลับ ElevenLabs · Azure · OpenAI-compatible · Kokoro ในเครื่องได้"],
        look="repo แยกของทีมเดียวกัน: `github.com/moeru-ai/unspeech`",
        exam=["TTS sidecar ของเราคือรุ่นเล็กของแนวคิดนี้ (endpoint เดียว · ผู้ให้บริการอยู่ข้างหลัง) — "
              "ต่างกันที่ของเรามีผู้ให้บริการเดียว"],
        read="`github.com/moeru-ai/unspeech`"),
    "olv_emo": dict(
        what="ตารางอารมณ์ของ Open-LLM-VTuber — ผูกชื่ออารมณ์กับ expression ของโมเดล Live2D แต่ละตัว",
        does=["อ่าน `emotionMap` จากข้อมูลโมเดล แล้วสร้างรายการ `[joy], [sadness], …` ใส่ใน prompt",
              "LLM ใส่แท็กในคำตอบ → backend แปลงเป็น expression ส่งไปหน้าจอ",
              "ตัวละครคนละตัวมีรายการอารมณ์ไม่เท่ากันได้"],
        look="`src/open_llm_vtuber/live2d_model.py` (emo_map · emo_str)",
        exam=["ของเราเขียนรายการอารมณ์ตายตัวใน persona.py — ถ้าจะรองรับโมเดลหลายตัว แบบ “อ่านจากโมเดล” นี้ยืดหยุ่นกว่า"],
        read=gh("olv", "src/open_llm_vtuber/live2d_model.py")),
    "olv_factory": dict(
        what="ทุกชิ้นส่วนเสียงและสมองเป็น interface + factory — เลือกตัวที่ใช้ใน `conf.yaml`",
        does=["`tts/` มี interface กลาง + ไฟล์ละผู้ให้บริการ (edge · melo · sherpa-onnx · elevenlabs …)",
              "`asr/` และ `agent/` ทำแบบเดียวกัน",
              "server เป็น FastAPI + WebSocket · พูดแทรกได้โดยไม่ต้องใส่หูฟัง"],
        look="`src/open_llm_vtuber/tts/tts_interface.py` · `tts_factory.py` · `server.py`",
        exam=["ใกล้ backend เราที่สุด (Python · FastAPI) — ถ้าจะเพิ่มทางเลือกเสียงหรือ STT ให้ลอกโครง interface + "
              "factory นี้"],
        read=gh("olv", "src/open_llm_vtuber/tts", tree=True)),
    # ---- ② ช่องทาง · แจ้งเตือน
    "oc_channels": dict(
        what="ช่องทางแชทของ OpenClaw เป็น plugin — WhatsApp · Telegram · Slack · Discord · LINE · iMessage และอีกมาก",
        does=["ทุกช่องทางต่อเข้า Gateway ตัวเดียว",
              "LINE: plugin รับ webhook บน Gateway (ต้องเป็น HTTPS) ใช้ channel access token + channel secret",
              "ผู้ส่งที่ไม่รู้จักใน DM ต้องจับคู่ (pairing) ก่อนคุยได้"],
        look="`docs/channels/` — ไฟล์ละช่องทาง เช่น `line.md` · `discord.md`",
        exam=[f"ใกล้ feature.md ({CH_LIST}) ที่สุด — อ่าน `docs/channels/line.md` ก่อนออกแบบฝั่ง LINE",
              "ถือว่าข้อความขาเข้า “เชื่อไม่ได้” เสมอ (prompt injection)"],
        read=gh("oc", "docs/channels/line.md")),
    "oc_pair": dict(
        what="ด่านตรวจของ OpenClaw: ผู้ส่งที่ไม่รู้จักต้องได้รับอนุมัติก่อน ข้อความถึงจะไปถึง agent",
        does=["อนุมัติด้วย `openclaw pairing approve <channel> <code>`",
              "อุปกรณ์ใหม่ก็ต้องจับคู่ก่อนต่อ Gateway"],
        look="—",
        exam=["ถ้าเลขาเราจะรับข้อความจาก LINE / Discord ต้องมีด่านแบบนี้ — ไม่งั้นใครก็สั่งงานเลขาได้"],
        read=gh("oc", "docs/channels/pairing.md")),
    "ga_bots": dict(
        what="บอตของ GAIA (Telegram · Discord · Slack · WhatsApp · iMessage) — หนึ่งโฟลเดอร์ต่อแพลตฟอร์ม ใช้ adapter pattern",
        does=["ทุกแพลตฟอร์ม implement `BaseBotAdapter` (boot → registerCommands → start)",
              "คำสั่งชุดเดียว (`/gaia` `/new` `/status` …) ใช้ร่วมกันทุกแพลตฟอร์ม",
              "ข้อความ → HTTP ไป backend (`call_agent`) → ตอบกลับเป็น SSE · แปลง Markdown ให้เข้ากับแต่ละแอป"],
        look="`apps/bots/<platform>/src/adapter.ts` · `libs/shared/ts/src/bots/`",
        exam=["แบบที่ลอกง่ายที่สุดสำหรับ LINE + Discord ของเรา: adapter บางๆ ต่อแพลตฟอร์ม + คำสั่งกลาง + "
              "ยิงเข้า `/chat` เดิม"],
        read=gh("ga", "ARCHITECTURE.md") + " (หัวข้อ 5 · Bots)"),
    "ai_server": dict(
        what="ตัวกลางของ AIRI ที่ส่งเหตุการณ์ระหว่าง module ที่ยืนยันตัวตนแล้ว — บอต Discord / Telegram "
             "หรือ agent เล่นเกมต่อเข้ามาที่นี่",
        does=["module ต่อด้วย `server-sdk` ผ่าน WebSocket",
              "ไม่ถือ session แชท และไม่รันโมเดลเอง — มีหน้าที่ส่งต่ออย่างเดียว",
              "รันแยกเป็น channel server หรือฝังใน desktop ก็ได้"],
        look="`packages/server-runtime` · `packages/server-sdk` · `packages/plugin-protocol`",
        exam=["อีกแบบของการต่อหลายช่องทาง: แทนที่ทุกบอตจะเรียก backend ตรงๆ ให้ทุกตัวเป็น “peer” บนสายเดียวกัน"],
        read=gh("ai", "packages/server-runtime", tree=True)),
    "ga_notif": dict(
        what="ตัวกระจายการแจ้งเตือนของ GAIA — เรื่องเดียวส่งได้หลายช่องทางตามที่ผู้ใช้ตั้งค่า",
        does=["`NotificationOrchestrator` เลือกช่องทาง · `ChannelAdapter` หนึ่งตัวต่อช่องทาง",
              "เก็บความชอบต่อช่องทาง (channel preferences)",
              "ส่งจริงได้ทั้ง in-app · อีเมล · bot · push · agent มี tool `send_notification` · "
              "`mark_notifications_read`"],
        look="`apps/api/app/utils/notification/` — orchestrator.py · channels.py · channel_preferences.py",
        exam=["feature.md อยากได้ “จัดการการแจ้งเตือนทั้งหมด” — โครงนี้คือคำตอบครึ่งหนึ่ง (ขาออก) · "
              "อีกครึ่ง (ดึงแจ้งเตือนจาก LINE / Discord เข้ามา) ต้องออกแบบเพิ่ม"],
        read=gh("ga", "ARCHITECTURE.md") + " (หัวข้อ 11 · Notifications)"),
    "ms_notify_plan": dict(
        what=f"ฟีเจอร์ที่วางแผนไว้ใน feature.md: จัดการการแจ้งเตือนทั้งหมด ({CH_LIST}) — ยังไม่เริ่ม",
        does=["ขาเข้า: ดึงแจ้งเตือนจากแต่ละช่องทางมารวมที่เดียว",
              "จัดการ: สรุป · ทำเครื่องหมายว่าอ่านแล้ว",
              "ขาออก (ถ้าต้องการ): ให้เลขาแจ้งคุณกลับทางช่องทางที่สะดวก"],
        look="ยังไม่มีโค้ด — `feature.md`",
        exam=["เริ่มจาก adapter ต่อช่องทาง + ตัวกระจายกลาง (แบบ GAIA) และด่าน pairing (แบบ OpenClaw) — ดูภาพ “รวมแจ้งเตือน”",
              "LINE ต้องมี webhook HTTPS ที่เข้าจากอินเทอร์เน็ตได้ แต่ backend ตอนนี้เปิดแค่ในเครื่อง"],
        read="`feature.md`"),
    # ---- ③ แกน agent
    "ga_voice": dict(
        what="โหมดเสียงของ GAIA เป็นแอป Python แยก (LiveKit worker) — ทำหน้าที่ขนส่งอย่างเดียว",
        does=["STT: Deepgram · TTS: ElevenLabs · VAD: Silero · ตรวจจังหวะพูดหลายภาษา",
              "ส่งข้อความที่ถอดได้ไป backend ผ่าน HTTP แล้วอ่านคำตอบออกเสียง",
              "การคิดทั้งหมดยังอยู่ที่ comms → executor"],
        look="`apps/voice-agent/src/agent.py`",
        exam=["คนละทางกับเรา: เราผูกเสียงไว้กับตัวละครบนหน้าเว็บ · GAIA ทำเสียงเป็นอีกช่องทางหนึ่งที่คุยกับสมองตัวเดียวกัน — "
              "ถ้าวันหนึ่งอยากโทรคุยกับเลขา โครงนี้ใช้ได้"],
        read=gh("ga", "ARCHITECTURE.md") + " (หัวข้อ 6 · Voice Mode)"),
    "ga_comms": dict(
        what="agent ตัวเดียวที่คุยกับผู้ใช้ของ GAIA — มี tool น้อยมากโดยตั้งใจ",
        does=["รับข้อความจากทุกช่องทาง (เว็บ · บอต · เสียง · workflow)",
              "ไม่ทำงานเอง — ส่งทุกงานผ่าน `call_executor` แล้วเล่าความคืบหน้า",
              "tool ที่มี: executor · memory · discovery"],
        look="`apps/api/app/agents/core/agent.py` — `call_agent()` (SSE) · `call_agent_silent()` (เบื้องหลัง)",
        exam=[f"agent ของเราถือ tool ครบ {len(TOOLS)} ตัวเอง — ถ้า M7 เพิ่ม tool ส่งเมลและอื่นๆ อีก "
              "การแยกเป็นสองชั้นแบบนี้ช่วยให้ prompt ไม่บวม"],
        read=gh("ga", "ARCHITECTURE.md") + " (หัวข้อ 2 · Comms Agent)"),
    "ga_exec": dict(
        what="agent ชั้นทำงานของ GAIA — ถือ tool ครบ และเปิด integration เข้ามาเฉพาะตอนต้องใช้",
        does=["`activate_integration(id)` โหลด tool ของ Gmail · Calendar · MCP ของผู้ใช้เข้ามาในบริบท",
              "รันเป็นงานเบื้องหลัง · แตก subagent สำหรับงานใหญ่",
              "สร้างบน LangGraph · มี todo ติดตามงาน"],
        look="`apps/api/app/agents/` · ARCHITECTURE.md หัวข้อ 3–4",
        exam=["“โหลด tool เมื่อจำเป็น” เป็นทางเดียวกับ Leon และ tool tiers ของ workspace-mcp — สามโปรเจกต์มาทางเดียวกัน "
              "แปลว่าปัญหา tool เยอะจน context เต็มเป็นของจริง"],
        read=gh("ga", "ARCHITECTURE.md") + " (หัวข้อ 3 · Executor)"),
    "gw_tiers": dict(
        what="MCP server สำเร็จรูปสำหรับ Google Workspace — 12 บริการ 120+ tool ใน server เดียว",
        does=["แบ่ง tool เป็น 3 ระดับ `core` · `extended` · `complete` (เลือกด้วย `--tool-tier`)",
              "เลือกเฉพาะบริการได้ (`--tools gmail calendar`) · มีโหมด read-only",
              "หนึ่งไฟล์ต่อบริการใน `g<service>/` · ลงทะเบียนด้วย `@server.tool`"],
        look="`gmail/` · `gcalendar/` · `core/tool_tiers.yaml` · `core/server.py`",
        exam=["ไม่มี Classroom — ส่วนนั้นเรายังต้องเขียนเอง",
              "ใช้ชื่อ tool และ parameter ของที่นี่เป็นแบบได้ เพราะมีคนใช้มาก"],
        read=gh("gw", "core/tool_tiers.yaml")),
    "gw_auth": dict(
        what="ชั้น OAuth ของ workspace-mcp — รองรับหลายผู้ใช้ด้วย OAuth 2.1 และรันแบบไม่เขียนดิสก์ได้",
        does=["ใช้ OAuth client ของเราเองใน GCP project ของเรา",
              "stateless mode: ไม่เขียนอะไรลงดิสก์ (เหมาะกับ container)",
              "`service_decorator.py` ส่ง Google service ที่ยืนยันตัวแล้วให้ tool แต่ละตัว"],
        look="`auth/` — oauth21_session_store.py · scopes.py · service_decorator.py",
        exam=["ของเราแก้ปัญหาสองบัญชี (ส่วนตัว + โรงเรียน) ด้วย token ต่อบัญชี — ที่นี่แก้ปัญหาหลายผู้ใช้ "
              "ซึ่งใหญ่กว่าที่เราต้องการ"],
        read=gh("gw", "auth", tree=True)),
    "oc_mem": dict(
        what="ความจำของ OpenClaw คือไฟล์ Markdown ธรรมดาใน workspace — ไม่มีสถานะซ่อน",
        does=["`USER.md` ความชอบและสไตล์ · `MEMORY.md` ข้อเท็จจริงระยะยาว · `memory/YYYY-MM-DD.md` บันทึกรายวัน",
              "โหลดเข้าบริบทตอนเริ่ม session",
              "ไฟล์ที่ไม่รู้ที่มา (provenance) ถูกกันออก"],
        look="`~/.openclaw/workspace/` · `docs/concepts/memory.md`",
        exam=["แชทของเรา stateless (ไม่มีความจำข้ามรอบ) — ไฟล์ Markdown เป็นวิธีเริ่มที่ง่ายที่สุด และอ่าน/แก้เองได้",
              "ความจำของ Claude Code ที่คุณใช้อยู่ก็เป็นไฟล์ Markdown แบบเดียวกัน"],
        read=gh("oc", "docs/concepts/memory.md")),
    "oc_gw": dict(
        what="หัวใจของ OpenClaw — daemon ตัวเดียวต่อเครื่อง ถือทุกช่องทาง session tool และเหตุการณ์",
        does=["client ทุกตัว (แอป · CLI · เว็บ · automation) ต่อผ่าน WebSocket ด้วยโปรโตคอลที่มี type "
              "(TypeBox → JSON Schema)",
              "ส่งเหตุการณ์ `agent` `chat` `presence` `cron` ให้ทุก client",
              "โมเดลและ agent harness (Claude · Codex · โมเดลในเครื่อง) เป็น plugin สลับได้"],
        look="`docs/concepts/architecture.md` · `docs/gateway/`",
        exam=["เราแยก `/chat/stream` (NDJSON) กับ `/events/stream` (SSE) · OpenClaw ใช้ WebSocket เส้นเดียว แต่บังคับ "
              "idempotency key ให้คำสั่งที่มีผล กันงานซ้ำตอนต่อใหม่ — ปัญหาเดียวกับที่ทำให้เราไม่ใช้ SSE ในแชท"],
        read=gh("oc", "docs/concepts/architecture.md")),
    "le_loop": dict(
        what="ลูป agent ของ Leon 2.0 (TypeScript) — เลือกได้ 3 โหมด",
        does=["`agent` วางแผนทีละขั้น · `controlled` รัน skill แบบกำหนดตายตัว · `smart` เลือกให้เอง",
              "โหลด schema ของ tool ทีละชุดตามงาน (toolkit → tool → function) ประหยัด context",
              "เก็บ trace ทุกขั้น และบัญชี token ต่อ turn"],
        look="`core/brain/brain.ts` · `core/context/ARCHITECTURE.md` (branch develop)",
        exam=["ความคิด controlled mode ตรงกับของเรา: งานที่รู้ขั้นตอนแน่นอน (เช่นสแกนเมล) ไม่ต้องให้ LLM คิด — "
              "ของเราทำแบบนั้นอยู่แล้วแค่ไม่ได้ตั้งชื่อ"],
        read=gh("le", "core/context/ARCHITECTURE.md", ref="develop")),
    "ms_agent": dict(
        what=f"agent ของเรา — Claude Agent SDK บน Pro login · ตัวเดียว ถือ tool ครบ {len(TOOLS)} ตัว",
        does=["หนึ่ง turn ต่อคำขอ (stateless) · stream กลับเป็น NDJSON",
              f"tool จาก {len(TOOL_SERVERS)} MCP server ในตัว: {' · '.join(TOOL_SERVERS)}",
              f"ใช้กับงานเชิงรุกด้วย: เขียนสรุปเช้าตอน {T_BRIEF}",
              f"ตอนนี้ตั้ง `permission_mode=\"{PERMISSION_MODE}\"` — ยังไม่มีด่านอนุมัติ tool"],
        look="`backend/app/agent/secretary.py` — `ask_stream()`",
        exam=["email-agent ใช้ SDK ตัวเดียวกัน — ดูวิธีจัด session ยาวผ่าน WebSocket ของเขาใน `ccsdk/`"],
        read="`docs/map/` (กล่อง ask_stream) · `backend/app/agent/secretary.py`"),
    "ms_mcp": dict(
        what=f"tool ของเราเป็น MCP server แบบ in-process {len(TOOL_SERVERS)} ตัว ห่อ service ที่เขียนเอง",
        does=[f"{' · '.join(TOOL_SERVERS)} — รวม {len(TOOLS)} tool",
              "ขอสิทธิ์ Google เท่าที่ใช้ (Classroom อ่านอย่างเดียว ไม่ขอ course materials)",
              "ไม่มี process แยก — เรียกฟังก์ชัน Python ตรงๆ"],
        look="`backend/app/agent/tools.py` · `classroom_tools.py` · `planner_tools.py` · `gmail_tools.py`",
        exam=["เทียบกับ workspace-mcp: เขาครอบคลุมกว้างกว่ามาก แต่เราคุมสิทธิ์ได้แคบกว่า และมี Classroom ที่เขาไม่มี"],
        read="`backend/app/agent/secretary.py` (`_ALLOWED_TOOLS`)"),
    "kh_search": dict(
        what="Khoj คือ “สมองที่สอง” ที่ค้นเอกสารของคุณ (markdown · org · pdf · notion) ตามความหมาย",
        does=["FastAPI สำหรับ API + Django สำหรับ ORM และหน้าแอดมิน",
              "เก็บ embedding ใน Postgres + pgvector",
              "เข้าได้จากเว็บ · Obsidian · Emacs · desktop · WhatsApp"],
        look="`src/khoj/main.py` · `src/khoj/routers/` · `src/khoj/database/`",
        exam=["ถ้าเลขาจะจำเอกสาร (เช่นสไลด์เรียน) ต้องมี vector store แบบนี้ — แต่ README ของเราตั้งใจให้เรื่องเอกสารเรียน"
              "เป็นอีกโปรเจกต์ (study manager)"],
        read=gh("kh", "src/khoj/main.py")),
    # ---- ④ งานเชิงรุก
    "le_pulse": dict(
        what="ระบบ “ชีพจร” ของ Leon — agent คิดเองว่ามีเรื่องอะไรควรทำ โดยไม่มีใครสั่ง",
        does=["ดูความจำ · การเปลี่ยนแปลงของบริบท · self-model แล้วเขียนเรื่องที่จะทำลง `PULSE.md`",
              "ทำได้ **เรื่องเดียวต่อรอบ**",
              "ถ้าเจ้าของปฏิเสธ จะไม่เสนอเรื่องเดิมซ้ำ"],
        look="ARCHITECTURE.md หัวข้อ Agent Loop (pulse manager)",
        exam=[f"ยืดหยุ่นแต่เปลือง token — ของเราเลือก cron ตายตัววันละ {len(JOBS)} งานเพื่อรักษาโควตา Pro · "
              "ถ้าจะลอง ให้ลอกกฎ “เรื่องเดียวต่อรอบ + จำการปฏิเสธ” มาด้วย"],
        read=gh("le", "core/context/ARCHITECTURE.md", ref="develop")),
    "ga_wf": dict(
        what="workflow ของ GAIA — งานอัตโนมัติที่เริ่มตามเวลา หรือตามเหตุการณ์ (เมลใหม่ · ปฏิทินเปลี่ยน · commit)",
        does=["trigger จาก Composio (gmail · calendar · slack · github …) หรือ cron",
              "ผู้ใช้พิมพ์เป็นประโยค → subagent เขียน workflow ให้",
              "ต่อ integration แล้วมี workflow ตั้งต้นให้ทันที เช่น Inbox desk ที่คัดเมลทุกเช้า"],
        look="`apps/api/app/services/workflow/` — trigger_service.py · scheduler.py · generation_service.py",
        exam=["ตัวอย่างที่เขาโชว์ “นัดบ่ายถูกยกเลิก → จัด to-do ใหม่” ตรงกับ replan ของเรา ซึ่งตอนนี้แค่แนะนำ (suggest-only)"],
        read=gh("ga", "ARCHITECTURE.md") + " (หัวข้อ 10 · Workflows)"),
    "ea_listen": dict(
        what="listener ของ email-agent — สคริปต์ TypeScript ที่ **agent เขียนเอง** แล้วระบบเรียกเมื่อเกิดเหตุการณ์",
        does=["ผู้ใช้: “บอกทันทีถ้าหัวหน้าส่งเมลด่วน” → agent ใช้ tool Write สร้าง `listeners/boss-urgent.ts`",
              "แต่ละไฟล์ export `config` (ฟังเหตุการณ์อะไร) + `handler`",
              "เหตุการณ์: `email_received` · `email_sent` · `scheduled_time` · `email_starred` …"],
        look="`email-agent/agent/custom_scripts/listeners/` · `ccsdk/listeners-manager.ts`",
        exam=["แนวคิดใหญ่: แทนที่จะให้ LLM ตัดสินทุกเมล ให้มันเขียนโค้ดกรองครั้งเดียวแล้วรันฟรีตลอด — "
              "ใช้กับฟีเจอร์แจ้งเตือนของเราได้"],
        read=gh("ea", "email-agent/LISTENERS_SPEC.md")),
    "ms_sched": dict(
        what=f"ตัวจับเวลาของเรา — APScheduler ใน process ของ FastAPI มี cron ตายตัว {len(JOBS)} งาน",
        does=[f"{T_BRIEF} อุ่นสรุปเช้าไว้ (Claude เขียน · แคชวันละครั้ง)",
              f"{T_MAIL} สแกนเมลของวันนี้ด้วยโมเดลในเครื่อง",
              "replan ตอนกลางคืนแค่แนะนำ ไม่แก้ปฏิทินเอง"],
        look="`backend/app/scheduler.py`",
        exam=["Khoj ใช้ APScheduler เหมือนกัน แต่ให้ผู้ใช้สร้างงานเองด้วยประโยค และเก็บงานใน DB (DjangoJobStore) "
              "ให้อยู่รอดหลังรีสตาร์ต"],
        read="`backend/app/scheduler.py`"),
    "oc_auto": dict(
        what="automation ของ OpenClaw — scheduler ในตัวที่เก็บงานถาวร ปลุก agent ตามกำหนด แล้วส่งผลไปที่แชท",
        does=["trigger ได้ 3 แบบ: ตั้งเวลา · webhook · Gmail PubSub",
              "แต่ละงานมี prompt · model · session · ช่องทางส่งผลของตัวเอง",
              "**heartbeat แบบเดิมเลิกใช้แล้ว** — `openclaw doctor --fix` แปลงเป็น automation ธรรมดา"],
        look="`docs/automation/cron-jobs.md` · `docs/gateway/heartbeat.md` (กลายเป็นหน้าวิธีย้าย)",
        exam=["บทเรียน: เขาเคยให้ agent ตื่นเองเป็นระยะ (heartbeat) แล้วเปลี่ยนมาเป็นงานที่มีกำหนดหรือ trigger ชัดเจน — "
              "ทางเดียวกับที่เราเลือกตั้งแต่แรก"],
        read=gh("oc", "docs/automation/cron-jobs.md")),
    "kh_auto": dict(
        what="automation ของ Khoj — ผู้ใช้พิมพ์เป็นประโยค ระบบแปลงเป็น cron + คำถาม แล้วส่งผลทางอีเมล",
        does=["LLM อ่านคำขอ → ได้ `crontime` + คำถามที่จะรัน + หัวข้ออีเมล (`schedule_query`)",
              "ลง APScheduler `CronTrigger` · เก็บงานใน DB ด้วย `DjangoJobStore`",
              "ถึงเวลา → รันแชท → ส่งผลทางอีเมล (Resend) · ไม่รับความถี่ระดับนาที"],
        look="`src/khoj/routers/api_automation.py` · `routers/helpers.py` (`schedule_automation`)",
        exam=["ไลบรารีเดียวกับเรา — ถ้าอยากให้สั่ง “สรุปเมลอาจารย์ให้ทุกศุกร์” ผ่านแชท ลอกสามขั้นนี้ได้เกือบตรงๆ",
              "เขาบล็อกงานทุกนาทีไว้ — เราก็ควรมีเพดานแบบนี้เพื่อโควตา Pro"],
        read=gh("kh", "src/khoj/routers/api_automation.py")),
    # ---- ⑤ อีเมล
    "ea_sdk": dict(
        what="แกนของ email-agent — ห่อ Claude Agent SDK (ตัวเดียวกับเรา) เป็น session ที่คุยกับหน้าเว็บผ่าน WebSocket",
        does=["`session.ts` · `message-queue.ts` จัดคิวข้อความต่อ session",
              "`custom-tools.ts` เพิ่ม tool อีเมล · `email-agent-prompt.ts` คือ system prompt",
              "เขียนไฟล์ listener และ action ให้ผู้ใช้ด้วย tool Write ของ SDK"],
        look="`email-agent/ccsdk/` · `server/` (Bun) · `client/` (React) · `database/` (IMAP → SQLite)",
        exam=["เขาใช้ `ANTHROPIC_API_KEY` (จ่ายตามใช้) · เราใช้ Pro login — ส่วนที่เหลือลอกได้",
              "README เตือนเองว่าเป็น demo: เก็บรหัสผ่านเมลเป็น plain text และไม่มี auth — ห้ามลอกส่วนนั้น"],
        read=gh("ea", "email-agent/ccsdk", tree=True)),
    "ea_actions": dict(
        what="action ของ email-agent — ปุ่มกดครั้งเดียวที่ agent เติมค่าให้ครบ เช่น “ส่งเตือนชำระเงิน ACME ใบที่ 2024-001”",
        does=["template (ไฟล์ .ts) เขียนตามงานจริงของผู้ใช้ ไม่ใช่ “ส่งเมล” กว้างๆ",
              "agent สร้าง instance พร้อมพารามิเตอร์ระหว่างคุย → หน้าเว็บแสดงเป็นปุ่ม",
              "กดแล้ว backend รันทันที · เก็บ log ทุกครั้ง (JSONL)"],
        look="`email-agent/agent/custom_scripts/actions/` · `ccsdk/actions-manager.ts`",
        exam=["เป็นรูปแบบ “อนุมัติด้วยการกด” ที่เข้ากับ M7 — ร่างตอบเมลแล้วแสดงเป็นปุ่ม “ส่ง” ให้กดเอง"],
        read=gh("ea", "email-agent/ACTIONS_SPEC.md")),
    "ms_mail": dict(
        what=f"การอ่านเมลของเรา — โมเดลในเครื่อง ({OLLAMA_MODEL.split('/')[-1]}) สกัดนัดและเส้นตายจากเมลทีละฉบับ",
        does=["เมลไม่ออกจากเครื่อง · ไม่ใช้ token ของ Claude",
              "ได้คำแนะนำเท่านั้น — ปักหมุดอัตโนมัติเฉพาะที่มีวันที่ หรือเป็นนัด / เส้นตาย",
              "อ่านอย่างเดียว (`gmail.readonly`)"],
        look="`backend/app/services/mail_extract.py` · `local_llm.py` · `pins.py`",
        exam=["โปรเจกต์อีเมลอื่นใช้โมเดลบนคลาวด์ทั้งหมด — การส่งงานปริมาณมากไปโมเดลในเครื่องเป็นจุดเด่นของเรา",
              "M7 (ตอบเมล) ควรมีด่านอนุมัติแบบ agents-from-scratch"],
        read="`docs/map/` (กล่อง mail_extract)"),
    "iz_push": dict(
        what="Inbox Zero ไม่วนถามหาเมลใหม่ — Gmail แจ้งเองผ่าน Google Pub/Sub มาที่ webhook",
        does=["สมัคร `watch` กับ Gmail ไว้",
              "มีเมลเข้า → Pub/Sub ยิง `POST /api/google/webhook` (ตรวจ verification token)",
              "อ่าน history ตั้งแต่รอบก่อน แล้วส่งเข้ากฎ"],
        look="`apps/web/app/api/google/webhook/route.ts` · `utils/webhook/google/process-history.ts`",
        exam=["ของเราสแกนวันละครั้ง (poll) — push เร็วระดับวินาที แต่ต้องมี URL HTTPS สาธารณะ แบบเดียวกับ LINE webhook"],
        read=gh("iz", "apps/web/app/api/google/webhook/route.ts")),
    "iz_rules": dict(
        what="กฎอีเมลที่ผู้ใช้เขียนเป็นภาษาคน แล้ว AI เลือกว่าเมลแต่ละฉบับตรงกับกฎไหน",
        does=["เช่น “ใบแจ้งหนี้ → ติดป้าย Finance แล้วเก็บ”",
              "`ai-choose-rule` เลือกกฎ · `ai-choose-args` เติมค่า · `run-rules` ทำ action (ป้าย · archive · ร่างตอบ)",
              "สร้างด้วย Next.js + Prisma (Postgres) + Upstash Redis"],
        look="`apps/web/utils/ai/choose-rule/` · `utils/ai/actions.ts`",
        exam=["แยก “กฎ” (ผู้ใช้เขียน) ออกจาก “การเลือกกฎ” (AI) — ผู้ใช้คุมพฤติกรรมได้โดยไม่ต้องแก้ prompt"],
        read=gh("iz", "apps/web/utils/ai/choose-rule", tree=True)),
    "afs_triage": dict(
        what="ด่านแรกของ email assistant แบบ LangGraph — LLM จัดเมลเป็น 3 กอง",
        does=["`ignore` ทิ้ง · `notify` แจ้งให้คนดู · `respond` ส่งต่อให้ agent ร่างตอบ",
              "เกณฑ์อยู่ใน prompt + ความชอบที่เรียนมา (Store)",
              "รุ่นก่อน (executive-ai-assistant) เขียนเกณฑ์ใน `config.yaml`: triage_no · triage_notify · triage_email"],
        look="`src/email_assistant/email_assistant_hitl_memory_gmail.py` — `triage_router`",
        exam=["mail_extract ของเราคล้าย triage แต่ตอบแค่ว่า “มีนัดไหม” — ถ้าทำ M7 ให้เพิ่มกอง respond"],
        read=gh("afs", "src/email_assistant/email_assistant_hitl_memory_gmail.py")),
    "afs_hitl": dict(
        what="จุดหยุดรอคน (human-in-the-loop) — `interrupt()` ของ LangGraph หยุดกราฟไว้จนกว่าคนจะตอบ",
        does=["หยุดก่อนเรียก `send_email_tool` · `schedule_meeting_tool` · `Question`",
              "คนเลือกได้: accept · edit · ignore · respond (ผ่าน Agent Inbox)",
              "เมลกอง notify ก็หยุดถามเหมือนกัน"],
        look="`interrupt_handler` · `triage_interrupt_handler` ในไฟล์เดียวกัน",
        exam=["นี่คือกฎ M7 ของเรา (“ร่างให้อนุมัติก่อนส่งเสมอ”) ในรูปโค้ด — หยุดเฉพาะ tool ที่ย้อนไม่ได้ "
              "tool อ่านอย่างเดียวผ่านไปเลย"],
        read=gh("afs", "notebooks/hitl.ipynb") + " · `github.com/langchain-ai/agent-inbox`"),
    "afs_store": dict(
        what="ความจำของ email assistant — เก็บความชอบแยก 3 เรื่อง แล้วปรับจากสิ่งที่คนแก้",
        does=["namespace: triage · response · calendar preferences",
              "คนแก้ร่างหรือปฏิเสธ → LLM อัปเดตโปรไฟล์ความชอบ (`update_memory`)",
              "รอบถัดไปใส่โปรไฟล์ลง prompt"],
        look="`get_memory` · `update_memory` + LangGraph `BaseStore`",
        exam=["ถ้าเลขาเราร่างเมลแล้วคุณแก้ทุกครั้ง นี่คือวิธีให้มันเรียนจากการแก้ — เก็บใน SQLite ของเราได้"],
        read=gh("afs", "notebooks/memory.ipynb")),
    "afs_cron": dict(
        what="การดึงเมลของ email assistant — กราฟเล็กที่รันตาม cron ดึงเมลย้อนหลัง N นาที",
        does=["`cron.py` มี `minutes_since` (ค่าเริ่ม 60)",
              "ส่งเมลแต่ละฉบับเข้ากราฟหลัก",
              "บน LangGraph Platform ตั้ง cron ได้ · รันในเครื่องใช้สคริปต์ ingest"],
        look="`src/email_assistant/cron.py` · `tools/gmail/run_ingest.py`",
        exam=["แบบ poll เหมือนของเรา — ต่างจาก Inbox Zero ที่ใช้ push"],
        read=gh("afs", "src/email_assistant/cron.py")),
    # ---- ⑥ วางแผนเวลา
    "sp_ui": dict(
        what="Super Productivity — แอป to-do + จับเวลา + วางแผนวัน แบบ offline-first (Angular · Electron · Android)",
        does=["planner: ลากงานลงวัน · schedule: ไทม์ไลน์ของวันข้างนัดในปฏิทิน",
              "timeboxing + จับเวลาจริง → ทำ timesheet",
              "ข้อมูลอยู่ในเครื่อง (IndexedDB) · sync ผ่าน WebDAV · Dropbox · SuperSync (เข้ารหัส)"],
        look="`src/app/features/planner` · `features/schedule` · `features/time-tracking`",
        exam=["คนวางเอง (ไม่อัตโนมัติ) — ดูไว้เป็นแบบหน้าจอ: ไทม์ไลน์งาน + นัดในวันเดียวกัน คล้ายหน้า Home ของเรา"],
        read=gh("sp", "src/app/features/schedule", tree=True)),
    "sp_issue": dict(
        what="issue provider — ดึงงานที่มอบให้คุณจาก GitHub · GitLab · Jira · Linear … เข้ามาเป็น task",
        does=["หนึ่ง provider ต่อหนึ่งระบบ",
              "นำเข้าอัตโนมัติ แล้ววางแผนรายละเอียดต่อในแอป",
              "CalDAV สำหรับปฏิทิน"],
        look="`src/app/features/issue/providers/`",
        exam=["repos.py ของเราอ่าน git log ตรงๆ — ถ้าอยากรวม issue ของ GitHub ด้วย ทำเป็น provider แบบนี้"],
        read=gh("sp", "src/app/features/issue/providers", tree=True)),
    "ms_planner": dict(
        what="ตัววางแผนของเรา — อัลกอริทึมธรรมดา (ไม่ใช้ token) หาช่องว่างในปฏิทินแล้ววางบล็อกงานก่อนเส้นตาย",
        does=[f"ช่วงทำงาน {PLAN['work_start']:02d}:00–{PLAN['work_end']}:00 · บล็อกละ {PLAN['block_hours']:g} ชม. · "
              f"ไม่เกิน {PLAN['max_hours_per_day']:g} ชม. ต่อวันต่อโปรเจกต์",
              "preview ก่อน → กด commit ถึงลงปฏิทิน",
              "เงื่อนไขซับซ้อน (“เช้าเท่านั้น”) ให้ agent จัดผ่าน `get_free_slots`"],
        look="`backend/app/services/planner.py` · `agent/planner_tools.py`",
        exam=["taskcheck มีสองอย่างที่เราไม่มี: เรียงหลายงานตาม urgency พร้อมกัน และ `--undo` ย้อนรอบล่าสุด"],
        read="`docs/map/` (ภาพจำลอง planner)"),
    "tc_sched": dict(
        what="taskcheck — ตัวจัดตารางแบบไม่ใช้ AI บน Taskwarrior เรียงงานด่วนก่อนแล้ววางลงเวลาว่าง",
        does=["ใช้ urgency · due · dependency + ชั่วโมงทำงานต่อวัน (`time_maps`) · กันเวลาด้วย iCal / Google Calendar",
              "งาน `+agent` คืองานที่ AI ทำ: วางพร้อมกันหลายงาน คิดเฉพาะเวลาที่คุณต้องดูแลด้วย `agent_weight`",
              "เส้นตายไม่ทัน → เตือนและปรับ urgency เอง"],
        look="`taskcheck/` — google_calendar.py · ical.py · dry_run.py · undo.py · timeline.py",
        exam=["`+agent` น่าสนใจสำหรับคุณที่ให้ Claude ทำงานหลายโปรเจกต์: งานที่ AI ทำไม่ได้กินเวลาคุณเต็มชั่วโมง"],
        read=gh("tc")),
    "tc_tw": dict(
        what="Taskwarrior — ที่เก็บงานของ taskcheck และเป็นแหล่งความจริงที่เดียว",
        does=["อ่านงาน pending / waiting พร้อม `estimated`",
              "เขียนกลับ `scheduled` (เริ่มเมื่อไร) · `completion_date` (เสร็จเมื่อไร)",
              "`--dry-run` เก็บแผนแยกไว้ดูโดยไม่แก้งานจริง · `--undo` คืนค่ารอบล่าสุด"],
        look="UDA ของ Taskwarrior: `estimated` · `time_map` · `agent_weight`",
        exam=["ของเราเขียนแผนลง Google Calendar ตรงๆ — ถ้าจะมี undo ต้องจำ id ของ event ที่สร้าง (pins.py ทำแบบนี้อยู่แล้ว)"],
        read=gh("tc", "REFERENCE.md")),
}

# ================================================================ ทัวร์ — อีเมลหนึ่งฉบับผ่านทุกแนวทาง
TOUR = [
    dict(act="รู้ตัว", t="เมลจากอาจารย์เข้ากล่อง Gmail — ใครรู้ก่อน?", n=["iz_push", "afs_cron", "ms_sched"],
         x=f"สามวิธีรู้ว่ามีเมลใหม่: Inbox Zero ให้ Gmail ยิง push มาทันที · agents-from-scratch ไปถามเป็นรอบ · "
           f"ของเรารอรอบสแกน {T_MAIL}"),
    dict(act="รู้ตัว", t="หรือให้ agent เขียนตัวเฝ้าเมลเอง", n=["ea_sdk", "ea_listen"], e=["e_sdk_listen"],
         x="email-agent: ผู้ใช้สั่งครั้งเดียว agent เขียน listener เป็นไฟล์ .ts — หลังจากนั้นทุกเมลผ่านโค้ดกรองโดยไม่ต้องเรียก LLM"),
    dict(act="รู้ตัว", t="OpenClaw · GAIA: เมลเป็นแค่ trigger หนึ่งของระบบอัตโนมัติ",
         n=["oc_auto", "oc_gw", "ga_wf", "ga_exec"], c=["cC", "cD"],
         x="OpenClaw รับ Gmail PubSub เป็น trigger ของ automation แล้วปลุก agent ผ่าน Gateway · GAIA ใช้ trigger ของ "
           "Composio ปลุก workflow ให้ executor ทำ"),
    dict(act="รู้ตัว", t="หรือคุณตั้งเองด้วยประโยค", n=["kh_auto", "kh_search"], e=["e_kauto_search"],
         x="Khoj: “สรุปเมลอาจารย์ให้ทุกศุกร์” → LLM แปลงเป็น crontime + คำถาม → ถึงเวลาก็รัน แล้วส่งผลทางอีเมล"),
    dict(act="คัดแยก", t="ของเรา: โมเดลในเครื่องอ่านทีละฉบับ", n=["ms_sched", "ms_mail"], e=["e_sched_mail"],
         x=f"{T_MAIL} สแกนเมลของวันนี้ด้วย Ollama — ได้รายการนัดและเส้นตาย เมลไม่ออกจากเครื่อง · "
           "เมลอาจารย์มีวันที่ จึงถูกปักหมุดลงปฏิทินอัตโนมัติ"),
    dict(act="คัดแยก", t="ถ้าให้ agent อ่านเมลเอง tool มาจากไหน", n=["ms_agent", "ms_mcp", "gw_tiers", "gw_auth"],
         e=["e_agent_mcp", "e_tiers_auth"],
         x="ของเราเขียน MCP ในตัวเฉพาะที่ใช้ · workspace-mcp เป็น server สำเร็จรูปที่เลือกระดับ tool และโหมด read-only ได้"),
    dict(act="คัดแยก", t="agents-from-scratch: จัดเป็น 3 กอง", n=["afs_cron", "afs_triage"], e=["e_cron_triage"],
         x="ignore · notify · respond — เมลอาจารย์มีเส้นตายและควรตอบรับ → respond"),
    dict(act="คัดแยก", t="Inbox Zero: กฎภาษาคนเป็นคนตัดสิน", n=["iz_push", "iz_rules"], e=["e_push_rules"],
         x="“เมลจากอาจารย์ → ติดป้าย Course แล้วร่างตอบรับ” — ผู้ใช้เขียนกฎ AI เลือกว่าเมลนี้ตรงกฎไหน"),
    dict(act="ร่างและอนุมัติ", t="ร่างตอบแล้วหยุดรอคน", n=["afs_triage", "afs_hitl"], e=["e_triage_hitl"],
         x="interrupt() หยุดก่อน send_email — คุณเลือก accept · edit · ignore · respond"),
    dict(act="ร่างและอนุมัติ", t="คุณแก้ร่าง → ระบบจำไว้", n=["afs_hitl", "afs_store"], e=["e_hitl_store"],
         x="การแก้ถูกสรุปเป็นความชอบ (เช่น “ตอบอาจารย์สุภาพและสั้น”) ร่างครั้งหน้าจึงใกล้ใจขึ้น"),
    dict(act="ร่างและอนุมัติ", t="อีกแบบ: ทำเป็นปุ่มให้กด", n=["ea_sdk", "ea_actions"], e=["e_sdk_actions"],
         x="email-agent สร้าง action ที่เติมค่าครบแล้ว หน้าเว็บแสดงเป็นปุ่มเดียว — กดเมื่อพร้อม"),
    dict(act="ร่างและอนุมัติ", t="ความจำแบบอื่น: ไฟล์ที่อ่านได้ หรือ vector", n=["oc_mem", "oc_gw", "kh_search"],
         e=["e_mem_gw"],
         x="OpenClaw เก็บว่า “อาจารย์คนนี้สอนวิชาอะไร” ไว้ใน MEMORY.md ที่โหลดทุก session · Khoj เก็บเอกสารเป็น vector "
           "ค้นตามความหมาย"),
    dict(act="ลงเวลา", t="เส้นตายต้องมีเวลาทำงาน: ของเราหาช่องว่าง", n=["ms_agent", "ms_mcp", "ms_planner"],
         e=["e_agent_mcp"], c=["cA"],
         x=f"agent เรียก get_free_slots → planner.py วางบล็อกละ {PLAN['block_hours']:g} ชม. ก่อนเส้นตาย "
           "(preview ก่อน แล้วค่อย commit ลงปฏิทิน)"),
    dict(act="ลงเวลา", t="taskcheck: เรียงทุกงานตาม urgency", n=["tc_tw", "tc_sched"], e=["e_tw_sched", "e_sched_tw"],
         x="HW3 แทรกระหว่างงานอื่นตามความด่วน แล้วเขียน scheduled กลับลง Taskwarrior · ย้อนได้ด้วย --undo"),
    dict(act="ลงเวลา", t="Super Productivity: คนวางเอง", n=["sp_issue", "sp_ui"], e=["e_issue_ui"],
         x="งานจาก GitHub / Jira ไหลเข้ามา แล้วคุณลากลงไทม์ไลน์ของวันเอง — ไม่มีอะไรอัตโนมัติ"),
    dict(act="แจ้งคุณ", t="แจ้งเตือนต้องออกไปหาคุณ", n=["ga_exec", "ga_notif"], e=["e_exec_notif"],
         x="GAIA: executor เรียก send_notification → ตัวกระจายเลือกช่องทางตามที่คุณตั้งไว้"),
    dict(act="แจ้งคุณ", t="ออกทาง LINE / Discord", n=["ga_notif", "ga_bots", "oc_channels", "ai_server"],
         x="GAIA ส่งผ่านบอตของแต่ละแพลตฟอร์ม · OpenClaw ส่งผ่าน channel plugin บน Gateway · "
           "AIRI ให้บอตเป็น module บน server-runtime"),
    dict(act="แจ้งคุณ", t="คุณตอบกลับในแชท → กลับเข้าสมอง", n=["ga_bots", "ga_comms", "oc_channels", "oc_pair", "oc_gw"],
         e=["e_bots_comms", "e_ch_gw"],
         x="ข้อความขาเข้าต้องผ่านด่าน: OpenClaw ให้จับคู่ผู้ส่งก่อน (pairing) — ไม่งั้นใครก็สั่งเลขาได้"),
    dict(act="แจ้งคุณ", t="ของเรา: ยังเป็นแผนใน feature.md", n=["ms_notify_plan", "ga_notif"], e=["e_plan_notif"],
         x=f"รวมแจ้งเตือน {CH_LIST} — โครงที่ใกล้ที่สุดคือ adapter + ตัวกระจายของ GAIA (ดูภาพ “รวมแจ้งเตือน”)"),
    dict(act="เล่าให้ฟัง", t="agent ต่อท้ายอารมณ์", n=["ms_agent", "ms_mood"], c=["cB"],
         x=f"<mood>{TOUR_MOOD[0]}:{TOUR_MOOD[1]}</mood> — เส้นตายใกล้ ตัวละครทำหน้ากังวลแล้วชี้"),
    dict(act="เล่าให้ฟัง", t="สร้างเสียง แล้วขยับปาก", n=["ms_mood", "ms_tts", "ms_vrm"], e=["e_mood_vrm", "e_tts_vrm"],
         x=f"Kokoro sidecar สร้าง WAV → หน้าเว็บแยก 3 ย่าน (<{LIP_CUTS[0]} Hz · กลาง · >{LIP_CUTS[1]} Hz) "
           "เป็นปาก ou · aa · ih"),
    dict(act="เล่าให้ฟัง", t="Amica: อารมณ์ทีละประโยค", n=["am_screen", "am_queue", "am_vrm"],
         e=["e_screen_queue", "e_queue_vrm"],
         x="แต่ละประโยคมีแท็กอารมณ์ของตัวเอง · สร้างเสียงประโยคถัดไปไว้ก่อนระหว่างพูด · ปากขยับตามความดัง"),
    dict(act="เล่าให้ฟัง", t="Open-LLM-VTuber · AIRI: เปลี่ยนเครื่องเสียงได้",
         n=["olv_emo", "olv_factory", "ai_unspeech", "ai_stage"], e=["e_emo_fac", "e_uns_stage"],
         x="OLV เลือก TTS ใน conf.yaml · AIRI เรียก endpoint เดียวแล้ว unspeech เลือกผู้ให้บริการให้ · "
           "ปากของ AIRI ขยับตามสระที่ตรวจได้"),
    dict(act="เล่าให้ฟัง", t="หรือโทรคุยกับเลขา", n=["ga_voice", "ga_comms"], e=["e_voice_comms"],
         x="GAIA แยกเสียงเป็น worker (LiveKit) ที่แปลงเสียง ↔ ข้อความ แล้วส่งเข้าสมองตัวเดิม — เสียงเป็นแค่อีกช่องทางหนึ่ง"),
    dict(act="เล่าให้ฟัง", t="ถ้าคุณเงียบไปนาน", n=["am_life", "am_screen", "le_pulse", "le_loop"],
         e=["e_life_screen", "e_pulse_loop"],
         x="Amica หาเรื่องคุยเอง · Leon ใช้ pulse คิดงานเอง — เลขาเราเลือกไม่ทำ เพื่อรักษาโควตา Pro"),
    dict(act="ปิดวง", t="ของเราอยู่ตรงไหนในภาพรวม",
         n=["ms_sched", "ms_mail", "ms_agent", "ms_planner", "ms_mood", "ms_notify_plan"],
         x="มีครบทุกคอลัมน์ ยกเว้นช่องทางแชท · ก้าวถัดไปที่โปรเจกต์อื่นพิสูจน์แล้ว: ด่านอนุมัติของ M7 (interrupt / ปุ่ม action) "
           "และ adapter + pairing สำหรับ feature.md"),
]

# ================================================================ คู่ที่มักสับสน = สองวิธีแก้ปัญหาเดียวกัน
PAIRS = [
    ("แท็ก <mood>", "screenplay [happy]", ["ms_mood", "am_screen"],
     "ทั้งคู่ให้ LLM ใส่อารมณ์ไว้ในข้อความแล้วแยกออกทีหลัง · ของเรา **แท็กเดียวต่อคำตอบ** · Amica **แท็กต่อประโยค** "
     "เปลี่ยนสีหน้าได้ทุกประโยค"),
    ("ปาก 3 ย่าน", "ความดัง → aa", ["ms_vrm", "am_vrm", "ai_stage"],
     "Amica อ่านความดังสดแล้วขยับปาก **ท่าเดียว** · ของเราคำนวณซองปาก **ล่วงหน้า** แยกต่ำ / กลาง / สูงเป็น 3 ท่า · "
     "AIRI ไปไกลกว่าคือ **ตรวจสระ** AEIOU"),
    ("Kokoro sidecar", "unspeech", ["ms_tts", "ai_unspeech"],
     "ทั้งคู่ซ่อนเครื่องสร้างเสียงไว้หลัง endpoint · sidecar ของเรามี **ผู้ให้บริการเดียว** · unspeech **สลับได้ทุกเจ้า** "
     "ทั้ง ASR และ TTS"),
    ("channel plugins", "bot adapters", ["oc_channels", "ga_bots"],
     "OpenClaw ให้ **Gateway เดียวเปิดทุกช่องทาง** (plugin อยู่ในตัว) · GAIA แยก **บอตเป็นแอปต่อแพลตฟอร์ม** แล้วยิง HTTP "
     "เข้า backend — แบบหลังเข้ากับ FastAPI ของเราง่ายกว่า"),
    ("Comms agent", "Executor", ["ga_comms", "ga_exec"],
     "Comms **คุยแต่ไม่ทำ** (tool น้อย) · Executor **ทำแต่ไม่คุย** (tool ครบ) — แยกเพื่อให้บทสนทนาไม่สะดุดระหว่างงานยาว"),
    ("ask_stream()", "ccsdk session", ["ms_agent", "ea_sdk"],
     "**SDK ตัวเดียวกัน** (Claude Agent SDK) · ของเรา **stateless** หนึ่ง turn ต่อคำขอผ่าน Pro login · demo ถือ "
     "**session ยาว** ผ่าน WebSocket และใช้ API key"),
    ("MCP ในตัว", "tool tiers", ["ms_mcp", "gw_tiers"],
     "ของเรา **เขียน tool เอง** เฉพาะที่ใช้ (แคบ คุมสิทธิ์ง่าย มี Classroom) · workspace-mcp เป็น **server สำเร็จรูป** "
     "120+ tool เลือกระดับได้ (กว้าง ไม่มี Classroom)"),
    ("MEMORY.md", "Store ความชอบ", ["oc_mem", "afs_store"],
     "OpenClaw จำ **ข้อเท็จจริงทั่วไป** เป็นไฟล์ที่อ่านได้ · email assistant จำ **ความชอบเฉพาะงาน** (คัด · ตอบ · นัด) "
     "ที่เรียนจากการแก้"),
    ("cron ตายตัว", "pulse ของ Leon", ["ms_sched", "le_pulse"],
     "cron = **คนกำหนด** ว่าทำอะไรเมื่อไร · pulse = **agent คิดเอง** ว่ามีเรื่องอะไรควรทำ — อย่างหลังยืดหยุ่นกว่า "
     "แต่เปลือง token และต้องมีเพดาน"),
    ("listener ที่ agent เขียน", "workflow ของ GAIA", ["ea_listen", "ga_wf"],
     "ทั้งคู่สร้างงานอัตโนมัติจากประโยคของผู้ใช้ · email-agent ได้ **ไฟล์โค้ด** ที่รันได้โดยไม่ต้องใช้ LLM · GAIA ได้ "
     "**workflow ที่ agent รัน** ทุกครั้ง"),
    ("Gmail push", "cron ingest", ["iz_push", "afs_cron"],
     "push = **Gmail บอกเรา** ทันทีที่มีเมล (ต้องมี URL สาธารณะ) · poll = **เราไปถาม** เป็นรอบ (ง่าย รันในเครื่องได้) — "
     "ของเราอยู่ฝั่ง poll"),
    ("interrupt()", "action (ปุ่มกด)", ["afs_hitl", "ea_actions"],
     "ทั้งคู่ให้คนอนุมัติก่อนทำ · interrupt **หยุดกราฟกลางทาง** รอคำตอบ · action **เตรียมเสร็จเป็นปุ่ม** ให้กดทีหลัง"),
    ("planner.py", "taskcheck", ["ms_planner", "tc_sched"],
     "ไม่ใช้ LLM ทั้งคู่ · ของเรา **วางทีละโปรเจกต์** ลงช่องว่าง · taskcheck **เรียงทุกงานตาม urgency** "
     "แล้ววางพร้อมกัน + undo ได้"),
]


# ================================================================ ภาพเทียบแนวทาง
def fig_trigger():
    """ใครเป็นคนตัดสินว่าจะเริ่มงาน — สามกลุ่ม เรียงจากคุมง่ายไปยืดหยุ่น"""
    d = Draw(1000, 384, topic="plat", aria="กลไกที่ทำให้ agent เริ่มงานเอง แบ่งเป็นสามกลุ่ม")
    zones = [  # (ขั้น, x, หัว, คำอธิบาย, [(หัว, รายละเอียด, topic)])
        (1, 20, "ตามเวลา", "คนกำหนดเวลา", [
            ("my_secretary", f"cron ตายตัว {T_BRIEF} · {T_MAIL}", "ours"),
            ("Khoj", "ประโยค → crontime", "plat"),
            ("OpenClaw", "automation ตั้งเวลา", "plat"),
            ("agents-from-scratch", "ดึงเมลย้อนหลังทุกรอบ", "mail")]),
        (2, 350, "ตามเหตุการณ์", "โลกภายนอกส่งสัญญาณ", [
            ("Inbox Zero", "Gmail push → webhook", "mail"),
            ("OpenClaw", "webhook · Gmail PubSub", "plat"),
            ("GAIA", "trigger: เมลใหม่ · ปฏิทินเปลี่ยน", "plat"),
            ("email-agent", "listener ที่ agent เขียนเอง", "mail")]),
        (3, 680, "agent คิดเอง", "ไม่มีใครสั่ง", [
            ("Leon", "pulse → PULSE.md · เรื่องเดียวต่อรอบ", "plat"),
            ("Amica", "ผู้ใช้เงียบนาน → หาเรื่องคุย", "char")]),
    ]
    every = (1, 2, 3)
    for k, x, head, sub, items in zones:
        d.rect(x, 14, 300, 302, cls="fcW", s=every)
        d.text(x + 14, 40, head, "ftB", s=every)
        d.text(x + 14, 60, sub, "fsm", s=every)
        d.step_badge(x + 282, 34, k)
        for i, (name, what, topic) in enumerate(items):
            d.tbox(x + 12, 74 + i * 60, 276, 50, f"{name}\n{what}", cls=f"fc-{topic}", s=(k,))
    d.line([(30, 342), (970, 342)], cls="flA", s=every)
    d.text(30, 368, "คุมง่าย · ประหยัด token", "fsm", s=every)
    d.text(970, 368, "ยืดหยุ่น · เปลือง token · คุมยาก", "fsm", anchor="end", s=every)
    return d


def fig_hitl():
    """email assistant ของ agents-from-scratch: เมลหนึ่งฉบับ → triage → ร่าง → หยุดรอคน → ส่ง / จำ"""
    def chip(i, x, y, name, gloss="", w=200, h=56, topic="mail", steps=()):
        return N(i, x, y, name, gloss, kind="chip", topic=topic, w=w, h=h, steps=steps)
    nodes = [  # แถวบน = ทางหลักของเมล · แถวกลาง = ทางแยก · แถวล่าง = ความจำ (ห่างกัน ≥ 90 ให้ป้ายเส้นวางได้)
        chip("h_mail", 20, 64, "เมลใหม่", "จาก cron ingest", w=140, steps=(1,)),
        chip("h_tri", 250, 64, "triage", "ignore · notify · respond", steps=(1, 2)),
        chip("h_agent", 540, 64, "ร่างตอบ", "response agent", w=170, steps=(2, 3)),
        chip("h_gate", 800, 64, "interrupt()", "ก่อนส่งเมล · นัดประชุม", w=180, topic="safe", steps=(3,)),
        chip("h_ign", 20, 200, "ignore", "จบ ไม่ทำอะไร", w=140, steps=(1,)),
        chip("h_ntf", 250, 200, "notify", "หยุดถามคนก่อน", steps=(1,)),
        chip("h_ok", 800, 200, "accept / edit", "ส่งจริง (ฉบับแก้ถ้าแก้)", w=180, steps=(3, 4)),
        chip("h_mem", 540, 330, "update_memory", "เรียนจากที่คนแก้", w=190, steps=(4,)),
    ]
    edges = [
        E("h1", "h_mail", "h_tri", "1 ฉบับ", kind="data", steps=(1,)),
        E("h2", "h_tri", "h_ign", "ignore", sp="s@0.15", dp="n@0.5", lside="l", lseg=0, steps=(1,)),
        E("h3", "h_tri", "h_ntf", "notify", sp="s@0.6", dp="n@0.6", lside="r", steps=(1,)),
        E("h4", "h_tri", "h_agent", "respond", steps=(2,)),
        E("h5", "h_agent", "h_gate", "จะส่งเมล", steps=(3,)),
        E("h6", "h_gate", "h_ok", "accept · edit", sp="s@0.5", dp="n@0.5", lside="r", lw=80, steps=(3,)),
        E("h7", "h_gate", "h_agent", "respond: ร่างใหม่", kind="sig", sp="n@0.3", dp="n@0.7",
          via=(("y", 30),), steps=(3,)),
        E("h8", "h_ok", "h_mem", "ถ้าแก้ → จำ", kind="data", sp="s@0.5", dp="e@0.5", via=(("y", 358),), steps=(4,)),
        E("h9", "h_mem", "h_tri", "ใช้รอบหน้า", kind="data", sp="w@0.5", dp="s@0.85",
          via=(("x", 470), ("y", 165), ("x", 420)), lside="r", lt=0.35, steps=(4,)),
    ]
    return Graph(1000, 410, nodes, edges, aria="ทางเดินของเมลหนึ่งฉบับใน email assistant ที่มีด่านอนุมัติ")


def fig_notify():
    """ข้อเสนอสำหรับ feature.md — ประกอบจากชิ้นที่โปรเจกต์ต้นแบบใช้จริง"""
    def chip(i, x, y, name, gloss="", w=190, h=56, topic="ours", steps=()):
        return N(i, x, y, name, gloss, kind="chip", topic=topic, w=w, h=h, steps=steps)
    nodes = [
        chip("n_line", 20, 20, "LINE", "webhook HTTPS", w=150, topic="plat", steps=(1,)),
        chip("n_disc", 20, 100, "Discord", "บอต (gateway)", w=150, topic="plat", steps=(1,)),
        chip("n_gmail", 20, 180, "Gmail", "push หรือ poll", w=150, topic="mail", steps=(1,)),
        chip("n_adapt", 240, 100, "adapter ต่อช่องทาง", "แปลงเป็นรูปแบบเดียว (GAIA)", w=200, topic="plat", steps=(1, 2)),
        chip("n_pair", 510, 100, "ตรวจผู้ส่ง", "pairing (OpenClaw)", w=170, topic="safe", steps=(2,)),
        chip("n_hub", 750, 100, "กล่องรวมแจ้งเตือน", "SQLite · อ่านแล้ว / ยัง", w=220, steps=(3,)),
        chip("n_rule", 750, 260, "กรองก่อนถึง LLM", "กฎ / listener (IZ · email-agent)", w=220, topic="mail", steps=(3,)),
        chip("n_agent", 510, 260, "สรุปด้วย agent", "เฉพาะที่ผ่านกรอง", w=170, steps=(4,)),
        chip("n_out", 240, 260, "ตัวกระจายขาออก", "เลือกช่องทางตอบ (GAIA)", w=200, topic="plat", steps=(4,)),
        chip("n_char", 20, 290, "ตัวละครเล่า", "หน้าเว็บของเรา", w=150, steps=(4,)),
    ]
    edges = [
        E("m1", "n_line", "n_adapt", "", kind="data", sp="e", dp="w@0.25", steps=(1,)),
        E("m2", "n_disc", "n_adapt", "", kind="data", steps=(1,)),
        E("m3", "n_gmail", "n_adapt", "", kind="data", sp="e", dp="w@0.75", steps=(1,)),
        E("m4", "n_adapt", "n_pair", "รูปแบบเดียว", kind="data", steps=(2,)),
        E("m5", "n_pair", "n_hub", "ผ่าน", kind="data", steps=(2, 3)),
        E("m6", "n_hub", "n_rule", "ของใหม่", kind="data", lside="r", steps=(3,)),
        E("m7", "n_rule", "n_agent", "เรื่องสำคัญ", kind="data", steps=(4,)),
        E("m8", "n_agent", "n_out", "สรุป", kind="data", steps=(4,)),
        E("m9", "n_out", "n_char", "เล่า", kind="data", sp="w@0.75", dp="e@0.5", steps=(4,)),
    ]
    return Graph(1000, 370, nodes, edges, aria="ข้อเสนอโครงรวมแจ้งเตือนหลายช่องทาง ประกอบจากโปรเจกต์ต้นแบบ")


GROUPS = [
    dict(id="g-design", short="แนวทาง", title="สามคำถามที่โปรเจกต์แนวนี้ต้องตอบ", sub="ภาพเทียบ",
         chapters=[
             dict(id="ch-trigger", num="1", nav="ใครปลุก agent", title="ใครเป็นคนเริ่มงาน", topic="plat",
                  q=("ms", "kh", "oc", "iz", "ea", "ga", "le", "am", "afs"),
                  thesis="ทุกโปรเจกต์ใช้กลไกไม่กี่แบบซ้ำกัน — ต่างกันแค่ว่าอำนาจตัดสินว่าจะเริ่มอยู่ที่คน ที่โลกภายนอก หรือที่ agent",
                  figs=[dict(id="f-trigger", title="สามกลุ่มของงานเชิงรุก", draw=fig_trigger,
                             caption="ซ้ายไปขวา = อำนาจตัดสินย้ายจากคนไปที่ agent · สีกรอบ = กลุ่มของโปรเจกต์",
                             steps=[("ตามเวลา", "คนเป็นคนเขียนเวลา (ตายตัว หรือแปลงจากประโยค)"),
                                    ("ตามเหตุการณ์", "Gmail · webhook · การเปลี่ยนแปลงในระบบอื่นเป็นตัวปลุก"),
                                    ("agent คิดเอง", "agent ตัดสินเองว่ามีเรื่องอะไรควรทำ")],
                             story=dict(
                                 problem="ผู้ช่วยที่รอให้สั่งอย่างเดียวยังไม่ใช่เลขา — ต้องเริ่มงานเองได้ แต่ทุกครั้งที่เริ่มเอง"
                                         "คือ token ที่ใช้ไปโดยไม่มีใครขอ",
                                 think="แยกตามว่าใครตัดสินว่าจะเริ่ม: คนตั้งเวลา · โลกภายนอกส่งเหตุการณ์ · หรือ agent คิดเอง",
                                 choose="วางทุกโปรเจกต์ลงสามกลุ่มนี้ เรียงจากคุมง่ายไปยืดหยุ่น เพราะกลไกจริงมีไม่กี่แบบ "
                                        "และแต่ละแบบมีต้นทุนต่างกันชัดเจน",
                                 read="ซ้ายไปขวา = อำนาจตัดสินย้ายจากคนไปที่ agent · กด “ทีละขั้น” เพื่อดูทีละกลุ่ม",
                                 result=f"ของเราอยู่ซ้ายสุด: {len(JOBS)} งานตายตัว ({T_BRIEF} · {T_MAIL}) · OpenClaw เคยมี "
                                        "heartbeat (กลุ่มขวา) แล้วเปลี่ยนมาเป็น automation (กลุ่มซ้ายและกลาง)",
                                 mean="ก้าวต่อไปที่ปลอดภัยของเราคือกลุ่มกลาง (push · listener) ไม่ใช่ pulse — "
                                      "ได้ความเร็วโดยไม่เผาโควตา Pro"),
                             traps=["“ตามเหตุการณ์” ไม่ได้แปลว่าถูก — ถ้าทุกเมลปลุก LLM ก็เปลืองพอกัน · email-agent "
                                    "เลี่ยงด้วยการให้ listener เป็นโค้ดกรองก่อน"],
                             onmap=["ms_sched", "kh_auto", "oc_auto", "iz_push", "ea_listen", "le_pulse"])]),
             dict(id="ch-hitl", num="2", nav="ร่างก่อน ส่งทีหลัง", title="ร่างก่อน ส่งทีหลัง", topic="mail",
                  q=("afs", "eaia", "ea"),
                  thesis="หยุดรอคนเฉพาะตรงที่ย้อนไม่ได้ (ส่งเมล · นัดประชุม) — ที่เหลือปล่อยให้ agent ทำต่อ",
                  figs=[dict(id="f-hitl", title="เมลหนึ่งฉบับใน email assistant ที่มีด่านอนุมัติ", draw=fig_hitl,
                             caption="ซ้ายไปขวาคือทางของเมล · กล่องแดงคือจุดหยุดรอคน · เส้นประย้อนกลับคือการสั่งให้ร่างใหม่",
                             steps=[("คัดแยก", "triage แบ่งเป็น ignore · notify · respond"),
                                    ("ร่าง", "กอง respond ไปให้ agent ร่างตอบ"),
                                    ("หยุดรอคน", "ก่อนเรียก tool ส่งเมล กราฟหยุดรอ accept · edit · ignore · respond"),
                                    ("เรียนรู้", "การแก้ของคนกลายเป็นความชอบที่ใช้รอบหน้า")],
                             story=dict(
                                 problem="agent ที่ส่งเมลแทนเราได้ ถ้าส่งผิดครั้งเดียวก็เรียกคืนไม่ได้ — M7 ของเราจึงตั้งกฎ"
                                         "ว่าต้องอนุมัติก่อนส่งเสมอ",
                                 think="ไม่ต้องหยุดทุกขั้น หยุดเฉพาะ tool ที่มีผลออกไปนอกระบบ (ส่งเมล · นัด) "
                                       "ที่เหลือให้ทำงานต่อ",
                                 choose="agents-from-scratch ใช้ interrupt() ของ LangGraph: กราฟหยุด เก็บสถานะ แล้วรอคำตอบ "
                                        "4 แบบ — ไม่ต้องเขียนระบบรอเอง",
                                 read="ซ้ายไปขวาคือทางของเมลหนึ่งฉบับ · กล่องแดงคือจุดหยุดรอคน · "
                                      "เส้นล่างคือการแก้ที่ย้อนกลับไปเป็นความจำ",
                                 result="คนเห็นทุกฉบับก่อนออก · การแก้ทุกครั้งกลายเป็นความชอบใน Store ร่างครั้งหน้าจึงดีขึ้น",
                                 mean=f"ของเราใช้ Agent SDK ซึ่งไม่มี interrupt() แบบนี้ — ทำได้สองทาง: ให้ tool แค่สร้าง "
                                      "draft แล้วหน้าเว็บมีปุ่มส่ง (แบบ actions ของ email-agent) หรือใช้ callback "
                                      f"`can_use_tool` ของ SDK (ตอนนี้ secretary.py ตั้ง `{PERMISSION_MODE}` ไว้)"),
                             traps=["อย่าหยุดทุก tool — คนจะกด accept รัวๆ จนไม่ได้อ่าน · หยุดเฉพาะที่ย้อนไม่ได้"],
                             onmap=["afs_triage", "afs_hitl", "afs_store", "ea_actions"])]),
             dict(id="ch-notify", num="3", nav="รวมแจ้งเตือน", title="รวมแจ้งเตือนหลายช่องทาง", topic="ours",
                  q=("ms", "ga", "oc", "ea", "iz"),
                  thesis=f"feature.md ({CH_LIST}) ประกอบได้จากชิ้นที่โปรเจกต์อื่นใช้จริง — แปลงทุกช่องทางเป็นรูปแบบเดียว "
                         "ตรวจผู้ส่ง เก็บ กรอง แล้วค่อยให้ LLM เห็น",
                  figs=[dict(id="f-notify", title="ข้อเสนอโครงรวมแจ้งเตือน (ยังไม่มีโค้ด)", draw=fig_notify,
                             caption="ภาพข้อเสนอ ไม่ใช่โค้ดที่มีอยู่ · แถวบนคือขาเข้า (ซ้าย → ขวา) แถวล่างคือขาออก "
                                     "(ขวา → ซ้าย) · วงเล็บบอกว่าชิ้นนั้นลอกแบบมาจากใคร",
                             steps=[("ขาเข้า", "แต่ละช่องทางมี adapter ของตัวเอง แปลงเป็นรูปแบบเดียว"),
                                    ("ตรวจผู้ส่ง", "ข้อความจากคนที่ไม่รู้จักไม่ผ่านไปถึงเลขา"),
                                    ("เก็บและกรอง", "เก็บทุกอย่างลง SQLite แล้วกรองด้วยกฎ/โค้ดก่อน"),
                                    ("ขาออก", "เฉพาะเรื่องสำคัญถึง LLM แล้วเลือกช่องทางแจ้งคุณ")],
                             story=dict(
                                 problem=f"feature.md อยากรวมแจ้งเตือนจาก {CH_LIST} ไว้ที่เดียว — แต่ละช่องทางส่งข้อมูลมา"
                                         "คนละรูปแบบ และข้อความจากข้างนอกเชื่อไม่ได้",
                                 think="ประกอบจากชิ้นที่พิสูจน์แล้ว: adapter ของ GAIA · pairing ของ OpenClaw · "
                                       "กรองด้วยกฎ/โค้ดแบบ Inbox Zero และ email-agent · ตัวกระจายขาออกของ GAIA",
                                 choose="แปลงทุกช่องทางเป็นรูปแบบเดียวก่อน แล้วค่อยเก็บ กรอง สรุป — ถูกที่สุด "
                                        "เพราะ LLM เห็นแค่ของที่ผ่านกรอง",
                                 read="แถวบนคือขาเข้า · แถวล่างคือขาออก · กล่องแดงคือด่านตรวจ · วงเล็บคือต้นแบบ",
                                 result="เป็นข้อเสนอ ยังไม่มีโค้ด · ทุกกล่องมีต้นแบบให้เปิดดูบนแผนที่",
                                 mean="เรื่องที่ต้องตัดสินก่อนเริ่ม: LINE ต้องมี URL HTTPS สาธารณะ แต่ backend ตอนนี้เปิด"
                                      "แค่ในเครื่อง — ต้องเลือกระหว่างเปิด tunnel หรือย้ายไปรันบนเซิร์ฟเวอร์"),
                             traps=["บอต LINE (Messaging API) รับได้เฉพาะข้อความที่ส่งถึงบัญชีบอต ไม่เห็นแชทส่วนตัวของคุณ",
                                    "บอต Discord เห็นเฉพาะเซิร์ฟเวอร์ที่บอตอยู่และ DM ถึงบอต — การแจ้งเตือนของบัญชีคุณเอง"
                                    "ดึงผ่านบอตไม่ได้ · “ทุกแจ้งเตือน” จึงต้องนิยามใหม่ให้เป็นของที่ส่งถึงเลขา"],
                             onmap=["ga_bots", "oc_pair", "ga_notif", "ea_listen", "iz_rules", "ms_notify_plan"])]),
         ]),
]

# ================================================================ ส่วนเสริม: ลิงก์ GitHub กดได้ · กล่องที่ยังเป็นแผนใช้เส้นประ
EXTRA_CSS = """
a.ghlink { color: inherit; }
a.ghlink > code { text-decoration: underline; text-underline-offset: 2px; }
#n-ms_notify_plan .n-box { stroke-dasharray: 6 4; }
/* ชื่อโปรเจกต์ (ป้ายมุมการ์ด) ซ้ำกับป้ายปุ่มกรองที่มีสีอยู่แล้ว — ซ่อนตัวที่ไม่มีสี
   แค็ตตาล็อก: [ชื่อ][ปุ่มกรอง…] · แผงข้าง: [ชั้น][ชื่อ][ปุ่มกรอง…] */
.cat .chips > .chip:not(.q):first-child,
.chips > .chip:not(.q) + .chip:not(.q) { display: none; }
"""

EXTRA_JS = r"""
(function () {
  // ข้อความ `github.com/...` ในแผงข้าง · แค็ตตาล็อก · การ์ด → ลิงก์เปิดแท็บใหม่
  // แผงข้างถูกสร้างใหม่ทุกครั้งที่กดกล่อง จึงต้องเฝ้าการเปลี่ยนแปลงของหน้า (MutationObserver)
  var RE = /^github\.com\/[\w.-]+\/[\w.-]+/;
  function linkify(root) {
    var list = root.matches && root.matches('code') ? [root] : root.querySelectorAll ? root.querySelectorAll('code') : [];
    Array.prototype.forEach.call(list, function (c) {
      if (c.dataset.gh || c.closest('a')) return;
      var t = c.textContent.trim();
      if (!RE.test(t)) return;
      c.dataset.gh = '1';
      var a = document.createElement('a');
      a.href = 'https://' + t; a.target = '_blank'; a.rel = 'noopener'; a.className = 'ghlink';
      c.parentNode.insertBefore(a, c); a.appendChild(c);
    });
  }
  linkify(document);
  new MutationObserver(function (ms) {
    ms.forEach(function (m) { Array.prototype.forEach.call(m.addedNodes, function (n) { if (n.nodeType === 1) linkify(n); }); });
  }).observe(document.body, { childList: true, subtree: true });
})();
"""
