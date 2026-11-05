"""ชุดเครื่องมือวาด SVG ของแผนที่: กล่อง (Node) · เส้น (Edge) · ตัวเชื่อมข้ามภาพ (Conn) · กราฟทั้งภาพ (Graph)

ทำไมวาด SVG เองด้วย Python แทนไลบรารีวาดกราฟ (mermaid / graphviz):
    - ต้องคุมตำแหน่งทุกกล่องเอง — ตำแหน่งคือข้อมูล (แนวตั้ง = อยู่ชั้นไหน · แนวนอน = ระบบย่อยไหน)
      ซึ่งตัวจัดวางอัตโนมัติไม่รู้
    - SVG ถูกเขียนลง HTML ตรงๆ → ภาพครบตั้งแต่เปิดหน้า ไม่ต้องรอ JavaScript
    - วัดความกว้างข้อความไทยด้วยฟอนต์จริง (fonts.text_w) → ตรวจได้ว่าข้อความล้นกล่อง
      หรือป้ายทับกันไหม ก่อนจะเปิดดูด้วยตา (ดู Graph.check)

หน่วยทุกอย่างเป็น "หน่วย SVG" ซึ่งเท่ากับ px เมื่อซูม 100%
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field

from .fonts import text_w
from .icons import icon

CH_PREFIX = "บท"          # ป้ายบทมุมการ์ด เช่น "บท 9" — build ตั้งค่าจาก META["ch_prefix"]


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def wrap(s: str, size: float, maxw: float, weight: int = 400) -> list[str]:
    """ตัดบรรทัดที่ช่องว่าง (ภาษาไทยไม่มีช่องว่างระหว่างคำ จึงเว้นวรรคไว้ตรงจุดที่ตัดได้)"""
    lines: list[str] = []
    for para in s.split("\n"):
        cur = ""
        for word in para.split(" "):
            trial = word if not cur else f"{cur} {word}"
            if not cur or text_w(trial, size, weight) <= maxw:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- กล่องและเส้น

CARD_W, CARD_H = 230, 80
ICON_BOX = 64            # พื้นหลังของไอคอน
TEXT_X = 82              # ข้อความเริ่มห่างจากขอบซ้ายของการ์ด
NAME_SIZE, GLOSS_SIZE, TAG_SIZE, LABEL_SIZE = 14, 12, 10.5, 12


@dataclass
class Node:
    id: str
    x: float
    y: float
    name: str
    gloss: str = ""
    icon: str = ""
    topic: str = "base"   # id ของกลุ่มเนื้อหาใน TOPICS → สีของกรอบ ("base" = สีหมึกกลางๆ)
    ch: str = ""          # ป้ายบท เช่น "9" หรือ "9–10" (แสดงเป็น "{CH_PREFIX} 9")
    w: float = CARD_W
    h: float = CARD_H
    kind: str = "card"    # card | badge (วงกลมด่านตรวจ) | panel (กล่องกว้างที่วาดของข้างในเอง) | chip
    steps: tuple = ()     # ภาพในบท: เลขขั้นที่กล่องนี้มีส่วนร่วม (ปุ่ม "ทีละขั้น")
    extra: str = ""       # SVG ที่วาดเพิ่มในกล่อง (kind="panel")
    q: tuple = ()         # id ใน FOCUS ที่กล่องนี้เกี่ยว (เช่นข้อสอบ "Q1") → ปุ่มกรองบนแผนที่
    lab: str = "r"        # badge: ป้ายอยู่ขวา (r) หรือซ้าย (l) ของวงกลม

    # badge = วงกลมด่านตรวจ (เช่นจุดตรวจสิทธิ์ · จุดป้องกันความเสียหาย): (x, y) คือจุดศูนย์กลาง
    @property
    def box(self) -> tuple[float, float, float, float]:
        if self.kind == "badge":
            r = 17
            return (self.x - r, self.y - r, 2 * r, 2 * r)
        return (self.x, self.y, self.w, self.h)

    def port(self, spec: str) -> tuple[tuple[float, float], tuple[int, int]]:
        """จุดต่อเส้นบนขอบกล่อง: 'n' 's' 'e' 'w' + '@สัดส่วน' เช่น 's@0.3'"""
        side, _, frac = spec.partition("@")
        f = float(frac) if frac else 0.5
        x, y, w, h = self.box
        if side == "n":
            return (x + w * f, y), (0, -1)
        if side == "s":
            return (x + w * f, y + h), (0, 1)
        if side == "w":
            return (x, y + h * f), (-1, 0)
        if side == "e":
            return (x + w, y + h * f), (1, 0)
        raise ValueError(spec)


@dataclass
class Edge:
    id: str
    src: str
    dst: str
    label: str = ""
    kind: str = "ctl"     # ctl = สั่ง/ขอ · data = ข้อมูลไหล · sig = trap/interrupt · rel = ความสัมพันธ์
    sp: str = ""          # port ต้นทาง ("" = เลือกตามทิศ)
    dp: str = ""          # port ปลายทาง
    via: tuple = ()       # จุดเลี้ยว: (("y", 985), ("x", 1865)) = ลงไป y=985 แล้วไปทาง x=1865
    lseg: int = -1        # ช่วงของเส้นที่วางป้าย (-1 = ช่วงที่ยาวที่สุด)
    lside: str = ""       # ป้ายอยู่ด้านไหนของเส้น: r/l (เส้นตั้ง) a/b (เส้นนอน)
    lt: float = 0.5       # ตำแหน่งตามความยาวช่วงนั้น
    lxy: tuple = ()       # (x, y, anchor) กำหนดตำแหน่งป้ายเอง
    lw: float = 150       # ความกว้างสูงสุดของป้ายก่อนตัดบรรทัด
    steps: tuple = ()
    arrow: bool = True


@dataclass
class Conn:
    """ตัวเชื่อมข้ามภาพ (วงกลมตัวอักษร) — แทนเส้นยาวที่จะลากผ่านทั้งแผนที่"""
    id: str
    letter: str
    src: str
    sp: str
    dst: str
    dp: str
    src_label: str
    dst_label: str
    stub: float = 30
    lside_src: str = ""   # ด้านที่วางป้ายของวงกลมต้นทาง (ค่าเริ่มตามทิศของ port)
    lside_dst: str = ""


@dataclass
class Label:
    x: float
    y: float
    lines: list
    anchor: str
    owner: str
    size: float = LABEL_SIZE

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        w = max(text_w(s, self.size) for s in self.lines)
        h = len(self.lines) * (self.size + 5)
        if self.anchor == "middle":
            x0 = self.x - w / 2
        elif self.anchor == "end":
            x0 = self.x - w
        else:
            x0 = self.x
        # y คือ baseline ของบรรทัดแรก
        return (x0 - 2, self.y - self.size + 1, w + 4, h + 1)


def _overlap(a, b, pad=0.0) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax < bx + bw + pad and bx < ax + aw + pad and
            ay < by + bh + pad and by < ay + ah + pad)


def _seg_hits_box(p, q, box, shrink=2.0) -> bool:
    """เส้นตรงแนวตั้ง/แนวนอนช่วง p→q ผ่านเข้าไปในกล่องไหม"""
    x, y, w, h = box
    x0, y0, x1, y1 = x + shrink, y + shrink, x + w - shrink, y + h - shrink
    (px, py), (qx, qy) = p, q
    if abs(px - qx) < 0.01:  # แนวตั้ง
        lo, hi = sorted((py, qy))
        return x0 < px < x1 and lo < y1 and hi > y0
    lo, hi = sorted((px, qx))   # แนวนอน
    return y0 < py < y1 and lo < x1 and hi > x0


def rounded_path(pts: list, r: float = 9) -> str:
    """เส้นหักมุมฉากที่มุมโค้งเล็กน้อย (อ่านง่ายกว่ามุมแหลมเมื่อเส้นหลายเส้นเลี้ยวใกล้กัน)"""
    if len(pts) < 3:
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    for i in range(1, len(pts) - 1):
        (ax, ay), (bx, by), (cx, cy) = pts[i - 1], pts[i], pts[i + 1]
        l1 = abs(bx - ax) + abs(by - ay)
        l2 = abs(cx - bx) + abs(cy - by)
        rr = min(r, l1 / 2, l2 / 2)

        def toward(p, q, dist):
            dx, dy = q[0] - p[0], q[1] - p[1]
            n = abs(dx) + abs(dy) or 1
            return (p[0] + dx / n * dist, p[1] + dy / n * dist)
        s = toward((bx, by), (ax, ay), rr)
        e = toward((bx, by), (cx, cy), rr)
        d.append(f"L{s[0]:.1f},{s[1]:.1f} Q{bx:.1f},{by:.1f} {e[0]:.1f},{e[1]:.1f}")
    d.append(f"L{pts[-1][0]:.1f},{pts[-1][1]:.1f}")
    return " ".join(d)


def arrow_head(tip, direction, length=9, half=4.2) -> str:
    dx, dy = direction
    bx, by = tip[0] - dx * length, tip[1] - dy * length
    px, py = -dy, dx
    return (f"M{tip[0]:.1f},{tip[1]:.1f} L{bx + px * half:.1f},{by + py * half:.1f} "
            f"L{bx - px * half:.1f},{by - py * half:.1f} Z")


def _dir(p, q):
    dx, dy = q[0] - p[0], q[1] - p[1]
    if abs(dx) > abs(dy):
        return (1 if dx > 0 else -1, 0)
    return (0, 1 if dy > 0 else -1)


def _auto_ports(a: Node, b: Node) -> tuple[str, str]:
    ax, ay, aw, ah = a.box
    bx, by, bw, bh = b.box
    if by >= ay + ah - 1:
        return "s", "n"
    if by + bh <= ay + 1:
        return "n", "s"
    if bx >= ax + aw:
        return "e", "w"
    return "w", "e"


def route(e: Edge, nodes: dict) -> list:
    a, b = nodes[e.src], nodes[e.dst]
    sp, dp = e.sp, e.dp
    if not sp or not dp:
        asp, adp = _auto_ports(a, b)
        sp, dp = sp or asp, dp or adp
    (p0, d0), (p1, d1) = a.port(sp), b.port(dp)
    pts = [p0]
    cur = p0
    for axis, v in e.via:
        cur = (cur[0], v) if axis == "y" else (v, cur[1])
        pts.append(cur)
    # เชื่อมจุดสุดท้ายเข้าปลายทางด้วยมุมฉาก ตามทิศที่ port ปลายทางหันออก
    if abs(cur[0] - p1[0]) > 0.5 and abs(cur[1] - p1[1]) > 0.5:
        if not e.via:
            # ไม่มีจุดเลี้ยว: เลือกรูปตัว Z หรือ L ตามทิศของทั้งสอง port
            if d0[0] == 0 and d1[0] == 0:          # ตั้ง → ตั้ง
                my = (cur[1] + p1[1]) / 2
                pts += [(cur[0], my), (p1[0], my)]
            elif d0[1] == 0 and d1[1] == 0:        # นอน → นอน
                mx = (cur[0] + p1[0]) / 2
                pts += [(mx, cur[1]), (mx, p1[1])]
            elif d0[0] == 0:                       # ตั้ง → นอน
                pts.append((cur[0], p1[1]))
            else:                                  # นอน → ตั้ง
                pts.append((p1[0], cur[1]))
        else:
            if d1[0] == 0:   # ปลายทางเข้าทางบน/ล่าง → เดินนอนก่อนแล้วลงตั้ง
                pts.append((p1[0], cur[1]))
            else:
                pts.append((cur[0], p1[1]))
    pts.append(p1)
    # ตัดจุดซ้ำ
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > 0.01 or abs(p[1] - out[-1][1]) > 0.01:
            out.append(p)
    return out


def label_for(e: Edge, pts: list) -> Label | None:
    if not e.label:
        return None
    lines = wrap(e.label, LABEL_SIZE, e.lw)
    if e.lxy:
        x, y, anchor = e.lxy
        return Label(x, y, lines, anchor, e.id)
    segs = list(zip(pts[:-1], pts[1:]))
    if e.lseg >= 0:
        i = min(e.lseg, len(segs) - 1)
    else:
        i = max(range(len(segs)), key=lambda k: abs(segs[k][1][0] - segs[k][0][0]) +
                abs(segs[k][1][1] - segs[k][0][1]))
    (x0, y0), (x1, y1) = segs[i]
    mx, my = x0 + (x1 - x0) * e.lt, y0 + (y1 - y0) * e.lt
    nl = len(lines)
    block_h = nl * (LABEL_SIZE + 5)
    if abs(x0 - x1) < 0.01:            # เส้นตั้ง → ป้ายข้างเส้น
        side = e.lside or "r"
        y = my - block_h / 2 + LABEL_SIZE - 1
        if side == "r":
            return Label(mx + 7, y, lines, "start", e.id)
        return Label(mx - 7, y, lines, "end", e.id)
    side = e.lside or "a"              # เส้นนอน → ป้ายเหนือ/ใต้เส้น
    if side == "a":
        return Label(mx, my - 7 - (nl - 1) * (LABEL_SIZE + 5), lines, "middle", e.id)
    return Label(mx, my + LABEL_SIZE + 5, lines, "middle", e.id)


def label_svg(lb: Label, cls: str = "e-lbl", attrs: str = "") -> str:
    parts = []
    for i, s in enumerate(lb.lines):
        dy = 0 if i == 0 else LABEL_SIZE + 5
        if i == 0:
            parts.append(f'<tspan x="{lb.x:.1f}" y="{lb.y:.1f}">{esc(s)}</tspan>')
        else:
            parts.append(f'<tspan x="{lb.x:.1f}" dy="{dy}">{esc(s)}</tspan>')
    return (f'<text class="{cls}" text-anchor="{lb.anchor}" data-for="{lb.owner}"{attrs}>'
            + "".join(parts) + "</text>")


def steps_attr(steps) -> str:
    return f' data-s="{" ".join(str(s) for s in steps)}"' if steps else ""


# ---------------------------------------------------------------- การ์ดอุปกรณ์

def card_svg(n: Node, interactive: bool = True) -> str:
    x, y, w, h = n.box
    focus = (f' tabindex="0" role="button" aria-label="{esc(n.name)} — {esc(n.gloss)}"'
             if interactive else "")
    head = (f'<g class="node topic-{n.topic} kind-{n.kind}" id="n-{n.id}" data-id="{n.id}"'
            f' data-q="{" ".join(n.q)}"{steps_attr(n.steps)}{focus}>')
    if n.kind == "badge":
        cx, cy = n.x, n.y
        tx, anchor = (cx + 24, "start") if n.lab == "r" else (cx - 24, "end")
        lines = [f'<circle class="b-ring" cx="{cx}" cy="{cy}" r="17"/>',
                 f'<g transform="translate({cx - 12},{cy - 12}) scale(0.43)">{icon(n.icon or "shield")}</g>',
                 f'<text class="b-name" x="{tx}" y="{cy - 1}" text-anchor="{anchor}">{esc(n.name)}</text>']
        if n.gloss:
            lines.append(f'<text class="b-gloss" x="{tx}" y="{cy + 13}" text-anchor="{anchor}">{esc(n.gloss)}</text>')
        return head + "".join(lines) + "</g>"
    if n.kind == "chip":
        # กล่องข้อความเล็ก (ใช้ในภาพของแต่ละบท) — ไม่มีไอคอน
        lines = wrap(n.name, 13, w - 16, 600)
        gl = wrap(n.gloss, 11.5, w - 16) if n.gloss else []
        total = len(lines) * 16 + len(gl) * 14
        ty = y + (h - total) / 2 + 12
        out = [f'<rect class="n-box" x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/>']
        for s in lines:
            out.append(f'<text class="c-name" x="{x + w / 2}" y="{ty:.1f}" text-anchor="middle">{esc(s)}</text>')
            ty += 16
        for s in gl:
            out.append(f'<text class="c-gloss" x="{x + w / 2}" y="{ty:.1f}" text-anchor="middle">{esc(s)}</text>')
            ty += 14
        return head + "".join(out) + "</g>"
    out = [f'<rect class="n-box" x="{x}" y="{y}" width="{w}" height="{h}" rx="10"/>']
    if n.kind == "panel":
        # กล่องกว้าง: ชื่ออยู่บนซ้าย แล้ววาดภาพข้างในเอง (เช่นแถบ frame ของ RAM)
        out.append(f'<text class="n-name" x="{x + 14}" y="{y + 22}">{esc(n.name)}</text>')
        gx = x + 14 + text_w(n.name, NAME_SIZE, 600) + 10
        out.append(f'<text class="n-gloss" x="{gx:.1f}" y="{y + 22}">{esc(n.gloss)}</text>')
        out.append(n.extra)
    else:
        out.append(f'<rect class="n-icobg" x="{x + 8}" y="{y + 8}" width="{ICON_BOX}" height="{ICON_BOX}" rx="8"/>')
        out.append(f'<g transform="translate({x + 12},{y + 12})">{icon(n.icon)}</g>')
        out.append(f'<text class="n-name" x="{x + TEXT_X}" y="{y + 26}">{esc(n.name)}</text>')
        gl = wrap(n.gloss, GLOSS_SIZE, w - TEXT_X - 8)
        for i, s in enumerate(gl[:2]):
            out.append(f'<text class="n-gloss" x="{x + TEXT_X}" y="{y + 44 + i * 15}">{esc(s)}</text>')
    if n.ch:
        # panel มีภาพเต็มกล่อง → ป้ายบทไปไว้มุมขวาบนแถวเดียวกับชื่อ
        ty = y + 22 if n.kind == "panel" else y + h - 7
        out.append(f'<text class="n-ch" x="{x + w - 10}" y="{ty}" text-anchor="end">{esc(CH_PREFIX)} {esc(n.ch)}</text>')
    return head + "".join(out) + "</g>"


# ---------------------------------------------------------------- กราฟทั้งภาพ

@dataclass
class Graph:
    w: float
    h: float
    nodes: list
    edges: list
    conns: list = field(default_factory=list)
    background: str = ""      # SVG ที่วาดก่อน (แถบชั้น หัวคอลัมน์)
    foreground: str = ""      # SVG ที่วาดทับ (โน้ต)
    svg_id: str = ""
    cls: str = "graph"
    aria: str = ""
    interactive: bool = True
    allow: tuple = ()         # คู่ (edge, node) ที่ตั้งใจให้เส้นผ่าน เช่น badge ด่านตรวจที่วางบนเส้น
    obstacles: list = field(default_factory=list)   # [(ชื่อ, (x, y, w, h))] ของที่วาดเองใน background/foreground
                                                    # เช่นกล่องคำอธิบายสัญลักษณ์ — ห้ามกล่อง เส้น และป้ายทับ

    def __post_init__(self):
        self.by_id = {n.id: n for n in self.nodes}
        self.paths = {e.id: route(e, self.by_id) for e in self.edges}
        self.labels = {e.id: label_for(e, self.paths[e.id]) for e in self.edges}

    # -------- วาด
    def edge_svg(self, e: Edge) -> str:
        pts = self.paths[e.id]
        # ตัดปลายเส้นให้หยุดที่ฐานหัวลูกศร ไม่ให้เส้นแทงทะลุปลายลูกศร
        line_pts = list(pts)
        d_end = _dir(pts[-2], pts[-1])
        if e.arrow:
            line_pts[-1] = (pts[-1][0] - d_end[0] * 7, pts[-1][1] - d_end[1] * 7)
        d = rounded_path(line_pts)
        head = (f'<path class="e-head" d="{arrow_head(pts[-1], d_end)}"/>' if e.arrow else "")
        return (f'<g class="edge k-{e.kind}" id="e-{e.id}" data-id="{e.id}" data-src="{e.src}"'
                f' data-dst="{e.dst}"{steps_attr(e.steps)}>'
                f'<path class="e-halo" d="{d}"/><path class="e-line" d="{d}"/>{head}</g>')

    def conn_svg(self, c: Conn) -> str:
        out = []
        for end in ("src", "dst"):
            nid = c.src if end == "src" else c.dst
            port = c.sp if end == "src" else c.dp
            (px, py), (dx, dy) = self.by_id[nid].port(port)
            cx, cy = px + dx * (c.stub + 11), py + dy * (c.stub + 11)
            text = c.src_label if end == "src" else c.dst_label
            side = (c.lside_src if end == "src" else c.lside_dst)
            if not side:
                side = {(1, 0): "e", (-1, 0): "w", (0, 1): "e", (0, -1): "e"}[(dx, dy)]
            if end == "src":   # ลูกศรวิ่งออกจากกล่องไปที่วงกลม
                line = f'M{px:.1f},{py:.1f} L{cx - dx * 11:.1f},{cy - dy * 11:.1f}'
                head = ""
            else:              # ลูกศรวิ่งจากวงกลมเข้ากล่อง
                tip = (px, py)
                line = f'M{cx - dx * 11:.1f},{cy - dy * 11:.1f} L{px + dx * 7:.1f},{py + dy * 7:.1f}'
                head = f'<path class="e-head" d="{arrow_head(tip, (-dx, -dy))}"/>'
            if side == "e":
                tx, anchor = cx + 16, "start"
            elif side == "w":
                tx, anchor = cx - 16, "end"
            else:
                tx, anchor = cx, "middle"
            ty = cy + 4 if side in ("e", "w") else (cy - 17 if side == "n" else cy + 25)
            out.append(
                f'<g class="conn" id="c-{c.id}-{end}" data-conn="{c.id}" data-end="{end}"'
                f' data-node="{nid}" tabindex="0" role="button"'
                f' aria-label="ตัวเชื่อม {esc(c.letter)}: {esc(text)}">'
                f'<path class="c-stub" d="{line}"/>{head}'
                f'<circle class="c-ring" cx="{cx:.1f}" cy="{cy:.1f}" r="11"/>'
                f'<text class="c-letter" x="{cx:.1f}" y="{cy + 4:.1f}" text-anchor="middle">{esc(c.letter)}</text>'
                f'<text class="c-lbl" x="{tx:.1f}" y="{ty:.1f}" text-anchor="{anchor}">{esc(text)}</text></g>')
        return "".join(out)

    def conn_boxes(self) -> list:
        """กรอบของวงกลมตัวเชื่อม + ป้าย (ใช้ตรวจการทับ)"""
        boxes = []
        for c in self.conns:
            for end in ("src", "dst"):
                nid = c.src if end == "src" else c.dst
                port = c.sp if end == "src" else c.dp
                (px, py), (dx, dy) = self.by_id[nid].port(port)
                cx, cy = px + dx * (c.stub + 11), py + dy * (c.stub + 11)
                text = c.src_label if end == "src" else c.dst_label
                tw = text_w(text, 11.5)
                side = (c.lside_src if end == "src" else c.lside_dst) or \
                    {(1, 0): "e", (-1, 0): "w", (0, 1): "e", (0, -1): "e"}[(dx, dy)]
                boxes.append((f"conn {c.id}/{end}", (cx - 11, cy - 11, 22, 22)))
                if side == "e":
                    boxes.append((f"conn-label {c.id}/{end}", (cx + 15, cy - 9, tw + 2, 15)))
                elif side == "w":
                    boxes.append((f"conn-label {c.id}/{end}", (cx - 17 - tw, cy - 9, tw + 2, 15)))
        return boxes

    def badge_boxes(self) -> list:
        out = []
        for n in self.nodes:
            if n.kind != "badge":
                continue
            w = max(text_w(n.name, 12, 600), text_w(n.gloss, 11) if n.gloss else 0)
            x = n.x + 22 if n.lab == "r" else n.x - 22 - w
            out.append((f"badge-label {n.id}", (x, n.y - 12, w + 2, 30)))
        return out

    def svg(self) -> str:
        parts = [f'<svg {"id=" + chr(34) + self.svg_id + chr(34) if self.svg_id else ""} class="{self.cls}"'
                 f' viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{esc(self.aria)}"'
                 f' xmlns="http://www.w3.org/2000/svg">',
                 self.background,
                 '<g class="edges">' + "".join(self.edge_svg(e) for e in self.edges) + "</g>",
                 '<g class="labels">' + "".join(
                     label_svg(lb, attrs=steps_attr(e.steps)) for e in self.edges
                     if (lb := self.labels[e.id])) + "</g>",
                 '<g class="nodes">' + "".join(card_svg(n, self.interactive) for n in self.nodes) + "</g>",
                 '<g class="conns">' + "".join(self.conn_svg(c) for c in self.conns) + "</g>",
                 self.foreground,
                 "</svg>"]
        return "".join(parts)

    # -------- ตรวจ
    def check(self, name: str = "") -> list[str]:
        """รายการปัญหาการจัดวาง: กล่องทับกัน · เส้นทะลุกล่อง · ป้ายทับกล่อง/ป้าย · ข้อความล้นการ์ด"""
        issues = []
        boxes = [(n.id, n.box) for n in self.nodes]
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if _overlap(boxes[i][1], boxes[j][1], pad=6):
                    issues.append(f"node overlap: {boxes[i][0]} × {boxes[j][0]}")
        for e in self.edges:
            pts = self.paths[e.id]
            for nid, b in boxes:
                if nid in (e.src, e.dst) or (e.id, nid) in self.allow:
                    continue
                for p, q in zip(pts[:-1], pts[1:]):
                    if _seg_hits_box(p, q, b):
                        issues.append(f"edge {e.id} passes through {nid}")
                        break
        labels = [(eid, lb.bbox) for eid, lb in self.labels.items() if lb]
        extra = self.conn_boxes() + self.badge_boxes()
        for eid, lbb in labels:
            for nid, b in boxes:
                if _overlap(lbb, b, pad=1):
                    issues.append(f"label of {eid} overlaps node {nid}")
            for cname, cb in extra:
                if _overlap(lbb, cb, pad=1):
                    issues.append(f"label of {eid} overlaps {cname}")
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                if _overlap(labels[i][1], labels[j][1], pad=1):
                    issues.append(f"labels overlap: {labels[i][0]} × {labels[j][0]}")
        for cname, cb in extra:
            for nid, b in boxes:
                if _overlap(cb, b, pad=1):
                    issues.append(f"{cname} overlaps node {nid}")
        for oname, ob in self.obstacles:
            for nid, b in boxes:
                if _overlap(ob, b, pad=4):
                    issues.append(f"{oname} overlaps node {nid}")
            for eid, lbb in labels:
                if _overlap(ob, lbb, pad=1):
                    issues.append(f"{oname} overlaps label of {eid}")
            for e in self.edges:
                pts = self.paths[e.id]
                if any(_seg_hits_box(p, q, ob) for p, q in zip(pts[:-1], pts[1:])):
                    issues.append(f"edge {e.id} passes through {oname}")
        # ข้อความในการ์ด
        for n in self.nodes:
            if n.kind == "card":
                if text_w(n.name, NAME_SIZE, 600) > n.w - TEXT_X - 6:
                    issues.append(f"name too wide: {n.id}")
                gl = wrap(n.gloss, GLOSS_SIZE, n.w - TEXT_X - 8)
                if len(gl) > 2 or any(text_w(s, GLOSS_SIZE) > n.w - TEXT_X - 6 for s in gl):
                    issues.append(f"gloss too long: {n.id} → {gl}")
            if n.kind == "panel":
                tag = text_w(f"{CH_PREFIX} {n.ch}", TAG_SIZE, 600) + 12 if n.ch else 0
                if 14 + text_w(n.name, NAME_SIZE, 600) + 10 + text_w(n.gloss, GLOSS_SIZE) + tag > n.w - 10:
                    issues.append(f"panel title too wide: {n.id}")
        # ทุกอย่างอยู่ในกรอบภาพ
        for nid, (x, y, w, h) in boxes:
            if x < 0 or y < 0 or x + w > self.w or y + h > self.h:
                issues.append(f"node outside canvas: {nid}")
        for eid, (x, y, w, h) in labels:
            if x < 0 or y < 0 or x + w > self.w or y + h > self.h:
                issues.append(f"label outside canvas: {eid}")
        return [f"[{name}] {s}" for s in issues] if name else issues
