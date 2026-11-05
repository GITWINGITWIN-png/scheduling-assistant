"""ภาพสัญลักษณ์ "หน้าตา" ของแต่ละกล่อง (กรอบ 56 × 56 หน่วย)

หลักการวาด: ภาพต้องบอก "รูปร่างจริง" ของสิ่งนั้น ไม่ใช่แค่ไอคอนตกแต่ง
    - ของจริงที่จับต้องได้ → วาดรูปชิ้นส่วนจริง (ชิปมีขา, จานดิสก์มีแขนหัวอ่าน, RAM มีชิปและขาทอง)
    - ซอฟต์แวร์ / แนวคิด → วาดโครงสร้างข้อมูลหรือรูปทรงของมัน (ตาราง, คิว, ต้นไม้, log, สมการ, กราฟ)
ชุดแรก (ICONS เดิม) มาจากแผนที่ OS: ฮาร์ดแวร์ · หน่วยความจำ · ระบบไฟล์ · I/O · ความปลอดภัย
ชุดทั่วไป (ICONS.update ด้านล่าง) ใช้กับวิชาหรือโปรเจกต์อื่น: ไฟล์ · โค้ด · ข้อมูล · การไหล · คน · วิทยาศาสตร์
ดูทุกไอคอนพร้อมชื่อ: python3 scripts/icon_gallery.py → เปิดไฟล์ HTML ที่ได้ · เพิ่มของวิชาเองด้วย register() หรือ ICONS ใน spec

สีทั้งหมดมาจาก class (ผูกกับ CSS token ใน page.py) จึงเปลี่ยนตามธีมสว่าง/มืดและสีของหมวด:
    i-s เส้นหมึก · i-b กล่องสีกระดาษ · i-a กล่องสีอ่อนของหมวด · i-A สีเข้มของหมวด
    i-k จุดสีหมึก · i-t ตัวอักษรเล็ก · i-ta ตัวอักษรเล็กสีหมวด
"""


def _pins(x0, x1, y_top, y_bot, n=4):
    """ขาชิปด้านบน/ล่าง"""
    step = (x1 - x0) / (n - 1)
    out = []
    for i in range(n):
        x = x0 + i * step
        out.append(f'<line class="i-s" x1="{x:.1f}" y1="{y_top[0]}" x2="{x:.1f}" y2="{y_top[1]}"/>')
        out.append(f'<line class="i-s" x1="{x:.1f}" y1="{y_bot[0]}" x2="{x:.1f}" y2="{y_bot[1]}"/>')
    return "".join(out)


def _pins_side(y0, y1, x_l, x_r, n=4):
    step = (y1 - y0) / (n - 1)
    out = []
    for i in range(n):
        y = y0 + i * step
        out.append(f'<line class="i-s" x1="{x_l[0]}" y1="{y:.1f}" x2="{x_l[1]}" y2="{y:.1f}"/>')
        out.append(f'<line class="i-s" x1="{x_r[0]}" y1="{y:.1f}" x2="{x_r[1]}" y2="{y:.1f}"/>')
    return "".join(out)


def _cyl(x, y, w, h, cls="i-b"):
    """ทรงกระบอก (ดิสก์ / ที่เก็บข้อมูล)"""
    ry = 4
    return (f'<path class="{cls}" d="M{x},{y + ry} V{y + h - ry} A{w / 2},{ry} 0 0 0 {x + w},{y + h - ry}'
            f' V{y + ry} A{w / 2},{ry} 0 0 0 {x},{y + ry} Z"/>'
            f'<ellipse class="{cls}" cx="{x + w / 2}" cy="{y + ry}" rx="{w / 2}" ry="{ry}"/>')


def _doc(x, y, w, h, cls="i-b"):
    """แผ่นเอกสารพับมุม"""
    f = 7
    return (f'<path class="{cls}" d="M{x},{y} H{x + w - f} L{x + w},{y + f} V{y + h} H{x} Z"/>'
            f'<path class="i-s" d="M{x + w - f},{y} V{y + f} H{x + w}"/>')


def _arrow(x1, y1, x2, y2, cls="i-s"):
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    a1, a2 = ang + 2.6, ang - 2.6
    hx1, hy1 = x2 + 5 * math.cos(a1), y2 + 5 * math.sin(a1)
    hx2, hy2 = x2 + 5 * math.cos(a2), y2 + 5 * math.sin(a2)
    return (f'<line class="{cls}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>'
            f'<path class="{cls}" d="M{hx1:.1f},{hy1:.1f} L{x2},{y2} L{hx2:.1f},{hy2:.1f}"/>')


ICONS = {
    # ---------------- ฮาร์ดแวร์
    "cpu": (
        '<rect class="i-b" x="12" y="12" width="32" height="32" rx="3"/>'
        + _pins(17, 39, (5, 12), (44, 51)) + _pins_side(17, 39, (5, 12), (44, 51))
        + '<rect class="i-a" x="18" y="18" width="20" height="20" rx="2"/>'
        '<text class="i-ta" x="28" y="31" text-anchor="middle">CPU</text>'
    ),
    "timer": (
        '<rect class="i-b" x="24" y="4" width="8" height="5" rx="1"/>'
        '<circle class="i-b" cx="28" cy="31" r="19"/>'
        '<circle class="i-a" cx="28" cy="31" r="14"/>'
        '<line class="i-s" x1="28" y1="31" x2="28" y2="20"/>'
        '<line class="i-s" x1="28" y1="31" x2="36" y2="35"/>'
        '<circle class="i-k" cx="28" cy="31" r="2"/>'
    ),
    "mmu": (
        '<rect class="i-b" x="6" y="12" width="44" height="32" rx="3"/>'
        + _pins(12, 44, (5, 12), (44, 51), n=5)
        + '<rect class="i-a" x="11" y="21" width="12" height="14" rx="2"/>'
        '<text class="i-ta" x="17" y="31" text-anchor="middle">L</text>'
        + _arrow(24, 28, 32, 28)
        + '<rect class="i-A" x="33" y="21" width="12" height="14" rx="2"/>'
        '<text class="i-t i-inv" x="39" y="31" text-anchor="middle">P</text>'
    ),
    "tlb": (
        '<rect class="i-b" x="4" y="10" width="48" height="38" rx="3"/>'
        '<rect class="i-a" x="4" y="10" width="48" height="9" rx="3"/>'
        '<line class="i-s" x1="4" y1="29" x2="52" y2="29"/>'
        '<line class="i-s" x1="4" y1="38" x2="52" y2="38"/>'
        '<line class="i-s" x1="17" y1="10" x2="17" y2="48"/>'
        '<line class="i-s" x1="34" y1="10" x2="34" y2="48"/>'
        '<text class="i-t" x="10.5" y="17" text-anchor="middle">AS</text>'
        '<text class="i-t" x="25.5" y="17" text-anchor="middle">p</text>'
        '<text class="i-t" x="43" y="17" text-anchor="middle">f</text>'
        '<circle class="i-A" cx="10.5" cy="24" r="2.2"/><circle class="i-A" cx="10.5" cy="33.5" r="2.2"/>'
        '<circle class="i-k" cx="10.5" cy="43" r="2.2"/>'
    ),
    "pagetable": (
        '<rect class="i-b" x="10" y="4" width="36" height="48" rx="3"/>'
        + "".join(f'<line class="i-s" x1="10" y1="{y}" x2="46" y2="{y}"/>' for y in (12, 20, 28, 36, 44))
        + '<line class="i-s" x1="36" y1="4" x2="36" y2="52"/>'
        + "".join(f'<rect class="{c}" x="38.5" y="{y}" width="5" height="5" rx="1"/>'
                  for y, c in ((5.5, "i-A"), (13.5, "i-A"), (21.5, "i-b"), (29.5, "i-A"),
                               (37.5, "i-b"), (45.5, "i-A")))
        + "".join(f'<line class="i-s" x1="14" y1="{y}" x2="{x}" y2="{y}"/>'
                  for y, x in ((8, 30), (16, 26), (32, 31), (48, 27)))
    ),
    "ram": (
        '<rect class="i-b" x="3" y="13" width="50" height="24" rx="2"/>'
        + "".join(f'<rect class="i-a" x="{x}" y="17" width="9" height="12" rx="1"/>' for x in (7, 19, 31, 43))
        + "".join(f'<line class="i-s" x1="{x}" y1="37" x2="{x}" y2="43"/>' for x in range(6, 52, 4))
        + '<rect class="i-k" x="25" y="36" width="5" height="3"/>'
    ),
    "dma": (
        '<rect class="i-b" x="20" y="5" width="16" height="12" rx="2"/>'
        '<text class="i-t" x="28" y="14" text-anchor="middle">CPU</text>'
        '<rect class="i-b" x="3" y="30" width="15" height="18" rx="2"/>'
        '<rect class="i-a" x="38" y="30" width="15" height="18" rx="2"/>'
        '<text class="i-t" x="10.5" y="42" text-anchor="middle">dev</text>'
        '<text class="i-ta" x="45.5" y="42" text-anchor="middle">RAM</text>'
        + _arrow(19, 39, 37, 39, "i-sA")
        + '<path class="i-s i-dash" d="M28,18 V30"/>'
    ),
    "controller": (
        '<rect class="i-b" x="4" y="10" width="44" height="36" rx="3"/>'
        '<rect class="i-a" x="11" y="17" width="17" height="17" rx="2"/>'
        '<rect class="i-A" x="46" y="20" width="7" height="14" rx="1"/>'
        '<path class="i-s" d="M28,22 H40 M28,29 H44 M19,34 V41 M24,34 V41"/>'
        + "".join(f'<line class="i-s" x1="{x}" y1="46" x2="{x}" y2="51"/>' for x in range(9, 44, 5))
    ),
    "nic": (
        '<rect class="i-b" x="4" y="14" width="36" height="26" rx="3"/>'
        '<rect class="i-a" x="40" y="19" width="12" height="16" rx="2"/>'
        '<path class="i-s" d="M43,31 H49 M44,23 V27 M48,23 V27"/>'
        '<rect class="i-k" x="10" y="20" width="12" height="9" rx="1"/>'
        + "".join(f'<line class="i-s" x1="{x}" y1="40" x2="{x}" y2="45"/>' for x in range(8, 38, 4))
    ),
    "hyp": (
        '<rect class="i-a" x="5" y="6" width="20" height="16" rx="2"/>'
        '<rect class="i-a" x="31" y="6" width="20" height="16" rx="2"/>'
        '<text class="i-ta" x="15" y="17" text-anchor="middle">VM</text>'
        '<text class="i-ta" x="41" y="17" text-anchor="middle">VM</text>'
        '<rect class="i-A" x="4" y="26" width="48" height="10" rx="2"/>'
        '<text class="i-t i-inv" x="28" y="34" text-anchor="middle">VMM</text>'
        '<rect class="i-b" x="2" y="40" width="52" height="10" rx="2"/>'
        '<text class="i-t" x="28" y="48" text-anchor="middle">HW</text>'
    ),
    # ---------------- ที่เก็บข้อมูล
    "hdd": (
        '<rect class="i-b" x="5" y="4" width="46" height="48" rx="4"/>'
        '<circle class="i-a" cx="25" cy="25" r="17"/>'
        '<circle class="i-s" cx="25" cy="25" r="11"/>'
        '<circle class="i-s" cx="25" cy="25" r="6"/>'
        '<circle class="i-k" cx="25" cy="25" r="2"/>'
        '<path class="i-sA" d="M46,47 L32,22"/>'
        '<circle class="i-A" cx="46" cy="47" r="3"/>'
        '<rect class="i-A" x="29" y="18" width="5" height="5" rx="1" transform="rotate(-30 31.5 20.5)"/>'
    ),
    "ssd": (
        '<rect class="i-b" x="4" y="8" width="48" height="40" rx="3"/>'
        + "".join(f'<rect class="i-a" x="{x}" y="{y}" width="11" height="11" rx="1"/>'
                  for x in (9, 22) for y in (13, 29))
        + '<rect class="i-A" x="37" y="17" width="10" height="18" rx="1"/>'
        '<text class="i-t" x="15" y="45" text-anchor="middle">NAND</text>'
    ),
    "raid": (
        _cyl(3, 10, 14, 36) + _cyl(21, 10, 14, 36) + _cyl(39, 10, 14, 36, "i-a")
        + '<rect class="i-a" x="5" y="20" width="10" height="6"/><rect class="i-a" x="23" y="20" width="10" height="6"/>'
        '<rect class="i-A" x="41" y="20" width="10" height="6"/>'
        '<rect class="i-a" x="5" y="30" width="10" height="6"/><rect class="i-A" x="23" y="30" width="10" height="6"/>'
        '<rect class="i-b" x="41" y="30" width="10" height="6"/>'
    ),
    "swap": (
        _cyl(8, 18, 40, 32)
        + _doc(20, 3, 16, 20, "i-a")
        + _arrow(14, 10, 14, 22) + _arrow(42, 22, 42, 10)
    ),
    "exe": (
        _doc(12, 4, 32, 46)
        + '<rect class="i-A" x="16" y="12" width="17" height="8" rx="1"/>'
        '<text class="i-t i-inv" x="24.5" y="18.5" text-anchor="middle">ELF</text>'
        + "".join(f'<line class="i-s" x1="17" y1="{y}" x2="{x}" y2="{y}"/>'
                  for y, x in ((27, 38), (33, 34), (39, 37), (45, 30)))
    ),
    "remote": (
        '<rect class="i-b" x="6" y="5" width="30" height="12" rx="2"/>'
        '<rect class="i-b" x="6" y="20" width="30" height="12" rx="2"/>'
        '<rect class="i-b" x="6" y="35" width="30" height="12" rx="2"/>'
        + "".join(f'<circle class="i-A" cx="12" cy="{y}" r="2"/>' for y in (11, 26, 41))
        + '<path class="i-s" d="M36,26 H44 V50 M40,50 H50"/>'
        '<circle class="i-a" cx="44" cy="14" r="7"/>'
        '<path class="i-s" d="M37,14 H51 M44,7 V21"/>'
    ),
    "volume": (
        '<rect class="i-b" x="3" y="30" width="15" height="16" rx="2"/>'
        '<rect class="i-b" x="21" y="30" width="15" height="16" rx="2"/>'
        '<rect class="i-b" x="39" y="30" width="14" height="16" rx="2"/>'
        '<rect class="i-a" x="3" y="10" width="50" height="12" rx="3"/>'
        '<path class="i-s i-dash" d="M10,22 V30 M28,22 V30 M46,22 V30"/>'
    ),
    "fsmap": (
        '<rect class="i-b" x="2" y="18" width="52" height="20" rx="2"/>'
        '<rect class="i-A" x="2" y="18" width="5" height="20"/>'
        '<rect class="i-a" x="7" y="18" width="7" height="20"/>'
        '<rect class="i-a" x="14" y="18" width="8" height="20"/>'
        '<path class="i-s" d="M7,18 V38 M14,18 V38 M22,18 V38 M44,18 V38"/>'
    ),
    # ---------------- ฝั่ง user
    "parent": (
        '<rect class="i-a" x="18" y="4" width="20" height="14" rx="3"/>'
        '<path class="i-s" d="M28,18 V26 M12,26 H44 M12,26 V34 M44,26 V34"/>'
        '<rect class="i-b" x="2" y="34" width="20" height="14" rx="3"/>'
        '<rect class="i-b" x="34" y="34" width="20" height="14" rx="3"/>'
    ),
    "process": (
        '<rect class="i-b" x="14" y="3" width="28" height="50" rx="3"/>'
        '<rect class="i-a" x="14" y="3" width="28" height="10" rx="3"/>'
        '<rect class="i-a" x="14" y="30" width="28" height="7"/>'
        '<rect class="i-b" x="14" y="37" width="28" height="6"/>'
        '<rect class="i-A" x="14" y="43" width="28" height="10" rx="2"/>'
        '<text class="i-t" x="28" y="10.5" text-anchor="middle">stack</text>'
        '<text class="i-t" x="28" y="35.5" text-anchor="middle">heap</text>'
        '<text class="i-t i-inv" x="28" y="50.5" text-anchor="middle">text</text>'
        + _arrow(28, 15, 28, 21) + _arrow(28, 29, 28, 23)
    ),
    "vas": (
        "".join(f'<rect class="{c}" x="16" y="{y}" width="24" height="9" rx="1.5"/>'
                for y, c in ((3, "i-a"), (13, "i-b"), (23, "i-b"), (33, "i-a"), (43, "i-a")))
        + "".join(f'<text class="i-t" x="12" y="{y + 7}" text-anchor="end">{k}</text>'
                  for k, y in ((4, 3), (3, 13), (2, 23), (1, 33), (0, 43)))
        + '<text class="i-ta" x="46" y="30" text-anchor="middle">p</text>'
    ),
    "files": (
        _doc(6, 4, 30, 40)
        + "".join(f'<line class="i-s" x1="11" y1="{y}" x2="{x}" y2="{y}"/>'
                  for y, x in ((16, 30), (22, 27), (28, 31), (34, 24)))
        + '<rect class="i-A" x="30" y="34" width="22" height="14" rx="3"/>'
        '<text class="i-t i-inv" x="41" y="44" text-anchor="middle">fd 3</text>'
    ),
    "socket": (
        '<rect class="i-b" x="6" y="16" width="26" height="24" rx="4"/>'
        '<path class="i-s" d="M32,22 H40 M32,34 H40"/>'
        '<rect class="i-a" x="40" y="18" width="10" height="20" rx="2"/>'
        '<text class="i-ta" x="19" y="31" text-anchor="middle">:80</text>'
    ),
    # ---------------- ฝั่ง kernel: process / scheduling
    "pcb": (
        '<rect class="i-b" x="9" y="4" width="38" height="48" rx="3"/>'
        '<rect class="i-a" x="9" y="4" width="38" height="10" rx="3"/>'
        '<text class="i-ta" x="28" y="11.5" text-anchor="middle">PID 42</text>'
        + "".join(f'<line class="i-s" x1="14" y1="{y}" x2="{x}" y2="{y}"/>'
                  for y, x in ((20, 40), (26, 34), (32, 42), (38, 36), (44, 30)))
    ),
    "queue": (
        "".join(f'<rect class="{c}" x="{x}" y="20" width="10" height="16" rx="2"/>'
                for x, c in ((3, "i-b"), (15, "i-b"), (27, "i-b"), (39, "i-a")))
        + _arrow(42, 44, 52, 44) + '<line class="i-s" x1="3" y1="44" x2="42" y2="44"/>'
    ),
    "waitq": (
        "".join(f'<rect class="i-b" x="{x}" y="26" width="10" height="14" rx="2"/>' for x in (3, 15, 27))
        + '<path class="i-a" d="M39,8 H53 L46,18 L53,28 H39 L46,18 Z"/>'
        '<path class="i-s" d="M39,8 H53 M39,28 H53"/>'
        + '<line class="i-s" x1="3" y1="46" x2="37" y2="46"/>'
    ),
    "sched": (
        '<circle class="i-b" cx="28" cy="30" r="20"/>'
        + "".join(f'<rect class="i-a" x="{x}" y="{y}" width="9" height="9" rx="2"/>'
                  for x, y in ((24, 13), (38, 26), (24, 39), (10, 26)))
        + _arrow(28, 30, 36, 22, "i-sA")
        + '<circle class="i-A" cx="28" cy="30" r="2.5"/>'
    ),
    "dispatch": (
        '<rect class="i-b" x="3" y="18" width="18" height="20" rx="3"/>'
        '<rect class="i-a" x="35" y="18" width="18" height="20" rx="3"/>'
        '<path class="i-s" d="M12,16 C14,6 42,6 44,14"/><path class="i-s" d="M40,12 L44,15 L46,10"/>'
        '<path class="i-s" d="M44,40 C42,50 14,50 12,42"/><path class="i-s" d="M16,44 L12,41 L10,46"/>'
        '<text class="i-t" x="12" y="31" text-anchor="middle">old</text>'
        '<text class="i-ta" x="44" y="31" text-anchor="middle">new</text>'
    ),
    "loader": (
        _doc(3, 12, 18, 26)
        + _arrow(23, 25, 33, 25, "i-sA")
        + "".join(f'<rect class="{c}" x="35" y="{y}" width="18" height="8" rx="1"/>'
                  for y, c in ((8, "i-a"), (18, "i-b"), (28, "i-b"), (38, "i-a")))
    ),
    "exit": (
        '<rect class="i-b" x="17" y="17" width="22" height="22" rx="3"/>'
        '<path class="i-sA" d="M22,22 L34,34 M34,22 L22,34"/>'
        + _arrow(17, 28, 5, 28) + _arrow(39, 28, 51, 28)
        + _arrow(28, 17, 28, 5) + _arrow(28, 39, 28, 51)
    ),
    # ---------------- deadlock
    "lock": (
        '<path class="i-s" d="M18,26 V18 a10,10 0 0 1 20,0 V26" style="stroke-width:3"/>'
        '<rect class="i-a" x="12" y="25" width="32" height="25" rx="4"/>'
        '<circle class="i-A" cx="28" cy="35" r="3.5"/><rect class="i-A" x="26.5" y="36" width="3" height="8"/>'
    ),
    "rag": (
        '<circle class="i-a" cx="12" cy="12" r="8"/><circle class="i-a" cx="44" cy="44" r="8"/>'
        '<rect class="i-b" x="36" y="4" width="16" height="16" rx="2"/>'
        '<rect class="i-b" x="4" y="36" width="16" height="16" rx="2"/>'
        '<circle class="i-k" cx="44" cy="12" r="2.5"/><circle class="i-k" cx="12" cy="44" r="2.5"/>'
        + _arrow(20, 12, 35, 12, "i-sA") + _arrow(44, 21, 44, 35, "i-sA")
        + _arrow(36, 44, 21, 44, "i-sA") + _arrow(12, 35, 12, 21, "i-sA")
        + '<text class="i-t" x="12" y="15" text-anchor="middle">P1</text>'
        '<text class="i-t" x="44" y="47" text-anchor="middle">P2</text>'
    ),
    # ---------------- หน่วยความจำ (kernel)
    "vma": (
        '<rect class="i-b" x="6" y="4" width="44" height="48" rx="3"/>'
        + "".join(f'<rect class="{c}" x="10" y="{y}" width="{w}" height="7" rx="1"/>'
                  for y, w, c in ((9, 18, "i-a"), (19, 26, "i-A"), (29, 14, "i-a"), (39, 22, "i-b")))
        + "".join(f'<text class="i-t" x="46" y="{y + 6}" text-anchor="end">{t}</text>'
                  for y, t in ((9, "rw"), (19, "rx"), (29, "rw"), (39, "r")))
    ),
    "kmem": (
        '<rect class="i-b" x="4" y="8" width="48" height="40" rx="2"/>'
        '<rect class="i-a" x="4" y="8" width="24" height="40"/>'
        '<rect class="i-a" x="28" y="8" width="12" height="20"/>'
        '<rect class="i-A" x="40" y="8" width="12" height="20"/>'
        '<path class="i-s" d="M28,8 V48 M28,28 H52 M40,8 V28"/>'
        '<text class="i-t" x="16" y="31" text-anchor="middle">32K</text>'
        '<text class="i-t" x="40" y="41" text-anchor="middle">16K</text>'
    ),
    "wss": (
        "".join(f'<rect class="{"i-a" if 4 <= i <= 7 else "i-b"}" x="{2 + i * 6.5}" y="22" width="5.5" height="11" rx="1"/>'
                for i in range(8))
        + '<path class="i-sA" d="M27,18 V14 H53 V18 M27,37 V41 H53 V41"/>'
        '<text class="i-ta" x="40" y="12" text-anchor="middle">Δ</text>'
        '<text class="i-t" x="40" y="51" text-anchor="middle">WS</text>'
    ),
    "freelist": (
        "".join(f'<rect class="i-b" x="{x}" y="20" width="12" height="16" rx="2"/>' for x in (2, 22, 42))
        + _arrow(14, 28, 21, 28) + _arrow(34, 28, 41, 28)
        + '<text class="i-t" x="8" y="31" text-anchor="middle">7</text>'
        '<text class="i-t" x="28" y="31" text-anchor="middle">2</text>'
        '<text class="i-t" x="48" y="31" text-anchor="middle">9</text>'
    ),
    "replace": (
        '<rect class="i-b" x="4" y="10" width="20" height="26" rx="2"/>'
        '<path class="i-sA" d="M7,13 L21,33 M21,13 L7,33"/>'
        '<rect class="i-a" x="32" y="20" width="20" height="26" rx="2"/>'
        + _arrow(14, 38, 14, 52) + _arrow(42, 4, 42, 18)
    ),
    "pfh": (
        '<rect class="i-b" x="6" y="12" width="26" height="34" rx="2"/>'
        '<path class="i-a" d="M38,6 L54,34 H22 Z"/>'
        '<line class="i-sA" x1="38" y1="15" x2="38" y2="25" style="stroke-width:2.5"/>'
        '<circle class="i-A" cx="38" cy="30" r="1.8"/>'
        '<text class="i-t" x="19" y="42" text-anchor="middle">v=0</text>'
    ),
    # ---------------- ระบบไฟล์
    "vfs": (
        '<rect class="i-A" x="16" y="3" width="24" height="12" rx="2"/>'
        '<text class="i-t i-inv" x="28" y="12" text-anchor="middle">VFS</text>'
        '<path class="i-s" d="M28,15 V24 M9,24 H47 M9,24 V32 M28,24 V32 M47,24 V32"/>'
        '<rect class="i-b" x="1" y="32" width="17" height="14" rx="2"/>'
        '<rect class="i-b" x="20" y="32" width="16" height="14" rx="2"/>'
        '<rect class="i-b" x="38" y="32" width="17" height="14" rx="2"/>'
        '<text class="i-t" x="9.5" y="42" text-anchor="middle">ext4</text>'
        '<text class="i-t" x="28" y="42" text-anchor="middle">nfs</text>'
        '<text class="i-t" x="46.5" y="42" text-anchor="middle">fat</text>'
    ),
    "dir": (
        '<path class="i-a" d="M4,6 H14 L17,9 H26 V18 H4 Z"/>'
        '<path class="i-s" d="M10,18 V44 M10,30 H24 M10,44 H24"/>'
        '<path class="i-b" d="M24,24 H33 L35,26 H44 V35 H24 Z"/>'
        '<path class="i-b" d="M24,38 H33 L35,40 H44 V49 H24 Z"/>'
    ),
    "inode": (
        '<rect class="i-b" x="3" y="4" width="22" height="48" rx="2"/>'
        '<rect class="i-a" x="3" y="4" width="22" height="12" rx="2"/>'
        + "".join(f'<line class="i-s" x1="3" y1="{y}" x2="25" y2="{y}"/>' for y in (22, 28, 34, 40, 46))
        + "".join(_arrow(25, y, 37, y) for y in (25, 31))
        + '<rect class="i-b" x="38" y="19" width="14" height="10" rx="1"/>'
        '<rect class="i-b" x="38" y="31" width="14" height="10" rx="1"/>'
        + _arrow(25, 43, 38, 49, "i-sA")
    ),
    "oft": (
        '<rect class="i-b" x="2" y="10" width="20" height="36" rx="2"/>'
        '<rect class="i-a" x="32" y="10" width="22" height="36" rx="2"/>'
        + "".join(f'<line class="i-s" x1="2" y1="{y}" x2="22" y2="{y}"/>' for y in (19, 28, 37))
        + "".join(f'<line class="i-s" x1="32" y1="{y}" x2="54" y2="{y}"/>' for y in (19, 28, 37))
        + _arrow(22, 23, 31, 23) + _arrow(22, 32, 31, 24)
        + '<text class="i-t" x="12" y="8" text-anchor="middle">fd</text>'
        '<text class="i-ta" x="43" y="8" text-anchor="middle">sys</text>'
    ),
    "fom": (
        "".join(f'<rect class="i-a" x="{4 + i * 12}" y="6" width="10" height="10" rx="1"/>' for i in range(4))
        + "".join(f'<rect class="{"i-A" if i in (1, 4, 6) else "i-b"}" x="{2 + i * 7.3:.1f}" y="40" width="6" height="10" rx="1"/>'
                  for i in range(7))
        + _arrow(9, 17, 11, 39) + _arrow(21, 17, 33, 39) + _arrow(33, 17, 47, 39)
    ),
    "cache": (
        '<rect class="i-b" x="14" y="4" width="28" height="34" rx="2"/>'
        '<rect class="i-b" x="9" y="9" width="28" height="34" rx="2"/>'
        '<rect class="i-a" x="4" y="14" width="28" height="34" rx="2"/>'
        + "".join(f'<line class="i-s" x1="9" y1="{y}" x2="{x}" y2="{y}"/>'
                  for y, x in ((23, 27), (29, 24), (35, 27)))
        + '<circle class="i-A" cx="42" cy="44" r="9"/>'
        '<path class="i-inv-s" d="M37.5,44 L41,47.5 L46.5,40.5"/>'
    ),
    "journal": (
        '<rect class="i-b" x="2" y="20" width="52" height="16" rx="2"/>'
        + "".join(f'<rect class="i-a" x="{4 + i * 10}" y="23" width="8" height="10" rx="1"/>' for i in range(4))
        + '<rect class="i-A" x="44" y="23" width="8" height="10" rx="1"/>'
        '<path class="i-sA" d="M48,23 V8 M48,8 L54,11 L48,14"/>'
        '<text class="i-t" x="24" y="48" text-anchor="middle">log</text>'
    ),
    "blocks": (
        "".join(f'<rect class="i-b" x="{6 + d}" y="{8 + d}" width="34" height="14" rx="2"/>' for d in (0,))
        + '<rect class="i-b" x="10" y="22" width="34" height="14" rx="2"/>'
        '<rect class="i-a" x="14" y="36" width="34" height="14" rx="2"/>'
        '<text class="i-t" x="23" y="18" text-anchor="middle">#88</text>'
        '<text class="i-t" x="27" y="32" text-anchor="middle">#91</text>'
        '<text class="i-ta" x="31" y="46" text-anchor="middle">#123</text>'
    ),
    "nfs": (
        '<path class="i-a" d="M3,10 H13 L16,13 H26 V28 H3 Z"/>'
        '<path class="i-s i-dash" d="M26,20 H34"/>'
        '<rect class="i-b" x="34" y="8" width="18" height="10" rx="2"/>'
        '<rect class="i-b" x="34" y="22" width="18" height="10" rx="2"/>'
        '<circle class="i-A" cx="38" cy="13" r="1.6"/><circle class="i-A" cx="38" cy="27" r="1.6"/>'
        '<text class="i-t" x="28" y="46" text-anchor="middle">RPC</text>'
    ),
    "netstack": (
        "".join(f'<rect class="{c}" x="8" y="{y}" width="40" height="9" rx="2"/>'
                for y, c in ((4, "i-a"), (16, "i-a"), (28, "i-b"), (40, "i-b")))
        + "".join(f'<text class="i-t" x="28" y="{y + 7}" text-anchor="middle">{t}</text>'
                  for y, t in ((4, "TCP"), (16, "IP"), (28, "link"), (40, "phy")))
    ),
    # ---------------- I/O
    "iosched": (
        '<line class="i-s" x1="4" y1="44" x2="52" y2="44"/>'
        + "".join(f'<circle class="i-k" cx="{x}" cy="44" r="2"/>' for x in (8, 19, 31, 46))
        + '<path class="i-sA" d="M26,8 L46,18 L8,28 L19,38"/>'
        '<circle class="i-A" cx="26" cy="8" r="3"/>'
    ),
    "volmgr": (
        _cyl(2, 26, 14, 24) + _cyl(21, 26, 14, 24) + _cyl(40, 26, 14, 24)
        + '<path class="i-s" d="M9,26 V20 H47 V26 M28,20 V26"/>'
        '<rect class="i-A" x="10" y="4" width="36" height="12" rx="3"/>'
        '<line class="i-s" x1="28" y1="16" x2="28" y2="20"/>'
    ),
    "driver": (
        '<circle class="i-a" cx="28" cy="28" r="14"/>'
        + "".join(f'<rect class="i-A" x="25" y="6" width="6" height="8" rx="1" transform="rotate({a} 28 28)"/>'
                  for a in range(0, 360, 45))
        + '<circle class="i-b" cx="28" cy="28" r="6"/>'
    ),
    "irq": (
        '<rect class="i-b" x="6" y="34" width="44" height="14" rx="3"/>'
        '<text class="i-t" x="28" y="44" text-anchor="middle">handler</text>'
        '<path class="i-A" d="M30,3 L18,20 H27 L22,32 L38,14 H29 Z"/>'
    ),
    # ---------------- ความปลอดภัย
    "shield": (
        '<path class="i-shield" d="M28,3 L50,11 V26 C50,40 40,49 28,54 C16,49 6,40 6,26 V11 Z"/>'
        '<path class="i-shield-in" d="M18,28 L25,35 L39,20"/>'
    ),
    "key": (
        '<circle class="i-a" cx="17" cy="28" r="11"/><circle class="i-b" cx="17" cy="28" r="4"/>'
        '<path class="i-sA" d="M28,28 H52 M44,28 V36 M50,28 V34" style="stroke-width:3"/>'
    ),
    "matrix": (
        '<rect class="i-b" x="4" y="6" width="48" height="44" rx="2"/>'
        + "".join(f'<line class="i-s" x1="4" y1="{y}" x2="52" y2="{y}"/>' for y in (17, 28, 39))
        + "".join(f'<line class="i-s" x1="{x}" y1="6" x2="{x}" y2="50"/>' for x in (16, 28, 40))
        + '<rect class="i-A" x="16" y="17" width="12" height="11"/><rect class="i-a" x="40" y="28" width="12" height="11"/>'
    ),
}


# ================================================================ ชุดทั่วไป (ใช้ได้กับทุกวิชา / โปรเจกต์)
# หลักเดิม: วาด "รูปร่างจริง" — ไฟล์ = แผ่นเอกสาร · สคริปต์ = หน้าต่างเทอร์มินัล · ข้อมูลตาราง = กริด · การทำซ้ำ = ลูกศรวน

def _gear(cx, cy, r, teeth=8, cls="i-a", hub="i-b"):
    """เฟือง: วงกลม + ฟันสี่เหลี่ยมหมุนรอบ"""
    t = "".join(f'<rect class="{cls}" x="{cx - 3}" y="{cy - r - 4}" width="6" height="7" rx="1"'
                f' transform="rotate({a} {cx} {cy})"/>' for a in range(0, 360, 360 // teeth))
    return t + f'<circle class="{cls}" cx="{cx}" cy="{cy}" r="{r}"/><circle class="{hub}" cx="{cx}" cy="{cy}" r="{r * 0.4:.1f}"/>'


def _head(x, y, ang_deg, cls="i-sA", size=5):
    """หัวลูกศรเปิด ที่จุด (x, y) ชี้ไปทางมุม ang (องศา)"""
    import math
    a = math.radians(ang_deg)
    p1 = (x - size * math.cos(a - 0.55), y - size * math.sin(a - 0.55))
    p2 = (x - size * math.cos(a + 0.55), y - size * math.sin(a + 0.55))
    return f'<path class="{cls}" d="M{p1[0]:.1f},{p1[1]:.1f} L{x},{y} L{p2[0]:.1f},{p2[1]:.1f}"/>'


ICONS.update({
    # ---------------- ไฟล์ · โค้ด · เอกสาร
    "doc": (_doc(12, 5, 32, 46)
            + "".join(f'<line class="i-s" x1="17" y1="{y}" x2="{x}" y2="{y}"/>' for y, x in ((19, 38), (26, 38), (33, 34), (40, 37)))),
    "code": (_doc(10, 5, 36, 46)
             + '<path class="i-sA" d="M22,23 L16,29 L22,35 M34,23 L40,29 L34,35 M30,21 L26,37"/>'
             + '<line class="i-s" x1="15" y1="44" x2="32" y2="44"/>'),
    "script": ('<rect class="i-b" x="5" y="9" width="46" height="38" rx="4"/>'
               '<path class="i-a" d="M5,13 A4,4 0 0 1 9,9 H47 A4,4 0 0 1 51,13 V18 H5 Z"/>'
               + "".join(f'<circle class="i-k" cx="{x}" cy="13.5" r="1.4"/>' for x in (10, 15, 20))
               + '<path class="i-sA" d="M13,26 L19,31 L13,36"/><line class="i-s" x1="22" y1="37" x2="33" y2="37"/>'),
    "build": (_doc(5, 4, 30, 40)
              + "".join(f'<line class="i-s" x1="10" y1="{y}" x2="28" y2="{y}"/>' for y in (15, 21, 27))
              + _gear(39, 39, 9, teeth=8)),
    "table": (_doc(9, 5, 38, 46)
              + '<rect class="i-a" x="13" y="14" width="30" height="7"/>'
              + "".join(f'<line class="i-s" x1="13" y1="{y}" x2="43" y2="{y}"/>' for y in (21, 28, 35, 42))
              + "".join(f'<line class="i-s" x1="{x}" y1="14" x2="{x}" y2="42"/>' for x in (23, 33))),
    "pdf": (_doc(10, 4, 36, 48)
            + '<rect class="i-A" x="6" y="30" width="30" height="12" rx="2"/>'
              '<text class="i-t i-inv" x="21" y="39" text-anchor="middle">PDF</text>'
            + "".join(f'<line class="i-s" x1="15" y1="{y}" x2="{x}" y2="{y}"/>' for y, x in ((13, 38), (19, 34), (25, 38)))),
    "checklist": (_doc(10, 4, 36, 48)
                  + "".join(f'<path class="i-sA" d="M15,{y} l3,3 l6,-6"/><line class="i-s" x1="27" y1="{y + 1}" x2="40" y2="{y + 1}"/>'
                            for y in (15, 26, 37))),
    "book": ('<path class="i-b" d="M28,14 C22,9 12,9 5,11 V45 C12,43 22,43 28,48 Z"/>'
             '<path class="i-a" d="M28,14 C34,9 44,9 51,11 V45 C44,43 34,43 28,48 Z"/>'
             + "".join(f'<line class="i-s" x1="10" y1="{y}" x2="23" y2="{y - 1}"/>' for y in (19, 26, 33))),
    "folder": ('<path class="i-a" d="M5,14 H21 L25,19 H51 V46 H5 Z"/>'
               '<rect class="i-b" x="5" y="23" width="46" height="23" rx="2"/>'),
    "parcel": ('<path class="i-b" d="M8,18 L28,8 L48,18 V42 L28,52 L8,42 Z"/>'
               '<path class="i-s" d="M8,18 L28,28 L48,18 M28,28 V52"/>'
               '<path class="i-A" d="M17,13.5 L37,23.5 V31 L33,29 V25.5 L13,15.5 Z"/>'),
    "procfs": (_doc(10, 4, 36, 48)
               + '<rect class="i-a" x="13" y="12" width="30" height="10" rx="2"/>'
                 '<text class="i-ta" x="28" y="20" text-anchor="middle">/proc</text>'
               + "".join(f'<line class="i-s" x1="15" y1="{y}" x2="{x}" y2="{y}"/>' for y, x in ((29, 40), (35, 33), (41, 38)))),
    # ---------------- ข้อมูล · ผลลัพธ์
    "chart": ('<path class="i-s" d="M7,7 V48 H51"/>'
              + "".join(f'<rect class="{c}" x="{x}" y="{48 - h}" width="7" height="{h}" rx="1"/>'
                        for x, h, c in ((12, 14, "i-a"), (22, 24, "i-a"), (32, 33, "i-A"), (42, 19, "i-a")))),
    "linechart": ('<path class="i-s" d="M7,7 V48 H51"/>'
                  '<path class="i-sA" d="M11,40 L20,31 L28,34 L37,20 L47,13"/>'
                  + "".join(f'<circle class="i-A" cx="{x}" cy="{y}" r="2.4"/>' for x, y in ((11, 40), (20, 31), (28, 34), (37, 20), (47, 13)))
                  + '<path class="i-s i-dash" d="M11,40 L47,9"/>'),
    "database": (_cyl(12, 30, 32, 18, "i-b") + _cyl(12, 18, 32, 16, "i-a") + _cyl(12, 6, 32, 16, "i-b")),
    "formula": ('<rect class="i-b" x="5" y="7" width="46" height="42" rx="4"/>'
                '<path class="i-sA" d="M34,15 H16 L26,28 L16,41 H34" style="stroke-width:3"/>'
                '<path class="i-s" d="M38,24 h7 M41.5,20.5 v7 M38,36 h7"/>'),
    "gauge": ('<path class="i-b" d="M6,40 A22,22 0 0 1 50,40 Z"/>'
              '<path class="i-a" d="M12,40 A16,16 0 0 1 44,40 Z"/>'
              '<line class="i-sA" x1="28" y1="40" x2="40" y2="25" style="stroke-width:2.6"/>'
              '<circle class="i-A" cx="28" cy="40" r="3"/>'
              + "".join(f'<line class="i-s" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>'
                        for x1, y1, x2, y2 in ((9, 33, 13, 34), (28, 18, 28, 22), (47, 33, 43, 34)))),
    # ---------------- การทำงาน · การไหล
    "loop": ('<path class="i-sA" d="M13,24 A16,16 0 0 1 42,19"/>' + _head(42, 19, 30)
             + '<path class="i-sA" d="M43,32 A16,16 0 0 1 14,37"/>' + _head(14, 37, 210)
             + '<text class="i-ta" x="28" y="31" text-anchor="middle">×N</text>'),
    "pipeline": ('<rect class="i-a" x="3" y="21" width="12" height="14" rx="2"/>'
                 '<rect class="i-a" x="22" y="21" width="12" height="14" rx="2"/>'
                 '<rect class="i-A" x="41" y="21" width="12" height="14" rx="2"/>'
                 '<path class="i-s" d="M15,28 H21 M34,28 H40"/>' + _head(21, 28, 0, "i-s", 4) + _head(40, 28, 0, "i-s", 4)),
    "threads": ('<path class="i-sA" d="M3,28 H13 M43,28 H53" style="stroke-width:2.4"/>'
                + "".join(f'<path class="i-s" d="M13,28 C17,28 17,{y} 21,{y} H35 C39,{y} 39,28 43,28"/>' for y in (11, 22, 34, 45))
                + '<circle class="i-A" cx="13" cy="28" r="3.2"/><circle class="i-A" cx="43" cy="28" r="3.2"/>'),
    "smt": ('<rect class="i-b" x="7" y="7" width="42" height="42" rx="4"/>'
            '<rect class="i-a" x="13" y="13" width="30" height="30" rx="3"/>'
            '<path class="i-sA" d="M17,23 H37" style="stroke-width:2.4"/>' + _head(38, 23, 0)
            + '<path class="i-sA i-dash" d="M17,33 H37" style="stroke-width:2.4"/>' + _head(38, 33, 0)),
    "cachehier": ('<rect class="i-A" x="22" y="6" width="12" height="10" rx="1.5"/>'
                  '<rect class="i-a" x="14" y="19" width="28" height="11" rx="1.5"/>'
                  '<rect class="i-b" x="6" y="33" width="44" height="15" rx="1.5"/>'
                  '<text class="i-t i-inv" x="28" y="13.5" text-anchor="middle">L1</text>'
                  '<text class="i-t" x="28" y="27" text-anchor="middle">L2</text>'
                  '<text class="i-t" x="28" y="43" text-anchor="middle">L3 · RAM</text>'),
    "stack": ('<rect class="i-b" x="15" y="5" width="26" height="46" rx="2"/>'
              + "".join(f'<rect class="i-a" x="15" y="{y}" width="26" height="7"/>' for y in (5, 12))
              + '<rect class="i-A" x="15" y="19" width="26" height="6"/>'
              + '<rect class="i-b i-dash" x="15" y="27" width="26" height="24" style="fill:none"/>'
              + '<path class="i-s" d="M8,12 V26"/>' + _head(8, 26, 90, "i-s", 4)),
    "heap": ('<rect class="i-b" x="5" y="8" width="46" height="40" rx="3"/>'
             + "".join(f'<rect class="{c}" x="{x}" y="{y}" width="{w}" height="{h}" rx="1.5"/>'
                       for x, y, w, h, c in ((9, 12, 14, 9, "i-a"), (25, 12, 22, 9, "i-A"), (9, 24, 24, 9, "i-a"),
                                             (35, 24, 12, 9, "i-a"), (9, 36, 9, 8, "i-A"), (20, 36, 27, 8, "i-a")))),
    "eye": ('<path class="i-b" d="M4,28 C14,12 42,12 52,28 C42,44 14,44 4,28 Z"/>'
            '<circle class="i-a" cx="28" cy="28" r="9.5"/><circle class="i-A" cx="28" cy="28" r="4.2"/>'),
    "magnifier": ('<circle class="i-a" cx="23" cy="23" r="14"/><circle class="i-b" cx="23" cy="23" r="9"/>'
                  '<path class="i-sA" d="M33,33 L48,48" style="stroke-width:5"/>'),
    "gear": _gear(28, 28, 15, teeth=8),
    "thermo": ('<rect class="i-b" x="22" y="4" width="12" height="36" rx="6"/>'
               '<circle class="i-a" cx="28" cy="43" r="9"/>'
               '<rect class="i-A" x="26" y="17" width="4" height="25" rx="2"/><circle class="i-A" cx="28" cy="43" r="5.5"/>'
               + "".join(f'<line class="i-s" x1="36" y1="{y}" x2="41" y2="{y}"/>' for y in (10, 17, 24, 31))),
    "power": ('<rect class="i-b" x="5" y="15" width="40" height="26" rx="3"/><rect class="i-k" x="45" y="23" width="5" height="10" rx="1"/>'
              '<rect class="i-a" x="9" y="19" width="14" height="18" rx="1.5"/>'
              '<path class="i-A" d="M30,17 L21,30 H28 L25,40 L35,26 H28 Z"/>'),
    "warning": ('<path class="i-a" d="M28,5 L52,48 H4 Z"/>'
                '<path class="i-sA" d="M28,19 V33" style="stroke-width:3.4"/><circle class="i-A" cx="28" cy="40" r="2.4"/>'),
    "target": ('<circle class="i-b" cx="26" cy="30" r="21"/><circle class="i-a" cx="26" cy="30" r="14"/>'
               '<circle class="i-A" cx="26" cy="30" r="6"/><path class="i-s" d="M26,30 L48,8 M42,8 H48 V14"/>'),
    "balance": ('<path class="i-s" d="M28,8 V46 M16,48 H40 M8,16 H48"/>'
                '<circle class="i-A" cx="28" cy="10" r="3"/>'
                '<path class="i-a" d="M3,32 L8,16 L13,32 Z"/><path class="i-a" d="M43,28 L48,16 L53,28 Z"/>'
                '<path class="i-s" d="M2,32 H14 M42,28 H54"/>'),
    "idea": ('<path class="i-a" d="M28,5 C17,5 10,13 10,22 C10,30 17,34 19,41 H37 C39,34 46,30 46,22 C46,13 39,5 28,5 Z"/>'
             '<rect class="i-b" x="19" y="41" width="18" height="5" rx="1.5"/><rect class="i-b" x="21" y="46" width="14" height="5" rx="2"/>'
             '<path class="i-sA" d="M23,30 L28,22 L33,30"/>'),
    "flask": ('<path class="i-b" d="M21,5 H35 V20 L49,46 C50,49 48,51 45,51 H11 C8,51 6,49 7,46 L21,20 Z"/>'
              '<path class="i-a" d="M14,36 H42 L48,47 C48,48 47,49 46,49 H10 C9,49 8,48 8,47 Z"/>'
              '<circle class="i-A" cx="22" cy="42" r="2.4"/><circle class="i-A" cx="32" cy="44" r="1.8"/>'),
    "person": ('<circle class="i-a" cx="28" cy="17" r="10"/>'
               '<path class="i-a" d="M8,51 C8,37 17,30 28,30 C39,30 48,37 48,51 Z"/>'),
    "people": ('<circle class="i-b" cx="38" cy="16" r="8"/><path class="i-b" d="M24,46 C24,35 30,28 38,28 C46,28 52,35 52,46 Z"/>'
               '<circle class="i-a" cx="20" cy="19" r="9"/><path class="i-a" d="M4,51 C4,39 11,32 20,32 C29,32 36,39 36,51 Z"/>'),
    "graph": ('<path class="i-s" d="M12,14 L40,12 M12,14 L18,42 M40,12 L44,40 M18,42 L44,40 M12,14 L44,40"/>'
              + "".join(f'<circle class="{c}" cx="{x}" cy="{y}" r="6"/>'
                        for x, y, c in ((12, 14, "i-A"), (40, 12, "i-a"), (18, 42, "i-a"), (44, 40, "i-a")))),
    "model": ("".join(f'<path class="i-s" d="M{x1},{y1} L{x2},{y2}"/>'
                      for x1 in (10,) for y1 in (14, 28, 42) for x2, y2 in ((28, 10), (28, 22), (28, 34), (28, 46)))
              + "".join(f'<path class="i-s" d="M28,{y} L46,28"/>' for y in (10, 22, 34, 46))
              + "".join(f'<circle class="i-a" cx="10" cy="{y}" r="4.5"/>' for y in (14, 28, 42))
              + "".join(f'<circle class="i-b" cx="28" cy="{y}" r="4.5"/>' for y in (10, 22, 34, 46))
              + '<circle class="i-A" cx="46" cy="28" r="5"/>'),
    "coin": ('<circle class="i-a" cx="28" cy="28" r="22"/><circle class="i-b" cx="28" cy="28" r="16"/>'
             '<path class="i-sA" d="M34,20 C31,17 21,17 21,23 C21,29 35,27 35,33 C35,39 24,39 21,35 M28,14 V42" style="stroke-width:2.4"/>'),
    "clock": ('<circle class="i-b" cx="28" cy="28" r="22"/><circle class="i-a" cx="28" cy="28" r="17"/>'
              '<path class="i-sA" d="M28,28 V16 M28,28 L37,33" style="stroke-width:2.4"/><circle class="i-A" cx="28" cy="28" r="2.4"/>'),
})


def register(name: str, svg: str) -> None:
    """เพิ่มไอคอนของวิชาเอง (กรอบ 56 × 56 · ใช้ class i-s / i-sA / i-b / i-a / i-A / i-k / i-t / i-ta)"""
    ICONS[name] = svg


def names() -> list[str]:
    return sorted(ICONS)


def icon(name: str) -> str:
    return ICONS.get(name, '<rect class="i-b" x="8" y="8" width="40" height="40" rx="6"/>')
