// The week on the schedule page, drawn as in the plan's W5 mockup (docs/plan-v2/stage2/web.py w5,
// look.css .wk and .ev): no grid lines, hour labels every two hours, each day's short name over its
// date with today in an accent pill, and every item a soft card with a coloured left edge, its
// title, and one line saying what it is (เลขาจอง · คุณย้ายมา · ทำแล้ว · เดดไลน์ · รอคุณรับ …).
// FullCalendar does the layout, the clicking and the dragging; index.css (.schedule-cal) does the look.
import type {
  DateSelectArg, DatesSetArg, DayHeaderContentArg, EventClickArg, EventContentArg, EventInput, EventSourceFuncArg,
} from "@fullcalendar/core";
import thLocale from "@fullcalendar/core/locales/th";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { api, type BlockItem, type CalItem, type DeadlineItem } from "../../api";
import { Banner, Button, Card, Seg } from "../../components/ui";
import { DAYS_SHORT, MONTHS, MONTHS_LONG, duration, hm, shortDay, when, ymd } from "../../format";
import { Icon } from "../../icons";
import type { Picked } from "./DetailCard";
import type { Ghost } from "./EditCard";
import type { Anchor } from "./Floating";

export type Create = (sel: { start: Date; end: Date; allDay: boolean } | null, anchor: Anchor, tab?: "event" | "task") => void;

type View = "timeGridDay" | "timeGridWeek" | "dayGridMonth";
const VIEWS: { key: View; label: string }[] = [
  { key: "timeGridDay", label: "วัน" }, { key: "timeGridWeek", label: "สัปดาห์" }, { key: "dayGridMonth", label: "เดือน" },
];
const DAY = 86_400_000;
const LEGEND: [string, string][] = [["bg-bad", "นัด"], ["bg-warn", "เดดไลน์"], ["bg-accent", "บล็อกงาน"], ["bg-ok", "ทำแล้ว"], ["bg-muted", "หลุดแผน / รอรับ"]];

// ------------------------------------------------------------------ what each item looks like
// (kind = the .ev modifier in index.css; sub = the card's second line)
function meetItem(e: CalItem): EventInput {
  const waiting = e.status === "proposed";
  const sub = waiting ? "รอคุณรับ" : [e.location, e.source === "email" ? "จากอีเมล" : ""].filter(Boolean).join(" · ");
  return { id: `e${e.id}`, title: waiting ? `${e.title}?` : e.title, start: e.start, end: e.end, allDay: e.all_day,
           classNames: ["ev", waiting ? "miss" : "meet"], extendedProps: { picked: { type: "meet", ev: e } satisfies Picked, sub } };
}

function blockItem(b: BlockItem): EventInput {
  // B3 can't tell yet whether you really worked in a block (B6 compares with ActivityWatch): a block
  // is ทำแล้ว when you marked its task done; otherwise a past block is just past.
  const [kind, sub] = b.task_status === "done" ? ["done", "ทำแล้ว"] : b.past ? ["past", "ผ่านไปแล้ว"]
    : b.running ? ["", "กำลังทำ"] : b.pinned ? ["", "คุณย้ายมา"] : ["", "เลขาจอง"];
  return { id: `b${b.id}`, title: b.title, start: b.start, end: b.end, classNames: ["ev", kind].filter(Boolean),
           extendedProps: { picked: { type: "block", block: b } satisfies Picked, sub } };
}

/** Where a due date sits on the calendar: a half-hour card starting at the due time, as the plan
 *  draws "ส่งร่างบทที่ 3" (due 12:00, drawn from 12:00). Near midnight (Classroom's 23:59) it moves
 *  up so it stays on its own day. */
export function dueSpan(due: Date): [Date, Date] {
  const end = new Date(due.getTime() + 30 * 60_000);
  if (ymd(end) === ymd(due) || (end.getHours() === 0 && end.getMinutes() === 0)) return [due, end];
  const midnight = new Date(due.getFullYear(), due.getMonth(), due.getDate() + 1);
  return [new Date(midnight.getTime() - 30 * 60_000), midnight];
}

function deadlineItem(d: DeadlineItem): EventInput {
  const due = new Date(d.due);
  const [start, end] = dueSpan(due);
  return { id: `d${d.task_id}`, title: d.title, start, end, classNames: ["ev", "dead"],
           extendedProps: { picked: { type: "deadline", d } satisfies Picked, sub: `เดดไลน์ ${hm(due)}` } };
}

/** The hours to show: 08–22 as in the plan, widened (to even hours, so the labels stay on the
 *  two-hour marks) when something falls outside: FullCalendar would otherwise hide it. */
function hoursFor(items: { start: Date; end: Date; allDay?: boolean }[]): [number, number] {
  let lo = 8, hi = 22;
  for (const it of items) {
    if (it.allDay) continue;
    if (ymd(it.start) !== ymd(new Date(it.end.getTime() - 1))) return [0, 24]; // runs past midnight
    lo = Math.min(lo, it.start.getHours());
    hi = Math.max(hi, it.end.getHours() + (it.end.getMinutes() ? 1 : 0));
  }
  return [lo - (lo % 2), Math.min(24, hi + (hi % 2))];
}

/** "2–8 พ.ย." and "สัปดาห์นี้", for the card's title. */
function heading(view: View, start: Date, end: Date): { title: string; sub: string } {
  const today = new Date(new Date().toDateString()).getTime();
  const last = new Date(end.getTime() - DAY);
  if (view === "dayGridMonth") {
    const now = new Date();
    return { title: `${MONTHS_LONG[start.getMonth()]} ${start.getFullYear() + 543}`,
             sub: start.getMonth() === now.getMonth() && start.getFullYear() === now.getFullYear() ? "เดือนนี้" : "" };
  }
  if (view === "timeGridDay") {
    const days = Math.round((start.getTime() - today) / DAY);
    return { title: shortDay(start), sub: { 0: "วันนี้", 1: "พรุ่งนี้", [-1]: "เมื่อวาน" }[days] ?? `${start.getFullYear() + 543}` };
  }
  const title = start.getMonth() === last.getMonth()
    ? `${start.getDate()}–${last.getDate()} ${MONTHS[last.getMonth()]}`
    : `${start.getDate()} ${MONTHS[start.getMonth()]} – ${last.getDate()} ${MONTHS[last.getMonth()]}`;
  const weeks = Math.round((start.getTime() - (today - ((new Date().getDay() + 6) % 7) * DAY)) / (7 * DAY));
  return { title, sub: { 0: "สัปดาห์นี้", 1: "สัปดาห์หน้า", [-1]: "สัปดาห์ที่แล้ว" }[weeks] ?? `${last.getFullYear() + 543}` };
}

function dayHeader(arg: DayHeaderContentArg) {
  const name = DAYS_SHORT[arg.date.getDay()];
  if (arg.view.type === "dayGridMonth") return <span className="wk-n">{name}</span>;
  return <span className="wk-d">{name}<b className={arg.isToday ? "today" : ""}>{arg.date.getDate()}</b></span>;
}

function eventContent(arg: EventContentArg) {
  const sub = arg.event.extendedProps.sub as string | undefined;
  return <div className="ev-in"><b>{arg.event.title}</b>{sub && <span>{sub}</span>}</div>;
}

// ------------------------------------------------------------------ the card
export function Week({ reloadKey, ghost, onPlanned, onCreate, onPick }: {
  reloadKey: number; ghost: Ghost | null; onPlanned: () => void; onCreate: Create; onPick: (p: Picked, anchor: Anchor) => void;
}) {
  const cal = useRef<FullCalendar>(null);
  const [plan, setPlan] = useState<{ planned_at: string | null; short: { title: string; minutes: number }[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [view, setView] = useState<View>("timeGridWeek");
  const [range, setRange] = useState<{ start: Date; end: Date; current: boolean } | null>(null);
  const [shown, setShown] = useState<{ start: Date; end: Date; allDay?: boolean }[]>([]);

  const events = useCallback((info: EventSourceFuncArg, ok: (e: EventInput[]) => void, fail: (e: Error) => void) => {
    api.week(info.startStr, info.endStr).then((w) => {
      setPlan(w.plan);
      const items = [...w.events.map(meetItem), ...w.blocks.map(blockItem), ...w.deadlines.map(deadlineItem)];
      setShown(items.map((it) => ({ start: new Date(it.start as string | Date), end: new Date(it.end as string | Date), allDay: it.allDay })));
      ok(items);
    }, fail);
  }, []);

  useEffect(() => { cal.current?.getApi().refetchEvents(); }, [reloadKey]);
  // While a card for something new is open, its draft sits on the calendar and follows what you
  // type (Google Calendar's "(ไม่มีชื่อ)"). It is added by hand, so refetching leaves it be.
  useEffect(() => {
    const c = cal.current?.getApi();
    if (!c) return;
    c.getEventById("ghost")?.remove();
    if (ghost) c.addEvent({ id: "ghost", title: ghost.title, start: ghost.start, end: ghost.end, allDay: ghost.allDay,
                            classNames: ["ev", ghost.kind === "event" ? "meet" : "dead", "ghost"], extendedProps: { sub: ghost.sub } });
  }, [ghost]);

  const everything = ghost ? [...shown, ghost] : shown;
  const [lo, hi] = hoursFor(everything);
  const anyAllDay = everything.some((it) => it.allDay);
  const pad = (n: number) => String(n).padStart(2, "0");

  const go = (fn: (c: ReturnType<FullCalendar["getApi"]>) => void) => { const c = cal.current?.getApi(); if (c) fn(c); };
  const switchView = (v: View) => { setView(v); go((c) => c.changeView(v)); };
  const dates = (arg: DatesSetArg) => {
    const now = Date.now();
    setRange({ start: arg.view.currentStart, end: arg.view.currentEnd,
               current: arg.view.currentStart.getTime() <= now && now < arg.view.currentEnd.getTime() });
  };
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

  const head = range ? heading(view, range.start, range.end) : { title: "", sub: "" };
  const arrow = "size-7 grid place-items-center rounded-full text-ink-2 hover:bg-panel-2 cursor-pointer";
  const title = (
    <span className="flex items-center gap-2 min-w-0">
      <span className="font-semibold text-[15px] whitespace-nowrap">{head.title}</span>
      <span className="text-xs text-muted font-normal whitespace-nowrap">{head.sub}</span>
      <span className="flex items-center ml-1">
        <button type="button" aria-label="ก่อนหน้า" className={arrow} onClick={() => go((c) => c.prev())}><Icon name="back" size={16} /></button>
        <button type="button" aria-label="ถัดไป" className={arrow} onClick={() => go((c) => c.next())}><Icon name="arrow" size={16} /></button>
      </span>
      {range && !range.current && (
        <button type="button" className="text-xs font-semibold text-accent-strong hover:underline cursor-pointer" onClick={() => go((c) => c.today())}>
          กลับวันนี้</button>
      )}
    </span>
  );

  return (
    <div className="flex flex-col gap-2 min-w-0">
      <Card title={title} right={
        <div className="flex items-center gap-2">
          <Button sm kind="p" icon="plus" onClick={() => onCreate(null, null)}>สร้าง</Button>
          <Seg options={VIEWS} value={view} onChange={switchView} />
          <Button sm icon="refresh" disabled={busy} onClick={replan}
            title={plan?.planned_at ? `วางล่าสุด ${when(plan.planned_at)}` : undefined}>{busy ? "กำลังวาง…" : "วางตารางใหม่"}</Button>
        </div>}>
        <div className="flex flex-col gap-3">
          {note && <p className="text-sm text-ink-2">{note}</p>}
          {!!plan?.short.length && (
            <Banner icon="clock">
              <b>เวลาไม่พอก่อนกำหนดส่ง:</b> {plan.short.map((s) => `${s.title} ขาด ${duration(s.minutes)}`).join(" · ")}
              <span className="text-muted"> · ลองลดเวลาที่ใช้ เพิ่มเวลาต่อวันของงาน เปลี่ยนเวลาทำงานใน{" "}
                <Link to="/settings#rules" className="underline hover:text-ink">กติกาตาราง</Link> หรือย้ายนัดออก</span>
            </Banner>
          )}
          <div className="schedule-cal">
            <FullCalendar ref={cal} plugins={[timeGridPlugin, dayGridPlugin, interactionPlugin]} locale={thLocale}
              initialView="timeGridWeek" firstDay={1} headerToolbar={false} height="auto"
              slotMinTime={`${pad(lo)}:00:00`} slotMaxTime={`${pad(hi)}:00:00`} slotDuration="00:30:00" slotLabelInterval="02:00"
              slotLabelFormat={{ hour: "2-digit", minute: "2-digit", hour12: false }}
              allDaySlot={anyAllDay} allDayText="ทั้งวัน" dayHeaderContent={dayHeader} dayHeaderFormat={{ weekday: "short" }}
              eventContent={eventContent} displayEventTime={false} eventMinHeight={18} dayMaxEvents={3} nowIndicator
              stickyHeaderDates={false}
              selectable selectMirror selectLongPressDelay={300} select={select}
              events={events} eventClick={click} datesSet={dates} />
          </div>
        </div>
      </Card>
      <div className="flex flex-wrap gap-x-3 gap-y-1 px-1 text-xs text-muted">
        {LEGEND.map(([c, label]) => <span key={label} className="inline-flex items-center gap-1.5"><i className={`size-2 rounded-full ${c}`} />{label}</span>)}
      </div>
    </div>
  );
}
