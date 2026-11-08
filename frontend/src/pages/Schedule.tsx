// W5 ตาราง (B3), laid out as the plan's mockup (docs/plan-v2/stage2/web.py w5): the week on the
// left (schedule/Week.tsx) with its colour key under it; on the right ⑤ ทำตามแผนได้ and ⑥ ข้อสังเกต
// (both B6) and ⑦ นัดที่รอคุณรับ. Below, two cards that aren't in the mockup but B3 needs: the task
// list the planner works from, and Classroom courses. The planner's rules are on the settings page.
// Adding and changing things works like Google Calendar: click or drag on the calendar (or press
// สร้าง) for a card with two tabs, กิจกรรม and งาน (schedule/EditCard.tsx); click anything on
// the calendar to see what it is (schedule/DetailCard.tsx).
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type CourseRow, type Decision, type Followed, type ScheduleRules, type TaskRow } from "../api";
import { Link } from "react-router";
import { AppointmentActions, CourseActions } from "../components/Bell";
import { LineEditor, Meter } from "../components/project";
import { Avatar, Banner, Button, Card, Chip, Spinner } from "../components/ui";
import { duration, when } from "../format";
import { Icon } from "../icons";
import { useStatus } from "../status";
import { DetailCard, type Picked } from "./schedule/DetailCard";
import { EditCard, type Done, type Draft, type Ghost } from "./schedule/EditCard";
import { Toast, type ToastMsg } from "../components/Toast";
import { type Anchor } from "./schedule/Floating";
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
/** ⑤ ทำตามแผนได้ (B6): this week's checked blocks you followed, against your target, per day. */
function FollowedCard({ f, onTarget }: { f: Followed | null; onTarget: (t: number) => void }) {
  const [editing, setEditing] = useState(false);
  if (!f) return <Card title="ทำตามแผนได้"><Spinner /></Card>;
  const maxDay = Math.max(60, ...f.days.map((d) => d.done + d.missed));
  return (
    <Card title="ทำตามแผนได้">
      {f.percent === null ? (
        <p className="text-sm text-muted">{f.recording ? "ยังไม่มีบล็อกที่เทียบได้สัปดาห์นี้ · บล็อกที่จบแล้วจะถูกเทียบกับ ActivityWatch ทุก 15 นาที"
          : <>ยังไม่ได้เปิดบันทึกกิจกรรม · <Link to="/time" className="underline">เปิดที่หน้าการใช้เวลา</Link></>}</p>
      ) : (
        <div className="flex flex-col gap-2.5">
          <div className="flex items-baseline gap-2">
            <b className="text-[28px] leading-none">{f.percent}%</b>
            <span className="text-sm text-muted">สัปดาห์นี้ ·{" "}
              <button type="button" className="hover:underline cursor-pointer" onClick={() => setEditing(!editing)}>เป้า {f.target}%</button></span>
          </div>
          {editing && <LineEditor line={f.target} onSave={(v) => { setEditing(false); onTarget(v); }} onCancel={() => setEditing(false)} />}
          <Meter value={f.percent} tone={f.percent >= f.target ? "ok" : "warn"} mark={f.target} thick />
          <svg viewBox="0 0 280 90" className="w-full h-auto" role="img" aria-label="ทำตามแผนรายวัน">
            {f.days.map((d, i) => {
              const x = 14 + i * 38, h = (v: number) => (64 * v) / maxDay;
              return (
                <g key={d.label}>
                  <rect x={x} y={70 - h(d.done)} width={22} height={h(d.done)} rx={3} fill="var(--c2)"><title>{`${d.label} ทำตามแผน ${duration(d.done)}`}</title></rect>
                  <rect x={x} y={70 - h(d.done) - h(d.missed)} width={22} height={h(d.missed)} rx={3} fill="var(--c5)"><title>{`${d.label} หลุดแผน ${duration(d.missed)}`}</title></rect>
                  <text x={x + 11} y={86} textAnchor="middle" fontSize="10" fill="var(--muted)">{d.label}</text>
                </g>
              );
            })}
          </svg>
          <div className="flex gap-3 text-xs text-ink-2">
            <span className="inline-flex items-center gap-1.5"><i className="size-2.5 rounded-sm" style={{ background: "var(--c2)" }} />ทำตามแผน</span>
            <span className="inline-flex items-center gap-1.5"><i className="size-2.5 rounded-sm" style={{ background: "var(--c5)" }} />หลุดแผน</span>
          </div>
        </div>
      )}
    </Card>
  );
}

/** ⑥ ข้อสังเกต (B6): a part of a weekday where blocks keep being missed; B7: one press makes it a
 *  rule (the planner keeps those hours free every week), kept in the rule book. */
function NotesCard({ f, onAvoid }: { f: Followed | null; onAvoid: (weekday: number, part: string, title: string) => void }) {
  return (
    <Card title="ข้อสังเกต">
      {!f || f.notes.length === 0 ? (
        <p className="text-sm text-muted">ยังไม่เห็นช่วงที่หลุดซ้ำ · เลขาดูย้อนหลัง 4 สัปดาห์ ช่วงเดียวกันหลุด 2 สัปดาห์ขึ้นไปจึงบอก</p>
      ) : (
        <ul className="divide-y divide-line">
          {f.notes.map((n) => (
            <li key={n.title} className="py-2 flex flex-col gap-1.5"><span className="block font-semibold text-[14px]">{n.title}</span>
              <span className="block text-xs text-muted">{n.sub}</span>
              {!n.avoided && <span><Button sm kind="p" onClick={() => onAvoid(n.weekday, n.part, n.title)}>ไม่วางบล็อกช่วงนี้</Button></span>}</li>
          ))}
        </ul>
      )}
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
  const [followedWeek, setFollowedWeek] = useState<Followed | null>(null);
  const loadFollowed = useCallback(() => { api.followed().then(setFollowedWeek, () => setFollowedWeek(null)); }, []);
  useEffect(() => { loadFollowed(); }, [loadFollowed, key]);
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
          <FollowedCard f={followedWeek} onTarget={async (v) => {
            try { const r = await api.setFollowTarget(v); setToast({ text: `ตั้งเป้าทำตามแผน ${v}%`, actionId: r.action_id, key: Date.now() }); loadFollowed(); }
            catch (e) { setToast({ text: (e as Error).message, actionId: null, key: Date.now() }); }
          }} />
          <NotesCard f={followedWeek} onAvoid={async (weekday, part, title) => {
            try {
              const r = await api.avoidHours(weekday, part);
              setToast({ text: `เลขาจะไม่วางบล็อกช่วงนี้แล้ว (${title.split(" หลุด")[0]}) · ${r.line || "ตารางเดิมไม่มีบล็อกช่วงนั้น"}`, actionId: r.action_id, key: Date.now() });
              changed();
            } catch (e) { setToast({ text: (e as Error).message, actionId: null, key: Date.now() }); }
          }} />
          <Pending reloadKey={key} onChange={changed} />
        </div>
      </div>
      <div className="grid gap-4 items-start xl:grid-cols-[minmax(0,3fr)_minmax(280px,1fr)]">
        <Tasks items={tasks} onAdd={() => create(null, null, "task")} onEdit={edit} onFinish={finish} />
        <div className="flex flex-col gap-4 min-w-0">
          <Courses reloadKey={key} />
          <Link to="/settings#rules" className="text-xs text-muted hover:text-ink px-1">
            เวลาทำงาน ความยาวบล็อก และเวลาต่อวัน: <span className="font-semibold text-accent-strong whitespace-nowrap">กติกาตาราง →</span></Link>
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
