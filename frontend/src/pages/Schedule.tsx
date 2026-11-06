// W5 ตาราง (B3), laid out as the plan's mockup (docs/plan-v2/stage2/web.py w5): the week on the
// left (schedule/Week.tsx) with its colour key under it; on the right ⑤ ทำตามแผนได้ and ⑥ ข้อสังเกต
// (both B6) and ⑦ นัดที่รอคุณรับ. Below, three cards that aren't in the mockup but B3 needs: the task
// list the planner works from, Classroom courses, and the planner's rules.
// Adding and changing things works like Google Calendar: click or drag on the calendar (or press
// สร้าง) for a card with two tabs, กิจกรรม and งาน (schedule/EditCard.tsx); click anything on
// the calendar to see what it is (schedule/DetailCard.tsx).
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type CourseRow, type Decision, type ScheduleRules, type TaskRow } from "../api";
import { AppointmentActions, CourseActions } from "../components/Bell";
import { Avatar, Banner, Button, Card, Chip, Phase, Spinner } from "../components/ui";
import { duration, when } from "../format";
import { Icon } from "../icons";
import { useStatus } from "../status";
import { DetailCard, type Picked } from "./schedule/DetailCard";
import { EditCard, field, type Done, type Draft, type Ghost } from "./schedule/EditCard";
import { Toast, type Anchor, type ToastMsg } from "./schedule/Floating";
import { sourceLabel } from "./schedule/links";
import { Week, type Create } from "./schedule/Week";

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
        <span className="font-medium flex items-center gap-1.5 min-w-0">
          <span className="truncate">{t.title}</span>
          {t.details && <span title={t.details} className="text-muted shrink-0"><Icon name="notes" size={13} /></span>}
        </span>
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
      {t.link && <a href={t.link} target="_blank" rel="noopener" title={sourceLabel(t.source)} className="p-1.5 mt-0.5 text-muted hover:text-ink"><Icon name="ext" size={15} /></a>}
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
      <p className="text-xs text-muted pb-1">เลขาจองเวลาทำให้จากรายการนี้ · คลิกงานเพื่อแก้กำหนดส่ง รายละเอียด เวลาที่ใช้ หรือขนาดบล็อก</p>
      {items === null ? <Spinner /> : (
        <ul className="divide-y divide-line">
          {items.length === 0 && <li className="py-3 text-sm text-muted">ยังไม่มีงาน · งานจากอีเมลและ Classroom จะขึ้นที่นี่เอง</li>}
          {items.map((t) => <TaskLine key={t.id} t={t} onEdit={onEdit} onFinish={onFinish} />)}
        </ul>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------ the right column (W5 ⑤ ⑥ ⑦)
/** ⑤ and ⑥ arrive with B6 (blocks compared with what you really did, from ActivityWatch). */
function Later({ title, children }: { title: string; children: string }) {
  return (
    <Card title={title} right={<Phase phase="B6" />}>
      <p className="text-sm text-muted">{children}</p>
    </Card>
  );
}

/** ⑦ Appointments from people you're interested in wait here (and in #อนุมัติ) for รับ / ไม่ไป. */
function Pending({ reloadKey, onChange }: { reloadKey: number; onChange: () => void }) {
  const [items, setItems] = useState<Decision[] | null>(null);
  useEffect(() => { api.decisions().then((r) => setItems(r.items.filter((d) => d.kind === "appointment")), () => setItems([])); }, [reloadKey]);
  return (
    <Card title="นัดที่รอคุณรับ">
      {items === null ? <Spinner /> : items.length === 0 ? (
        <p className="text-sm text-muted">ไม่มีนัดที่รอ · นัดจากคนที่คุณสนใจจะมารอให้กดรับที่นี่ก่อนลงปฏิทิน</p>
      ) : (
        <ul className="divide-y divide-line">
          {items.map((d) => (
            <li key={d.id} className="py-2.5 flex items-center gap-2.5">
              <Avatar name={d.from || d.title} size="sm" />
              <span className="grow min-w-0">
                <span className="block font-semibold text-[13.5px] truncate">{d.title}</span>
                <span className="block text-xs text-ink-2 truncate">{[d.from, d.when].filter(Boolean).join(" · ")}</span>
              </span>
              <AppointmentActions decisionId={d.id} onChange={onChange} />
            </li>
          ))}
        </ul>
      )}
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
      <div className="grid gap-4 items-start xl:grid-cols-[minmax(0,3fr)_minmax(280px,1fr)]">
        <Week reloadKey={key} ghost={ghost} onPlanned={changed} onCreate={create}
          onPick={(p, anchor) => { setEditing(null); setPicked({ picked: p, anchor }); }} />
        <div className="flex flex-col gap-4 min-w-0">
          <Later title="ทำตามแผนได้">เทียบบล็อกในตารางกับสิ่งที่ทำจริงจาก ActivityWatch เป็นเปอร์เซ็นต์ต่อสัปดาห์ เทียบกับเป้าที่คุณตั้ง</Later>
          <Later title="ข้อสังเกต">จากบล็อกที่หลุดบ่อย เลขาเสนอวิธีวางตารางแบบใหม่ คุณกดใช้หรือไม่ก็ได้ · ที่ใช้แล้วเก็บในสมุดกติกา</Later>
          <Pending reloadKey={key} onChange={changed} />
        </div>
      </div>
      <div className="grid gap-4 items-start xl:grid-cols-[minmax(0,3fr)_minmax(280px,1fr)]">
        <Tasks items={tasks} onAdd={() => create(null, null, "task")} onEdit={edit} onFinish={finish} />
        <div className="flex flex-col gap-4 min-w-0">
          <Courses reloadKey={key} />
          <Rules onSaved={changed} />
        </div>
      </div>
      {editing && <EditCard key={JSON.stringify(editing.draft)} draft={editing.draft} anchor={editing.anchor} rules={rules}
        onClose={closeEditor} onDone={done} onPreview={setGhost} />}
      {picked && <DetailCard picked={picked.picked} anchor={picked.anchor} onClose={closeDetail} onDone={done} onChanged={changed}
        task={picked.picked.type === "meet" ? undefined : byId.get(picked.picked.type === "block" ? picked.picked.block.task_id : picked.picked.d.task_id)}
        onEdit={(t) => edit(t, picked.anchor)} />}
      <Toast key={toast?.key} msg={toast} onUndo={undo} onClose={closeToast} />
    </div>
  );
}
