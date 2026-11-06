// W5 ตาราง (B3): the week as the secretary sees it (appointments, work blocks, due dates), the task
// list the planner works from, appointments waiting for you, Classroom courses, and the planner's rules.
// The calendar is FullCalendar (v6); its colours follow the theme through the .fc rules in index.css.
// Adding and changing things works like Google Calendar: click or drag on the calendar (or press
// + สร้าง) for a card with two tabs, กิจกรรม and งาน (schedule/EditCard.tsx); click anything on
// the calendar to see what it is (schedule/DetailCard.tsx).
import type { DateSelectArg, EventClickArg, EventInput, EventSourceFuncArg } from "@fullcalendar/core";
import thLocale from "@fullcalendar/core/locales/th";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type CourseRow, type Decision, type ScheduleRules, type TaskRow } from "../api";
import { AppointmentActions, CourseActions } from "../components/Bell";
import { Banner, Button, Card, Chip, Phase, Spinner } from "../components/ui";
import { duration, when } from "../format";
import { Icon } from "../icons";
import { useStatus } from "../status";
import { DetailCard, type Picked } from "./schedule/DetailCard";
import { EditCard, field, type Done, type Draft, type Ghost } from "./schedule/EditCard";
import { Toast, type Anchor, type ToastMsg } from "./schedule/Floating";

type Create = (sel: { start: Date; end: Date; allDay: boolean } | null, anchor: Anchor, tab?: "event" | "task") => void;

// ------------------------------------------------------------------ the week
function Week({ reloadKey, ghost, onPlanned, onCreate, onPick }: {
  reloadKey: number; ghost: Ghost | null; onPlanned: () => void; onCreate: Create; onPick: (p: Picked, anchor: Anchor) => void;
}) {
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
          extendedProps: { picked: { type: "meet", ev: e } satisfies Picked },
        })),
        ...w.blocks.map((b) => ({
          id: `b${b.id}`, title: b.title + (b.pinned ? " · คุณย้ายมา" : ""), start: b.start, end: b.end,
          classNames: ["ev-block", b.pinned ? "ev-pinned" : "", b.past ? "ev-done" : ""],
          extendedProps: { picked: { type: "block", block: b } satisfies Picked },
        })),
        ...w.deadlines.map((d) => ({
          id: `d${d.task_id}`, title: `ส่ง ${new Date(d.due).toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit" })} · ${d.title}`,
          start: d.due.slice(0, 10), allDay: true, classNames: ["ev-dead"],
          extendedProps: { picked: { type: "deadline", d } satisfies Picked },
        })),
      ]);
    }, fail);
  }, []);

  useEffect(() => { cal.current?.getApi().refetchEvents(); }, [reloadKey]);
  // While a card for something new is open, its draft sits on the calendar and follows what
  // you type (Google Calendar's "(ไม่มีชื่อ)"). It is added by hand, so refetching leaves it be.
  useEffect(() => {
    const c = cal.current?.getApi();
    if (!c) return;
    c.getEventById("ghost")?.remove();
    if (ghost) c.addEvent({ id: "ghost", title: ghost.title, start: ghost.start, end: ghost.end, allDay: ghost.allDay,
                            classNames: [ghost.kind === "event" ? "ev-meet" : "ev-dead", "ev-ghost"] });
  }, [ghost]);

  const select = (arg: DateSelectArg) => {
    arg.view.calendar.unselect(); // the draft takes the highlight's place
    onCreate({ start: arg.start, end: arg.end, allDay: arg.allDay }, arg.jsEvent ? { x: arg.jsEvent.clientX, y: arg.jsEvent.clientY } : null);
  };
  const click = (arg: EventClickArg) => {
    arg.jsEvent.preventDefault();
    const picked = arg.event.extendedProps.picked as Picked | undefined;
    if (picked) onPick(picked, { x: arg.jsEvent.clientX, y: arg.jsEvent.clientY });
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
            <b>เวลาไม่พอก่อนกำหนดส่ง:</b> {plan.short.map((s) => `${s.title} ขาด ${duration(s.minutes)}`).join(" · ")}
            <span className="text-muted"> · ลองลดเวลาที่ใช้ เพิ่มเวลาต่อวันของงาน เปลี่ยนเวลาทำงานในกติกา หรือย้ายนัดออก</span>
          </Banner>
        )}
        <div className="schedule-cal">
          <FullCalendar ref={cal} plugins={[timeGridPlugin, dayGridPlugin, interactionPlugin]} locale={thLocale} initialView="timeGridWeek" firstDay={1}
            customButtons={{ create: { text: "+ สร้าง", click: (_e, el) => {
              const r = el.getBoundingClientRect();
              onCreate(null, { x: r.left - 16, y: r.bottom + 64 });
            } } }}
            headerToolbar={{ left: "create prev,next today", center: "title", right: "timeGridDay,timeGridWeek,dayGridMonth" }}
            buttonText={{ today: "วันนี้", day: "วัน", week: "สัปดาห์", month: "เดือน" }}
            slotMinTime="07:00:00" slotMaxTime="24:00:00" scrollTime="08:00:00" nowIndicator height={720} expandRows
            allDayText="ทั้งวัน" slotLabelFormat={{ hour: "2-digit", minute: "2-digit", hour12: false }}
            eventTimeFormat={{ hour: "2-digit", minute: "2-digit", hour12: false }}
            selectable selectMirror selectLongPressDelay={300} select={select}
            events={events} eventClick={click} />
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
          {[["ev-meet", "นัด"], ["ev-dead", "เดดไลน์"], ["ev-block", "บล็อกงาน (ปฏิทิน “เลขา”)"], ["ev-block ev-pinned", "บล็อกที่คุณย้าย"], ["ev-meet ev-recurring", "นัดซ้ำทุกสัปดาห์ (ไม่เตือน)"]].map(([c, label]) => (
            <span key={label} className="inline-flex items-center gap-1.5"><i className={`legend ${c}`} />{label}</span>
          ))}
          <span className="grow" />
          <span>คลิกหรือลากบนช่องว่างเพื่อเพิ่มกิจกรรมหรืองาน · คลิกของในปฏิทินเพื่อดูรายละเอียด</span>
        </div>
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------ tasks
function TaskLine({ t, onEdit, onFinish }: { t: TaskRow; onEdit: (t: TaskRow, a: Anchor) => void; onFinish: (t: TaskRow) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const need = t.est_minutes ?? t.est_default;
  const have = t.done_minutes + t.booked_minutes;
  const closed = t.status !== "open";
  const sizes = [t.block_minutes && `บล็อกละ ${duration(t.block_minutes)}`, t.daily_minutes && `วันละ ${duration(t.daily_minutes)}`].filter(Boolean);
  return (
    <li className={`py-1.5 flex items-start gap-1.5 ${closed ? "opacity-55" : ""}`}>
      <button type="button" disabled={closed} onClick={(e) => onEdit(t, { x: e.clientX, y: e.clientY })}
        className="grow min-w-0 text-left rounded-s -ml-1.5 px-1.5 py-1 cursor-pointer hover:bg-panel-2 disabled:cursor-default disabled:hover:bg-transparent">
        <span className="font-medium block truncate">{t.title}</span>
        <span className="block text-xs text-muted">
          {[t.due ? `ส่ง ${when(t.due)}` : "ไม่มีกำหนดส่ง", t.source, closed ? (t.status === "done" ? "เสร็จแล้ว" : "เอาออกแล้ว")
            : `จองแล้ว ${duration(have)} จาก ${duration(need)}`, ...sizes].join(" · ")}
        </span>
        {!closed && (
          <span className="mt-1.5 block h-1 rounded-full bg-panel-2 overflow-hidden">
            <span className="block h-full rounded-full bg-accent" style={{ width: `${Math.min(100, (have / Math.max(need, 1)) * 100)}%` }} />
          </span>
        )}
      </button>
      {t.link && <a href={t.link} target="_blank" rel="noopener" title="เปิดที่มา" className="p-1.5 mt-0.5 text-muted hover:text-ink"><Icon name="ext" size={15} /></a>}
      {!closed && <Button sm icon="check" disabled={busy} onClick={async () => { setBusy(true); try { await onFinish(t); } finally { setBusy(false); } }}>เสร็จ</Button>}
    </li>
  );
}

function Tasks({ items, onAdd, onEdit, onFinish }: {
  items: TaskRow[] | null; onAdd: () => void; onEdit: (t: TaskRow, a: Anchor) => void; onFinish: (t: TaskRow) => Promise<void>;
}) {
  const open = items?.filter((t) => t.status === "open") ?? [];
  return (
    <Card title={`งาน · ${open.length}`} right={<Button sm kind="p" icon="plus" onClick={onAdd}>เพิ่มงาน</Button>}>
      <p className="text-xs text-muted pb-1">เลขาจองเวลาทำให้จากรายการนี้ · คลิกงานเพื่อแก้กำหนดส่ง เวลาที่ใช้ หรือขนาดบล็อก</p>
      {items === null ? <Spinner /> : (
        <ul className="divide-y divide-line">
          {items.length === 0 && <li className="py-3 text-sm text-muted">ยังไม่มีงาน · งานจากอีเมลและ Classroom จะขึ้นที่นี่เอง</li>}
          {items.map((t) => <TaskLine key={t.id} t={t} onEdit={onEdit} onFinish={onFinish} />)}
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
    <select className={field} value={r?.rules[k]} onChange={(e) => set(k, Number(e.target.value))}>
      {opts.map((m) => <option key={m} value={m}>{m === 0 ? "ไม่เว้น" : duration(m)}</option>)}
    </select>
  );
  return (
    <Card title="กติกาตาราง" right={<Button sm kind="ghost" onClick={() => setOpen((o) => !o)}>{open ? "ซ่อน" : "ดูและแก้"}</Button>}>
      {!open && <p className="text-xs text-muted">วางเฉพาะช่วงเวลาทำงาน เว้นระยะจากนัด จำกัดเวลาต่องานต่อวัน และเตือนก่อน 1 วันกับ 1 ชั่วโมง</p>}
      {open && !r && <Spinner />}
      {open && r && (
        <div className="flex flex-col gap-2.5 text-sm">
          <label className="flex items-center gap-2">วางบล็อกช่วง
            <input type="time" className={field} value={r.rules.day_start} onChange={(e) => set("day_start", e.target.value)} />–
            <input type="time" className={field} value={r.rules.day_end} onChange={(e) => set("day_end", e.target.value)} /></label>
          <label className="flex items-center gap-2">บล็อกยาวไม่เกิน {num("max_block", [60, 90, 120, 180])}</label>
          <label className="flex items-center gap-2">งานละไม่เกินวันละ {num("per_task_per_day", [120, 180, 240, 360])}</label>
          <label className="flex items-center gap-2">เว้นห่างจากนัด และพักระหว่างบล็อกงานเดียวกัน {num("gap", [0, 10, 15, 30])}</label>
          <div className="flex flex-col gap-1">เวลาที่ใช้เมื่องานไม่ได้บอก (นาที)
            <div className="flex flex-wrap gap-2">
              {Object.entries({ classroom: "Classroom", email: "อีเมล", you: "คุณเพิ่ม" }).map(([k, label]) => (
                <label key={k} className="flex items-center gap-1 text-xs">{label}
                  <input type="number" min={15} max={1440} step={15} className={`${field} w-20`} value={r.estimates[k] ?? 60}
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
/** The next half hour from now, for "+ สร้าง" with no slot picked. */
function nextHalfHour(): Date {
  const d = new Date();
  d.setSeconds(0, 0);
  d.setMinutes(d.getMinutes() < 30 ? 30 : 60);
  return d;
}

export function Schedule() {
  const { refresh } = useStatus();
  const [key, setKey] = useState(0);
  const [roundOff, setRoundOff] = useState(false);
  const [rules, setRules] = useState<ScheduleRules | null>(null);
  const [tasks, setTasks] = useState<TaskRow[] | null>(null);
  const [editing, setEditing] = useState<{ draft: Draft; anchor: Anchor } | null>(null);
  const [ghost, setGhost] = useState<Ghost | null>(null);
  const [picked, setPicked] = useState<{ picked: Picked; anchor: Anchor } | null>(null);
  const [toast, setToast] = useState<ToastMsg | null>(null);

  useEffect(() => {
    api.settings().then((s) => setRoundOff(!s.clock.find((r) => r.id === "schedule")?.enabled), () => {});
  }, []);
  useEffect(() => {
    api.rules().then(setRules, () => {});
    api.tasks().then((r) => setTasks(r.items), () => setTasks([]));
  }, [key]);
  const changed = useCallback(() => { setKey((k) => k + 1); refresh(); }, [refresh]);
  const byId = useMemo(() => new Map((tasks ?? []).map((t) => [t.id, t])), [tasks]);

  const say = (text: string, actionId: number | null = null) => setToast({ text, actionId, key: Date.now() });
  const done = (d: Done) => { setEditing(null); setPicked(null); say(d.text, d.saved?.action_id ?? null); changed(); };
  const undo = async (actionId: number) => {
    try {
      await api.undo(actionId);
      // Put the blocks right now if the secretary is placing them by itself; otherwise
      // they follow on the next วางตารางใหม่.
      if (!roundOff) await api.replan().catch(() => {});
      say("เลิกทำแล้ว");
    } catch (e) { say((e as Error).message); }
    changed();
  };
  const create: Create = (sel, anchor, tab = "event") => {
    setPicked(null);
    const start = sel?.start ?? nextHalfHour();
    setEditing({ draft: { kind: "new", tab, start, end: sel?.end ?? new Date(start.getTime() + 3_600_000), allDay: sel?.allDay ?? false, slot: !!sel },
                 anchor });
  };
  const edit = (t: TaskRow, anchor: Anchor) => { setPicked(null); setEditing({ draft: { kind: "edit", task: t }, anchor }); };
  const finish = async (t: TaskRow) => {
    try { done({ text: `ทำเสร็จแล้ว: ${t.title}`, saved: await api.taskDone(t.id) }); } catch (e) { say((e as Error).message); }
  };
  const closeEditor = useCallback(() => setEditing(null), []);
  const closeDetail = useCallback(() => setPicked(null), []);
  const closeToast = useCallback(() => setToast(null), []);

  return (
    <div className="flex flex-col gap-4">
      {roundOff && (
        <Banner icon="clock">รอบ <b>วางและซิงก์ตาราง</b> ยังปิดอยู่: เลขายังไม่วางบล็อกเอง · กด <b>วางตารางใหม่</b> เพื่อวางครั้งเดียว
          หรือเปิดรอบในหน้าตั้งค่า (นาฬิกาเลขา)</Banner>
      )}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(320px,1.15fr)]">
        <div className="flex flex-col gap-4 min-w-0">
          <Week reloadKey={key} ghost={ghost} onPlanned={changed} onCreate={create}
            onPick={(p, anchor) => { setEditing(null); setPicked({ picked: p, anchor }); }} />
          <Card title="ทำตามแผนได้" right={<Phase phase="B6" />}>
            <p className="text-sm text-muted">เทียบบล็อกกับสิ่งที่ทำจริงจาก ActivityWatch และข้อสังเกตเพื่อปรับวิธีวาง มาในช่วง B6 · ตอนนี้บล็อกที่ผ่านไปแล้วนับว่าทำแล้ว</p>
          </Card>
        </div>
        <div className="flex flex-col gap-4 min-w-0">
          <Tasks items={tasks} onAdd={() => create(null, null, "task")} onEdit={edit} onFinish={finish} />
          <Pending reloadKey={key} />
          <Courses reloadKey={key} />
          <Rules onSaved={changed} />
        </div>
      </div>
      {editing && <EditCard key={JSON.stringify(editing.draft)} draft={editing.draft} anchor={editing.anchor} rules={rules}
        onClose={closeEditor} onDone={done} onPreview={setGhost} />}
      {picked && <DetailCard picked={picked.picked} anchor={picked.anchor} onClose={closeDetail} onDone={done}
        task={picked.picked.type === "meet" ? undefined : byId.get(picked.picked.type === "block" ? picked.picked.block.task_id : picked.picked.d.task_id)}
        onEdit={(t) => edit(t, picked.anchor)} />}
      <Toast key={toast?.key} msg={toast} onUndo={undo} onClose={closeToast} />
    </div>
  );
}
