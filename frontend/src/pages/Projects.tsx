// W3 โปรเจค (B5), laid out as the plan's mockup (docs/plan-v2/stage2/web.py w3): a banner for new
// folders waiting for their levels, the registry (status, potential, urgency, when it last moved,
// its latest news), the secretary's advice from each PROGRESS.md (จองเวลา), and the guide for other
// projects (CONNECT.md). A row opens the project's card: its levels and status, "ให้เลขาทำต่อได้"
// (the gate for background work, off until you switch it on), ทำต่อ, จองเวลา, hide.
import { useCallback, useEffect, useState, type MouseEvent } from "react";
import { Link } from "react-router";
import { api, type ProjectRow, type ProjectsPage } from "../api";
import { Markdown, Button, Card, Chip, Seg, Spinner, Switch } from "../components/ui";
import { Rank, Urgency } from "../components/project";
import { Toast, type ToastMsg } from "../components/Toast";
import { ago } from "../format";
import { Icon } from "../icons";
import { useStatus } from "../status";
import { Floating, type Anchor } from "./schedule/Floating";

type Say = (text: string, actionId?: number | null) => void;
const POTENTIALS = ["S", "A", "B", "C", "D", "F"];
const STATUS_TONE: Record<string, "ok" | "acc" | "muted" | "warn"> = { active: "ok", auto: "acc", paused: "muted", idea: "muted", done: "muted" };
const JOB_WORDS: Record<string, string> = { queued: "รอวางแผน", asking: "รอคุณอนุมัติ", ready: "รอทำ", running: "กำลังทำ" };

function StatusChip({ p }: { p: ProjectRow }) {
  if (p.missing) return <Chip tone="bad">ไม่พบโฟลเดอร์</Chip>;
  if (p.decision_id) return <Chip tone="warn">● ใหม่</Chip>;
  return <Chip tone={STATUS_TONE[p.status] ?? "muted"}>● {p.status_name}</Chip>;
}

// ------------------------------------------------------------------ one project's card
function ProjectCard({ p, anchor, onClose, say }: { p: ProjectRow; anchor: Anchor; onClose: () => void; say: Say }) {
  const [pot, setPot] = useState(p.potential);
  const [urg, setUrg] = useState(p.urgency);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const edit = (change: Parameters<typeof api.editProject>[1], words: string) =>
    api.editProject(p.id, change).then((r) => say(words, r.action_id), (e) => say((e as Error).message));
  const asking = !!p.decision_id;
  const levels = () => asking
    ? api.answerLevel(p.decision_id!, pot, urg).then(() => { say(`ตั้งระดับ ${p.name}: ${pot} · เร่งด่วน ${urg}`); onClose(); }, (e) => say((e as Error).message))
    : edit({ potential: pot, urgency: urg }, `ตั้งระดับ ${p.name}: ${pot} · เร่งด่วน ${urg}`);
  const why = p.is_self ? "เลขาไม่แก้โค้ดของตัวเองขณะทำงาน" : !p.is_git ? "ไม่มี git จึงไม่มี branch ให้ทำงานแยก" : p.missing ? "ไม่พบโฟลเดอร์" : "";
  return (
    <Floating anchor={anchor} onClose={onClose} width={440}>
      <div className="p-5 flex flex-col gap-3.5">
        <div className="flex items-start gap-2.5">
          <Rank potential={p.potential} set={p.level_set || !asking} />
          <div className="grow min-w-0">
            <h3 className="text-lg font-semibold leading-tight">{p.name}</h3>
            <span className="text-xs text-muted break-all">{p.path}</span>
          </div>
          <button type="button" aria-label="ปิด" onClick={onClose} className="text-muted hover:text-ink cursor-pointer p-1"><Icon name="x" size={16} /></button>
        </div>
        <div className="flex flex-col gap-2 text-sm">
          <div className="flex items-center gap-2"><span className="w-24 text-ink-2">potential</span>
            <Seg options={POTENTIALS.map((x) => ({ key: x, label: x }))} value={pot} onChange={setPot} /></div>
          <div className="flex items-center gap-2"><span className="w-24 text-ink-2">เร่งด่วน</span>
            <Seg options={[5, 4, 3, 2, 1, 0].map((x) => ({ key: String(x), label: String(x) }))} value={String(urg)} onChange={(v) => setUrg(Number(v))} />
            <span className="text-xs text-muted">5 = เร่งสุด</span></div>
          {(pot !== p.potential || urg !== p.urgency || asking) && (
            <div><Button sm kind="p" onClick={levels}>{asking ? "ตั้งระดับ" : "บันทึกระดับ"}</Button>
              {asking && <span className="text-xs text-muted ml-2">ระหว่างรอใช้ C · 2</span>}</div>
          )}
          {!asking && (
            <div className="flex items-center gap-2"><span className="w-24 text-ink-2">สถานะ</span>
              <select value={p.status} onChange={(e) => edit({ status: e.target.value }, `สถานะ ${p.name}: ${e.target.selectedOptions[0].text}`)}
                className="h-8 rounded-s border border-line-2 bg-panel px-2 text-[13px]">
                {[["idea", "ไอเดีย"], ["active", "กำลังทำ"], ["paused", "พัก"], ["auto", "รันอัตโนมัติ"], ["done", "จบแล้ว"]].map(([k, w]) => <option key={k} value={k}>{w}</option>)}
              </select></div>
          )}
        </div>
        <div className="rounded-card bg-panel-2 p-3 flex flex-col gap-2 text-sm">
          <div className="flex items-center gap-2.5">
            <Switch on={p.allow_jobs} onChange={why ? undefined : (on) => edit({ allow_jobs: on }, on ? `${p.name}: ให้เลขาทำต่อได้` : `${p.name}: ปิดการทำต่อ`)}
              title={why || undefined} />
            <span className="grow"><b>ให้เลขาทำต่อได้</b><span className="block text-xs text-muted">{why || "เลขาเอาขั้นถัดไปใน PROGRESS.md มาวางแผนตอนกลางคืน ทำบน branch แยก ไม่ push"}</span></span>
          </div>
          {p.job ? (
            <Link to={`/jobs?plan=${p.job.id}`} className="text-xs font-semibold text-accent-strong hover:underline">
              งานในคิว: {p.job.title} · {JOB_WORDS[p.job.status] ?? p.job.status} →</Link>
          ) : p.allow_jobs && !why && (
            <div className="flex gap-1.5">
              <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={p.progress.next ? `ว่างไว้ = ${p.progress.next}` : "ให้ทำอะไร"}
                className="h-8 grow min-w-0 rounded-s border border-line-2 bg-panel px-2 text-xs" />
              <Button sm kind="p" onClick={() => api.addJob(p.id, note).then((r) => { say(`${p.name} เข้าคิวแล้ว · รอวางแผน`, r.action_id); onClose(); },
                (e) => say((e as Error).message))}>ทำต่อ</Button>
            </div>
          )}
        </div>
        <div className="text-[13px] flex flex-col gap-1">
          <span><span className="text-ink-2">ขั้นถัดไปใน PROGRESS.md:</span> {p.progress.next || "—"}
            {p.progress.todo ? <span className="text-xs text-muted"> · เสร็จ {p.progress.done ?? 0} เหลือ {p.progress.todo}</span> : null}</span>
          <span className="text-ink-2">ล่าสุด {ago(p.last_activity)}{p.is_git ? ` · ${p.commits_14d} commit ใน 14 วัน` : ""}</span>
          {p.news && <span><span className="text-ink-2">ข่าวล่าสุด:</span> {p.news.title}</span>}
        </div>
        <div className="flex flex-wrap gap-1.5 border-t border-line pt-3">
          <Button sm icon="calendar" disabled={busy} onClick={() => { setBusy(true); api.bookProject(p.id).then(() => say(`จองเวลา 2 ชม. ให้ ${p.name} แล้ว · ตัววางตารางหาช่องว่างให้`), (e) => say((e as Error).message)).finally(() => setBusy(false)); }}>จองเวลา 2 ชม.</Button>
          <Button sm kind="ghost" icon="eye" onClick={() => edit({ hidden: !p.hidden }, p.hidden ? `แสดง ${p.name} แล้ว` : `ซ่อน ${p.name} แล้ว`).then(onClose)}>{p.hidden ? "แสดงในทะเบียน" : "ซ่อน (ไม่ใช่โปรเจค)"}</Button>
        </div>
      </div>
    </Floating>
  );
}

// ------------------------------------------------------------------ the guide for other projects
function Connect({ say }: { say: Say }) {
  const [guide, setGuide] = useState<{ text: string; inbox: string; example: string } | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => { api.connect().then(setGuide, () => setGuide(null)); }, []);
  return (
    <Card title="คู่มือเชื่อมต่อ">
      <div className="flex flex-col gap-2.5">
        <p className="text-[13px] text-ink-2">โปรเจคอื่นส่งรายงาน กำหนดการ และสถานะงาน เป็นไฟล์ JSON ลงโฟลเดอร์กลาง · เลขาอ่านทางเดียว ไม่ใช้โมเดล</p>
        <div className="flex items-center gap-2 h-9 rounded-s border border-line-2 bg-panel px-3 text-[13px] font-mono"><Icon name="folder" size={15} className="text-muted" />
          <span className="truncate">{guide?.inbox ?? "~/.secretary/inbox/<โปรเจค>/*.json"}</span></div>
        <div className="flex flex-wrap gap-1.5">
          <Button sm icon="ext" onClick={() => setOpen(true)} disabled={!guide?.text}>เปิด CONNECT.md</Button>
          <Button sm onClick={() => guide && navigator.clipboard?.writeText(guide.example).then(() => say("คัดลอกตัวอย่างแล้ว"))}>คัดลอกตัวอย่าง</Button>
        </div>
      </div>
      {open && guide && (
        <Floating anchor={null} onClose={() => setOpen(false)} width={640}>
          <div className="p-5"><Markdown text={guide.text} /></div>
        </Floating>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------ the page
export function Projects() {
  const { refresh } = useStatus();
  const [page, setPage] = useState<ProjectsPage | null>(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<ToastMsg | null>(null);
  const [card, setCard] = useState<{ id: number; anchor: Anchor } | null>(null);
  const [showHidden, setShowHidden] = useState(false);
  const [scanning, setScanning] = useState(false);
  const load = useCallback(() => { api.projects().then(setPage, (e) => setError((e as Error).message)); }, []);
  useEffect(load, [load]);
  const say: Say = (text, actionId = null) => { setToast({ text, actionId, key: Date.now() }); load(); refresh(); };
  const undo = async (id: number) => { await api.undo(id); setToast(null); load(); refresh(); };
  const scan = () => { setScanning(true); api.scanProjects().then((r) => say(r.line ?? "สแกนแล้ว"), (e) => say((e as Error).message)).finally(() => setScanning(false)); };

  if (error) return <p className="text-sm text-bad">{error}</p>;
  if (!page) return <Spinner label="กำลังโหลด…" />;
  const shown = page.items.filter((p) => !p.hidden && !p.missing);
  const tucked = page.items.filter((p) => p.hidden || p.missing);
  const asking = page.items.filter((p) => p.decision_id);
  const open = (p: ProjectRow, e?: MouseEvent) => setCard({ id: p.id, anchor: e ? { x: e.clientX, y: e.clientY } : null });
  const current = card && page.items.find((p) => p.id === card.id);
  const row = (p: ProjectRow) => (
    <tr key={p.id} onClick={(e) => open(p, e)} className={`border-b border-line last:border-0 cursor-pointer hover:bg-panel-2 ${p.hidden || p.missing ? "opacity-60" : ""}`}>
      <td className="px-4 py-2.5"><b className="block whitespace-nowrap">{p.name}</b>
        {(p.job || p.allow_jobs) && (
          <span className="flex items-center gap-1 text-[11.5px] text-accent-strong whitespace-nowrap" title="ให้เลขาทำต่อได้">
            <Icon name="robot" size={12} />{p.job ? `งานเบื้องหลัง: ${JOB_WORDS[p.job.status] ?? p.job.status}` : "ทำต่อได้"}</span>
        )}</td>
      <td className="px-4 py-2.5"><StatusChip p={p} /></td>
      <td className="px-4 py-2.5"><Rank potential={p.potential} set={!p.decision_id} /></td>
      <td className="px-4 py-2.5">{p.decision_id ? <span className="text-muted">?</span> : <Urgency level={p.urgency} />}</td>
      <td className="px-4 py-2.5 text-muted whitespace-nowrap">{ago(p.last_activity)}</td>
      <td className="px-4 py-2.5 min-w-48">{p.decision_id ? <span className="text-muted">ยังไม่ตั้งระดับ</span>
        : p.news ? <span className={p.news.urgent ? "text-bad" : ""}>{p.news.title}</span>
        : <span className="text-muted">{p.progress.next ? `ต่อไป: ${p.progress.next}` : "—"}</span>}</td>
    </tr>
  );
  return (
    <div className="flex flex-col gap-4">
      {asking.length > 0 && (
        <div className="flex items-center gap-3 rounded-card bg-accent-soft px-4 py-3">
          <Icon name="folder" className="text-accent-strong" />
          <span className="grow text-sm">พบโปรเจคใหม่ {asking.map((p) => p.name).join(", ")} ใน ~/Projects · ระหว่างรอใช้ระดับ C · 2</span>
          <Button sm kind="p" onClick={() => open(asking[0])}>ตั้งระดับ</Button>
        </div>
      )}
      {!page.scanned && (
        <div className="flex items-center gap-3 rounded-card bg-panel-2 px-4 py-3">
          <span className="grow text-sm">ยังไม่ได้สแกน {page.root} · รอบสแกน 06:30 ยังปิดอยู่จนถึงเช็กของ B5 หรือกดสแกนตอนนี้ (ไม่ใช้โมเดล)</span>
          <Button sm kind="p" onClick={scan} disabled={scanning}>{scanning ? <Spinner label="กำลังสแกน…" /> : "สแกนตอนนี้"}</Button>
        </div>
      )}
      <div className="grid gap-4 items-start lg:grid-cols-[minmax(0,3fr)_minmax(280px,1fr)]">
        <Card flush title={<span className="flex items-baseline gap-2">ทะเบียนโปรเจค<span className="text-xs text-muted font-normal">สแกนจาก ~/Projects ทุกเช้า</span></span>}
          right={<span className="flex items-center gap-1.5"><Chip>potential S–F</Chip><Chip>เร่งด่วน 5 = เร่งสุด</Chip>
            <Button sm kind="ghost" icon="refresh" onClick={scan} disabled={scanning} title="สแกน ~/Projects ตอนนี้">{scanning ? "…" : ""}</Button></span>}>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead><tr className="text-left text-xs text-muted border-y border-line">
                {["โปรเจค", "สถานะ", "potential", "เร่งด่วน", "ล่าสุด", "ข่าวล่าสุด"].map((h) => <th key={h} className="font-medium px-4 py-2 whitespace-nowrap">{h}</th>)}
              </tr></thead>
              <tbody>{shown.map(row)}{showHidden && tucked.map(row)}</tbody>
            </table>
          </div>
          {tucked.length > 0 && (
            <button type="button" onClick={() => setShowHidden((x) => !x)} className="w-full text-left px-4 py-2.5 text-xs text-muted hover:text-ink border-t border-line cursor-pointer">
              {showHidden ? "ซ่อนรายการที่ซ่อนไว้" : `แสดงที่ซ่อนไว้และโฟลเดอร์ที่หายไป (${tucked.length})`}</button>
          )}
        </Card>
        <div className="flex flex-col gap-4 min-w-0">
          <Card title={<span className="flex items-baseline gap-2">คำแนะนำจากเลขา<span className="text-xs text-muted font-normal">อ่านจาก PROGRESS.md</span></span>}>
            {page.advice.length === 0 ? <p className="text-sm text-muted">ยังไม่มีคำแนะนำ · ตั้ง potential ให้โปรเจคที่สำคัญ แล้วเลขาจะบอกเมื่อมันนิ่งนานหรือได้เวลาน้อยไป</p> : (
              <ul className="divide-y divide-line">
                {page.advice.slice(0, 6).map((a) => (
                  <li key={`${a.project_id}-${a.kind}`} className="py-2.5 flex items-start gap-2.5">
                    <Icon name={a.kind === "stale" ? "clock" : "chart"} size={16} className="mt-0.5 text-muted shrink-0" />
                    <span className="grow min-w-0">
                      <span className="block font-semibold text-[13.5px]">{a.title}</span>
                      <span className="block text-xs text-ink-2">{a.detail}</span>
                    </span>
                    <span className="flex flex-col gap-1 items-end">
                      <Button sm onClick={() => api.bookProject(a.project_id).then(() => say(`จองเวลา 2 ชม. ให้ ${a.project} แล้ว`), (e) => say((e as Error).message))}>จองเวลา</Button>
                      {a.kind === "short" && <Link to="/schedule" className="text-[11.5px] font-semibold text-accent-strong hover:underline">ดูตาราง →</Link>}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Connect say={say} />
        </div>
      </div>
      {current && <ProjectCard key={current.id} p={current} anchor={card!.anchor} onClose={() => setCard(null)} say={say} />}
      <Toast msg={toast} onUndo={undo} onClose={() => setToast(null)} />
    </div>
  );
}
