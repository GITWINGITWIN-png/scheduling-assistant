// W5 ตาราง (B3): the week as the secretary sees it (appointments, work blocks, due dates), the task
// list the planner works from, appointments waiting for you, Classroom courses, and the planner's rules.
// The calendar is FullCalendar (v6); its colours follow the theme through the .fc rules in index.css.
import dayGridPlugin from "@fullcalendar/daygrid";
import type { EventClickArg, EventInput, EventSourceFuncArg } from "@fullcalendar/core";
import thLocale from "@fullcalendar/core/locales/th";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type CourseRow, type Decision, type PlanMode, type ScheduleRules, type TaskRow } from "../api";
import { AppointmentActions, CourseActions } from "../components/Bell";
import { Banner, Button, Card, Chip, Phase, Seg, Spinner } from "../components/ui";
import { when } from "../format";
import { useStatus } from "../status";

const MODES: { key: PlanMode; label: string }[] = [{ key: "early", label: "เริ่มเร็ว" }, { key: "late", label: "ชิดเดดไลน์" }];
const input = "bg-panel border border-line-2 rounded-lg px-2.5 py-1.5 text-sm text-ink min-w-0";

function hours(min: number): string {
  if (min < 60) return `${min} นาที`;
  const h = Math.floor(min / 60), m = min % 60;
  return m ? `${h} ชม. ${m} นาที` : `${h} ชม.`;
}

/** "2026-11-10T17:00" for a datetime-local input, from an ISO time. */
function localInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ------------------------------------------------------------------ the week
function Week({ reloadKey, onPlanned }: { reloadKey: number; onPlanned: () => void }) {
  const cal = useRef<FullCalendar>(null);
  const [plan, setPlan] = useState<{ planned_at: string | null; short: { title: string; minutes: number }[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const events = useCallback((info: EventSourceFuncArg, ok: (e: EventInput[]) => void, fail: (e: Error) => void) => {
    api.week(info.startStr, info.endStr).then((w) => {
      setPlan(w.plan);
      ok([
        ...w.events.map((e) => ({
          id: `e${e.id}`, title: e.title + (e.location ? ` · ${e.location}` : ""), start: e.start, end: e.end, allDay: e.all_day,
          classNames: ["ev-meet", e.recurring ? "ev-recurring" : "", e.source === "email" ? "ev-email" : ""],
          extendedProps: { link: e.link },
        })),
        ...w.blocks.map((b) => ({
          id: `b${b.id}`, title: b.title + (b.pinned ? " · คุณย้ายมา" : ""), start: b.start, end: b.end,
          classNames: ["ev-block", b.pinned ? "ev-pinned" : "", b.past ? "ev-done" : ""],
        })),
        ...w.deadlines.map((d) => ({
          id: `d${d.task_id}`, title: `ส่ง ${new Date(d.due).toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit" })} · ${d.title}`,
          start: d.due.slice(0, 10), allDay: true, classNames: ["ev-dead"], extendedProps: { link: d.link },
        })),
      ]);
    }, fail);
  }, []);

  useEffect(() => { cal.current?.getApi().refetchEvents(); }, [reloadKey]);

  const open = (arg: EventClickArg) => {
    const link = arg.event.extendedProps.link as string | undefined;
    if (link) window.open(link, "_blank", "noopener");
  };
  const replan = async () => {
    setBusy(true); setNote("");
    try { setNote((await api.replan()).line); onPlanned(); } catch (e) { setNote((e as Error).message); } finally { setBusy(false); }
  };

  return (
    <Card title="สัปดาห์นี้" right={<div className="flex items-center gap-2">
      {plan?.planned_at && <span className="text-xs text-muted">วางล่าสุด {when(plan.planned_at)}</span>}
      <Button sm icon="refresh" disabled={busy} onClick={replan}>{busy ? "กำลังวาง…" : "วางตารางใหม่"}</Button>
    </div>}>
      <div className="flex flex-col gap-3">
        {note && <p className="text-sm text-ink-2">{note}</p>}
        {!!plan?.short.length && (
          <Banner icon="clock">
            <b>เวลาไม่พอก่อนกำหนดส่ง:</b> {plan.short.map((s) => `${s.title} ขาด ${hours(s.minutes)}`).join(" · ")}
            <span className="text-muted"> · ลองลดเวลาที่ใช้ เปลี่ยนเวลาทำงานในกติกา หรือย้ายนัดออก</span>
          </Banner>
        )}
        <div className="schedule-cal">
          <FullCalendar ref={cal} plugins={[timeGridPlugin, dayGridPlugin]} locale={thLocale} initialView="timeGridWeek" firstDay={1}
            headerToolbar={{ left: "prev,next today", center: "title", right: "timeGridDay,timeGridWeek,dayGridMonth" }}
            buttonText={{ today: "วันนี้", day: "วัน", week: "สัปดาห์", month: "เดือน" }}
            slotMinTime="07:00:00" slotMaxTime="24:00:00" scrollTime="08:00:00" nowIndicator height={720} expandRows
            allDayText="ทั้งวัน" slotLabelFormat={{ hour: "2-digit", minute: "2-digit", hour12: false }}
            eventTimeFormat={{ hour: "2-digit", minute: "2-digit", hour12: false }}
            events={events} eventClick={open} />
        </div>
        <div className="flex flex-wrap gap-3 text-xs text-muted">
          {[["ev-meet", "นัด"], ["ev-dead", "เดดไลน์"], ["ev-block", "บล็อกงาน (ปฏิทิน “เลขา”)"], ["ev-block ev-pinned", "บล็อกที่คุณย้าย"], ["ev-meet ev-recurring", "นัดซ้ำทุกสัปดาห์ (ไม่เตือน)"]].map(([c, label]) => (
            <span key={label} className="inline-flex items-center gap-1.5"><i className={`legend ${c}`} />{label}</span>
          ))}
        </div>
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------ tasks
function AddTask({ onAdded }: { onAdded: (plan: string | null) => void }) {
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [est, setEst] = useState(0);
  const [mode, setMode] = useState<PlanMode>("early");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const add = async () => {
    setBusy(true); setError("");
    try {
      const r = await api.addTask({ title, due: due || null, est_minutes: est || null, plan_mode: mode });
      setTitle(""); setDue(""); setEst(0); setMode("early"); onAdded(r.plan);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="flex flex-col gap-2 pb-3 border-b border-line">
      <input className={input} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="เพิ่มงาน เช่น เขียนรายงาน datacom" />
      <div className="flex flex-wrap gap-2 items-center">
        <input type="datetime-local" className={input} value={due} onChange={(e) => setDue(e.target.value)} title="กำหนดส่ง (ไม่ใส่ก็ได้)" />
        <select className={input} value={est} onChange={(e) => setEst(Number(e.target.value))} title="เวลาที่ต้องใช้">
          <option value={0}>เวลาตามค่าเริ่มต้น</option>
          {[30, 60, 90, 120, 180, 240, 360, 480].map((m) => <option key={m} value={m}>{hours(m)}</option>)}
        </select>
        <Seg options={MODES} value={mode} onChange={setMode} />
        <Button kind="p" sm icon="plus" disabled={busy || !title.trim()} onClick={add}>เพิ่ม</Button>
      </div>
      {error && <p className="text-xs text-bad">{error}</p>}
    </div>
  );
}

function TaskLine({ t, onChange }: { t: TaskRow; onChange: (plan?: string | null) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = async (fn: () => Promise<{ plan?: string | null }>) => {
    setBusy(true); setError("");
    try { onChange((await fn()).plan); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const need = t.est_minutes ?? t.est_default;
  const closed = t.status !== "open";
  return (
    <li className={`py-2.5 flex flex-col gap-1.5 ${closed ? "opacity-55" : ""}`}>
      <div className="flex items-start gap-2">
        <span className="grow min-w-0">
          {t.link ? <a href={t.link} target="_blank" rel="noopener" className="font-medium hover:underline">{t.title}</a> : <span className="font-medium">{t.title}</span>}
          <span className="block text-xs text-muted">
            {[t.due ? `ส่ง ${when(t.due)}` : "ไม่มีกำหนดส่ง", t.source, closed ? (t.status === "done" ? "เสร็จแล้ว" : "เอาออกแล้ว")
              : `วางแล้ว ${hours(t.done_minutes + t.booked_minutes)} จาก ${hours(need)}`].join(" · ")}
          </span>
        </span>
        {!closed && <Button sm icon="check" disabled={busy} onClick={() => run(() => api.taskDone(t.id))}>เสร็จ</Button>}
      </div>
      {!closed && (
        <div className="flex flex-wrap gap-2 items-center">
          <select className={`${input} text-xs py-1`} value={t.est_minutes ?? 0} disabled={busy}
            onChange={(e) => run(() => api.editTask(t.id, Number(e.target.value) ? { est_minutes: Number(e.target.value) } : { clear_est: true }))}>
            <option value={0}>ใช้เวลา {hours(t.est_default)} (ค่าเริ่มต้น)</option>
            {[30, 60, 90, 120, 180, 240, 360, 480].map((m) => <option key={m} value={m}>ใช้เวลา {hours(m)}</option>)}
          </select>
          <Seg options={MODES} value={t.plan_mode} onChange={(m) => run(() => api.editTask(t.id, { plan_mode: m }))} />
          {t.due && <input type="datetime-local" className={`${input} text-xs py-1`} defaultValue={localInput(t.due)} disabled={busy}
            onBlur={(e) => e.target.value && e.target.value !== localInput(t.due) && run(() => api.editTask(t.id, { due: e.target.value }))} />}
        </div>
      )}
      {error && <p className="text-xs text-bad">{error}</p>}
    </li>
  );
}

function Tasks({ reloadKey, changed }: { reloadKey: number; changed: (plan?: string | null) => void }) {
  const [items, setItems] = useState<TaskRow[] | null>(null);
  const [note, setNote] = useState("");
  useEffect(() => { api.tasks().then((r) => setItems(r.items), () => setItems([])); }, [reloadKey]);
  const after = (plan?: string | null) => { setNote(plan ? `วางตารางแล้ว: ${plan}` : ""); changed(plan); };
  const open = items?.filter((t) => t.status === "open") ?? [];
  return (
    <Card title={`งาน · ${open.length}`} right={<span className="text-xs text-muted">ตัววางตารางจองเวลาให้จากรายการนี้</span>}>
      <AddTask onAdded={after} />
      {note && <p className="text-xs text-ok pt-2">{note}</p>}
      {items === null ? <Spinner /> : (
        <ul className="divide-y divide-line">
          {items.length === 0 && <li className="py-3 text-sm text-muted">ยังไม่มีงาน · งานจากอีเมลและ Classroom จะขึ้นที่นี่เอง</li>}
          {items.map((t) => <TaskLine key={t.id} t={t} onChange={after} />)}
        </ul>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------ waiting for you
function Pending({ reloadKey }: { reloadKey: number }) {
  const [items, setItems] = useState<Decision[] | null>(null);
  useEffect(() => { api.decisions().then((r) => setItems(r.items.filter((d) => d.kind === "appointment")), () => setItems([])); }, [reloadKey]);
  if (!items?.length) return null;
  return (
    <Card title="นัดที่รอคุณรับ">
      <ul className="divide-y divide-line">
        {items.map((d) => (
          <li key={d.id} className="py-2.5 flex flex-col gap-1.5">
            <span><span className="font-medium">{d.title}</span>
              <span className="block text-xs text-muted">{[d.when, d.from && `จาก ${d.from}`].filter(Boolean).join(" · ")}</span></span>
            <AppointmentActions decisionId={d.id} />
          </li>
        ))}
      </ul>
    </Card>
  );
}

// ------------------------------------------------------------------ Classroom
function Courses({ reloadKey }: { reloadKey: number }) {
  const [items, setItems] = useState<CourseRow[] | null>(null);
  const [showOld, setShowOld] = useState(false);
  useEffect(() => { api.courses().then((r) => setItems(r.items), () => setItems([])); }, [reloadKey]);
  if (items === null) return null;
  const active = items.filter((c) => c.state === "asking" || c.state === "followed");
  const old = items.filter((c) => c.state === "ended" || c.state === "ignored");
  return (
    <Card title="วิชาใน Classroom" right={<span className="text-xs text-muted">ดึงทุก 2 ชั่วโมง</span>}>
      {items.length === 0 && <p className="text-sm text-muted">ยังไม่ได้ซิงก์ · เปิดรอบ “ดึงงานและสื่อจาก Classroom” ในหน้าตั้งค่า</p>}
      {items.length > 0 && active.length === 0 && <p className="text-sm text-muted">ยังไม่มีวิชาที่ติดตาม · วิชาใหม่หรือวิชาที่มีงานใหม่ เลขาจะถามใน #อนุมัติ</p>}
      <ul className="divide-y divide-line">
        {active.map((c) => (
          <li key={c.id} className="py-2.5 flex flex-col gap-1.5">
            <div className="flex items-center gap-2">
              <a href={c.link} target="_blank" rel="noopener" className="font-medium grow hover:underline">{c.name}</a>
              <Chip tone={c.state === "followed" ? "ok" : "warn"}>{c.state_name}</Chip>
            </div>
            {c.state === "asking" && c.decision_id ? <CourseActions decisionId={c.decision_id} folder={c.folder} exists={false} /> : (
              <span className="text-xs text-muted font-mono break-all">{c.folder} · {c.file_count} ไฟล์
                {c.files.length > 0 && <span className="block font-sans">ล่าสุด: {c.files.map((f) => f.name).join(", ")}</span>}</span>
            )}
          </li>
        ))}
      </ul>
      {old.length > 0 && (
        <button type="button" className="text-xs text-muted pt-2 cursor-pointer hover:text-ink" onClick={() => setShowOld((v) => !v)}>
          {showOld ? "ซ่อน" : `วิชาที่จบแล้วหรือไม่ติดตาม ${old.length} วิชา`}
        </button>
      )}
      {showOld && <ul className="text-xs text-muted pt-1">{old.map((c) => <li key={c.id}>{c.name} · {c.state_name}</li>)}</ul>}
    </Card>
  );
}

// ------------------------------------------------------------------ rules
function Rules({ onSaved }: { onSaved: () => void }) {
  const [r, setR] = useState<ScheduleRules | null>(null);
  const [open, setOpen] = useState(false);
  const [msg, setMsg] = useState("");
  useEffect(() => { if (open) api.rules().then(setR, () => setR(null)); }, [open]);
  const set = (k: keyof ScheduleRules["rules"], v: string | number) => r && setR({ ...r, rules: { ...r.rules, [k]: v } });
  const save = async () => {
    if (!r) return;
    setMsg("");
    try {
      await api.saveRules({ day_start: r.rules.day_start, day_end: r.rules.day_end, max_block: r.rules.max_block,
        per_task_per_day: r.rules.per_task_per_day, gap: r.rules.gap, estimates: r.estimates, reminders: r.reminders });
      setMsg("บันทึกแล้ว · ตารางจะวางตามกติกาใหม่ในรอบถัดไป · ย้อนกลับได้ในหน้าสิ่งที่เลขาทำ"); onSaved();
    } catch (e) { setMsg((e as Error).message); }
  };
  const num = (k: "max_block" | "per_task_per_day" | "gap", opts: number[]) => (
    <select className={input} value={r?.rules[k]} onChange={(e) => set(k, Number(e.target.value))}>
      {opts.map((m) => <option key={m} value={m}>{m === 0 ? "ไม่เว้น" : hours(m)}</option>)}
    </select>
  );
  return (
    <Card title="กติกาตาราง" right={<Button sm kind="ghost" onClick={() => setOpen((o) => !o)}>{open ? "ซ่อน" : "ดูและแก้"}</Button>}>
      {!open && <p className="text-xs text-muted">วางเฉพาะช่วงเวลาทำงาน เว้นระยะจากนัด จำกัดเวลาต่องานต่อวัน และเตือนก่อน 1 วันกับ 1 ชั่วโมง</p>}
      {open && !r && <Spinner />}
      {open && r && (
        <div className="flex flex-col gap-2.5 text-sm">
          <label className="flex items-center gap-2">วางบล็อกช่วง
            <input type="time" className={input} value={r.rules.day_start} onChange={(e) => set("day_start", e.target.value)} />–
            <input type="time" className={input} value={r.rules.day_end} onChange={(e) => set("day_end", e.target.value)} /></label>
          <label className="flex items-center gap-2">บล็อกยาวไม่เกิน {num("max_block", [60, 90, 120, 180])}</label>
          <label className="flex items-center gap-2">งานละไม่เกินวันละ {num("per_task_per_day", [120, 180, 240, 360])}</label>
          <label className="flex items-center gap-2">เว้นห่างจากนัด {num("gap", [0, 10, 15, 30])}</label>
          <div className="flex flex-col gap-1">เวลาที่ใช้เมื่องานไม่ได้บอก (นาที)
            <div className="flex flex-wrap gap-2">
              {Object.entries({ classroom: "Classroom", email: "อีเมล", you: "คุณเพิ่ม" }).map(([k, label]) => (
                <label key={k} className="flex items-center gap-1 text-xs">{label}
                  <input type="number" min={15} max={1440} step={15} className={`${input} w-20`} value={r.estimates[k] ?? 60}
                    onChange={(e) => setR({ ...r, estimates: { ...r.estimates, [k]: Number(e.target.value) } })} /></label>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-3">เตือนใน #ด่วน
            {[["1d", "ก่อน 1 วัน"], ["1h", "ก่อน 1 ชั่วโมง"]].map(([k, label]) => (
              <label key={k} className="flex items-center gap-1 text-xs">
                <input type="checkbox" checked={r.reminders.includes(k)}
                  onChange={(e) => setR({ ...r, reminders: e.target.checked ? [...r.reminders, k] : r.reminders.filter((x) => x !== k) })} />{label}</label>
            ))}
          </div>
          <div className="flex items-center gap-2"><Button kind="p" sm onClick={save}>บันทึกกติกา</Button>{msg && <span className="text-xs text-muted">{msg}</span>}</div>
        </div>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------ the page
export function Schedule() {
  const { refresh } = useStatus();
  const [key, setKey] = useState(0);
  const [roundOff, setRoundOff] = useState(false);
  useEffect(() => {
    api.settings().then((s) => setRoundOff(!s.clock.find((r) => r.id === "schedule")?.enabled), () => {});
  }, []);
  const changed = () => { setKey((k) => k + 1); refresh(); };
  return (
    <div className="flex flex-col gap-4">
      {roundOff && (
        <Banner icon="clock">รอบ <b>วางและซิงก์ตาราง</b> ยังปิดอยู่: เลขายังไม่วางบล็อกเอง · กด <b>วางตารางใหม่</b> เพื่อวางครั้งเดียว
          หรือเปิดรอบในหน้าตั้งค่า (นาฬิกาเลขา)</Banner>
      )}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(320px,1.15fr)]">
        <div className="flex flex-col gap-4 min-w-0">
          <Week reloadKey={key} onPlanned={changed} />
          <Card title="ทำตามแผนได้" right={<Phase phase="B6" />}>
            <p className="text-sm text-muted">เทียบบล็อกกับสิ่งที่ทำจริงจาก ActivityWatch และข้อสังเกตเพื่อปรับวิธีวาง มาในช่วง B6 · ตอนนี้บล็อกที่ผ่านไปแล้วนับว่าทำแล้ว</p>
          </Card>
        </div>
        <div className="flex flex-col gap-4 min-w-0">
          <Tasks reloadKey={key} changed={changed} />
          <Pending reloadKey={key} />
          <Courses reloadKey={key} />
          <Rules onSaved={changed} />
        </div>
      </div>
    </div>
  );
}
