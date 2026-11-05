"""เนื้อหา "อธิบายละเอียด" ของแต่ละกล่อง → HTML (แผงข้างแผนที่ · แค็ตตาล็อก · ท้ายภาพรายบท)

DEEP[node_id] = dict(blocks=[...], figs=[id ของภาพรายบทที่เกี่ยว])
แต่ละ block (เขียนเรียงตามลำดับที่อยากให้อ่าน):
    ("p", หัวข้อ, ข้อความ)                       ย่อหน้า
    ("ol" | "ul", หัวข้อ, [ข้อ, ...])             รายการมีลำดับ / ไม่มีลำดับ
    ("calc", หัวข้อ, [บรรทัด, ...])               ตัวอย่างตัวเลขทีละบรรทัด — ตัวเลขต้องคำนวณใน spec ไม่พิมพ์มือ
    ("table", หัวข้อ, [หัวตาราง], [[แถว], ...])
    ("img", path, คำบรรยาย)                       ภาพ (gif/png/svg) พับไว้ กดเปิดเอง · path นับจากไฟล์ HTML
    ("trap", [ข้อ, ...])                          กับดัก / จุดที่มักเข้าใจผิด
ข้อความใช้ **ตัวหนา** · `โค้ดหรือสูตร` · *ตัวเอียง* ได้

FIG_DEEP[fig_id] = [node_id | (node_id, [ลำดับ block])] — ย้ายเนื้อหาละเอียดไปแสดงท้ายภาพรายบทที่อธิบายเรื่องนั้น
ถ้ามี FIG_DEEP: ทุก block ต้องอยู่ในภาพใดภาพหนึ่งพอดีหนึ่งครั้ง (check_fig_deep)
"""
from __future__ import annotations

import re

from .svg import esc

UI = {"deep": "อธิบายละเอียด", "fig_links": "ภาพกระบวนการที่เกี่ยวข้อง", "more_in": "อ่านต่อในภาพ",
      "img": "ภาพประกอบ", "trap": "กับดัก / จุดที่มักเข้าใจผิด", "show": "ชี้บนแผนที่", "in_fig": "เรื่องในภาพนี้"}


def fmt(s: str) -> str:
    """escape แล้วแปลง **ตัวหนา** · `สูตร` · *ตัวเอียง*"""
    out = esc(s)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", out)


def blocks_html(node_id: str, blocks) -> str:
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "p":
            out.append(f'<div class="db"><h4>{fmt(b[1])}</h4><p>{fmt(b[2])}</p></div>')
        elif kind in ("ol", "ul"):
            items = "".join(f"<li>{fmt(x)}</li>" for x in b[2])
            out.append(f'<div class="db"><h4>{fmt(b[1])}</h4><{kind}>{items}</{kind}></div>')
        elif kind == "calc":
            lines = "".join(f"<li>{fmt(x)}</li>" for x in b[2])
            out.append(f'<div class="db calc"><h4>{fmt(b[1])}</h4><ul>{lines}</ul></div>')
        elif kind == "table":
            head = "".join(f"<th>{fmt(h)}</th>" for h in b[2])
            rows = "".join("<tr>" + "".join(f"<td>{fmt(c)}</td>" for c in r) + "</tr>" for r in b[3])
            out.append(f'<div class="db"><h4>{fmt(b[1])}</h4><div class="dscroll"><table class="dtab"><thead><tr>{head}</tr></thead>'
                       f'<tbody>{rows}</tbody></table></div></div>')
        elif kind in ("img", "gif"):
            src = b[1] if kind == "img" or "." in b[1] else f"assets/{b[1]}.gif"   # "gif" = รูปแบบเดิมของแผนที่ OS
            out.append(f'<details class="dgif"><summary>{UI["img"]}: {fmt(b[2])}</summary>'
                       f'<img src="{esc(src)}" alt="{esc(b[2])}" loading="lazy"></details>')
        elif kind == "trap":
            out.append(f'<div class="db dtrap"><h4>{UI["trap"]}</h4><ul>' + "".join(f"<li>{fmt(x)}</li>" for x in b[1]) + "</ul></div>")
        else:
            raise ValueError(f"{node_id}: block ไม่รู้จัก {kind!r}")
    return "".join(out)


def _fig_links(figs, fig_titles, label) -> str:
    figs = [f for f in figs or [] if f in fig_titles]
    if not figs:
        return ""
    return f'<p class="dfigs">{label}: ' + " · ".join(f'<a href="#{f}">{esc(fig_titles[f])}</a>' for f in figs) + "</p>"


class Deep:
    """ผูกเนื้อหาละเอียดของ spec ทั้งหมด (DEEP + FIG_DEEP) ไว้ด้วยกัน"""

    def __init__(self, deep: dict, fig_deep: dict | None = None):
        self.deep = {k: dict(blocks=list(v.get("blocks", [])), figs=list(v.get("figs", []))) for k, v in (deep or {}).items()}
        self.fig_deep = fig_deep or {}
        # กล่องลิงก์ไปภาพที่เก็บเนื้อหาของมันเสมอ
        for fig in self.fig_deep:
            for box, _ in self.items(fig):
                if box in self.deep and fig not in self.deep[box]["figs"]:
                    self.deep[box]["figs"].append(fig)

    def items(self, fig_id):
        for it in self.fig_deep.get(fig_id, []):
            box, idx = (it, None) if isinstance(it, str) else it
            n = len(self.deep.get(box, {}).get("blocks", []))
            yield box, (range(n) if idx is None else idx)

    def moved(self, node_id) -> set:
        """ลำดับ block ของกล่องนี้ที่ถูกย้ายไปแสดงในภาพรายบทแล้ว"""
        out = set()
        for fig in self.fig_deep:
            for box, idx in self.items(fig):
                if box == node_id:
                    out |= set(idx)
        return out

    def render(self, node_id: str, fig_titles: dict, open_: bool = True) -> str:
        """เนื้อหาละเอียดของกล่องหนึ่ง — แผงข้างแผนที่ (เปิดไว้) และแค็ตตาล็อก (พับไว้) แสดงครบทุก block"""
        d = self.deep.get(node_id)
        if not d or not d["blocks"]:
            return ""
        body = blocks_html(node_id, d["blocks"]) + _fig_links(d["figs"], fig_titles, UI["fig_links"])
        return (f'<details class="deep"{" open" if open_ else ""}><summary>{UI["deep"]}</summary>'
                f'<div class="deep-b">{body}</div></details>')

    def render_fig(self, fig_id: str, names: dict, fig_titles: dict) -> str:
        """เนื้อหาละเอียดของทุกกล่องที่ FIG_DEEP ผูกกับภาพนี้ — ต่อท้ายภาพรายบท"""
        parts = []
        for box, idx in self.items(fig_id):
            if box not in self.deep:
                continue
            blocks = [self.deep[box]["blocks"][i] for i in idx]
            others = [f for f in self.deep[box]["figs"] if f != fig_id]
            parts.append(f'<div class="dsub"><h4 class="dsub-h"><span>{esc(names.get(box, box))}</span>'
                         f'<button type="button" class="dshow" data-show="{box}">{UI["show"]}</button></h4>'
                         f'{blocks_html(box, blocks)}{_fig_links(others, fig_titles, UI["more_in"])}</div>')
        if not parts:
            return ""
        return (f'<details class="deep fdeep" open><summary>{UI["deep"]} · {len(parts)} {UI["in_fig"]}</summary>'
                f'<div class="deep-b">{"".join(parts)}</div></details>')

    def check(self, fig_ids, node_ids) -> list[str]:
        issues = []
        for box, d in self.deep.items():
            if box not in node_ids:
                issues.append(f"DEEP: ไม่มีกล่อง {box!r} บนแผนที่")
            for f in d["figs"]:
                if f not in fig_ids:
                    issues.append(f"DEEP[{box}].figs: ไม่มีภาพ {f!r}")
            for b in d["blocks"]:
                if not b or b[0] not in ("p", "ol", "ul", "calc", "table", "img", "gif", "trap"):
                    issues.append(f"DEEP[{box}]: block ไม่รู้จัก {b[:1]!r}")
        if not self.fig_deep:
            return issues
        seen = {}
        for fig in self.fig_deep:
            if fig not in fig_ids:
                issues.append(f"FIG_DEEP: ไม่มีภาพ {fig!r}")
            for box, idx in self.items(fig):
                if box not in self.deep:
                    issues.append(f"FIG_DEEP[{fig}]: กล่อง {box!r} ไม่มีใน DEEP")
                    continue
                for i in idx:
                    seen.setdefault((box, i), []).append(fig)
        for box, d in self.deep.items():
            for i in range(len(d["blocks"])):
                where = seen.get((box, i), [])
                if len(where) > 1:
                    issues.append(f"FIG_DEEP: {box} block {i} อยู่หลายภาพ {where}")
        return issues
