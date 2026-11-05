"""ประกอบหน้า HTML: CSS (สองธีม · สีตามหมวดที่ spec กำหนด) + JavaScript สำหรับซูม/คลิก/ทัวร์/ดูทีละขั้น

JavaScript ทำแค่ "เพิ่มความสามารถ" — ภาพทุกภาพเป็น SVG นิ่งที่เขียนไว้ใน HTML แล้ว
ถ้า JS ไม่ทำงาน หน้ายังอ่านได้ครบ (แค่คลิกดูรายละเอียด/ทัวร์ไม่ได้)

สี: TOPIC_PALETTE ผ่านการเลือกให้อ่านออกทั้งธีมสว่างและมืด · สีแดงอยู่ท้ายสุดเพราะใช้เป็นสี "เตือน/กับดัก" ด้วย
"""
from __future__ import annotations

import re

# (สว่าง: เข้ม, อ่อน, จาง), (มืด: เข้ม, อ่อน, จาง)
TOPIC_PALETTE = {
    "blue":   (("#2459C9", "#DCE6FA", "#EEF3FD"), ("#7AA5FF", "#1D2C4B", "#151F33")),
    "teal":   (("#0A7F72", "#D3EFEA", "#ECF8F6"), ("#3FC9B4", "#123A35", "#0F2724")),
    "purple": (("#8A2BA6", "#EEDCF4", "#F7EEFA"), ("#D18BEB", "#351F42", "#251730")),
    "amber":  (("#9A5B00", "#F5E6CC", "#FBF4E8"), ("#E3A548", "#3A2A12", "#281E0F")),
    "green":  (("#4E7A16", "#E1EED2", "#F1F7EA"), ("#9CCB5F", "#24351A", "#192514")),
    "brown":  (("#7A5531", "#EDE3D8", "#F7F2EC"), ("#D2A47A", "#35281C", "#251D15")),
    "slate":  (("#4A5869", "#E2E7ED", "#F1F4F7"), ("#9AA8BA", "#232C38", "#1A212B")),
    "red":    (("#C2381A", "#F8DDD5", "#FCEFEB"), ("#FF8566", "#43211A", "#2D1813")),
}
PALETTE_ORDER = ["blue", "teal", "purple", "amber", "green", "brown", "slate", "red"]
BAND_PALETTE = [("#E5EDF9", "#111C2C"), ("#FAF0E1", "#221B11"), ("#E4F2E9", "#0F1F17"), ("#EEE8F7", "#1B1727"),
                ("#E3F3F1", "#0F2220"), ("#F8E9EC", "#24161A"), ("#EEF0F3", "#161A20")]
CSS_ID = re.compile(r"^[a-z][a-z0-9-]*$")


def theme_css(topics: list, bands: list) -> str:
    """token ของหมวด (topic) และแถบ (band) ทั้งสองธีม + class ที่ใช้ token เหล่านั้น"""
    light, dark, rules = [], [], []
    for i, t in enumerate(topics):
        tid = t["id"]
        name = t.get("color") or PALETTE_ORDER[i % len(PALETTE_ORDER)]
        (lc, ls, lw), (dc, ds, dw) = TOPIC_PALETTE[name]
        light.append(f"--c-{tid}: {lc}; --c-{tid}-soft: {ls}; --c-{tid}-wash: {lw};")
        dark.append(f"--c-{tid}: {dc}; --c-{tid}-soft: {ds}; --c-{tid}-wash: {dw};")
        rules.append(
            f".topic-{tid} {{ --acc: var(--c-{tid}); --acc-soft: var(--c-{tid}-soft); --acc-wash: var(--c-{tid}-wash); }}\n"
            f".qc-{tid} {{ --qc: var(--c-{tid}); }}\n"
            f".fc-{tid} {{ fill: var(--c-{tid}-soft); stroke: var(--c-{tid}); stroke-width: 1.3; }}\n"
            f".fl-{tid} {{ fill: none; stroke: var(--c-{tid}); stroke-width: 2; stroke-linejoin: round; }}\n"
            f".fhd-{tid} {{ fill: var(--c-{tid}); }}\n"
            f".fa-{tid} {{ font: 600 12px var(--f-body); fill: var(--c-{tid}); }}")
    for i, b in enumerate(bands):
        lb, db = BAND_PALETTE[i % len(BAND_PALETTE)]
        light.append(f"--band-{b['id']}: {lb};")
        dark.append(f"--band-{b['id']}: {db};")
        rules.append(f".band-{b['id']} {{ fill: var(--band-{b['id']}); }}")
    L, D = "\n  ".join(light), "\n  ".join(dark)
    return (f":root {{\n  {L}\n}}\n"
            f"@media (prefers-color-scheme: dark) {{ :root:not([data-theme=\"light\"]) {{\n  {D}\n}} }}\n"
            f":root[data-theme=\"dark\"] {{\n  {D}\n}}\n" + "\n".join(rules) + "\n")


CSS = r"""
/* แนวคิด layout: แผนผังที่ตำแหน่งคือข้อมูล — แถบแนวนอน = ชั้น (อยู่ระดับไหน) · คอลัมน์ = ระบบย่อย / ขั้นตอน
   สีของกรอบ = หมวดเนื้อหา (TOPICS) · สีแดง = กับดัก / จุดที่มักผิด */
:root {
  --paper: #F3F5F8; --paper-2: #E8ECF1; --card: #FFFFFF;
  --ink: #16202C; --ink-2: #475467; --ink-3: #6E7A8A; --rule: #D3DAE3;
  --link: #2459C9;
  --warn: #C2381A; --warn-soft: #F8DDD5; --warn-wash: #FCEFEB;
  --f-display: "Chakra Petch", "Sarabun", "Noto Sans Thai", sans-serif;
  --f-body: "Sarabun", "Noto Sans Thai", "Leelawadee UI", Tahoma, sans-serif;
  --f-mono: "IBM Plex Mono", ui-monospace, "DejaVu Sans Mono", monospace;
  --radius: 10px;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --paper: #0D1117; --paper-2: #121821; --card: #161D27;
  --ink: #E7ECF2; --ink-2: #A8B3C1; --ink-3: #8390A2; --rule: #2A3441;
  --link: #7AA5FF;
  --warn: #FF8566; --warn-soft: #43211A; --warn-wash: #2D1813;
  color-scheme: dark; } }
:root[data-theme="dark"] {
  --paper: #0D1117; --paper-2: #121821; --card: #161D27;
  --ink: #E7ECF2; --ink-2: #A8B3C1; --ink-3: #8390A2; --rule: #2A3441;
  --link: #7AA5FF;
  --warn: #FF8566; --warn-soft: #43211A; --warn-wash: #2D1813;
  color-scheme: dark; }
/*THEME*/
html { scroll-behavior: smooth; scroll-padding-top: 64px; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
body { background: var(--paper); color: var(--ink); font: 400 16px/1.65 var(--f-body); margin: 0;
  --acc: var(--ink-2); --acc-soft: var(--paper-2); --acc-wash: var(--paper); }
body::before { content: ""; position: fixed; inset: 0 0 auto; height: env(safe-area-inset-top, 0px);
  z-index: 10; background: var(--paper); }
[hidden] { display: none !important; }
.wrap { max-width: 1240px; margin: 0 auto;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.wide { max-width: 1840px; }
a { color: var(--link); }
:focus-visible { outline: 2.5px solid var(--link); outline-offset: 2px; border-radius: 4px; }
h1, h2, h3 { font-family: var(--f-display); text-wrap: balance; line-height: 1.2; margin: 0; }
h2 { font-size: clamp(24px, 3vw, 32px); font-weight: 600; }
h3 { font-size: 19px; font-weight: 600; }
p { margin: 0; }
.mono { font-family: var(--f-mono); }
.topic-base { --acc: var(--ink-2); --acc-soft: var(--paper-2); --acc-wash: var(--paper); }
.qc-base { --qc: var(--ink-2); }

/* ---------- หัวหน้า */
.top { padding-block: 40px 22px; border-bottom: 1px solid var(--rule); }
.eyebrow { font: 600 12.5px/1.4 var(--f-display); letter-spacing: .04em; text-transform: uppercase; color: var(--ink-3); }
.top h1 { font-size: clamp(34px, 5vw, 54px); font-weight: 700; margin: 8px 0 12px; letter-spacing: -.01em; }
.lead { max-width: 72ch; color: var(--ink-2); font-size: 17px; }
.exam { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; margin-top: 22px; }
.q { border: 1px solid var(--rule); border-left: 4px solid var(--qc); background: var(--card); border-radius: 8px;
  padding: 10px 12px; display: grid; gap: 2px; }
.q b { font: 600 14px var(--f-display); letter-spacing: .04em; }
.q span { color: var(--ink-2); font-size: 14px; line-height: 1.45; }
.q .pts { float: right; font: 600 13.5px var(--f-body); color: var(--qc); }

/* ---------- แถบนำทาง */
.nav { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 20; background: var(--paper);
  border-bottom: 1px solid var(--rule); }
.nav .wrap { display: flex; gap: 4px; overflow-x: auto; padding-block: 8px; scrollbar-width: thin; }
.nav a { flex: none; text-decoration: none; color: var(--ink-2); font: 500 14px var(--f-body); padding: 5px 10px;
  border-radius: 999px; white-space: nowrap; }
.nav a:hover { background: var(--paper-2); color: var(--ink); }
.nav .grp { flex: none; font: 600 11.5px var(--f-display); letter-spacing: .03em; color: var(--ink-3);
  align-self: center; padding: 0 2px 0 10px; text-transform: uppercase; }

main > section, main > div > section { padding-block: 44px 8px; }
.sec-head { display: grid; gap: 8px; margin-bottom: 18px; max-width: 80ch; }
.sec-head p { color: var(--ink-2); }

/* ---------- แผนที่ */
.legend { display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; margin: 4px 0 14px;
  font-size: 14px; color: var(--ink-2); }
.legend .sw { display: inline-flex; align-items: center; gap: 6px; }
.legend svg { width: 34px; height: 12px; overflow: visible; }
.dot { width: 12px; height: 12px; border-radius: 3px; display: inline-block; background: var(--qc); }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }
.btn { font: 500 14px var(--f-body); color: var(--ink); background: var(--card); border: 1px solid var(--rule);
  border-radius: 8px; padding: 6px 12px; cursor: pointer; line-height: 1.3; }
.btn:hover { border-color: var(--ink-3); }
.btn[aria-pressed="true"] { background: var(--ink); color: var(--paper); border-color: var(--ink); }
.btn.qbtn { border-left: 4px solid var(--qc); }
.zoomval { font: 500 13px var(--f-mono); color: var(--ink-3); min-width: 44px; text-align: center; }
.sep { width: 1px; height: 26px; background: var(--rule); margin: 0 4px; }
.shell { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 14px; align-items: start; }
@media (max-width: 1100px) { .shell { grid-template-columns: minmax(0, 1fr); } }
.stage { min-width: 0; display: grid; gap: 10px; }
.tourbar { background: var(--card); border: 1px solid var(--rule); border-radius: var(--radius); padding: 12px 14px;
  display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 12px; align-items: center; }
.tourbar .num { font: 700 26px/1 var(--f-display); color: var(--ink-3); min-width: 56px; text-align: center; }
.tourbar .num small { display: block; font: 500 11px var(--f-body); letter-spacing: .04em; margin-top: 4px; }
.tourbar h3 { font-size: 17px; }
.tourbar .act { font: 600 12px var(--f-display); letter-spacing: .03em; text-transform: uppercase; color: var(--link); }
.tourbar p { color: var(--ink-2); font-size: 15px; line-height: 1.55; margin-top: 2px; }
.tourbar .nav2 { display: flex; gap: 6px; flex-wrap: wrap; }
@media (max-width: 640px) { .tourbar { grid-template-columns: minmax(0, 1fr); } .tourbar .num { text-align: left; } }
.vp { position: relative; height: min(74vh, 880px); overflow: auto; border: 1px solid var(--rule);
  border-radius: var(--radius); background-color: var(--paper-2);
  background-image: radial-gradient(var(--rule) 1px, transparent 1.2px); background-size: 22px 22px;
  overscroll-behavior: contain; touch-action: pan-x pan-y; }
.vp.grab { cursor: grabbing; }
.vp svg { display: block; }
.panel { position: sticky; top: 62px; max-height: calc(100vh - 80px); overflow: auto; background: var(--card);
  border: 1px solid var(--rule); border-radius: var(--radius); padding: 16px 18px; min-width: 0; }
@media (max-width: 1100px) { .panel { position: static; max-height: none; } }
.panel h3 { font-size: 21px; }
.panel .gl { color: var(--ink-2); margin-top: 2px; }
.panel .pico { width: 72px; height: 72px; float: right; margin: 0 0 6px 10px; background: var(--acc-wash);
  border-radius: 10px; padding: 6px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 4px; }
.chip { font: 600 12px var(--f-body); padding: 2px 9px; border-radius: 999px; background: var(--paper-2); color: var(--ink-2); }
.chip.q { background: var(--qc); color: var(--card); border: 0; display: inline; padding: 2px 9px; }
.panel dl { margin: 12px 0 0; display: grid; gap: 10px; }
.panel dt { font: 600 12.5px var(--f-display); letter-spacing: .02em; text-transform: uppercase; color: var(--ink-3); }
.panel dd { margin: 2px 0 0; font-size: 15px; line-height: 1.6; }
.panel ul { margin: 2px 0 0; padding-left: 18px; }
.panel li { margin: 2px 0; }
.panel .exam-box { background: var(--warn-wash); border-radius: 8px; padding: 8px 10px 8px 26px; }
.panel .exam-box li::marker { color: var(--warn); }
.links { display: grid; gap: 4px; margin-top: 4px; }
.links button { text-align: left; font: 400 14px/1.45 var(--f-body); color: var(--ink); background: var(--paper);
  border: 1px solid var(--rule); border-radius: 7px; padding: 5px 9px; cursor: pointer; }
.links button:hover { border-color: var(--ink-3); }
.links .dir { font: 600 12px var(--f-mono); color: var(--ink-3); margin-right: 4px; }
.hint { font-size: 14px; color: var(--ink-3); }
.howto { display: grid; gap: 10px; font-size: 15px; }
.howto ul { margin: 0; padding-left: 18px; }
.howto li { margin: 3px 0; }

/* ---------- รายการขั้นของทัวร์ */
.tour-list { columns: 3 300px; column-gap: 26px; margin: 18px 0 0; padding: 0; list-style: none; }
.tour-list .act-h { font: 600 12.5px var(--f-display); letter-spacing: .03em; text-transform: uppercase; color: var(--ink-3);
  margin: 10px 0 4px; break-after: avoid; }
.tour-list button { all: unset; display: grid; grid-template-columns: 30px minmax(0, 1fr); gap: 6px; cursor: pointer;
  padding: 4px 6px; border-radius: 6px; font-size: 14.5px; line-height: 1.45; break-inside: avoid; width: calc(100% - 12px); }
.tour-list button:hover { background: var(--paper-2); }
.tour-list button:focus-visible { outline: 2.5px solid var(--link); }
.tour-list button.cur { background: var(--ink); color: var(--paper); }
.tour-list .n { font: 600 13px var(--f-mono); color: var(--ink-3); }
.tour-list button.cur .n { color: var(--paper); }

/* ---------- คู่ที่สับสน */
.pairs { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(330px, 100%), 1fr)); gap: 10px; }
.pair { background: var(--card); border: 1px solid var(--rule); border-radius: var(--radius); padding: 12px 14px;
  display: grid; gap: 6px; align-content: start; min-width: 0; }
.pair h3 { font-size: 16px; }
.pair h3 i { font-style: normal; color: var(--ink-3); font-weight: 500; margin: 0 6px; }
.pair p { font-size: 14.5px; color: var(--ink-2); line-height: 1.55; }
.pair .btn { justify-self: start; font-size: 13px; padding: 3px 10px; }

/* ---------- แค็ตตาล็อก */
.cat-group { margin-top: 26px; }
.cat-group > h3 { margin-bottom: 10px; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }
.cat-group > h3 small { font: 400 14px var(--f-body); color: var(--ink-3); }
.cat { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(340px, 100%), 1fr)); gap: 12px; }
.card { background: var(--card); border: 1px solid var(--rule); border-top: 3px solid var(--acc); border-radius: var(--radius);
  padding: 14px 16px; display: grid; gap: 8px; align-content: start; min-width: 0; }
.card header { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 12px; align-items: center; }
.card header svg { width: 64px; height: 64px; background: var(--acc-wash); border-radius: 10px; padding: 4px; }
.card h4 { font: 600 17px var(--f-display); margin: 0; }
.card .gl { color: var(--ink-2); font-size: 14px; line-height: 1.4; }
.card p, .card li { font-size: 14.5px; line-height: 1.6; }
.card ul { margin: 0; padding-left: 18px; }
.card .lbl { font: 600 12px var(--f-display); letter-spacing: .02em; text-transform: uppercase; color: var(--ink-3); margin-top: 2px; }
.card .ex { background: var(--warn-wash); border-radius: 7px; padding: 6px 10px 6px 24px; margin: 0; }
.card .read { font-size: 13.5px; color: var(--ink-3); }
.card .btn { justify-self: start; font-size: 13px; padding: 3px 10px; }

/* ---------- บท / ภาพรายบท */
.ch { border-top: 1px solid var(--rule); padding-block: 44px 8px; }
.ch-head { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 18px; align-items: start; margin-bottom: 16px; }
.ch-num { font: 700 64px/0.9 var(--f-display); color: var(--acc); grid-row: span 3; min-width: 1.3em; }
.ch-head .tags { display: flex; flex-wrap: wrap; gap: 6px; }
.ch-head .thesis { color: var(--ink-2); max-width: 78ch; font-size: 16.5px; }
@media (max-width: 640px) { .ch-num { font-size: 44px; } }
.ch-group { padding-top: 56px; }
.ch-group > .wrap > h2 { display: flex; gap: 12px; align-items: baseline; flex-wrap: wrap; }
.ch-group > .wrap > h2 small { font: 500 16px var(--f-body); color: var(--ink-2); }
figure.fig { margin: 18px 0 26px; background: var(--card); border: 1px solid var(--rule); border-radius: var(--radius);
  padding: 14px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; min-width: 0; }
figure.fig > * { min-width: 0; }
.fig-title { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; align-items: baseline; }
.fig-title h3 { font-size: 18px; }
.figbox { overflow-x: auto; border-radius: 8px; background: var(--paper); }
.figbox svg { display: block; width: 100%; min-width: 720px; height: auto; }
figcaption { color: var(--ink-2); font-size: 15px; }
.stepper { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.stepper .cnt { font: 500 13.5px var(--f-body); color: var(--ink-3); margin-left: 4px; }
.steps { margin: 0; padding: 0; list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(290px, 100%), 1fr)); gap: 6px; }
.steps li { display: grid; grid-template-columns: 30px minmax(0, 1fr); gap: 8px; padding: 7px 9px; border-radius: 8px;
  background: var(--paper); cursor: pointer; font-size: 14.5px; line-height: 1.5; border: 1px solid transparent; }
.steps li:hover { border-color: var(--rule); }
.steps li.cur { border-color: var(--acc); background: var(--acc-wash); }
.steps .k { font: 700 15px var(--f-display); color: var(--acc); }
.story { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr)); gap: 10px; margin: 0; }
.story > div { background: var(--paper); border-radius: 8px; padding: 10px 12px; }
.story dt { font: 600 12.5px var(--f-display); letter-spacing: .02em; text-transform: uppercase; color: var(--acc); }
.story dd { margin: 3px 0 0; font-size: 15px; line-height: 1.6; }
.traps { background: var(--warn-wash); border-radius: 8px; padding: 10px 14px; }
.traps b { font: 600 13px var(--f-display); letter-spacing: .02em; color: var(--warn); text-transform: uppercase; }
.traps ul { margin: 4px 0 0; padding-left: 20px; }
.traps li { font-size: 15px; margin: 3px 0; }
.onmap { font-size: 14px; color: var(--ink-3); }
.onmap button { font: 500 13px var(--f-body); background: none; border: 1px dashed var(--rule); border-radius: 999px;
  padding: 1px 9px; margin: 2px 3px; color: var(--ink-2); cursor: pointer; }
.onmap button:hover { border-style: solid; color: var(--ink); }
.figbody { display: grid; gap: 14px; grid-template-columns: minmax(0, 1fr); }
.figbody > * { min-width: 0; }
.foot { padding-block: 40px 60px; color: var(--ink-3); font-size: 14px; border-top: 1px solid var(--rule); margin-top: 50px; }
.foot p { margin-top: 6px; max-width: 90ch; }

/* ---------- SVG */
svg text { font-family: var(--f-body); }
.band-lbl { font: 700 15px var(--f-display); letter-spacing: .06em; fill: var(--ink-3); }
.col-h { font: 700 19px var(--f-display); letter-spacing: .02em; fill: var(--acc); }
.col-sub { font: 500 13px var(--f-body); fill: var(--ink-2); }
.col-tag { font: 600 12px var(--f-mono); fill: var(--acc); }
.col-rule { stroke: var(--acc); stroke-width: 3; }
.bnd { stroke: var(--ink-3); stroke-width: 1.2; stroke-dasharray: 10 6; fill: none; }
.bnd-lbl { font: 500 12px var(--f-body); fill: var(--ink-2); paint-order: stroke; stroke: var(--paper); stroke-width: 4px; stroke-linejoin: round; }
.node { cursor: pointer; }
.node:focus { outline: none; }
.node:focus-visible .n-box, .node:focus-visible .b-ring { stroke-width: 3.5; stroke: var(--ink); }
.n-box { fill: var(--card); stroke: var(--acc); stroke-width: 1.6; }
.n-icobg { fill: var(--acc-wash); }
.n-name { font: 600 14px var(--f-body); fill: var(--ink); }
.n-gloss { font: 400 12px var(--f-body); fill: var(--ink-2); }
.n-ch { font: 600 10.5px var(--f-body); fill: var(--acc); }
.c-name { font: 600 13px var(--f-body); fill: var(--ink); }
.c-gloss { font: 400 11.5px var(--f-body); fill: var(--ink-2); }
.kind-chip .n-box { fill: var(--acc-wash); }
.i-s { fill: none; stroke: var(--ink-2); stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
.i-sA { fill: none; stroke: var(--acc); stroke-width: 1.9; stroke-linecap: round; stroke-linejoin: round; }
.i-b { fill: var(--card); stroke: var(--ink-2); stroke-width: 1.4; }
.i-a { fill: var(--acc-soft); stroke: var(--acc); stroke-width: 1.4; }
.i-A { fill: var(--acc); stroke: none; }
.i-k { fill: var(--ink-2); }
.i-t { font: 500 7.5px var(--f-mono); fill: var(--ink-2); }
.i-ta { font: 700 7.5px var(--f-mono); fill: var(--acc); }
text.i-inv { fill: var(--card); }
.i-inv-s { fill: none; stroke: var(--card); stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; }
.i-dash { stroke-dasharray: 3 3; }
.i-shield { fill: var(--acc-soft); stroke: var(--acc); stroke-width: 3.5; }
.i-shield-in { fill: none; stroke: var(--acc); stroke-width: 4.5; stroke-linecap: round; stroke-linejoin: round; }
.b-ring { fill: var(--card); stroke: var(--acc); stroke-width: 1.8; }
.b-name { font: 600 12.5px var(--f-body); fill: var(--acc); paint-order: stroke; stroke: var(--paper); stroke-width: 4px; stroke-linejoin: round; }
.b-gloss { font: 400 11.5px var(--f-body); fill: var(--ink-2); paint-order: stroke; stroke: var(--paper); stroke-width: 4px; stroke-linejoin: round; }
.e-halo { fill: none; stroke: var(--paper); stroke-width: 6; stroke-linejoin: round; opacity: .85; }
.e-line { fill: none; stroke: var(--ink-3); stroke-width: 1.6; stroke-linejoin: round; }
.e-head { fill: var(--ink-3); }
.k-data .e-line { stroke: var(--ink-2); stroke-width: 3.2; }
.k-data .e-head { fill: var(--ink-2); }
.k-data .e-halo { stroke-width: 8; }
.k-sig .e-line { stroke-dasharray: 7 4; stroke: var(--ink-2); }
.k-sig .e-head { fill: var(--ink-2); }
.k-rel .e-line { stroke-dasharray: 2 4; stroke-width: 1.5; }
.e-lbl { font: 400 12px var(--f-body); fill: var(--ink-2); paint-order: stroke; stroke: var(--paper); stroke-width: 4.5px; stroke-linejoin: round; }
.c-stub { fill: none; stroke: var(--ink-3); stroke-width: 1.5; stroke-dasharray: 2 3; }
.conn { cursor: pointer; }
.conn .e-head { fill: var(--ink-3); }
.c-ring { fill: var(--card); stroke: var(--ink); stroke-width: 1.8; }
.c-letter { font: 700 12.5px var(--f-display); fill: var(--ink); }
.c-lbl { font: 600 11.5px var(--f-body); fill: var(--ink); paint-order: stroke; stroke: var(--paper); stroke-width: 4px; stroke-linejoin: round; }
.a-cell { fill: var(--card); stroke: var(--ink-3); stroke-width: 1; }
.a-cellA { fill: var(--acc-soft); stroke: var(--acc); stroke-width: 1.2; }
.a-cellB { fill: var(--acc); stroke: none; }
.a-txt { font: 500 11.5px var(--f-body); fill: var(--ink); }
.a-txtB { font: 600 11.5px var(--f-body); fill: var(--card); }
.a-sub { font: 400 11px var(--f-body); fill: var(--ink-2); }
.a-tiny { font: 400 10px var(--f-body); fill: var(--ink-2); }
.a-warn { font: 600 11px var(--f-body); fill: var(--warn); }
.a-ln { fill: none; stroke: var(--ink-2); stroke-width: 1.4; }
.a-head { fill: var(--ink-2); }
.legend-box { fill: var(--card); stroke: var(--rule); }
.lg-h { font: 700 13px var(--f-display); letter-spacing: .03em; fill: var(--ink-3); }
.lg-t { font: 400 12.5px var(--f-body); fill: var(--ink-2); }

/* ---------- ภาพของแต่ละบท (Draw) */
.ft { font: 400 12.5px var(--f-body); fill: var(--ink); }
.ftB { font: 600 12.5px var(--f-body); fill: var(--ink); }
.ftW { font: 600 12.5px var(--f-body); fill: var(--card); }
.ft2 { font: 400 12px var(--f-body); fill: var(--ink-2); }
.fh { font: 600 13.5px var(--f-body); fill: var(--ink); }
.fa { font: 600 12px var(--f-body); fill: var(--acc); }
.fw { font: 600 12px var(--f-body); fill: var(--ink); }
.fsm { font: 400 11px var(--f-body); fill: var(--ink-2); }
.fsmB { font: 600 11px var(--f-body); fill: var(--ink); }
.fsmW { font: 600 11px var(--f-body); fill: var(--card); }
.fmono { font: 500 12px var(--f-mono); fill: var(--ink); }
.fbig { font: 600 16px var(--f-display); fill: var(--ink); }
.flbl { font: 400 12px var(--f-body); fill: var(--ink-2); paint-order: stroke; stroke: var(--paper); stroke-width: 4px; stroke-linejoin: round; }
.fc { fill: var(--card); stroke: var(--ink-3); stroke-width: 1.1; }
.fcA { fill: var(--acc-soft); stroke: var(--acc); stroke-width: 1.3; }
.fcB { fill: var(--acc); stroke: none; }
.fcH { fill: var(--acc-wash); stroke: var(--acc); stroke-width: 2; }
.fcW { fill: var(--paper-2); stroke: var(--ink-3); stroke-width: 1; }
.fcD { fill: var(--warn-soft); stroke: var(--warn); stroke-width: 1.3; }
.fcN { fill: none; stroke: var(--ink-3); stroke-width: 1.2; stroke-dasharray: 5 4; }
.fl { fill: none; stroke: var(--ink-2); stroke-width: 1.5; stroke-linejoin: round; }
.flA { fill: none; stroke: var(--acc); stroke-width: 2.2; stroke-linejoin: round; }
.fld { fill: none; stroke: var(--ink-2); stroke-width: 1.4; stroke-dasharray: 6 4; }
.flD { fill: none; stroke: var(--warn); stroke-width: 2; stroke-linejoin: round; }
.flDd { fill: none; stroke: var(--warn); stroke-width: 2; stroke-dasharray: 7 4; }
.fpt, .fptB { font: 400 11px var(--f-body); fill: var(--ink-2); paint-order: stroke; stroke: var(--paper); stroke-width: 4px; stroke-linejoin: round; }
.fptB { font-weight: 600; fill: var(--ink); }
.fhd { fill: var(--ink-2); } .fhdA { fill: var(--acc); } .fhdD { fill: var(--warn); }
.fstep { fill: var(--acc); } .fstepT { font: 700 12px var(--f-display); fill: var(--card); }
svg.stepping [data-s].on .fcA, svg.stepping [data-s].on .fcH { stroke-width: 2.6; }
/* ไฮไลต์ */
svg.dim .node:not(.on), svg.dim .edge:not(.on), svg.dim .e-lbl:not(.on), svg.dim .conn:not(.on) { opacity: .13; }
svg .node, svg .edge, svg .e-lbl, svg .conn { transition: opacity .18s; }
.node.on .n-box, .node.on .b-ring { stroke-width: 3; }
.node.sel .n-box, .node.sel .b-ring { stroke-width: 4; stroke: var(--ink); }
.edge.on .e-line { stroke: var(--ink); stroke-width: 2.6; }
.edge.k-data.on .e-line { stroke-width: 3.6; }
.edge.on .e-head, .conn.on .e-head { fill: var(--ink); }
.edge.on.flow .e-line { stroke-dasharray: 10 6; animation: flow .9s linear infinite; }
.e-lbl.on { fill: var(--ink); font-weight: 600; }
.conn.on .c-ring { stroke-width: 3; fill: var(--paper-2); }
@keyframes flow { to { stroke-dashoffset: -16; } }
svg.stepping [data-s]:not(.on) { opacity: .14; }
svg [data-s] { transition: opacity .18s; }
svg.stepping .edge.on .e-line { stroke: var(--ink); stroke-width: 2.4; }
svg.stepping .node.on .n-box { stroke-width: 3; }
@media (prefers-reduced-motion: reduce) { .edge.on.flow .e-line { animation: none; } svg * { transition: none !important; } }

/* ---------- อธิบายละเอียด (แผงข้าง + แค็ตตาล็อก + ท้ายภาพรายบท) */
.deep { margin-top: 14px; border-top: 1px solid var(--rule); padding-top: 10px; }
.deep > summary { cursor: pointer; font: 600 13.5px var(--f-display); letter-spacing: .02em; text-transform: uppercase; color: var(--ink-2); }
.deep-b { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; margin-top: 10px; font-size: 14.5px; line-height: 1.62; }
.deep-b > * { min-width: 0; }
.deep-b h4 { font: 600 14.5px var(--f-body); margin: 0 0 3px; color: var(--ink); letter-spacing: 0; text-transform: none; }
.deep-b p { margin: 0; }
.deep-b ul, .deep-b ol { margin: 0; padding-left: 20px; display: grid; gap: 3px; }
.deep-b code { font: 500 13px var(--f-mono); background: var(--paper-2); padding: 0 4px; border-radius: 4px; }
.deep .calc { background: var(--acc-wash, var(--paper-2)); border-radius: 8px; padding: 8px 10px; }
.deep .calc ul { list-style: none; padding-left: 0; }
.deep .dtrap { background: var(--warn-wash); border-radius: 8px; padding: 8px 10px; }
.deep .dtrap li::marker { color: var(--warn); }
.dscroll { overflow-x: auto; }
.dtab { border-collapse: collapse; width: 100%; font-size: 13.5px; }
.dtab th, .dtab td { border-bottom: 1px solid var(--rule); padding: 4px 6px; text-align: left; vertical-align: top; }
.dtab th { font-weight: 600; color: var(--ink-2); background: var(--paper-2); }
.dgif > summary { cursor: pointer; font-size: 14px; color: var(--ink-2); }
.dgif img { display: block; max-width: 100%; height: auto; margin-top: 6px; border-radius: 8px; border: 1px solid var(--rule); background: #fff; }
.dfigs { font-size: 13.5px; color: var(--ink-3); }
.card .deep { margin-top: 8px; }
.fdeep { margin-top: 4px; }
.fdeep > summary { font-size: 13.5px; }
.dsub { display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; padding-top: 12px; border-top: 1px dashed var(--rule); }
.dsub > * { min-width: 0; }
.dsub:first-child { border-top: 0; padding-top: 0; }
.dsub-h { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font: 600 17px var(--f-display) !important; color: var(--acc) !important; }
.dshow { font: 500 12.5px var(--f-body); color: var(--ink-2); background: var(--paper); border: 1px solid var(--rule); border-radius: 999px;
  padding: 1px 10px; cursor: pointer; }
.dshow:hover { border-color: var(--ink-3); color: var(--ink); }
figure.fig .deep-b { font-size: 15px; }
"""

JS = r"""
(() => {
  const D = JSON.parse(document.getElementById('submap-data').textContent);
  const U = D.ui;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const svg = $('#bigmap-svg');
  const vp = $('#map-vp');
  const panel = $('#map-panel');
  const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  // ---------- ภาพของแต่ละบท: ดูทีละขั้น (ทำงานแม้ไม่มีแผนที่รวม)
  $$('figure.fig[data-steps]').forEach(fig => {
    const fs = $('svg', fig), items = $$('.steps li', fig), cnt = $('.cnt', fig);
    const n = items.length; let cur = 0;
    function show(k) {
      cur = clamp(k, 0, n);
      if (fs) {
        fs.classList.toggle('stepping', cur > 0);
        $$('[data-s]', fs).forEach(el => el.classList.toggle('on', cur > 0 && el.dataset.s.split(' ').includes(String(cur))));
      }
      items.forEach((li, i) => li.classList.toggle('cur', i + 1 === cur));
      cnt.textContent = cur ? U.step + ' ' + cur + ' / ' + n : U.whole;
    }
    $('.s-next', fig).addEventListener('click', () => show(cur >= n ? 1 : cur + 1));
    $('.s-prev', fig).addEventListener('click', () => show(cur <= 1 ? n : cur - 1));
    $('.s-all', fig).addEventListener('click', () => show(0));
    items.forEach((li, i) => { li.tabIndex = 0; li.addEventListener('click', () => show(i + 1));
      li.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); show(i + 1); } }); });
  });

  if (!svg || !vp) return;
  const BW = svg.viewBox.baseVal.width, BH = svg.viewBox.baseVal.height;
  const zv = $('#zoomval');
  let zoom = 1;
  const fitZoom = () => Math.min(vp.clientWidth / BW, vp.clientHeight / BH);
  function setZoom(z, ax, ay) {
    z = clamp(z, Math.min(fitZoom(), 1), 1.8);
    if (ax === undefined) { ax = vp.clientWidth / 2; ay = vp.clientHeight / 2; }
    const sx = (vp.scrollLeft + ax) / zoom, sy = (vp.scrollTop + ay) / zoom;
    zoom = z;
    svg.style.width = (BW * z) + 'px';
    svg.style.height = (BH * z) + 'px';
    vp.scrollLeft = sx * z - ax;
    vp.scrollTop = sy * z - ay;
    if (zv) zv.textContent = Math.round(z * 100) + '%';
  }
  // ซูม: ปุ่ม + ctrl/⌘ + ล้อเมาส์ (trackpad pinch ส่ง ctrlKey มาด้วย)
  $('#z-in').addEventListener('click', () => setZoom(zoom * 1.25));
  $('#z-out').addEventListener('click', () => setZoom(zoom / 1.25));
  $('#z-fit').addEventListener('click', () => setZoom(fitZoom()));
  $('#z-100').addEventListener('click', () => setZoom(1));
  vp.addEventListener('wheel', (e) => {
    if (!(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    const r = vp.getBoundingClientRect();
    setZoom(zoom * Math.exp(-e.deltaY * 0.0022), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  // ลากเพื่อเลื่อน (เมาส์) — นิ้วบนมือถือเลื่อนเองตามปกติ
  let drag = null;
  vp.addEventListener('pointerdown', (e) => {
    if (e.pointerType !== 'mouse' || e.button !== 0 || e.target.closest('.node, .conn')) return;
    drag = { x: e.clientX, y: e.clientY, l: vp.scrollLeft, t: vp.scrollTop, moved: false };
    vp.setPointerCapture(e.pointerId);
  });
  vp.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) { drag.moved = true; vp.classList.add('grab'); }
    vp.scrollLeft = drag.l - dx; vp.scrollTop = drag.t - dy;
  });
  const endDrag = () => { drag = null; vp.classList.remove('grab'); };
  vp.addEventListener('pointerup', endDrag); vp.addEventListener('pointercancel', endDrag);

  // ---------- ไฮไลต์
  function clearMarks() {
    $$('.on, .sel, .flow', svg).forEach(el => el.classList.remove('on', 'sel', 'flow'));
    svg.classList.remove('dim');
  }
  function mark(nodes, edges, conns) {
    clearMarks();
    svg.classList.add('dim');
    nodes.forEach(id => { const el = svg.getElementById('n-' + id); if (el) el.classList.add('on'); });
    edges.forEach(id => {
      const el = svg.getElementById('e-' + id); if (el) el.classList.add('on', 'flow');
      const lb = svg.querySelector('.e-lbl[data-for="' + id + '"]'); if (lb) lb.classList.add('on');
    });
    (conns || []).forEach(c => $$('.conn[data-conn="' + c + '"]', svg).forEach(el => el.classList.add('on')));
  }
  function bboxOf(ids, conns) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    const els = ids.map(id => svg.getElementById('n-' + id)).filter(Boolean);
    (conns || []).forEach(c => $$('.conn[data-conn="' + c + '"]', svg).forEach(el => els.push(el)));
    els.forEach(el => { const b = el.getBBox(); x0 = Math.min(x0, b.x); y0 = Math.min(y0, b.y);
      x1 = Math.max(x1, b.x + b.width); y1 = Math.max(y1, b.y + b.height); });
    return isFinite(x0) ? { x0, y0, x1, y1 } : null;
  }
  function focusOn(ids, conns, keepZoom) {
    const b = bboxOf(ids, conns); if (!b) return;
    const pad = 90, w = b.x1 - b.x0 + pad * 2, h = b.y1 - b.y0 + pad * 2;
    if (!keepZoom) setZoom(clamp(Math.min(vp.clientWidth / w, vp.clientHeight / h), fitZoom(), 1));
    const cx = (b.x0 + b.x1) / 2 * zoom, cy = (b.y0 + b.y1) / 2 * zoom;
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    vp.scrollTo({ left: cx - vp.clientWidth / 2, top: cy - vp.clientHeight / 2, behavior: reduce ? 'auto' : 'smooth' });
  }

  function iconClone(id) {
    const n = D.nodes[id];
    const g = svg.querySelector('#n-' + id + ' > g[transform]');
    if (!g || n.kind !== 'card') return '';
    return '<svg class="pico topic-' + n.topic + '" viewBox="0 0 56 56" aria-hidden="true">' + g.innerHTML + '</svg>';
  }
  const fchip = (q) => '<span class="chip q qc-' + ((D.focus[q] || {}).topic || 'base') + '">' + esc((D.focus[q] || {}).label || q) + '</span>';
  function renderNode(id) {
    const n = D.nodes[id];
    const ins = D.edges.filter(e => e.dst === id), outs = D.edges.filter(e => e.src === id);
    const cs = D.conns.filter(c => c.src === id || c.dst === id);
    const link = (dir, e, other) => '<button data-go="' + other + '"><span class="dir">' + dir + '</span>' +
      esc(e.label || '') + ' <b>' + esc(D.nodes[other].name) + '</b></button>';
    let html = '<div class="topic-' + n.topic + '">' + iconClone(id) +
      '<h3>' + esc(n.name) + '</h3><p class="gl">' + esc(n.gloss) + '</p><div class="chips">' +
      (n.layer ? '<span class="chip">' + esc(D.layers[n.layer] || n.layer) + '</span>' : '') +
      (n.ch ? '<span class="chip">' + esc(U.ch) + ' ' + esc(n.ch) + '</span>' : '') +
      n.q.map(fchip).join('') + '</div><dl>';
    // what · does · look · exam · read มาจาก fmt() ฝั่ง Python ซึ่ง escape แล้วจึงเติม <b> <code> <i> — ห้าม esc ซ้ำ
    if (n.what) html += '<div><dt>' + esc(U.what) + '</dt><dd>' + n.what + '</dd></div>';
    if (n.does.length) html += '<div><dt>' + esc(U.does) + '</dt><dd><ul>' + n.does.map(s => '<li>' + s + '</li>').join('') + '</ul></dd></div>';
    if (n.look) html += '<div><dt>' + esc(U.look) + '</dt><dd>' + n.look + '</dd></div>';
    if (n.exam.length) html += '<div><dt>' + esc(U.exam) + '</dt><dd><ul class="exam-box">' + n.exam.map(s => '<li>' + s + '</li>').join('') + '</ul></dd></div>';
    if (ins.length + outs.length + cs.length) {
      html += '<div><dt>' + esc(U.links) + '</dt><dd><div class="links">' +
        ins.map(e => link('←', e, e.src)).join('') + outs.map(e => link('→', e, e.dst)).join('') +
        cs.map(c => '<button data-go="' + (c.src === id ? c.dst : c.src) + '"><span class="dir">' + esc(c.letter) + '</span>' +
          esc(c.src === id ? c.src_label : c.dst_label) + '</button>').join('') + '</div></dd></div>';
    }
    if (n.read) html += '<div><dt>' + esc(U.read) + '</dt><dd>' + n.read + '</dd></div>';
    html += '</dl>' + (n.deep || '') + '</div>';   // deep = HTML ที่ Python สร้างและ escape แล้ว
    panel.innerHTML = html;
    panel.scrollTop = 0;
  }
  function select(id, scroll) {
    if (!D.nodes[id]) return;
    const es = D.edges.filter(e => e.src === id || e.dst === id);
    const cs = D.conns.filter(c => c.src === id || c.dst === id);
    const ns = new Set([id]);
    es.forEach(e => { ns.add(e.src); ns.add(e.dst); });
    cs.forEach(c => { ns.add(c.src); ns.add(c.dst); });
    mark([...ns], es.map(e => e.id), cs.map(c => c.id));
    svg.getElementById('n-' + id).classList.add('sel');
    renderNode(id);
    if (scroll) focusOn([id], null, true);
  }
  svg.addEventListener('click', (e) => {
    if (drag && drag.moved) return;
    const n = e.target.closest('.node');
    if (n) { select(n.dataset.id, false); return; }
    const c = e.target.closest('.conn');
    if (c) {
      const conn = D.conns.find(x => x.id === c.dataset.conn);
      const other = c.dataset.end === 'src' ? conn.dst : conn.src;
      mark([conn.src, conn.dst], [], [conn.id]);
      focusOn([conn.src, conn.dst], [conn.id]);
      renderNode(other);
    }
  });
  svg.addEventListener('keydown', (e) => {
    const n = e.target.closest('.node, .conn');
    if (n && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); n.dispatchEvent(new MouseEvent('click', { bubbles: true })); }
  });
  panel.addEventListener('click', (e) => {
    const b = e.target.closest('[data-go]');
    if (b) select(b.dataset.go, true);
  });
  const howto = panel.innerHTML;
  const listOf = (ids) => '<div class="links" style="margin-top:8px">' + ids.map(id => '<button data-go="' + id + '"><b>' +
    esc(D.nodes[id].name) + '</b> — ' + esc(D.nodes[id].gloss) + '</button>').join('') + '</div>';

  // ---------- ทัวร์
  const tb = $('#tourbar');
  const tlist = $$('#tour-list button');
  let step = -1;
  function goStep(i) {
    step = clamp(i, 0, D.tour.length - 1);
    const s = D.tour[step];
    mark(s.n, s.e, s.c);
    $('.num', tb).innerHTML = (step + 1) + '<small>' + esc(U.of) + ' ' + D.tour.length + '</small>';
    $('.act', tb).textContent = s.act;
    $('h3', tb).textContent = s.t;
    $('p', tb).textContent = s.x;
    tlist.forEach((b, k) => b.classList.toggle('cur', k === step));
    focusOn(s.n, s.c);
    panel.innerHTML = '<p class="hint">' + esc(U.tour_hint.replace('{n}', s.n.length)) + '</p>' + listOf(s.n);
    $$('.qbtn').forEach(b => b.setAttribute('aria-pressed', 'false'));
  }
  if (tb && D.tour.length) {
    $('#t-next').addEventListener('click', () => goStep(step + 1));
    $('#t-prev').addEventListener('click', () => goStep(step < 0 ? 0 : step - 1));
    $('#t-reset').addEventListener('click', () => { step = -1; clearMarks(); panel.innerHTML = howto;
      $('.num', tb).innerHTML = '—<small>' + D.tour.length + ' ' + esc(U.steps) + '</small>'; $('.act', tb).textContent = U.tour;
      $('h3', tb).textContent = tb.dataset.title; $('p', tb).textContent = tb.dataset.intro;
      tlist.forEach(b => b.classList.remove('cur')); setZoom(fitZoom()); });
    tlist.forEach((b, k) => b.addEventListener('click', () => { goStep(k); $('#map').scrollIntoView(); }));
    document.addEventListener('keydown', (e) => {
      if (e.target.closest('input, textarea, button, a, select') || step < 0) return;
      const r = $('#map').getBoundingClientRect();
      if (r.bottom < 0 || r.top > innerHeight) return;
      if (e.key === 'ArrowRight') { e.preventDefault(); goStep(step + 1); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); goStep(step - 1); }
    });
  }

  // ---------- กรองตามหัวข้อที่สนใจ (เช่นข้อสอบ)
  $$('.qbtn').forEach(b => b.addEventListener('click', () => {
    const on = b.getAttribute('aria-pressed') !== 'true';
    $$('.qbtn').forEach(x => x.setAttribute('aria-pressed', 'false'));
    if (!on) { clearMarks(); panel.innerHTML = howto; return; }
    b.setAttribute('aria-pressed', 'true');
    const q = b.dataset.q;
    const ids = Object.keys(D.nodes).filter(id => D.nodes[id].q.includes(q));
    const set = new Set(ids);
    const es = D.edges.filter(e => set.has(e.src) && set.has(e.dst)).map(e => e.id);
    mark(ids, es, []);
    setZoom(fitZoom());
    panel.innerHTML = '<h3>' + esc(b.dataset.title) + '</h3><p class="gl">' + esc(U.focus_desc) + '</p>' + listOf(ids);
  }));

  // ---------- ปุ่มจากส่วนอื่นของหน้า → ชี้บนแผนที่
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-show]');
    if (!b) return;
    const ids = b.dataset.show.split(' ').filter(id => D.nodes[id]);
    if (!ids.length) return;
    $('#map').scrollIntoView();
    if (ids.length === 1) { select(ids[0], false); focusOn(ids, null, false); return; }
    mark(ids, D.edges.filter(x => ids.includes(x.src) && ids.includes(x.dst)).map(x => x.id), []);
    focusOn(ids, null, false);
    if (b.dataset.text) panel.innerHTML = '<h3>' + esc(b.dataset.title || '') + '</h3><p style="margin-top:8px">' + esc(b.dataset.text) +
      '</p>' + listOf(ids);
  });

  // กรอบแผนที่ไม่สูงเกินภาพ (แผนที่เล็ก/จอแคบ จะไม่มีพื้นที่ว่างใต้ภาพ)
  function sizeVp() {
    vp.style.height = '';
    const natural = BH * (vp.clientWidth / BW) + 2;
    if (natural < vp.clientHeight) vp.style.height = Math.ceil(natural) + 'px';
  }
  // เริ่มต้น: แสดงทั้งแผนที่
  requestAnimationFrame(() => { sizeVp(); setZoom(fitZoom()); });
  addEventListener('resize', () => { sizeVp(); if (zoom < fitZoom()) setZoom(fitZoom()); });
})();
"""
