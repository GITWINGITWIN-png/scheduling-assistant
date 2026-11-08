// W7 การใช้เวลา (B6), laid out as the plan's mockup (docs/plan-v2/stage2/web.py w7): time per day by
// category (①), by project against the plan (②), what the rules noticed (③), and the privacy card
// (④ ⑤): the recording switch, หยุดบันทึก, and the blocklist. Everything comes from ActivityWatch on
// this computer, through the secretary's filter; nothing here uses a model.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { api, type Behaviour, type PrivacyCard, type PrivacyRuleRow, type TimeBar, type TimePage, type TimeProject, type TimeRange } from "../api";
import { Toast, type ToastMsg } from "../components/Toast";
import { Banner, Button, Card, Spinner, Switch, Tabs } from "../components/ui";
import { hm } from "../format";
import { Icon } from "../icons";
import { useStatus } from "../status";

type Say = (text: string, actionId?: number | null) => void;

// The mockup's colours per category (W7 ①): code c1, study c2, meeting c3, web c6, other c5; mail and chat c4.
const CAT_COLOR: Record<string, string> = { code: "var(--c1)", study: "var(--c2)", meeting: "var(--c3)", chat: "var(--c4)",
  web: "var(--c6)", other: "var(--c5)" };
const CAT_ORDER = ["code", "study", "meeting", "chat", "web", "other"];
const PROJECT_COLORS = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c6)", "var(--c5)"];

function hours(min: number): string {
  if (min < 60) return `${Math.round(min)} นาที`;
  const h = min / 60;
  return `${h >= 10 ? Math.round(h) : Math.round(h * 2) / 2} ชม.`;
}

/** ① Stacked bars, one per day (per hour today), the categories in the mockup's order. */
function Bars({ bars, categories, perHour }: { bars: TimeBar[]; categories: Record<string, string>; perHour: boolean }) {
  const W = 640, H = 200, top = 18, bottom = 24, left = 44;
  const totals = bars.map((b) => Object.values(b.minutes).reduce((a, v) => a + v, 0));
  const maxMin = Math.max(60, ...totals);
  const stepMin = perHour ? 15 : maxMin > 600 ? 180 : maxMin > 240 ? 120 : 60;
  const scaleMax = Math.ceil(maxMin / stepMin) * stepMin;
  const y = (m: number) => top + (H - top - bottom) * (1 - m / scaleMax);
  const slot = (W - left) / bars.length;
  const bw = Math.min(46, slot * 0.62);
  const used = CAT_ORDER.filter((c) => bars.some((b) => b.minutes[c]));
  return (
    <div className="flex flex-col gap-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="เวลาต่อวันตามหมวด">
        {Array.from({ length: scaleMax / stepMin + 1 }, (_, i) => i * stepMin).map((m) => (
          <g key={m}>
            <line x1={left} x2={W} y1={y(m)} y2={y(m)} stroke="var(--line)" />
            <text x={left - 6} y={y(m) + 4} textAnchor="end" fontSize="11" fill="var(--muted)">{perHour ? `${m}น.` : `${m / 60} ชม.`}</text>
          </g>
        ))}
        {bars.map((b, i) => {
          let acc = 0;
          const x = left + slot * i + (slot - bw) / 2;
          return (
            <g key={b.start}>
              {CAT_ORDER.filter((c) => b.minutes[c]).map((c) => {
                const y0 = y(acc), y1 = y(acc + b.minutes[c]);
                acc += b.minutes[c];
                return <rect key={c} x={x} y={y1} width={bw} height={Math.max(0, y0 - y1 - 1)} rx={3} fill={CAT_COLOR[c]}>
                  <title>{`${b.label} · ${categories[c]} ${hours(b.minutes[c])}`}</title></rect>;
              })}
              {(!perHour || i % 2 === 0) && <text x={x + bw / 2} y={H - 6} textAnchor="middle" fontSize="11" fill="var(--muted)">{b.label}</text>}
            </g>
          );
        })}
      </svg>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-2">
        {used.map((c) => <span key={c} className="inline-flex items-center gap-1.5"><i className="size-2.5 rounded-sm" style={{ background: CAT_COLOR[c] }} />{categories[c]}</span>)}
      </div>
    </div>
  );
}

/** ② Per project, against the schedule's plan for it. */
function Projects({ items }: { items: TimeProject[] }) {
  const total = items.reduce((a, p) => a + p.minutes, 0);
  return (
    <Card title="แยกตามโปรเจค">
      {items.length === 0 ? <p className="text-sm text-muted">ยังไม่มีเวลาที่ผูกกับโปรเจค · เลขาดูชื่อโปรเจคจากชื่อหน้าต่าง เช่น VS Code และ terminal</p> : (
        <div className="flex flex-col gap-2.5">
          {total > 0 && (
            <div className="flex h-2.5 overflow-hidden rounded-full bg-panel-2">
              {items.filter((p) => p.minutes).map((p, i) => <i key={p.name} title={`${p.name} ${hours(p.minutes)}`} style={{ width: `${(100 * p.minutes) / total}%`, background: PROJECT_COLORS[i % PROJECT_COLORS.length] }} />)}
            </div>
          )}
          <ul className="divide-y divide-line">
            {items.map((p, i) => (
              <li key={p.name} className="flex items-start gap-2.5 py-2">
                <i className="mt-1.5 size-2 shrink-0 rounded-full" style={{ background: PROJECT_COLORS[i % PROJECT_COLORS.length] }} />
                <span className="grow min-w-0">
                  <span className="block font-semibold text-[14px] truncate">{p.name}</span>
                  {p.planned > 0 && <span className="block text-xs text-muted">แผนถึงตอนนี้ {hours(p.planned)}{p.short >= 30 ? ` · ขาด ${hours(p.short)}` : ""}</span>}
                </span>
                <span className="text-sm text-ink-2 whitespace-nowrap">{hours(p.minutes)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

/** ③ What the rules noticed. */
function Behaviours({ items, days }: { items: Behaviour[]; days: number }) {
  return (
    <Card title="พฤติกรรมที่เจอ">
      {items.length === 0 ? (
        <p className="text-sm text-muted">{days ? "ยังไม่เห็นอะไรชัด · ข้อมูลยิ่งหลายวันยิ่งเห็น" : "ยังไม่มีข้อมูล"}</p>
      ) : (
        <ul className="divide-y divide-line">
          {items.map((b) => (
            <li key={b.title} className="flex items-start gap-3 py-2.5">
              <Icon name={b.icon} className="mt-0.5 text-ink-2" />
              <span className="grow min-w-0">
                <span className="block font-semibold text-[14px]">{b.title}</span>
                <span className="block text-xs text-muted">{b.sub}</span>
              </span>
              {b.link && <Link to={b.link} className="text-xs font-semibold text-accent-strong hover:underline whitespace-nowrap">ตาราง →</Link>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** อื่นๆ: what the rules couldn't sort, for you to sort (it becomes a rule of yours). */
function Unsorted({ page, say, fail }: { page: TimePage; say: Say; fail: (e: unknown) => void }) {
  if (page.unsorted.length === 0) return null;
  return (
    <Card title="ยังไม่จัดหมวด" right={<span className="text-xs text-muted">กติกาจัดไม่ได้ · เลือกหมวดแล้วเลขาจำเป็นกติกาของคุณ</span>}>
      <ul className="divide-y divide-line">
        {page.unsorted.map((u) => (
          <li key={u.app} className="flex flex-wrap items-center gap-2.5 py-2">
            <span className="grow min-w-0 basis-48">
              <span className="block font-semibold text-[14px] truncate">{u.app || "(ไม่มีชื่อแอป)"}</span>
              <span className="block text-xs text-muted truncate" title={u.title}>{u.title}</span>
            </span>
            <span className="text-sm text-ink-2">{hours(u.minutes)}</span>
            <select defaultValue="" aria-label={`จัดหมวด ${u.app}`} className="rounded-full border border-line-2 bg-panel px-2 py-1 text-xs"
              onChange={async (e) => {
                const cat = e.currentTarget.value;
                if (!cat) return;
                try { const r = await api.sortTime("app", u.app, cat); say(`${u.app} → ${page.categories[cat]} · จัดของเดิมใหม่ด้วย`, r.action_id); }
                catch (err) { fail(err); }
              }}>
              <option value="">จัดหมวด…</option>
              {CAT_ORDER.filter((c) => c !== "other").map((c) => <option key={c} value={c}>{page.categories[c]}</option>)}
            </select>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** What the recorder is doing, in one line. */
function recorderLine(p: PrivacyCard): { text: string; bad?: boolean } {
  const r = p.recorder;
  if (!r.installed) return { text: "ยังไม่ได้ติดตั้ง ActivityWatch · ดู docs/setup/ideas-and-time.md", bad: true };
  if (r.paused_until) return { text: `หยุดบันทึกถึง ${hm(new Date(r.paused_until))} แล้วจะบันทึกต่อเอง` };
  if (r.extension === "after_login") return { text: "ติดตั้งแล้ว · ล็อกเอาต์แล้วล็อกอินใหม่ 1 ครั้งก่อน ส่วนเสริม GNOME จึงจะทำงาน", bad: true };
  if (r.extension === "missing") return { text: "ไม่พบส่วนเสริม GNOME “Focused Window D-Bus” · ติดตั้งใหม่ด้วย desktop/activitywatch.py install", bad: true };
  if (!r.enabled) return { text: "ปิดอยู่ · ไม่มีอะไรถูกบันทึก" };
  if (!r.running) return { text: "เปิดไว้แต่ตัวบันทึกไม่ได้ทำงาน · ดู journalctl --user -u awatcher", bad: true };
  const read = p.last_read;
  if (read.error && (!read.at || (read.error_at ?? "") > read.at)) return { text: `อ่าน ActivityWatch ไม่ได้: ${read.error}`, bad: true };
  return { text: read.to ? `บันทึกอยู่ · เลขาอ่านล่าสุด ${hm(new Date(read.to))} (ทุก 15 นาที)` : "บันทึกอยู่ · เลขาจะอ่านรอบแรกภายใน 15 นาที" };
}

/** ④ ⑤ The privacy card. */
function Privacy({ p, set, say, fail }: { p: PrivacyCard; set: (p: PrivacyCard) => void; say: Say; fail: (e: unknown) => void }) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const r = p.recorder;
  const on = r.enabled && r.round_on;
  const line = recorderLine(p);
  const run = async (f: () => Promise<void>) => { setBusy(true); try { await f(); } catch (e) { fail(e); } setBusy(false); };
  const notes = [...new Set(p.rules.filter((x) => x.kind !== "word").map((x) => x.note || x.value))];
  const words = p.rules.filter((x) => x.kind === "word").length;
  return (
    <Card title="ความเป็นส่วนตัว">
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center gap-3">
          <span className="grow text-sm font-semibold">บันทึกกิจกรรม</span>
          <Switch on={on} title={on ? "ปิด: หยุดบันทึก และไม่เปิดเองตอนล็อกอิน" : "เปิด: ActivityWatch บันทึก และเลขาอ่านทุก 15 นาที"}
            onChange={r.installed && !busy ? (v) => run(async () => {
              const out = await api.setRecording(v); set(out);
              say(v ? "เปิดบันทึกกิจกรรมแล้ว · เลขาอ่านทุก 15 นาที" : "ปิดบันทึกกิจกรรมแล้ว", out.action_id);
            }) : undefined} />
        </div>
        <span className={`text-xs ${line.bad ? "text-warn" : "text-ink-2"}`}>{line.text}</span>
        {on && (r.paused_until ? (
          <div className="flex"><Button icon="play" disabled={busy} onClick={() => run(async () => {
            const out = await api.resumeRecording(); set(out); say("บันทึกต่อแล้ว");
          })}>บันทึกต่อเลย</Button></div>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <Button icon="pause" disabled={busy} onClick={() => run(async () => {
              const out = await api.pauseRecording(60); set(out); say(`หยุดบันทึกถึง ${hm(new Date(out.until))} · กดบันทึกต่อเลยเพื่อเลิกหยุด`);
            })}>หยุดบันทึก 1 ชั่วโมง</Button>
            {r.pause_minutes.filter((m) => m !== 60).map((m) => (
              <button key={m} type="button" disabled={busy} className="text-xs text-ink-2 hover:underline cursor-pointer"
                onClick={() => run(async () => { const out = await api.pauseRecording(m); set(out); say(`หยุดบันทึกถึง ${hm(new Date(out.until))} · กดบันทึกต่อเลยเพื่อเลิกหยุด`); })}>
                {m < 60 ? `${m} นาที` : `${m / 60} ชม.`}</button>
            ))}
          </div>
        ))}
        <div className="flex items-start gap-2 text-sm">
          <span className="grow text-ink-2">ห้ามบันทึก: {notes.slice(0, 3).join(", ")}{notes.length > 3 ? ` +${notes.length - 3}` : ""} · ซ่อนชื่อหน้าต่างที่มี {words} คำ</span>
          <button type="button" onClick={() => setEditing(!editing)} className="font-semibold text-accent-strong hover:underline cursor-pointer">
            {editing ? "เสร็จ" : "แก้"}</button>
        </div>
        {editing && <RulesEditor p={p} set={set} say={say} fail={fail} />}
        <span className="flex items-start gap-1.5 text-xs text-muted"><Icon name="lock" size={14} className="mt-0.5" />
          log อยู่บนเครื่องนี้เท่านั้น · หน้าต่างที่ห้ามไม่ถูกส่งเข้า ActivityWatch ตั้งแต่แรก และเลขากรองซ้ำอีกชั้นก่อนเก็บ</span>
        {r.installed && <a href={r.web} target="_blank" rel="noreferrer" className="text-xs text-ink-2 hover:underline">เปิด ActivityWatch ของเครื่องนี้ ({r.web}) ↗</a>}
      </div>
    </Card>
  );
}

const KIND_HINT: Record<PrivacyRuleRow["kind"], string> = {
  app: "ชื่อแอป เช่น keepassxc · ไม่บันทึกเลย",
  title: "ชื่อเว็บหรือคำในชื่อหน้าต่าง เช่น kasikorn · ไม่บันทึกเลย",
  word: "คำในชื่อหน้าต่าง เช่น รหัสผ่าน · เก็บเวลาไว้ แต่ซ่อนชื่อหน้าต่าง",
};

function RulesEditor({ p, set, say, fail }: { p: PrivacyCard; set: (p: PrivacyCard) => void; say: Say; fail: (e: unknown) => void }) {
  return (
    <div className="flex flex-col gap-3 rounded-s border border-line bg-panel-2 p-3">
      {(["app", "title", "word"] as const).map((kind) => (
        <div key={kind} className="flex flex-col gap-1.5">
          <span className="text-xs font-semibold">{p.kinds[kind]} <span className="font-normal text-muted">· {KIND_HINT[kind]}</span></span>
          <div className="flex flex-wrap gap-1">
            {p.rules.filter((x) => x.kind === kind).map((x) => (
              <span key={x.id} title={x.note} className="inline-flex items-center gap-1 rounded-full border border-line-2 bg-panel px-2 py-0.5 text-xs">
                {x.value}
                <button type="button" aria-label={`เลิกห้าม ${x.value}`} className="text-muted hover:text-bad cursor-pointer" onClick={async () => {
                  try { const out = await api.removePrivacyRule(x.id); set(out); say(`เลิกห้าม “${x.value}” แล้ว`, out.action_id); } catch (e) { fail(e); }
                }}><Icon name="x" size={12} /></button>
              </span>
            ))}
            <input placeholder="+ เพิ่ม" className="w-28 rounded-full border border-dashed border-line-2 bg-panel px-2 py-0.5 text-xs outline-none focus:border-accent"
              onKeyDown={async (e) => {
                if (e.key !== "Enter" || !e.currentTarget.value.trim()) return;
                const input = e.currentTarget, value = input.value;
                try { const out = await api.addPrivacyRule(kind, value); set(out); input.value = ""; say(`ห้ามบันทึก “${value.trim()}” แล้ว · ลบของเดิมที่ตรงออกจาก log ด้วย`, out.action_id); }
                catch (err) { fail(err); }
              }} />
          </div>
        </div>
      ))}
    </div>
  );
}

const RANGES: { key: TimeRange; label: string }[] = [{ key: "today", label: "วันนี้" }, { key: "week", label: "สัปดาห์นี้" }, { key: "month", label: "เดือนนี้" }];

export function Time() {
  const { refresh } = useStatus();
  const [range, setRange] = useState<TimeRange>("week");
  const [page, setPage] = useState<TimePage | null>(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<ToastMsg | null>(null);
  const load = useCallback(() => {
    api.time(range).then((p) => { setPage(p); setError(""); }, (e) => setError((e as Error).message));
  }, [range]);
  useEffect(() => {
    load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, [load]);
  const say: Say = (text, actionId = null) => { setToast({ text, actionId, key: Date.now() }); refresh(); load(); };
  const fail = (e: unknown) => setError((e as Error).message);
  const undo = async (id: number) => { await api.undo(id); setToast(null); load(); refresh(); };
  if (page === null) return error ? <p className="text-sm text-bad">{error}</p> : <Spinner />;
  const setPrivacy = (privacy: PrivacyCard) => setPage({ ...page, privacy });
  const r = page.privacy.recorder;
  return (
    <div className="flex flex-col gap-4">
      {error && <p className="text-sm text-bad">{error}</p>}
      {!(r.enabled && r.round_on) && (
        <Banner icon="clock">ยังไม่ได้บันทึกกิจกรรม · เปิด <b>บันทึกกิจกรรม</b> ในการ์ดความเป็นส่วนตัว แล้วหน้านี้จะเริ่มมีเวลาต่อวัน แยกตามหมวดและโปรเจค</Banner>
      )}
      <div className="flex flex-wrap items-end gap-3">
        <Tabs options={RANGES} value={range} onChange={setRange} />
        <span className="ml-auto text-sm text-muted">{page.label} · จาก ActivityWatch{page.total ? ` · รวม ${hours(page.total)}` : ""}</span>
      </div>
      <div className="grid gap-4 items-start xl:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
        <div className="flex flex-col gap-4 min-w-0">
          <Card title={range === "today" ? "เวลาต่อชั่วโมง" : "เวลาต่อวัน"}>
            {page.total ? <Bars bars={page.bars} categories={page.categories} perHour={range === "today"} />
              : <p className="text-sm text-muted">ยังไม่มีเวลาที่บันทึกใน{RANGES.find((x) => x.key === range)!.label}</p>}
          </Card>
          <Behaviours items={page.behaviours} days={page.days_with_data} />
          <Unsorted page={page} say={say} fail={fail} />
        </div>
        <div className="flex flex-col gap-4 min-w-0">
          <Projects items={page.projects} />
          <Privacy p={page.privacy} set={setPrivacy} say={say} fail={fail} />
        </div>
      </div>
      <Toast msg={toast} onUndo={undo} onClose={() => setToast(null)} />
    </div>
  );
}
