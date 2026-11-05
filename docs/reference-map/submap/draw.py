"""เครื่องมือวาดภาพอิสระของแต่ละบท (ภาพกายวิภาค · ไทม์ไลน์ · ตารางไล่ทีละขั้น · กราฟแท่งจากข้อมูล)

ต่างจาก Graph ตรงที่วางของได้ทุกที่ แต่ยังบันทึกกรอบของข้อความทุกชิ้นไว้ตรวจว่าทับกันไหม
ทุกชิ้นใส่เลขขั้นได้ (s=(1, 2)) → ปุ่ม "ทีละขั้น" ของหน้าเว็บจะไฮไลต์เฉพาะชิ้นของขั้นนั้น

class ของรูปทรง (กำหนดสีใน page.CSS):
    fc กล่องธรรมดา · fcA กล่องสีของหมวด (อ่อน) · fcB ทึบสีหมวด · fcH เน้น · fcW สีพื้น · fcN เส้นประ · fcD อันตราย/ผิด
    fc-<topic> กล่องสีของหมวดอื่น (สร้างให้ทุก topic ใน TOPICS) · fl เส้น · flA เส้นสีหมวด · fld เส้นประ
    flD / flDd เส้นอันตราย · fl-<topic> · หัวลูกศร fhd / fhdA / fhdD / fhd-<topic>
class ของข้อความ (FONT ด้านล่าง): ft ปกติ · ftB หนา · ftW ขาวบนพื้นทึบ · ft2 รอง · fh หัวเรื่อง · fa สีหมวด
    fsm เล็ก · fsmB · fsmW · fmono ตัวพิมพ์ดีด · fbig ใหญ่ · fpt / fptB ป้ายเล็กมีขอบพื้น
"""
from __future__ import annotations

import math

from .fonts import text_w
from .svg import esc, steps_attr

# class ของข้อความ → (ขนาด, น้ำหนัก) สำหรับวัดความกว้าง
FONT = {"ft": (12.5, 400), "ftB": (12.5, 600), "ft2": (12, 400), "fh": (13.5, 600), "fa": (12, 600),
        "fsm": (11, 400), "fsmB": (11, 600), "fmono": (12, "mono"), "fbig": (16, 600), "fw": (12, 600),
        "ftW": (12.5, 600), "fsmW": (11, 600), "fpt": (11, 400), "fptB": (11, 600)}


# บรรทัดแรกของกล่องหลายบรรทัดใช้ตัวหนาของขนาดเดียวกัน
HEAD = {"ft": "ftB", "ft2": "fw", "fsm": "fsmB"}


def measure(s: str, cls: str) -> float:
    size, weight = FONT[cls]
    if weight == "mono":
        return len(s) * size * 0.6
    w = text_w(s, size, weight)
    return w * (1.02 if weight == 400 else 1.0)


class Draw:
    def __init__(self, w: int, h: int, topic: str = "mem", aria: str = ""):
        self.w, self.h, self.topic, self.aria = w, h, topic, aria
        self.parts: list[str] = []
        self.texts: list[tuple] = []     # (bbox, ข้อความ, กลุ่ม) สำหรับตรวจทับ
        self.issues: list[str] = []
        self._grp = 0

    # ---------- ชิ้นพื้นฐาน
    def raw(self, svg: str, s=()):
        self.parts.append(f'<g{steps_attr(s)}>{svg}</g>' if s else svg)

    def rect(self, x, y, w, h, cls="fc", rx=5, s=(), extra=""):
        self.raw(f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}"{extra}/>', s)

    def text(self, x, y, t, cls="ft", anchor="start", s=(), group=None, check=True):
        lines = str(t).split("\n")
        size = FONT[cls][0]
        lh = size + 6           # ภาษาไทยมีสระ/วรรณยุกต์ซ้อนบน-ล่าง ต้องเว้นบรรทัดมากกว่าภาษาอังกฤษ
        out = []
        if group is None:            # แต่ละครั้งที่เรียก = กลุ่มใหม่ (บรรทัดในกลุ่มเดียวกันไม่นับว่าทับกัน)
            self._grp += 1
            group = self._grp
        for i, line in enumerate(lines):
            out.append(f'<text class="{cls}" x="{x:.1f}" y="{y + i * lh:.1f}" text-anchor="{anchor}">{esc(line)}</text>')
            if check:
                w = measure(line, cls)
                x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
                bbox = (x0, y + i * lh - size + 1.5, w, size + 1)
                if x0 < 0 or x0 + w > self.w + 0.5:
                    self.issues.append(f"text outside canvas: {line!r}")
                self.texts.append((bbox, line, group))
        self.raw("".join(out), s)
        return len(lines) * lh

    def tbox(self, x, y, w, h, t, cls="fc", tcls="ft", rx=5, s=(), pad=8, align="middle"):
        """กล่องพร้อมข้อความตรงกลาง (หลายบรรทัดได้ด้วย \\n) — ตรวจว่าข้อความพอดีกล่อง"""
        self._grp += 1
        lines = str(t).split("\n")
        size = FONT[tcls][0]
        lh = size + 6
        # กล่องหลายบรรทัด: บรรทัดแรกเป็นหัวเรื่อง (ตัวหนา)
        classes = [HEAD.get(tcls, tcls) if (i == 0 and len(lines) > 1) else tcls for i in range(len(lines))]
        for line, c in zip(lines, classes):
            if measure(line, c) > w - pad:
                self.issues.append(f"text overflows box ({w:.0f}): {line!r}")
        total = len(lines) * lh - 6
        if total + size * 0.6 > h:
            self.issues.append(f"text too tall for box ({h:.0f}): {lines[0]!r}")
        ty = y + (h - total) / 2 + size - 2
        tx = x + w / 2 if align == "middle" else x + pad / 2 + 2
        anchor = "middle" if align == "middle" else "start"
        body = f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}"/>'
        txt = []
        for i, (line, c) in enumerate(zip(lines, classes)):
            txt.append(f'<text class="{c}" x="{tx:.1f}" y="{ty + i * lh:.1f}" text-anchor="{anchor}">{esc(line)}</text>')
            w = measure(line, c)
            x0 = tx - w / 2 if anchor == "middle" else tx
            self.texts.append(((x0, ty + i * lh - size + 1.5, w, size + 1), line, ("box", self._grp)))
        self.raw(body + "".join(txt), s)

    def line(self, pts, cls="fl", s=(), head=True, hcls="fhd", r=7):
        """เส้นหักมุม (หรือเส้นตรง) พร้อมหัวลูกศรที่ปลาย"""
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        out = [f'<path class="{cls}" d="{d}"/>']
        if head:
            (x1, y1), (x2, y2) = pts[-2], pts[-1]
            ang = math.atan2(y2 - y1, x2 - x1)
            hx1, hy1 = x2 - 9 * math.cos(ang) + 4.2 * math.sin(ang), y2 - 9 * math.sin(ang) - 4.2 * math.cos(ang)
            hx2, hy2 = x2 - 9 * math.cos(ang) - 4.2 * math.sin(ang), y2 - 9 * math.sin(ang) + 4.2 * math.cos(ang)
            out.append(f'<path class="{hcls}" d="M{x2:.1f},{y2:.1f} L{hx1:.1f},{hy1:.1f} L{hx2:.1f},{hy2:.1f} Z"/>')
        self.raw("".join(out), s)

    def label(self, x, y, t, anchor="start", s=(), cls="flbl"):
        """ป้ายบนเส้น (มีขอบสีพื้นหลังรอบตัวอักษร)"""
        lines = str(t).split("\n")
        out = []
        for i, line in enumerate(lines):
            out.append(f'<text class="{cls}" x="{x:.1f}" y="{y + i * 17:.1f}" text-anchor="{anchor}">{esc(line)}</text>')
            w = measure(line, "ft2")
            x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
            self.texts.append(((x0, y + i * 17 - 11, w, 13), line, ("lbl", x, y)))
            if x0 < 0 or x0 + w > self.w + 0.5:
                self.issues.append(f"label outside canvas: {line!r}")
        self.raw("".join(out), s)

    def step_badge(self, x, y, k, s=()):
        """วงกลมเลขขั้น"""
        self.raw(f'<circle class="fstep" cx="{x}" cy="{y}" r="11"/>'
                 f'<text class="fstepT" x="{x}" y="{y + 4.5}" text-anchor="middle">{k}</text>', s or (k,))

    # ---------- ผลลัพธ์
    def check(self, name: str) -> list[str]:
        out = list(self.issues)
        T = self.texts
        for i in range(len(T)):
            for j in range(i + 1, len(T)):
                (a, sa, ga), (b, sb, gb) = T[i], T[j]
                if ga == gb:
                    continue
                if (a[0] < b[0] + b[2] - 0.5 and b[0] < a[0] + a[2] - 0.5 and
                        a[1] < b[1] + b[3] - 0.5 and b[1] < a[1] + a[3] - 0.5):
                    out.append(f"texts overlap: {sa!r} × {sb!r}")
        return [f"[{name}] {s}" for s in out]

    def svg(self) -> str:
        return (f'<svg class="fig-svg topic-{self.topic}" viewBox="0 0 {self.w} {self.h}" role="img"'
                f' aria-label="{esc(self.aria)}" xmlns="http://www.w3.org/2000/svg">' + "".join(self.parts) + "</svg>")
