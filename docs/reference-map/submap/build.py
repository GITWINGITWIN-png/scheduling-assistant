"""ประกอบ "แผนที่วิชา" จาก spec → HTML หน้าเดียว (+ fragment สำหรับเผยแพร่เป็น artifact) และตรวจทุกอย่างก่อนเขียนไฟล์

ใช้จาก build.py ของโปรเจกต์แผนที่ (สร้างให้โดย scripts/new_map.py):
    import spec
    from submap.build import main
    main(spec, out=Path(__file__).with_name("my-map.html"))

    python3 build.py                     เขียนไฟล์ HTML (พิมพ์ปัญหาการจัดวางถ้ามี)
    python3 build.py --check             ตรวจอย่างเดียว · exit code 1 ถ้ามีปัญหา
    python3 build.py --fragment X.html   เขียนฉบับไม่มี <html>/<head> ไว้เผยแพร่เป็น artifact ด้วย

หน้าที่ได้ (ทุกส่วนเลือกได้ — ถ้า spec ไม่มีข้อมูลส่วนนั้น ส่วนนั้นจะไม่แสดง):
    หัวหน้า (+ การ์ด FOCUS) · แถบนำทาง · แผนที่รวม (ซูม/ลาก/คลิก/ทัวร์/กรอง) · คู่ที่สับสน
    · ภาพรายบท (ทีละขั้น + เล่าเรื่อง 6 จังหวะ + กับดัก + อธิบายละเอียด) · แค็ตตาล็อกทุกกล่อง · ท้ายหน้า
รายละเอียดของ spec ทุกช่อง: references/spec.md ของ skill subject-map
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import fonts
from . import icons as I
from . import svg as SV
from .deep import UI as DEEP_UI
from .deep import Deep, fmt
from .draw import Draw
from .page import CSS, CSS_ID, JS, PALETTE_ORDER, TOPIC_PALETTE, theme_css
from .svg import Graph, esc, text_w

FONTS = ("https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700"
         "&family=IBM+Plex+Mono:wght@400;500;600;700&family=Sarabun:wght@400;500;600;700&display=swap")

EDGE_KINDS = {"ctl": "สั่ง / เรียกใช้", "data": "ข้อมูลไหลจริง", "sig": "สัญญาณย้อนกลับ (interrupt · event · callback)",
              "rel": "อยู่บน / เป็นส่วนของ"}

UI = dict(
    nav_map="แผนที่รวม", nav_tour="ทัวร์", nav_pairs="คู่ที่สับสน", nav_catalog="ทุกกล่อง",
    map_title="แผนที่รวม",
    map_intro="อ่านจากบนลงล่างคือจากชั้นบนสุดลงไปถึงชั้นล่างสุด · อ่านซ้ายไปขวาคือระบบย่อย · เส้นทุกเส้นมีป้ายบอกว่าวิ่งไปทำอะไร",
    howto_title="วิธีใช้แผนที่",
    howto_lead="แต่ละกล่องคือสิ่งหนึ่งในเรื่องนี้ ภาพเล็กในกล่องคือหน้าตาจริงของมัน (ของจริงวาดเป็นชิ้นส่วน ของนามธรรมวาดเป็นโครงสร้าง)",
    howto_click="<b>กดกล่อง</b> → แผงนี้แสดงคำอธิบายเต็ม และแผนที่ไฮไลต์เฉพาะกล่องที่ต่อกับมัน",
    howto_tour="<b>ถัดไป / ←→</b> → เดินทัวร์ทีละขั้น ภาพจะเลื่อนไปที่ขั้นนั้นเอง",
    howto_focus="<b>ปุ่มกรอง</b> → ดูเฉพาะกล่องที่ใช้ตอบหัวข้อนั้น",
    howto_zoom="ลากเพื่อเลื่อน · Ctrl/⌘ + ล้อเมาส์ หรือปุ่ม + − เพื่อซูม",
    fit="ทั้งภาพ", zoom_in="ซูมเข้า", zoom_out="ซูมออก", focus_hint="ดูเฉพาะ",
    prev="← ก่อนหน้า", next="ถัดไป →", reset="ทั้งภาพ", tour="ทัวร์", tour_list_title="ทัวร์ทั้ง {n} ขั้น",
    tour_list_intro="กดขั้นไหนก็ได้ แผนที่จะไฮไลต์กล่องและเส้นของขั้นนั้น แล้วเลื่อนไปให้เอง",
    tour_hint="ขั้นนี้ไฮไลต์ {n} กล่อง — กดที่ชื่อเพื่อดูคำอธิบาย",
    focus_desc="กล่องที่ใช้ตอบหัวข้อนี้ — กดชื่อเพื่ออ่านคำอธิบาย",
    what="คืออะไร", does="ทำงานอย่างไร", look="หน้าตา / โครงสร้าง", exam="จุดที่มักพลาด · ออกสอบ", links="เชื่อมกับ", read="อ่านต่อ",
    ch="บท", step="ขั้น", whole="ทั้งภาพ", of="จาก", steps="ขั้น",
    pairs_title="คู่ที่มักสับสน",
    pairs_intro="ความสับสนส่วนใหญ่มาจากของสองอย่างที่ทำงานคู่กันแต่อยู่คนละชั้น หรือชื่อคล้ายกันแต่หน้าที่ต่างกัน · กด “ชี้บนแผนที่” เพื่อดูว่าสองตัวนี้อยู่ตรงไหน",
    show_on_map="ชี้บนแผนที่", vs="vs",
    chapters_title="ภาพกระบวนการของแต่ละเรื่อง",
    chapters_intro="ทุกภาพกด “ทีละขั้น” ได้ และมีคำบรรยายว่าภาพแก้ปัญหาอะไร อ่านอย่างไร และแปลว่าอะไร",
    step_next="ทีละขั้น →", step_prev="ขั้นก่อนหน้า", traps="กับดัก", onmap="อยู่ตรงไหนบนแผนที่รวม",
    catalog_title="ทุกกล่องในแผนที่",
    catalog_intro="คำอธิบายชุดเดียวกับที่แสดงเมื่อกดกล่องบนแผนที่ — รวมไว้ให้อ่านต่อเนื่องได้โดยไม่ต้องคลิก เรียงตามชั้น",
    legend_title="วิธีอ่านแผนที่", conn_legend="ตัวเชื่อม: วงกลมตัวอักษรเดียวกัน = สายเดียวกันที่ต่อข้ามแผนที่",
    badge_legend="ด่านตรวจ / จุดสำคัญที่ต้องผ่าน",
)
STORY = [("problem", "ปัญหา"), ("think", "คิดอะไรอยู่"), ("choose", "วิธีที่เลือก และเพราะอะไร"),
         ("read", "อ่านภาพอย่างไร"), ("result", "ผลที่ได้"), ("mean", "แปลว่า")]


# ---------------------------------------------------------------- อ่าน spec พร้อมค่าเริ่มต้น
class Spec:
    def __init__(self, mod):
        g = lambda name, default: getattr(mod, name, default)  # noqa: E731
        self.mod = mod
        self.meta = dict(g("META", {}))
        self.ui = {**UI, **g("UI", {})}
        self.story = list(g("STORY", STORY))
        self.edge_kinds = {**EDGE_KINDS, **g("EDGE_KINDS", {})}
        self.topics = [t if isinstance(t, dict) else dict(id=t[0], label=t[1], **({"color": t[2]} if len(t) > 2 else {}))
                       for t in g("TOPICS", [])]
        self.focus = [dict(f) for f in g("FOCUS", [])]
        self.bands = [dict(b) for b in g("BANDS", [])]
        self.columns = [dict(c) for c in g("COLUMNS", [])]
        self.boundaries = list(g("BOUNDARIES", []))
        self.w, self.h = g("SIZE", (1600, 1000))
        self.nodes = list(g("NODES", []))
        self.edges = list(g("EDGES", []))
        self.conns = list(g("CONNS", []))
        self.allow = tuple(g("ALLOW", ()))
        self.desc = dict(g("DESC", {}))
        self.deep = Deep(g("DEEP", {}), g("FIG_DEEP", {}))
        self.tour = list(g("TOUR", []))
        self.pairs = list(g("PAIRS", []))
        self.groups = list(g("GROUPS", []))
        self.legend_at = g("MAP_LEGEND_AT", None)
        self.extra_css = g("EXTRA_CSS", "")
        self.extra_js = g("EXTRA_JS", "")
        for name, svg_ in g("ICONS", {}).items():
            I.register(name, svg_)
        self.by_id = {n.id: n for n in self.nodes}
        self.figs = [f for grp in self.groups for ch in grp["chapters"] for f in ch["figs"]]
        self.fig_titles = {f["id"]: f["title"] for f in self.figs}
        self.focus_by_id = {f["id"]: f for f in self.focus}


def validate(S: Spec) -> list[str]:
    """อ้างอิงที่ผิด (id ไม่มีจริง ฯลฯ) — ถ้ามี จะไม่เขียนไฟล์ เพราะหน้าจะพังแบบเงียบๆ"""
    err = []

    def dup(kind, ids):
        seen = set()
        for i in ids:
            if i in seen:
                err.append(f"{kind}: id ซ้ำ {i!r}")
            seen.add(i)
    topic_ids = {t["id"] for t in S.topics} | {"base"}
    for t in S.topics:
        if not CSS_ID.match(t["id"]):
            err.append(f"TOPICS: id {t['id']!r} ต้องเป็นตัวพิมพ์เล็กอังกฤษ/ตัวเลข/ขีด (ใช้เป็นชื่อ class)")
        if t.get("color") and t["color"] not in TOPIC_PALETTE:
            err.append(f"TOPICS {t['id']}: สี {t['color']!r} ไม่มี — เลือกจาก {', '.join(PALETTE_ORDER)}")
    for b in S.bands:
        if not CSS_ID.match(b["id"]):
            err.append(f"BANDS: id {b['id']!r} ต้องเป็นตัวพิมพ์เล็กอังกฤษ/ตัวเลข/ขีด")
    for c in S.columns:
        if c.get("topic", "base") not in topic_ids:
            err.append(f"COLUMNS {c.get('head')!r}: ไม่มี topic {c.get('topic')!r}")
    dup("TOPICS", [t["id"] for t in S.topics])
    dup("BANDS", [b["id"] for b in S.bands])
    dup("FOCUS", [f["id"] for f in S.focus])
    dup("NODES", [n.id for n in S.nodes])
    dup("EDGES", [e.id for e in S.edges])
    dup("CONNS", [c.id for c in S.conns])
    dup("ภาพรายบท", [f["id"] for f in S.figs])
    dup("บท", [ch["id"] for grp in S.groups for ch in grp["chapters"]])
    for f in S.focus:
        if f.get("topic", "base") not in topic_ids:
            err.append(f"FOCUS {f['id']}: ไม่มี topic {f.get('topic')!r}")
    for n in S.nodes:
        if n.topic not in topic_ids:
            err.append(f"NODE {n.id}: ไม่มี topic {n.topic!r}")
        for q in n.q:
            if q not in S.focus_by_id:
                err.append(f"NODE {n.id}: q={q!r} ไม่มีใน FOCUS")
        if n.kind == "card" and n.icon and n.icon not in I.ICONS:
            err.append(f"NODE {n.id}: ไม่มีไอคอน {n.icon!r} (ดูรายชื่อด้วย scripts/icon_gallery.py หรือเพิ่มใน ICONS ของ spec)")
    for e in S.edges:
        for end in (e.src, e.dst):
            if end not in S.by_id:
                err.append(f"EDGE {e.id}: ไม่มีกล่อง {end!r}")
        if e.kind not in S.edge_kinds:
            err.append(f"EDGE {e.id}: kind {e.kind!r} ต้องเป็นหนึ่งใน {list(S.edge_kinds)}")
    for c in S.conns:
        for end in (c.src, c.dst):
            if end not in S.by_id:
                err.append(f"CONN {c.id}: ไม่มีกล่อง {end!r}")
    eids, cids = {e.id for e in S.edges}, {c.id for c in S.conns}
    for e, n in S.allow:
        if e not in eids or n not in S.by_id:
            err.append(f"ALLOW: ไม่มี ({e!r}, {n!r})")
    for nid in S.desc:
        if nid not in S.by_id:
            err.append(f"DESC: ไม่มีกล่อง {nid!r}")
    for i, s in enumerate(S.tour, 1):
        for nid in s.get("n", []):
            if nid not in S.by_id:
                err.append(f"TOUR ขั้น {i}: ไม่มีกล่อง {nid!r}")
        for eid in s.get("e", []):
            if eid not in eids:
                err.append(f"TOUR ขั้น {i}: ไม่มีเส้น {eid!r}")
        for cid in s.get("c", []):
            if cid not in cids:
                err.append(f"TOUR ขั้น {i}: ไม่มีตัวเชื่อม {cid!r}")
    for p in S.pairs:
        for nid in p[2]:
            if nid not in S.by_id:
                err.append(f"PAIRS {p[0]} vs {p[1]}: ไม่มีกล่อง {nid!r}")
    for grp in S.groups:
        for ch in grp["chapters"]:
            if ch.get("topic", "base") not in topic_ids:
                err.append(f"บท {ch['id']}: ไม่มี topic {ch.get('topic')!r}")
            for q in ch.get("q", ()):
                if q not in S.focus_by_id:
                    err.append(f"บท {ch['id']}: q={q!r} ไม่มีใน FOCUS")
            for f in ch["figs"]:
                if not ("draw" in f or "html" in f):
                    err.append(f"ภาพ {f['id']}: ต้องมี draw (คืน Graph/Draw) หรือ html (คืนสตริง HTML)")
                for nid in f.get("onmap", []):
                    if nid not in S.by_id:
                        err.append(f"ภาพ {f['id']}.onmap: ไม่มีกล่อง {nid!r}")
                for k in f.get("story", {}):
                    if k not in dict(S.story):
                        err.append(f"ภาพ {f['id']}.story: ไม่รู้จัก {k!r} (ใช้ {', '.join(dict(S.story))})")
    err += S.deep.check(set(S.fig_titles), set(S.by_id))
    return err


def advisories(S: Spec) -> list[str]:
    """ไม่ผิด แต่ควรเติม (พิมพ์เป็นคำแนะนำ)"""
    out = []
    for n in S.nodes:
        if n.id not in S.desc:
            out.append(f"กล่อง {n.id} ยังไม่มี DESC (คลิกแล้วแผงข้างจะว่าง)")
        if layer_of(S, n) is None and S.bands:
            out.append(f"กล่อง {n.id} ไม่อยู่ในแถบไหนเลย (BANDS)")
    for f in S.figs:
        if "draw" in f and not f.get("story"):
            out.append(f"ภาพ {f['id']} ยังไม่มี story (ปัญหา → คิด → วิธี → อ่านภาพ → ผล → แปลว่า)")
    return out


def layer_of(S: Spec, n):
    cy = n.y if n.kind == "badge" else n.y + n.h / 2
    for b in S.bands:
        if b["y0"] <= cy <= b["y1"]:
            return b["id"]
    return None


# ---------------------------------------------------------------- แผนที่รวม
def map_background(S: Spec) -> str:
    out = []
    for b in S.bands:
        y0, y1 = b["y0"], b["y1"]
        out.append(f'<rect class="band-{b["id"]}" x="8" y="{y0}" width="{S.w - 16}" height="{y1 - y0}" rx="14"/>')
        label = f'{b["name"]} · {b["sub"]}' if b.get("sub") else b["name"]
        out.append(f'<text class="band-lbl" transform="translate(34,{(y0 + y1) / 2}) rotate(-90)" text-anchor="middle">{esc(label)}</text>')
    for c in S.columns:
        x0, x1 = c["x0"], c["x1"]
        y = c.get("y", 42)
        sub_x = x0 + text_w(c["head"], 19, 700) * 1.12 + 14   # Chakra Petch กว้างกว่า Sarabun ราว 12%
        out.append(f'<g class="topic-{c.get("topic", "base")}">'
                   f'<line class="col-rule" x1="{x0}" y1="{y + 14}" x2="{x1}" y2="{y + 14}"/>'
                   f'<text class="col-h" x="{x0}" y="{y}">{esc(c["head"])}</text>'
                   + (f'<text class="col-sub" x="{sub_x:.0f}" y="{y}">{esc(c["sub"])}</text>' if c.get("sub") else "")
                   + (f'<text class="col-tag" x="{x1}" y="{y}" text-anchor="end">{esc(c["tag"])}</text>' if c.get("tag") else "")
                   + "</g>")
    for bd in S.boundaries:
        y, x, text = bd[0], bd[1], bd[2]
        below = len(bd) > 3 and bd[3] == "below"
        out.append(f'<line class="bnd" x1="8" y1="{y}" x2="{S.w - 8}" y2="{y}"/>')
        out.append(f'<text class="bnd-lbl" x="{x}" y="{y + 16 if below else y - 7}">{esc(text)}</text>')
    return "".join(out)


def map_legend(S: Spec) -> tuple[str, list]:
    """กล่องคำอธิบายสัญลักษณ์ที่วาดในแผนที่เอง (ตำแหน่ง MAP_LEGEND_AT) — อ่านได้แม้ซูมอยู่"""
    if not S.legend_at:
        return "", []
    x0, y0 = S.legend_at
    kinds = [k for k in ("ctl", "data", "sig", "rel") if any(e.kind == k for e in S.edges)]
    has_conn, has_badge = bool(S.conns), any(n.kind == "badge" for n in S.nodes)
    texts = ([S.edge_kinds[k] for k in kinds] + ([S.ui["conn_legend"]] if has_conn else [])
             + ([S.ui["badge_legend"]] if has_badge else []))
    w = max([88 + text_w(t, 12.5) for t in texts] + [46 + text_w(t["label"], 12.5) for t in S.topics]
            + [16 + text_w(S.ui["legend_title"], 13, 700) * 1.25]) + 18
    h = 48 + len(texts) * 28 + (8 + len(S.topics) * 24 if S.topics else 0)
    out = [f'<rect class="legend-box" x="{x0}" y="{y0}" width="{w:.0f}" height="{h}" rx="10"/>',
           f'<text class="lg-h" x="{x0 + 16}" y="{y0 + 28}">{esc(S.ui["legend_title"])}</text>']
    y = y0 + 56
    for kind in kinds:
        out.append(f'<g class="edge k-{kind}"><path class="e-line" d="M{x0 + 18},{y - 4} H{x0 + 66}"/>'
                   + ('' if kind == "rel" else f'<path class="e-head" d="M{x0 + 74},{y - 4} l-9,-4.2 v8.4 Z"/>')
                   + f'</g><text class="lg-t" x="{x0 + 88}" y="{y}">{esc(S.edge_kinds[kind])}</text>')
        y += 28
    if has_conn:
        out.append(f'<circle class="c-ring" cx="{x0 + 44}" cy="{y - 4}" r="11"/>'
                   f'<text class="c-letter" x="{x0 + 44}" y="{y + 0.5}" text-anchor="middle">A</text>'
                   f'<text class="lg-t" x="{x0 + 88}" y="{y}">{esc(S.ui["conn_legend"])}</text>')
        y += 28
    if has_badge:
        out.append(f'<g class="topic-base"><circle class="b-ring" cx="{x0 + 44}" cy="{y - 4}" r="13"/>'
                   f'<g transform="translate({x0 + 35},{y - 13}) scale(0.32)">{I.icon("shield")}</g></g>'
                   f'<text class="lg-t" x="{x0 + 88}" y="{y}">{esc(S.ui["badge_legend"])}</text>')
        y += 28
    if S.topics:
        y -= 8
        for i, t in enumerate(S.topics):
            cy = y + i * 24
            out.append(f'<g class="topic-{t["id"]}"><rect class="n-box" x="{x0 + 16}" y="{cy}" width="22" height="14" rx="3"/>'
                       f'<text class="lg-t" x="{x0 + 46}" y="{cy + 12}">{esc(t["label"])}</text></g>')
    return "".join(out), [("legend", (x0, y0, w, h))]


def build_map(S: Spec) -> Graph:
    legend, obstacles = map_legend(S)
    return Graph(S.w, S.h, S.nodes, S.edges, S.conns, background=map_background(S), foreground=legend,
                 svg_id="bigmap-svg", cls="map", aria=S.meta.get("map_aria", S.meta.get("title", "")),
                 allow=S.allow, obstacles=obstacles)


def _desc_html(S: Spec, nid: str) -> dict:
    d = S.desc.get(nid, {})
    return dict(what=fmt(d.get("what", "")), does=[fmt(x) for x in d.get("does", [])], look=fmt(d.get("look", "")),
                exam=[fmt(x) for x in d.get("exam", [])], read=fmt(d.get("read", "")))


def map_data(S: Spec) -> dict:
    nodes = {}
    for n in S.nodes:
        nodes[n.id] = dict(name=n.name, gloss=n.gloss, topic=n.topic, ch=n.ch, q=list(n.q), kind=n.kind,
                           layer=layer_of(S, n), **_desc_html(S, n.id), deep=S.deep.render(n.id, S.fig_titles))
    edges = [dict(id=e.id, src=e.src, dst=e.dst, label=e.label) for e in S.edges]
    conns = [dict(id=c.id, letter=c.letter, src=c.src, dst=c.dst, src_label=c.src_label, dst_label=c.dst_label) for c in S.conns]
    tour = [dict(act=s.get("act", ""), t=s["t"], x=s.get("x", ""), n=s.get("n", []), e=s.get("e", []), c=s.get("c", []))
            for s in S.tour]
    layers = {b["id"]: b.get("chip", b["name"]) for b in S.bands}
    focus = {f["id"]: dict(label=f.get("label", f["id"]), topic=f.get("topic", "base")) for f in S.focus}
    ui = {k: S.ui[k] for k in ("what", "does", "look", "exam", "links", "read", "ch", "step", "whole", "of", "steps",
                               "tour", "tour_hint", "focus_desc")}
    return dict(nodes=nodes, edges=edges, conns=conns, tour=tour, layers=layers, focus=focus, ui=ui)


# ---------------------------------------------------------------- ส่วนต่างๆ ของหน้า
def header(S: Spec) -> str:
    m = S.meta
    cards = ""
    if any(f.get("card", True) for f in S.focus):
        cards = '<div class="exam">' + "".join(
            f'<div class="q qc-{f.get("topic", "base")}"><b>{esc(f.get("label", f["id"]))}'
            + (f' <span class="pts">{esc(f["points"])}</span>' if f.get("points") else "") + "</b>"
            + f'<span>{esc(f.get("title", ""))}</span>' + (f'<span>{esc(f["where"])}</span>' if f.get("where") else "")
            + "</div>" for f in S.focus if f.get("card", True)) + "</div>"
    return (f'<header class="top"><div class="wrap">'
            + (f'<p class="eyebrow">{esc(m["eyebrow"])}</p>' if m.get("eyebrow") else "")
            + f'<h1>{esc(m.get("title", "แผนที่"))}</h1>'
            + (f'<p class="lead">{fmt(m["lead"])}</p>' if m.get("lead") else "")
            + f"{cards}</div></header>")


def nav(S: Spec) -> str:
    u = S.ui
    links = [f'<a href="#map">{esc(u["nav_map"])}</a>']
    if S.tour:
        links.append(f'<a href="#tour">{esc(u["nav_tour"])} {len(S.tour)} {esc(u["steps"])}</a>')
    if S.pairs:
        links.append(f'<a href="#pairs">{esc(u["nav_pairs"])}</a>')
    for g in S.groups:
        links.append(f'<span class="grp">{esc(g.get("short", ""))}</span>')
        links += [f'<a href="#{ch["id"]}">{esc(_nav_label(u, ch))}</a>' for ch in g["chapters"]]
    links.append(f'<a href="#catalog">{esc(u["nav_catalog"])}</a>')
    return f'<nav class="nav" aria-label="ไปยังส่วนต่างๆ"><div class="wrap">{"".join(links)}</div></nav>'


def _nav_label(u: dict, ch: dict) -> str:
    """ป้ายของบทในแถบนำทาง: nav ที่ spec ให้ → "บท 9" → ชื่อบท (เมื่อไม่ใช้คำนำหน้าบท)"""
    if ch.get("nav"):
        return ch["nav"]
    if u["ch"] and ch.get("num"):
        return f'{u["ch"]} {ch["num"]}'
    return ch["title"]


def legend_html(S: Spec) -> str:
    def line(kind):
        dash = {"ctl": "", "data": "", "sig": ' stroke-dasharray="7 4"', "rel": ' stroke-dasharray="2 4"'}[kind]
        wdt = {"data": 3.2}.get(kind, 1.6)
        return (f'<svg viewBox="0 0 34 12" aria-hidden="true"><path d="M1,6 H26" stroke="currentColor" stroke-width="{wdt}"'
                f' fill="none"{dash}/>' + ('' if kind == "rel" else '<path d="M33,6 l-8,-4 v8 Z" fill="currentColor"/>') + '</svg>')
    items = [line(k) + esc(S.edge_kinds[k]) for k in ("ctl", "data", "sig", "rel") if any(e.kind == k for e in S.edges)]
    items += [f'<span class="dot qc-{t["id"]}"></span>{esc(t["label"])}' for t in S.topics]
    return '<div class="legend">' + "".join(f'<span class="sw">{i}</span>' for i in items) + "</div>"


def howto(S: Spec) -> str:
    u, ax = S.ui, S.meta.get("axes", {})
    rows = []
    if ax.get("vertical"):
        rows.append(f'<li><b>{esc(ax.get("vertical_label", "ตำแหน่งแนวตั้ง"))}</b> — {fmt(ax["vertical"])}</li>')
    if ax.get("horizontal"):
        rows.append(f'<li><b>{esc(ax.get("horizontal_label", "คอลัมน์"))}</b> — {fmt(ax["horizontal"])}</li>')
    rows.append(f"<li>{u['howto_click']}</li>")
    if S.tour:
        rows.append(f"<li>{u['howto_tour']}</li>")
    if S.focus:
        rows.append(f"<li>{u['howto_focus']}</li>")
    rows.append(f"<li>{u['howto_zoom']}</li>")
    return (f'<h3>{esc(u["howto_title"])}</h3><div class="howto"><p class="gl">{fmt(u["howto_lead"])}</p>'
            f'<ul>{"".join(rows)}</ul></div>')


def map_section(S: Spec, g: Graph) -> str:
    u = S.ui
    qbtns = ""
    if S.focus:
        qbtns = f'<span class="sep"></span><span class="hint">{esc(u["focus_hint"])}</span>' + "".join(
            f'<button type="button" class="btn qbtn qc-{f.get("topic", "base")}" aria-pressed="false" data-q="{esc(f["id"])}" '
            f'data-title="{esc(f.get("label", f["id"]))} · {esc(f.get("title", ""))}">{esc(f.get("label", f["id"]))}</button>'
            for f in S.focus)
    tourbar, tour_list = "", ""
    if S.tour:
        title = S.meta.get("tour_title", u["tour"])
        intro = S.meta.get("tour_intro", "")
        tourbar = (f'<div class="tourbar" id="tourbar" data-title="{esc(title)}" data-intro="{esc(intro)}">'
                   f'<div class="num">—<small>{len(S.tour)} {esc(u["steps"])}</small></div>'
                   f'<div><p class="act">{esc(u["tour"])}</p><h3>{esc(title)}</h3><p>{esc(intro)}</p></div>'
                   f'<div class="nav2"><button type="button" class="btn" id="t-prev">{esc(u["prev"])}</button>'
                   f'<button type="button" class="btn" id="t-next">{esc(u["next"])}</button>'
                   f'<button type="button" class="btn" id="t-reset">{esc(u["reset"])}</button></div></div>')
        items, last = [], None
        for i, s in enumerate(S.tour):
            if s.get("act") and s["act"] != last:
                items.append(f'<li class="act-h">{esc(s["act"])}</li>')
                last = s["act"]
            items.append(f'<li><button type="button"><span class="n">{i + 1:02d}</span><span>{esc(s["t"])}</span></button></li>')
        tour_list = (f'<div id="tour" class="sec-head" style="margin-top:34px"><h3>{esc(u["tour_list_title"].format(n=len(S.tour)))}</h3>'
                     f'<p>{esc(u["tour_list_intro"])}</p></div><ol class="tour-list" id="tour-list">{"".join(items)}</ol>')
    return (f'<section id="map"><div class="wrap wide"><div class="sec-head"><h2>{esc(S.meta.get("map_title", u["map_title"]))}</h2>'
            f'<p>{fmt(S.meta.get("map_intro", u["map_intro"]))}</p></div>{legend_html(S)}'
            f'<div class="toolbar" role="toolbar" aria-label="ควบคุมแผนที่">'
            f'<button type="button" class="btn" id="z-fit">{esc(u["fit"])}</button>'
            f'<button type="button" class="btn" id="z-out" aria-label="{esc(u["zoom_out"])}">−</button>'
            f'<span class="zoomval" id="zoomval">100%</span>'
            f'<button type="button" class="btn" id="z-in" aria-label="{esc(u["zoom_in"])}">+</button>'
            f'<button type="button" class="btn" id="z-100">100%</button>{qbtns}</div>'
            f'<div class="shell"><div class="stage">{tourbar}<div class="vp" id="map-vp">{g.svg()}</div></div>'
            f'<aside class="panel" id="map-panel" aria-live="polite">{howto(S)}</aside></div>{tour_list}</div></section>')


def pairs_section(S: Spec) -> str:
    if not S.pairs:
        return ""
    u = S.ui
    cards = []
    for p in S.pairs:
        a, b, ids, text = p[0], p[1], p[2], p[3]
        cards.append(f'<div class="pair"><h3>{esc(a)}<i>{esc(u["vs"])}</i>{esc(b)}</h3><p>{fmt(text)}</p>'
                     f'<button type="button" class="btn" data-show="{" ".join(ids)}" data-title="{esc(a)} {esc(u["vs"])} {esc(b)}"'
                     f' data-text="{esc(text)}">{esc(u["show_on_map"])}</button></div>')
    return (f'<section id="pairs"><div class="wrap"><div class="sec-head"><h2>{esc(u["pairs_title"])}</h2>'
            f'<p>{fmt(S.meta.get("pairs_intro", u["pairs_intro"]))}</p></div><div class="pairs">{"".join(cards)}</div></div></section>')


def figure_html(S: Spec, f: dict, topic: str) -> tuple[str, list]:
    u = S.ui
    if "html" in f:                                # ภาพที่เป็น HTML เอง (ตารางโต้ตอบ ฯลฯ) ไม่ใช่ SVG
        body, issues = f'<div class="figbody">{f["html"]()}</div>', []
    else:
        art = f["draw"]()
        if isinstance(art, Graph):
            art.interactive = False                # กล่องในภาพรายบทไม่ได้กดได้ → ไม่ประกาศเป็นปุ่ม
        elif not isinstance(art, Draw):
            raise TypeError(f"ภาพ {f['id']}: draw() ต้องคืน Graph หรือ Draw")
        body, issues = f'<div class="figbox">{art.svg()}</div>', art.check(f["id"])
    steps = f.get("steps", [])
    stepper = ""
    if steps:
        stepper = (f'<div class="stepper"><button type="button" class="btn s-prev" aria-label="{esc(u["step_prev"])}">←</button>'
                   f'<button type="button" class="btn s-next">{esc(u["step_next"])}</button>'
                   f'<button type="button" class="btn s-all">{esc(u["whole"])}</button><span class="cnt">{esc(u["whole"])}</span></div>')
    parts = [f'<figure class="fig topic-{f.get("topic", topic)}" id="{f["id"]}"{" data-steps" if steps else ""}>',
             f'<div class="fig-title"><h3>{esc(f["title"])}</h3>{stepper}</div>', body]
    if f.get("caption"):
        parts.append(f'<figcaption>{fmt(f["caption"])}</figcaption>')
    if steps:
        parts.append('<ol class="steps">' + "".join(
            f'<li><span class="k">{i + 1}</span><span><b>{fmt(t)}</b> — {fmt(x)}</span></li>' for i, (t, x) in enumerate(steps)) + "</ol>")
    if f.get("story"):
        parts.append('<dl class="story">' + "".join(
            f'<div><dt>{esc(label)}</dt><dd>{fmt(f["story"][k])}</dd></div>' for k, label in S.story if k in f["story"]) + "</dl>")
    if f.get("traps"):
        parts.append(f'<div class="traps"><b>{esc(u["traps"])}</b><ul>' + "".join(f"<li>{fmt(t)}</li>" for t in f["traps"]) + "</ul></div>")
    if f.get("onmap"):
        parts.append(f'<p class="onmap">{esc(u["onmap"])}: ' + "".join(
            f'<button type="button" data-show="{nid}">{esc(S.by_id[nid].name)}</button>' for nid in f["onmap"]) + "</p>")
    parts.append(S.deep.render_fig(f["id"], {n.id: n.name for n in S.nodes}, S.fig_titles))
    parts.append("</figure>")
    return "".join(parts), issues


def chapters_html(S: Spec) -> tuple[str, list]:
    if not S.groups:
        return "", []
    u = S.ui
    out = [f'<section id="chapters"><div class="wrap"><div class="sec-head"><h2>{esc(S.meta.get("chapters_title", u["chapters_title"]))}</h2>'
           f'<p>{fmt(S.meta.get("chapters_intro", u["chapters_intro"]))}</p></div></div></section>']
    issues = []
    for g in S.groups:
        out.append(f'<div class="ch-group" id="{g["id"]}"><div class="wrap"><h2>{esc(g["title"])} '
                   f'<small>{esc(g.get("sub", ""))}</small></h2></div></div>')
        for ch in g["chapters"]:
            tags = "".join(f'<span class="chip q qc-{S.focus_by_id[q].get("topic", "base")}">{esc(S.focus_by_id[q].get("label", q))}</span>'
                           for q in ch.get("q", ()))
            for extra in ("stars", "note"):
                if ch.get(extra):
                    tags += f'<span class="chip">{esc(ch[extra])}</span>'
            figs = []
            for f in ch["figs"]:
                h, iss = figure_html(S, f, ch.get("topic", "base"))
                figs.append(h)
                issues += iss
            head = (f'<header class="ch-head"><div class="ch-num">{esc(ch.get("num", ""))}</div><h2>{esc(ch["title"])}</h2>'
                    f'<div class="tags">{tags}</div>' + (f'<p class="thesis">{fmt(ch["thesis"])}</p>' if ch.get("thesis") else "")
                    + "</header>")
            out.append(f'<section class="ch topic-{ch.get("topic", "base")}" id="{ch["id"]}"><div class="wrap">{head}{"".join(figs)}</div></section>')
    return "\n".join(out), issues


def catalog_section(S: Spec) -> str:
    u = S.ui
    groups = {b["id"]: [] for b in S.bands}
    groups[None] = []
    for n in sorted(S.nodes, key=lambda n: (n.x, n.y)):
        groups.setdefault(layer_of(S, n), []).append(n)
    names = {b["id"]: b for b in S.bands}
    out = []
    for lid, ns in groups.items():
        if not ns:
            continue
        b = names.get(lid, dict(name="อื่นๆ", note=""))
        cards = []
        for n in ns:
            d = _desc_html(S, n.id)
            ic = n.icon or ("shield" if n.kind == "badge" else "")
            chips = (f'<span class="chip">{esc(u["ch"])} {esc(n.ch)}</span>' if n.ch else "") + "".join(
                f'<span class="chip q qc-{S.focus_by_id[q].get("topic", "base")}">{esc(S.focus_by_id[q].get("label", q))}</span>' for q in n.q)
            body = [f"<p>{d['what']}</p>"] if d["what"] else []
            if d["does"]:
                body.append(f'<p class="lbl">{esc(u["does"])}</p><ul>' + "".join(f"<li>{s}</li>" for s in d["does"]) + "</ul>")
            if d["look"]:
                body.append(f'<p class="lbl">{esc(u["look"])}</p><p>{d["look"]}</p>')
            if d["exam"]:
                body.append(f'<p class="lbl">{esc(u["exam"])}</p><ul class="ex">' + "".join(f"<li>{s}</li>" for s in d["exam"]) + "</ul>")
            if d["read"]:
                body.append(f'<p class="read">{esc(u["read"])}: {d["read"]}</p>')
            cards.append(f'<article class="card topic-{n.topic}" id="cat-{n.id}"><header>'
                         f'<svg viewBox="0 0 56 56" aria-hidden="true">{I.icon(ic)}</svg>'
                         f'<div><h4>{esc(n.name)}</h4><p class="gl">{esc(n.gloss)}</p><div class="chips">{chips}</div></div></header>'
                         f'{"".join(body)}{S.deep.render(n.id, S.fig_titles, open_=False)}'
                         f'<button type="button" class="btn" data-show="{n.id}">{esc(u["show_on_map"])}</button></article>')
        out.append(f'<div class="cat-group"><h3>{esc(b["name"])} <small>{esc(b.get("note", ""))}</small></h3>'
                   f'<div class="cat">{"".join(cards)}</div></div>')
    return (f'<section id="catalog"><div class="wrap"><div class="sec-head"><h2>{esc(u["catalog_title"])}</h2>'
            f'<p>{fmt(u["catalog_intro"])}</p></div>{"".join(out)}</div></section>')


def footer(S: Spec) -> str:
    lines = S.meta.get("footer", [])
    if isinstance(lines, str):
        lines = [lines]
    return '<footer class="foot"><div class="wrap">' + "".join(f"<p>{fmt(s)}</p>" for s in lines) + "</div></footer>"


def page(S: Spec, fragment: bool) -> tuple[str, list]:
    SV.CH_PREFIX = S.ui["ch"]
    DEEP_UI["show"] = S.ui["show_on_map"]
    g = build_map(S)
    issues = g.check("map")
    ch_html, ch_issues = chapters_html(S)
    issues += ch_issues
    data = json.dumps(map_data(S), ensure_ascii=False).replace("</", "<\\/")
    body = "\n".join([header(S), nav(S), "<main>", map_section(S, g), pairs_section(S), ch_html, catalog_section(S), "</main>",
                      footer(S), f'<script type="application/json" id="submap-data">{data}</script>', f"<script>{JS}</script>"]
                     + ([f"<script>{S.extra_js}</script>"] if S.extra_js else []))
    css = CSS.replace("/*THEME*/", theme_css(S.topics, S.bands)) + S.extra_css
    title = S.meta.get("title", "แผนที่")
    head = (f'<title>{esc(title)}</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
            f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            f'<link rel="stylesheet" href="{FONTS}">\n<style>{css}</style>\n')
    if fragment:
        return head + body, issues
    return (f'<!doctype html>\n<html lang="{esc(S.meta.get("lang", "th"))}">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'{head}</head>\n<body>\n{body}\n</body>\n</html>\n'), issues


def main(spec_module, out: Path, argv=None) -> int:
    ap = argparse.ArgumentParser(description="สร้างแผนที่วิชาจาก spec")
    ap.add_argument("--check", action="store_true", help="ตรวจอย่างเดียว ไม่เขียนไฟล์ (exit 1 ถ้ามีปัญหา)")
    ap.add_argument("--fragment", type=Path, help="เขียนฉบับไม่มี <html>/<head> ไปที่ไฟล์นี้ด้วย (สำหรับ artifact)")
    ap.add_argument("--out", type=Path, default=out, help=f"ไฟล์ HTML ที่จะเขียน (ค่าเริ่ม {out})")
    args = ap.parse_args(argv)
    S = Spec(spec_module)
    errors = validate(S)
    if errors:
        for s in errors:
            print("✗", s)
        print(f"อ้างอิงผิด {len(errors)} จุด — แก้ใน spec ก่อน (ยังไม่เขียนไฟล์)")
        sys.exit(2)
    html, issues = page(S, fragment=False)
    for s in advisories(S):
        print("·", s)
    for s in fonts.WARNINGS:
        print("⚠ ฟอนต์:", s)
    for s in issues:
        print("⚠", s)
    stats = (f"{len(S.nodes)} กล่อง · {len(S.edges)} เส้น · {len(S.conns)} ตัวเชื่อม · ทัวร์ {len(S.tour)} ขั้น · "
             f"คู่สับสน {len(S.pairs)} · ภาพรายบท {len(S.figs)}")
    print(f"ตรวจแล้ว: {len(issues)} ปัญหาการจัดวาง · {stats}")
    if args.check:
        sys.exit(1 if issues else 0)
    args.out.write_text(html, encoding="utf-8")
    print(f"เขียน {args.out} ({len(html.encode()) / 1024:.0f} KB)")
    if args.fragment:
        frag, _ = page(S, fragment=True)
        args.fragment.write_text(frag, encoding="utf-8")
        print(f"เขียน {args.fragment} ({len(frag.encode()) / 1024:.0f} KB)")
    return 0
