// The card for adding a กิจกรรม or a งาน, and for changing a งาน: Google Calendar's quick-create
// card with two tabs.
// - กิจกรรม: something at a fixed time (a meeting, a trip). It goes into your main Google
//   Calendar; the secretary reminds you of it and keeps work blocks away from it.
// - งาน: work with a due date that the secretary finds time for, as blocks in the "เลขา"
//   calendar. Its box at the bottom says in words what the secretary will do with what you
//   typed, so no field has to be guessed at.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type NewTask, type PlanMode, type Saved, type ScheduleRules, type TaskRow } from "../../api";
import { Button, Chip } from "../../components/ui";
import { duration, hm, shortDay, ymd } from "../../format";
import { Icon } from "../../icons";
import { Floating, type Anchor } from "./Floating";
import { findLinks, shortLink, sourceLabel } from "./links";
import { dueSpan } from "./Week";

export const field = "bg-panel border border-line-2 rounded-lg px-2.5 py-1.5 text-sm text-ink min-w-0";

export type Draft =
  // slot: opened from a click or drag on the calendar (its time is used), not from a button
  | { kind: "new"; tab: "event" | "task"; start: Date; end: Date; allDay: boolean; slot: boolean }
  | { kind: "edit"; task: TaskRow };

/** What happened, for the bar at the bottom of the page (saved: the action to undo). */
export type Done = { text: string; saved: Saved | null };

const MODES: { key: PlanMode; label: string; sub: string }[] = [
  { key: "early", label: "เริ่มเร็ว", sub: "จองช่องว่างแรก ๆ ตั้งแต่ตอนนี้ เสร็จก่อนกำหนด" },
  { key: "late", label: "ชิดเดดไลน์", sub: "จองช่องว่างที่ใกล้กำหนดส่งที่สุด" },
];
const TOTAL_CHIPS = [30, 60, 120, 240, 480, 720, 1200];
const DAY = 86_400_000;

function addDays(d: Date, n: number): Date {
  const out = new Date(d);
  out.setDate(out.getDate() + n);
  return out;
}

function at(date: string, time: string): Date {
  return new Date(`${date}T${time}`);
}

/** What the calendar shows while the card is open: Google Calendar's "(ไม่มีชื่อ)" draft. */
export type Ghost = { start: Date; end: Date; allDay: boolean; title: string; kind: "event" | "task"; sub?: string };

const toMin = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
const toTime = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
const QUARTERS = Array.from({ length: 96 }, (_, i) => toTime(i * 15));

/** A 24-hour time picked from quarter hours, like Google Calendar's (the browser's own time
 *  box follows the computer's language and may show "05:00 PM"). `from` lists only later times,
 *  each with how long it is after `from`: the end of an appointment. */
function TimeSelect({ value, onChange, label, from, disabled }: {
  value: string; onChange: (v: string) => void; label: string; from?: string; disabled?: boolean;
}) {
  const times = [...new Set([...QUARTERS, value])].sort().filter((t) => !from || t > from);
  return (
    <select aria-label={label} className={field} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
      {times.map((t) => <option key={t} value={t}>{from ? `${t} (${duration(toMin(t) - toMin(from))})` : t}</option>)}
    </select>
  );
}

/** The rules' defaults (กติกาตาราง), or the built-in ones while they load. */
function defaults(rules: ScheduleRules | null) {
  return {
    est: rules?.estimates.you ?? 60, block: rules?.rules.max_block ?? 120, daily: rules?.rules.per_task_per_day ?? 180,
    dayStart: rules?.rules.day_start ?? "09:00", dayEnd: rules?.rules.day_end ?? "22:00",
    horizon: rules?.rules.horizon_days ?? 14, gap: rules?.rules.gap ?? 15,
    reminders: ["1d", "1h"].filter((r) => (rules?.reminders ?? ["1d", "1h"]).includes(r)),
  };
}

/** Hours + minutes, typed freely (no ceiling but the backend's sanity limits). */
function Minutes({ value, onChange, label }: { value: number; onChange: (v: number) => void; label: string }) {
  const h = Math.floor(value / 60), m = value % 60;
  const steps = [0, 15, 30, 45].includes(m) ? [0, 15, 30, 45] : [0, 15, 30, 45, m].sort((a, b) => a - b);
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <input type="number" min={0} max={200} aria-label={`${label} ชั่วโมง`} className={`${field} w-16`} value={h}
        onChange={(e) => onChange(Math.max(0, Math.min(200, Number(e.target.value) || 0)) * 60 + m)} />ชม.
      <select aria-label={`${label} นาที`} className={field} value={m} onChange={(e) => onChange(h * 60 + Number(e.target.value))}>
        {steps.map((x) => <option key={x} value={x}>{x}</option>)}
      </select>นาที
    </span>
  );
}

function Row({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[96px_minmax(0,1fr)] gap-x-3 items-start">
      <span className="text-sm text-ink-2 pt-1.5 leading-tight">{label}{hint && <span className="block text-[11px] text-muted">{hint}</span>}</span>
      <div className="flex flex-col gap-1.5 min-w-0">{children}</div>
    </div>
  );
}

/** What the planner will do with this task, in words, plus what may go wrong. */
function PlanWords({ est, block, daily, due, mode, d }: {
  est: number; block: number; daily: number; due: Date | null; mode: PlanMode; d: ReturnType<typeof defaults>;
}) {
  const now = new Date();
  const days = Math.ceil(est / daily);
  const warn: string[] = [];
  if (due && due <= now) warn.push("กำหนดส่งผ่านไปแล้ว: เลขาจะไม่จองเวลาให้");
  else if (due) {
    const start = at(ymd(now), "00:00").getTime();
    const left = Math.round((at(ymd(due), "00:00").getTime() - start) / DAY) + (hm(due) > d.dayStart ? 1 : 0);
    if (days > left) warn.push(`อาจไม่ทัน: วันละไม่เกิน ${duration(daily)} ต้องใช้อย่างน้อย ${days} วัน แต่เหลือ ${left} วันก่อนส่ง`);
  }
  if (block > daily) warn.push("บล็อกยาวกว่าเวลาต่อวัน: บล็อกจะยาวได้แค่เวลาต่อวัน");
  return (
    <div className="rounded-s bg-panel-2 px-3 py-2.5 text-[13px] text-ink-2 flex gap-2">
      <Icon name="sparkle" size={16} className="text-accent-strong shrink-0 mt-0.5" />
      <div className="flex flex-col gap-1">
        <span>เลขาจะหาเวลาว่างรวม <b>{duration(est)}</b> {due ? <>ก่อน <b>{shortDay(due)} {hm(due)}</b></> : `ภายใน ${d.horizon} วันข้างหน้า`}
          {mode === "early" ? " เริ่มจากช่องว่างแรกตั้งแต่ตอนนี้" : " ไล่จากกำหนดส่งย้อนขึ้นมา"}</span>
        <span>ตัดเป็นบล็อกละไม่เกิน <b>{duration(Math.min(block, daily))}</b> (ประมาณ {Math.ceil(est / Math.min(block, daily))} บล็อก)
          · วันละไม่เกิน <b>{duration(daily)}</b>{days > 1 ? ` (อย่างน้อย ${days} วัน)` : ""}</span>
        <span className="text-muted">ลงปฏิทิน “เลขา” ช่วง {d.dayStart}–{d.dayEnd} หลบนัดที่มีอยู่{d.gap ? ` · พัก ${d.gap} นาทีระหว่างบล็อก` : ""}
          {" "}· ย้ายบล็อกเองใน Google Calendar ได้</span>
        {warn.map((w) => <span key={w} className="text-warn">{w}</span>)}
      </div>
    </div>
  );
}

export function EditCard({ draft, anchor, rules, onClose, onDone, onPreview }: {
  draft: Draft; anchor: Anchor; rules: ScheduleRules | null; onClose: () => void; onDone: (d: Done) => void;
  onPreview?: (g: Ghost | null) => void;
}) {
  const d = defaults(rules);
  const editing = draft.kind === "edit" ? draft.task : null;
  const fresh = draft.kind === "new" ? draft : null;
  const [tab, setTab] = useState<"event" | "task">(fresh?.tab ?? "task");
  const [title, setTitle] = useState(editing?.title ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // กิจกรรม: a click gives one slot (half an hour); like Google Calendar, make it an hour.
  const s0 = fresh?.start ?? new Date();
  let e0 = fresh?.end ?? new Date();
  if (fresh && !fresh.allDay && e0.getTime() - s0.getTime() <= 30 * 60_000) e0 = new Date(s0.getTime() + 60 * 60_000);
  const lastDay = fresh?.allDay ? addDays(e0, -1) : s0; // an all-day selection ends at the next midnight
  const [allDay, setAllDay] = useState(fresh?.allDay ?? false);
  const [date, setDate] = useState(ymd(s0));
  const [endDate, setEndDate] = useState(ymd(lastDay));
  const [startTime, setStartTime] = useState(fresh?.allDay ? "09:00" : hm(s0));
  const [endTime, setEndTime] = useState(fresh?.allDay ? "10:00" : hm(e0));
  const [location, setLocation] = useState("");
  const [note, setNote] = useState("");

  // งาน: the clicked time is the due time (as with Google Calendar's tasks); from a button, tomorrow 17:00.
  const due0 = editing ? (editing.due ? new Date(editing.due) : null)
    : fresh?.slot ? (fresh.allDay ? at(ymd(lastDay), "23:59") : s0) : at(ymd(addDays(new Date(), 1)), "17:00");
  const estDefault = editing ? editing.est_default : d.est;
  const initial = useMemo(() => ({
    noDue: due0 === null, dueDate: ymd(due0 ?? addDays(new Date(), 1)), dueTime: due0 ? hm(due0) : "17:00",
    est: editing?.est_minutes ?? estDefault, block: editing?.block_minutes ?? d.block, daily: editing?.daily_minutes ?? d.daily,
    mode: editing?.plan_mode ?? ("early" as PlanMode), details: editing?.details ?? "",
  }), []); // eslint-disable-line react-hooks/exhaustive-deps -- the values the card opened with
  const [noDue, setNoDue] = useState(initial.noDue);
  const [dueDate, setDueDate] = useState(initial.dueDate);
  const [dueTime, setDueTime] = useState(initial.dueTime);
  const [est, setEst] = useState(initial.est);
  const [block, setBlock] = useState(initial.block);
  const [daily, setDaily] = useState(initial.daily);
  const [mode, setMode] = useState<PlanMode>(initial.mode);
  const [details, setDetails] = useState(initial.details);
  const links = findLinks(details);

  const due = noDue ? null : at(dueDate, dueTime || "23:59");

  // Moving the start keeps the length, as in Google Calendar (capped at the end of the day).
  const moveStart = (t: string) => {
    const length = Math.max(15, toMin(endTime) - toMin(startTime));
    setStartTime(t);
    setEndTime(toTime(Math.min(toMin(t) + length, 23 * 60 + 59)));
  };

  // The draft on the calendar follows the card while you type (new things only).
  useEffect(() => {
    if (!onPreview || editing) return;
    let g: Ghost | null = null;
    if (tab === "event") {
      const s = allDay ? at(date, "00:00") : at(date, startTime);
      const e = allDay ? addDays(at(endDate, "00:00"), 1) : at(date, endTime);
      if (!isNaN(s.getTime()) && e > s) g = { start: s, end: e, allDay, title: title.trim() || "(ไม่มีชื่อ)", kind: "event",
                                              sub: allDay ? "ทั้งวัน" : `${startTime}–${endTime}` };
    } else if (!noDue && !isNaN(at(dueDate, dueTime || "23:59").getTime())) {
      // drawn where the due date will be (Week.dueSpan)
      const [start, end] = dueSpan(at(dueDate, dueTime || "23:59"));
      g = { start, end, allDay: false, title: title.trim() || "(ไม่มีชื่อ)", kind: "task", sub: `เดดไลน์ ${dueTime || "23:59"}` };
    }
    onPreview(g);
  }, [onPreview, editing, tab, allDay, date, endDate, startTime, endTime, title, noDue, dueDate, dueTime]);
  useEffect(() => () => onPreview?.(null), [onPreview]);
  const eventProblem = !allDay && date && startTime && endTime && endTime <= startTime ? "เวลาจบต้องหลังเวลาเริ่ม"
    : allDay && endDate < date ? "วันสุดท้ายต้องไม่ก่อนวันแรก" : "";
  const taskProblem = est < 15 ? "เวลาทำรวมอย่างน้อย 15 นาที" : block < 15 ? "บล็อกอย่างน้อย 15 นาที"
    : daily < 15 ? "เวลาต่อวันอย่างน้อย 15 นาที" : "";
  const problem = tab === "event" ? eventProblem : taskProblem;

  // A value equal to the default is sent as null ("use the default"), so changing the rules
  // later still moves tasks you never set by hand.
  const fieldsOf = (v: typeof initial): NewTask => ({
    title: title.trim(), due: v.noDue ? null : `${v.dueDate}T${v.dueTime || "23:59"}`, plan_mode: v.noDue ? "early" : v.mode,
    est_minutes: v.est === estDefault ? null : v.est, block_minutes: v.block === d.block ? null : v.block,
    daily_minutes: v.daily === d.daily ? null : v.daily, details: v.details.trim(),
  });

  const save = async () => {
    if (!title.trim() || problem || busy) return;
    setBusy(true); setError("");
    try {
      if (tab === "event") {
        const r = await api.addEvent({ title: title.trim(), all_day: allDay, location, description: note,
          start: allDay ? date : `${date}T${startTime}`, end: allDay ? endDate : `${date}T${endTime}` });
        onDone({ text: `ลงปฏิทินแล้ว: ${title.trim()}`, saved: r });
      } else {
        const now = fieldsOf({ noDue, dueDate, dueTime, est, block, daily, mode, details });
        if (!editing) {
          const r = await api.addTask(now);
          onDone({ text: `เพิ่มงานแล้ว: ${now.title}` + (r.plan ? ` · ${r.plan}` : ""), saved: r });
        } else {
          const was = { ...fieldsOf(initial), title: editing.title };
          const change = Object.fromEntries(Object.entries(now).filter(([k, v]) => was[k as keyof NewTask] !== v)) as Partial<NewTask>;
          if (!Object.keys(change).length) { onClose(); return; }
          const r = await api.editTask(editing.id, change);
          onDone({ text: `แก้งานแล้ว: ${now.title}` + (r.plan ? ` · ${r.plan}` : ""), saved: r });
        }
      }
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  const finish = async () => {
    if (!editing) return;
    setBusy(true); setError("");
    try { onDone({ text: `ทำเสร็จแล้ว: ${editing.title}`, saved: await api.taskDone(editing.id) }); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  const tabs = (
    <div className="flex gap-1.5">
      {([["event", "กิจกรรม"], ["task", "งาน"]] as const).map(([k, label]) => (
        <button key={k} type="button" onClick={() => setTab(k)}
          className={`px-3.5 py-1 rounded-full text-sm cursor-pointer ${tab === k ? "bg-accent-soft text-accent-strong font-semibold" : "text-ink-2 hover:bg-panel-2"}`}>{label}</button>
      ))}
    </div>
  );

  return (
    <Floating anchor={anchor} onClose={onClose} width={480}>
      <form className="p-4 pt-3 flex flex-col gap-3.5" onSubmit={(e) => { e.preventDefault(); save(); }}>
        <div className="flex items-center gap-2">
          <span className="grow text-xs text-muted">{editing ? "แก้งาน" : tab === "event" ? "กิจกรรมใหม่ · ลงปฏิทินหลัก" : "งานใหม่ · เลขาหาเวลาให้"}</span>
          {editing && editing.source !== "คุณเพิ่ม" && <Chip>จาก {editing.source}</Chip>}
          <button type="button" aria-label="ปิด" onClick={onClose} className="text-muted hover:text-ink cursor-pointer p-1"><Icon name="x" size={16} /></button>
        </div>
        <input autoFocus={!editing} value={title} onChange={(e) => setTitle(e.target.value)}
          placeholder={tab === "event" ? "เพิ่มชื่อ เช่น ประชุมกับอาจารย์" : "เพิ่มชื่องาน เช่น เขียนรายงาน datacom"}
          className="bg-transparent border-0 border-b-2 border-line-2 focus:border-accent outline-none text-lg px-0.5 py-1 text-ink placeholder:text-muted" />
        {!editing && tabs}

        {tab === "event" ? (
          <div className="flex flex-col gap-2.5">
            <div className="flex gap-2.5 items-start">
              <Icon name="clock" size={18} className="text-muted mt-2 shrink-0" />
              <div className="flex flex-col gap-1.5 min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <input type="date" aria-label="วันที่" className={field} value={date} onChange={(e) => { setDate(e.target.value); if (e.target.value > endDate) setEndDate(e.target.value); }} />
                  {allDay && <>ถึง<input type="date" aria-label="วันสุดท้าย" className={field} value={endDate} onChange={(e) => setEndDate(e.target.value)} /></>}
                </div>
                {!allDay && (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <TimeSelect label="เวลาเริ่ม" value={startTime} onChange={moveStart} />–
                    <TimeSelect label="เวลาจบ" value={endTime} onChange={setEndTime} from={startTime} />
                  </div>
                )}
                <label className="inline-flex items-center gap-1.5 text-sm text-ink-2 w-fit cursor-pointer">
                  <input type="checkbox" checked={allDay} onChange={(e) => setAllDay(e.target.checked)} />ทั้งวัน</label>
              </div>
            </div>
            <div className="flex gap-2.5 items-center">
              <Icon name="pin" size={18} className="text-muted shrink-0" />
              <input className={`${field} grow`} value={location} onChange={(e) => setLocation(e.target.value)} placeholder="เพิ่มสถานที่" />
            </div>
            <div className="flex gap-2.5 items-start">
              <Icon name="notes" size={18} className="text-muted mt-2 shrink-0" />
              <textarea rows={2} className={`${field} grow resize-y`} value={note} onChange={(e) => setNote(e.target.value)} placeholder="เพิ่มรายละเอียด" />
            </div>
            <p className="text-xs text-muted">ลงปฏิทินหลักใน Google Calendar
              {d.reminders.length > 0 && ` · เลขาเตือนใน #ด่วน ก่อน ${d.reminders.map((r) => (r === "1d" ? "1 วัน" : "1 ชั่วโมง")).join(" และ ")}`}
              {" "}· บล็อกงานจะหลบช่วงนี้</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <Row label="กำหนดส่ง">
              <div className="flex flex-wrap items-center gap-1.5">
                <input type="date" aria-label="วันส่ง" disabled={noDue} className={field} value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
                <TimeSelect label="เวลาส่ง" disabled={noDue} value={dueTime} onChange={setDueTime} />
              </div>
              <label className="inline-flex items-center gap-1.5 text-sm text-ink-2 w-fit cursor-pointer">
                <input type="checkbox" checked={noDue} onChange={(e) => setNoDue(e.target.checked)} />ไม่มีกำหนดส่ง</label>
            </Row>
            <Row label="รายละเอียด" hint="ทำอะไร ที่ไหน ส่งที่ไหน">
              <textarea rows={3} aria-label="รายละเอียดงาน" className={`${field} resize-y`} value={details} onChange={(e) => setDetails(e.target.value)}
                placeholder={"เช่น ทำแบบฝึกหัดข้อ 1–5 ส่งเป็น PDF\nส่งที่: วางลิงก์ได้เลย"} />
              {links.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {links.map((u) => (
                    <a key={u} href={u} target="_blank" rel="noopener" title={u}
                      className="inline-flex items-center gap-1 max-w-full text-xs rounded-full border border-line px-2 py-0.5 text-accent-strong hover:bg-panel-2">
                      <Icon name="ext" size={12} /><span className="truncate">{shortLink(u)}</span></a>
                  ))}
                </div>
              )}
            </Row>
            <Row label="ใช้เวลาทำรวม" hint="ทั้งงาน ไม่ใช่ต่อวัน">
              <Minutes label="เวลาทำรวม" value={est} onChange={setEst} />
              <div className="flex flex-wrap gap-1">
                {TOTAL_CHIPS.map((m) => (
                  <button key={m} type="button" onClick={() => setEst(m)}
                    className={`text-xs rounded-full border px-2 py-0.5 cursor-pointer ${est === m ? "border-accent bg-accent-soft text-accent-strong" : "border-line text-ink-2 hover:bg-panel-2"}`}>{duration(m)}</button>
                ))}
              </div>
            </Row>
            <Row label="บล็อกละ" hint="ยาวสุดต่อครั้ง">
              <Minutes label="ความยาวบล็อก" value={block} onChange={setBlock} />
            </Row>
            <Row label="วันละไม่เกิน" hint="รวมทุกบล็อกในวัน">
              <Minutes label="เวลาต่อวัน" value={daily} onChange={setDaily} />
            </Row>
            <Row label="จองเวลา">
              <div className="grid grid-cols-2 gap-1.5">
                {MODES.map((m) => {
                  const off = m.key === "late" && noDue;
                  const on = (noDue ? "early" : mode) === m.key;
                  return (
                    <button key={m.key} type="button" disabled={off} onClick={() => setMode(m.key)}
                      title={off ? "ชิดเดดไลน์ใช้ได้เมื่อมีกำหนดส่ง" : undefined}
                      className={`text-left rounded-s border px-2.5 py-1.5 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed
                        ${on ? "border-accent bg-accent-soft/60" : "border-line hover:bg-panel-2"}`}>
                      <span className="block text-sm font-medium">{m.label}</span>
                      <span className="block text-[11px] text-muted leading-snug">{m.sub}</span>
                    </button>
                  );
                })}
              </div>
            </Row>
            <PlanWords est={est} block={block} daily={daily} due={due} mode={noDue ? "early" : mode} d={d} />
            <p className="text-[11px] text-muted -mt-1.5">ค่าที่ตรงกับกติกาตาราง ({duration(d.block)} ต่อบล็อก, {duration(d.daily)} ต่อวัน) จะเปลี่ยนตามเมื่อคุณแก้กติกา</p>
          </div>
        )}

        {(error || (problem && title.trim())) && <p className="text-sm text-bad">{error || problem}</p>}
        {/* kept in view at the bottom when the card scrolls (a phone) */}
        <div className="flex items-center gap-2 pt-2 pb-1 -mb-1 sticky bottom-0 bg-panel">
          {editing && <Button sm icon="check" disabled={busy} onClick={finish}>ทำเสร็จแล้ว</Button>}
          {editing?.link && <a href={editing.link} target="_blank" rel="noopener" className="text-xs text-ink-2 hover:underline inline-flex items-center gap-1">
            <Icon name="ext" size={13} />{sourceLabel(editing.source)}</a>}
          <span className="grow" />
          <Button kind="ghost" onClick={onClose}>ยกเลิก</Button>
          <Button kind="p" type="submit" disabled={busy || !title.trim() || !!problem}>{busy ? "กำลังบันทึก…" : "บันทึก"}</Button>
        </div>
      </form>
    </Floating>
  );
}
