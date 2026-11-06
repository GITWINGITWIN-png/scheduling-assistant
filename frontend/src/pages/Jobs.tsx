// W4 งานเบื้องหลัง (B5), laid out as the plan's mockup (docs/plan-v2/stage2/web.py w4_body): the quota
// and the 70% line, three numbers, what's running with its budget and หยุด, the queue in order
// (where each project is stuck, the model and effort, budget, risk, the rule check), and on the
// right the plan you picked: its steps, why it asks, the model and effort to change before you
// approve (the budget follows), อนุมัติ 3 วัน · แก้แผน · ไม่เอา. Below, what was done and on which
// branch. Every change shows a toast with เลิกทำ.
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api, type JobRow, type JobsPage } from "../api";
import { LineEditor, Meter, Rank } from "../components/project";
import { Toast, type ToastMsg } from "../components/Toast";
import { Button, Card, Chip, Markdown, Spinner } from "../components/ui";
import { kTokens, shortDay, when } from "../format";
import { Icon } from "../icons";
import { useStatus } from "../status";

const EFFORTS = ["low", "medium", "high", "xhigh", "max"];
const cap = (m: string) => (m ? m[0].toUpperCase() + m.slice(1) : "—");
type Say = (text: string, actionId?: number | null) => void;

function RuleChip({ j }: { j: JobRow }) {
  if (j.status === "asking") return <Chip tone="warn">ต้องถาม</Chip>;
  if (j.status === "ready" && j.approved_until) return <Chip tone="acc">อนุมัติถึง {shortDay(new Date(j.approved_until))}</Chip>;
  if (j.status === "ready") return <Chip tone="ok"><Icon name="check" size={12} />ผ่าน</Chip>;
  return <Chip>รอวางแผน</Chip>;
}

function RiskChip({ j }: { j: JobRow }) {
  if (!j.planned_at) return <span className="text-muted">—</span>;
  return j.high_risk ? <Chip tone="bad" title={j.risks.join(" · ")}>สูง</Chip> : <Chip tone="ok">ต่ำ</Chip>;
}

// ------------------------------------------------------------------ the quota card and the numbers
function QuotaCard({ q, usage, onRead, reading, say }: { q: JobsPage["quota"]; usage: JobsPage["usage"]; onRead: () => void; reading: boolean; say: Say }) {
  const [editing, setEditing] = useState(false);
  const left = q.week_left;
  const above = left !== undefined && left > q.line;
  const resets = q.week_resets_at ? new Date(q.week_resets_at) : null;
  const word = left === undefined ? "ยังไม่ได้อ่านโควตา · ทุกแผนถามคุณก่อน"
    : !q.auto ? "ปิดการทำเองไว้ · ทุกแผนถามคุณก่อน"
    : above ? `เส้น ${q.line}%: เหนือเส้น งานเสี่ยงต่ำทำเองได้` : `เส้น ${q.line}%: ต่ำกว่าเส้น ทุกแผนถามคุณก่อน`;
  return (
    <Card title="โควตา Claude สัปดาห์นี้" right={<Button sm kind="ghost" icon="refresh" onClick={onRead} disabled={reading} title="เรียก Claude สั้นๆ (ไม่กี่ร้อยโทเคน) เพื่ออ่านค่าล่าสุด">
      {reading ? <Spinner label="กำลังอ่าน…" /> : "อ่านตอนนี้"}</Button>}>
      <div className="flex flex-col gap-2">
        <div className="flex items-baseline gap-2">
          <span className="text-[26px] font-semibold tabular-nums">{left === undefined ? "—" : `${Math.round(left)}%`}</span>
          <span className="text-[13px] text-muted">เหลือ{resets ? ` · รีเซ็ต ${shortDay(resets)} ${resets.toTimeString().slice(0, 5)}` : ""}</span>
        </div>
        <Meter value={left ?? 0} tone={above ? "ok" : "warn"} mark={q.line} thick />
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span className="text-muted grow">{left === undefined ? "" : `Claude รายงาน: สัปดาห์ใช้ไป ${Math.round(100 - left)}%`}
            {q.five_left != null ? ` · 5 ชั่วโมงใช้ไป ${Math.round(100 - q.five_left)}%` : ""}</span>
          <b>{word}</b>
          {!editing && <Button sm kind="ghost" icon="edit" onClick={() => setEditing(true)} title="เส้นนี้เป็นกติกาในสมุดกติกา">แก้เส้น</Button>}
        </div>
        {editing && <LineEditor line={q.line} onCancel={() => setEditing(false)}
          onSave={(line) => api.setJobsRule({ line }).then((x) => { setEditing(false); say(`เส้นโควตาเป็น ${x.line}% แล้ว`, x.action_id); }, (e) => say((e as Error).message))} />}
        <div className="flex flex-wrap gap-x-3 text-xs text-muted border-t border-line pt-2">
          <span className="grow">เลขาใช้วันนี้ <b className="text-ink">{kTokens(usage.today)}</b> โทเคน (งานเบื้องหลัง {kTokens(usage.jobs_today)}) · 7 วัน {kTokens(usage.week)}</span>
          {q.at && <span>อ่านเมื่อ {when(q.at)}</span>}
        </div>
        <span className="text-[11px] text-muted">Claude ส่งตัวเลขเป็นจำนวนเต็ม % · โทเคนของงานส่วนใหญ่เป็นการอ่าน cache ซ้ำ (ดูได้ในงานที่ทำแล้ว) งานเล็กๆ จึงยังไม่ถึง 1% ของสัปดาห์ · โควตา 5 ชั่วโมงขยับเร็วกว่า</span>
      </div>
    </Card>
  );
}

function Kpi({ n, label, title }: { n: number; label: string; title?: string }) {
  return (
    <div title={title} className="rounded-card bg-panel-2 px-4 py-3.5 flex flex-col gap-1 min-w-0">
      <span className="text-[24px] font-semibold leading-none tabular-nums">{n}</span>
      <span className="text-xs text-muted">{label}</span>
    </div>
  );
}

// ------------------------------------------------------------------ what's running
function Running({ j, page, say }: { j: JobRow | null; page: JobsPage; say: Say }) {
  if (!j) {
    return (
      <Card title="กำลังทำ">
        <p className="text-sm text-muted">ไม่มีงานที่กำลังทำ · {page.round_on
          ? `เลขาเริ่มงานที่พร้อมเองในช่วง ${page.window}`
          : <>รอบกลางคืน ({page.window}) ยังปิดอยู่ · <Link to="/settings" className="underline">เปิดที่หน้าตั้งค่า</Link> หรือกดทำเลยที่แผนที่พร้อม</>}</p>
      </Card>
    );
  }
  const pct = j.budget ? (100 * j.used) / j.budget : 0;
  return (
    <Card title="กำลังทำ">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2.5">
          <Rank potential={j.potential || "C"} />
          <span className="grow min-w-0">
            <span className="block font-semibold text-[13.5px] truncate">{j.project} · ทำต่อจาก “{j.title || j.stuck_at}”</span>
            <span className="block text-xs text-muted truncate">เริ่ม {when(j.started_at)} · {j.branch} · เปิด ponytail</span>
          </span>
          <Chip>{cap(j.model)} · {j.effort}</Chip>
          <Button sm kind="bad" icon="x" onClick={() => api.stopJob(j.id).then(() => say("สั่งหยุดแล้ว · งานที่ทำไปจะถูก commit บน branch ของมัน"), (e) => say((e as Error).message))}>หยุด</Button>
        </div>
        <Meter value={pct} tone={pct > 90 ? "warn" : "accent"} mark={100} />
        <div className="flex text-xs text-muted"><span className="grow">ใช้ {kTokens(j.used)} / งบ {kTokens(j.budget)} โทเคน</span><span>เกินงบ = หยุด แล้วไปงานถัดไป</span></div>
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------ the queue
function NewJob({ page, say }: { page: JobsPage; say: Say }) {
  const [open, setOpen] = useState(false);
  const [project, setProject] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  if (!open) return <Button sm icon="plus" onClick={() => setOpen(true)} disabled={!page.projects.length}
    title={page.projects.length ? "สั่งให้เลขาทำต่อในโปรเจค (วางแผนทันที)" : "เปิด “ให้เลขาทำต่อได้” ที่หน้าโปรเจคก่อน"}>ทำต่อ</Button>;
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <select value={project} onChange={(e) => setProject(e.target.value)} className="h-8 rounded-s border border-line-2 bg-panel px-2 text-xs">
        <option value="">เลือกโปรเจค…</option>
        {page.projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="ให้ทำอะไร (ว่างไว้ = ขั้นถัดไปใน PROGRESS.md)"
        className="h-8 w-64 max-w-full rounded-s border border-line-2 bg-panel px-2 text-xs" />
      <Button sm kind="p" disabled={!project || busy} onClick={() => { setBusy(true); api.addJob(Number(project), note)
        .then((r) => { setOpen(false); setNote(""); say(r.go === null ? r.why : r.go ? `วางแผนแล้ว · ผ่านกฎ รอทำ · ${r.why}` : `วางแผนแล้ว · ส่งไปถามใน #อนุมัติ · ${r.why}`, r.action_id); },
          (e) => say((e as Error).message)).finally(() => setBusy(false)); }}>{busy ? <Spinner label="Opus กำลังวางแผน…" /> : "ทำต่อ"}</Button>
      <Button sm kind="ghost" onClick={() => setOpen(false)}>ยกเลิก</Button>
    </span>
  );
}

function Queue({ page, picked, pick, say }: { page: JobsPage; picked: number | null; pick: (id: number) => void; say: Say }) {
  return (
    <Card flush title={<span className="flex items-baseline gap-2">คิวงานที่ค้าง<span className="text-xs text-muted font-normal">เรียงตาม potential และความเร่งด่วน</span></span>}
      right={<NewJob page={page} say={say} />}>
      {page.queue.length === 0 ? (
        <p className="text-sm text-muted px-4 pb-4">ยังไม่มีงานในคิว · เปิด “ให้เลขาทำต่อได้” ที่<Link to="/projects" className="underline">หน้าโปรเจค</Link> แล้วเลขาจะเอาขั้นถัดไปใน PROGRESS.md มาวางแผน</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead><tr className="text-left text-xs text-muted border-y border-line">
              {["งาน", "ค้างตรงไหน", "โมเดล · effort", "งบ", "ความเสี่ยง", "กฎ", ""].map((h, i) => <th key={h} className={`font-medium py-2 whitespace-nowrap ${i ? "px-2.5" : "pl-4 pr-2.5"}`}>{h}</th>)}
            </tr></thead>
            <tbody>
              {page.queue.map((j) => (
                <tr key={j.id} onClick={() => pick(j.id)} className={`border-b border-line last:border-0 cursor-pointer ${picked === j.id ? "bg-accent-soft/60" : "hover:bg-panel-2"}`}>
                  <td className="pl-4 pr-2.5 py-2.5"><b className="block whitespace-nowrap">{j.project}</b>
                    {j.title && <span className="block text-xs text-ink-2">{j.title}</span>}</td>
                  <td className="px-2.5 py-2.5 text-[12.5px]">{j.stuck_at || j.note}{j.source === "you" ? <span className="text-muted"> · คุณสั่ง</span> : null}</td>
                  <td className="px-2.5 py-2.5 whitespace-nowrap">{j.planned_at ? `${cap(j.model)} · ${j.effort}` : "—"}</td>
                  <td className="px-2.5 py-2.5 font-mono whitespace-nowrap">{j.planned_at ? kTokens(j.budget) : "—"}</td>
                  <td className="px-2.5 py-2.5"><RiskChip j={j} /></td>
                  <td className="px-2.5 py-2.5"><RuleChip j={j} /></td>
                  <td className="pl-2.5 pr-4 py-2.5 text-right whitespace-nowrap">
                    {j.status === "asking" ? <Button sm kind="p" onClick={() => pick(j.id)}>ดูแผน</Button>
                      : <span className="text-xs text-muted">{j.status === "ready" ? "รอคิว" : "รอวางแผน"}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------ the plan panel
function ModelBox({ j, editable, say }: { j: JobRow; editable: boolean; say: Say }) {
  const [budget, setBudget] = useState<string | null>(null); // thousands, while you type a budget of your own
  const i = EFFORTS.indexOf(j.effort);
  const set = (model: string, effort: string) =>
    api.setJobEffort(j.id, model, effort).then(() => say(`ปรับเป็น ${cap(model)} · ${effort} แล้ว · งบ ${kTokens(j.efforts[effort])}`), (e) => say((e as Error).message));
  const lower = EFFORTS[i - 1], higher = EFFORTS[i + 1];
  return (
    <div className="rounded-card bg-panel-2 p-3.5 flex flex-col gap-2.5 text-sm">
      <div className="flex items-center"><span className="grow">โมเดล</span>
        <select value={j.model} disabled={!editable} onChange={(e) => set(e.target.value, j.effort)}
          className="h-8 rounded-s border border-line-2 bg-panel px-2 text-[13px] disabled:opacity-70">
          {["sonnet", "opus"].map((m) => <option key={m} value={m}>{cap(m)}</option>)}
        </select>
      </div>
      <div className="flex items-center"><span className="grow">effort</span>
        <span className="inline-flex items-center rounded-full border border-line-2 bg-panel">
          <button type="button" aria-label="ลด effort" disabled={!editable || !lower} onClick={() => set(j.model, lower)} className="px-3 py-1 disabled:opacity-40 cursor-pointer">−</button>
          <span className="px-3 font-semibold border-x border-line">{j.effort}</span>
          <button type="button" aria-label="เพิ่ม effort" disabled={!editable || !higher} onClick={() => set(j.model, higher)} className="px-3 py-1 disabled:opacity-40 cursor-pointer">+</button>
        </span>
      </div>
      <div className="flex items-center gap-1.5"><span className="grow">งบโทเคน</span>
        {budget === null ? (
          <>
            <b className="font-mono">{kTokens(j.budget)}</b>
            {editable && <Button sm kind="ghost" icon="edit" title="ตั้งงบเอง (ค่าเริ่มคือค่าประมาณ × 1.2) เช่น ตั้งต่ำๆ เพื่อดูว่าเลขาหยุดเองเมื่อเกินงบ"
              onClick={() => setBudget(String(Math.round(j.budget / 1000)))}>แก้งบ</Button>}
          </>
        ) : (
          <>
            <input type="number" min={1} value={budget} onChange={(e) => setBudget(e.target.value)} autoFocus
              className="w-20 h-7 rounded-s border border-line-2 bg-panel px-1.5 text-right font-mono text-[13px]" />
            <span className="text-xs">k</span>
            <Button sm kind="p" onClick={() => api.setJobBudget(j.id, Math.round(Number(budget) * 1000))
              .then(() => { setBudget(null); say(`ตั้งงบ ${budget}k แล้ว · เกินแล้วหยุดเอง`); }, (e) => say((e as Error).message))}>ตั้ง</Button>
            <Button sm kind="ghost" onClick={() => setBudget(null)}>✕</Button>
          </>
        )}
      </div>
      <span className="text-xs text-muted">{[lower && `ลดเป็น ${lower} ≈ ${kTokens(j.efforts[lower])}`, higher && `เพิ่มเป็น ${higher} ≈ ${kTokens(j.efforts[higher])}`].filter(Boolean).join(" · ")}</span>
    </div>
  );
}

function Plan({ j, page, say, reload }: { j: JobRow | null; page: JobsPage; say: Say; reload: () => void }) {
  const [revising, setRevising] = useState(false);
  const [change, setChange] = useState("");
  const [busy, setBusy] = useState("");
  useEffect(() => { setRevising(false); setChange(""); }, [j?.id]);
  if (!j) return <Card title="แผน"><p className="text-sm text-muted">เลือกงานในคิวเพื่อดูแผน</p></Card>;
  const act = <T,>(what: string, p: Promise<T>, done: (r: T) => void) => {
    setBusy(what);
    p.then(done, (e) => say((e as Error).message)).finally(() => { setBusy(""); reload(); });
  };
  const head = j.status === "asking" ? "แผนที่รอคุณ" : j.status === "ready" ? "แผนที่พร้อมทำ" : "รอวางแผน";
  return (
    <Card className={j.status === "asking" ? "border-accent! border-2" : ""} title={`${head} · ${j.project}${j.title ? ` ${j.title}` : ""}`}>
      <div className="flex flex-col gap-3">
        {j.planned_at ? (
          <ol className="list-decimal pl-5 text-[13.5px] flex flex-col gap-0.5">{j.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
        ) : (
          <p className="text-[13.5px] text-ink-2">ค้างที่: {j.stuck_at || "—"}{j.note ? <><br />คุณสั่ง: {j.note}</> : null}<br />
            <span className="text-xs text-muted">Opus จะอ่านโปรเจค (อ่านอย่างเดียว) แล้ววางแผน เลือกโมเดลและ effort ประมาณงบ และบอกความเสี่ยง</span></p>
        )}
        {j.planned_at && (
          <div className={`flex items-start gap-2 rounded-s px-3 py-2.5 text-[13px] ${j.high_risk ? "bg-bad-soft text-bad" : j.rule_ok ? "bg-ok-soft text-ok" : "bg-warn-soft text-warn"}`}>
            <Icon name="shield" size={16} className="mt-0.5 shrink-0" />
            <span>{j.high_risk ? `เสี่ยงสูง: ${j.risks.join(" · ")} · ไม่ผ่านกฎ จึงถามคุณ` : j.rule_why}</span>
          </div>
        )}
        {j.planned_at && <ModelBox j={j} editable={j.status === "asking"} say={say} />}
        {j.planned_at && j.why && <span className="text-xs text-muted">คนวางแผน: {j.why} · วางแผนใช้ {kTokens(j.plan_tokens)} โทเคน</span>}
        {j.status === "asking" && <span className="text-xs text-muted">อนุมัติแล้วใช้ได้ {page.approval_days} วัน เฉพาะแผนนี้ · ทำบน branch แยก ไม่ push</span>}
        {revising && (
          <div className="flex flex-col gap-2">
            <textarea value={change} onChange={(e) => setChange(e.target.value)} rows={3} placeholder="อยากให้แก้ตรงไหน เช่น ไม่ต้องลงแพ็กเกจใหม่"
              className="rounded-s border border-line-2 bg-panel px-2.5 py-2 text-sm" />
            <div className="flex gap-2">
              <Button sm kind="p" disabled={!change.trim() || !!busy} onClick={() => act("revise", api.reviseJob(j.decision_id!, change),
                () => { setRevising(false); say("แก้แผนแล้ว"); })}>{busy === "revise" ? <Spinner label="Opus กำลังวางแผนใหม่…" /> : "ส่งให้แก้"}</Button>
              <Button sm kind="ghost" onClick={() => setRevising(false)}>ยกเลิก</Button>
            </div>
          </div>
        )}
        <div className="flex flex-wrap gap-1.5">
          {j.status === "asking" && !revising && <>
            <Button kind="ok" icon="check" disabled={!!busy} onClick={() => act("approve", api.answerJob(j.decision_id!, true),
              (r) => say(`อนุมัติแล้ว · ใช้ได้ ${page.approval_days} วัน`, r.action_id))}>อนุมัติ {page.approval_days} วัน</Button>
            <Button onClick={() => setRevising(true)}>แก้แผน</Button>
            <Button kind="ghost" disabled={!!busy} onClick={() => act("reject", api.answerJob(j.decision_id!, false),
              (r) => say("ไม่เอาแผนนี้ · ขั้นนี้จะไม่กลับมาเอง", r.action_id))}>ไม่เอา</Button>
          </>}
          {j.status === "ready" && <Button kind="ok" icon="send" disabled={!!busy || !!page.running} title={page.running ? "ทำทีละงาน" : ""}
            onClick={() => act("run", api.runJob(j.id), (r) => say(r.line))}>ทำเลย</Button>}
          {j.status === "queued" && <Button kind="p" disabled={!!busy} onClick={() => act("plan", api.planJob(j.id),
            (r) => say(r.go ? `วางแผนแล้ว · ${r.why}` : `วางแผนแล้ว · ต้องถามคุณ: ${r.why}`))}>
            {busy === "plan" ? <Spinner label="Opus กำลังวางแผน…" /> : "วางแผนเลย"}</Button>}
          {["queued", "ready"].includes(j.status) && <Button kind="ghost" disabled={!!busy}
            onClick={() => act("drop", api.dropJob(j.id), (r) => say("เอาออกจากคิวแล้ว", r.action_id))}>เอาออกจากคิว</Button>}
        </div>
        {j.status === "ready" && <span className="text-xs text-muted">{page.round_on ? `เลขาเริ่มเองในช่วง ${page.window}` : `รอบกลางคืน (${page.window}) ปิดอยู่ · กดทำเลย หรือเปิดรอบที่หน้าตั้งค่า`}</span>}
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------ what was done
const DONE_TONE = { done: ["ok", "ทำเสร็จ"], stopped: ["warn", "หยุด"], failed: ["bad", "ไม่สำเร็จ"] } as const;

function Recent({ rows, say }: { rows: JobRow[]; say: Say }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!rows.length) return null;
  return (
    <Card title={<span className="flex items-baseline gap-2">งานที่ทำแล้ว<span className="text-xs text-muted font-normal">งานอยู่บน branch ของมัน ดูและรวมเองได้</span></span>}>
      <ul className="divide-y divide-line">
        {rows.map((j) => {
          const [tone, word] = DONE_TONE[j.status as keyof typeof DONE_TONE] ?? ["muted", j.status];
          return (
            <li key={j.id} className="py-2.5 flex flex-col gap-1">
              <div className="flex flex-wrap items-center gap-2 cursor-pointer" onClick={() => setOpen(open === j.id ? null : j.id)}>
                <Chip tone={tone}>{word}</Chip>
                <span className="font-semibold text-[13.5px] grow min-w-0 truncate">{j.project} · {j.title || j.stuck_at}</span>
                <code className="text-xs text-ink-2">{j.branch}</code>
                <button type="button" title="คัดลอกชื่อ branch" className="text-muted hover:text-ink cursor-pointer"
                  onClick={(e) => { e.stopPropagation(); navigator.clipboard?.writeText(j.branch).then(() => say(`คัดลอก ${j.branch} แล้ว`)); }}>
                  <Icon name="notes" size={14} /></button>
                <span className="text-xs text-muted whitespace-nowrap">{kTokens(j.used)} / {kTokens(j.budget)} · {when(j.finished_at)}</span>
              </div>
              {open === j.id
                ? <div className="rounded-s bg-panel-2 px-3 py-2"><Markdown small text={j.result.split("\n").slice(1).join("\n").trim() || j.result} /></div>
                : <span className="text-xs text-ink-2 truncate">{j.result.split("\n")[0]} · <span className="text-accent-strong">กดดูรายละเอียด</span></span>}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

// ------------------------------------------------------------------ the page
export function Jobs() {
  const { refresh } = useStatus();
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState<JobsPage | null>(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<ToastMsg | null>(null);
  const [reading, setReading] = useState(false);
  const load = useCallback(() => { api.jobs().then(setPage, (e) => setError((e as Error).message)); }, []);
  useEffect(load, [load]);
  useEffect(() => { // while a job runs, its tokens fill up: look again every few seconds
    if (!page?.running) return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [page?.running, load]);
  const say: Say = (text, actionId = null) => { setToast({ text, actionId, key: Date.now() }); load(); refresh(); };
  const undo = async (id: number) => { await api.undo(id); setToast(null); load(); refresh(); };

  if (error) return <p className="text-sm text-bad">{error}</p>;
  if (!page) return <Spinner label="กำลังโหลด…" />;
  const wanted = Number(params.get("plan")) || null;
  const picked = page.queue.find((j) => j.id === wanted) ?? page.queue.find((j) => j.status === "asking") ?? page.queue[0] ?? null;
  const pick = (id: number) => setParams({ plan: String(id) }, { replace: true });
  return (
    <div className="grid gap-4 items-start lg:grid-cols-[minmax(0,3fr)_minmax(280px,1fr)]">
      <div className="flex flex-col gap-4 min-w-0">
        <div className="grid gap-4 md:grid-cols-2">
          <QuotaCard q={page.quota} usage={page.usage} reading={reading} say={say} onRead={() => {
            const before = page.quota.week_left;
            setReading(true);
            api.readQuota().then((r) => {
              const now = r.quota?.week_left;
              say(now === undefined ? "อ่านโควตาไม่ได้" : before === undefined || Math.round(now) === Math.round(before)
                ? `อ่านแล้ว · เหลือ ${Math.round(now)}% เท่าเดิม`
                : `อ่านแล้ว · เหลือ ${Math.round(now)}% (เดิม ${Math.round(before)}%)`);
            }, (e) => say((e as Error).message)).finally(() => setReading(false));
          }} />
          <div className="grid grid-cols-3 gap-3">
            <Kpi n={page.kpi.auto} label="ทำเองได้ตามกฎ" />
            <Kpi n={page.kpi.asking} label="รอคุณอนุมัติ" />
            <Kpi n={page.kpi.over_budget} label="หยุดเพราะเกินงบ" title="ใน 7 วันที่ผ่านมา" />
          </div>
        </div>
        <Running j={page.running} page={page} say={say} />
        <Queue page={page} picked={picked?.id ?? null} pick={pick} say={say} />
        <Recent rows={page.recent} say={say} />
      </div>
      <div className="lg:sticky lg:top-4 min-w-0"><Plan j={picked} page={page} say={say} reload={load} /></div>
      <Toast msg={toast} onUndo={undo} onClose={() => setToast(null)} />
    </div>
  );
}

