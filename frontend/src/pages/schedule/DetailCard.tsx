// The card that opens when you click something on the calendar (like Google Calendar's event
// card): what it is, when, where it came from, and what you can do with it. Appointments are
// changed in Google Calendar itself; blocks and due dates lead to their task (แก้งาน, ทำเสร็จแล้ว).
import { useState, type ReactNode } from "react";
import { api, type BlockItem, type CalItem, type DeadlineItem, type TaskRow } from "../../api";
import { AppointmentActions } from "../../components/Bell";
import { Button } from "../../components/ui";
import { duration, hm, shortDay, when, ymd } from "../../format";
import { Icon, type IconName } from "../../icons";
import type { Done } from "./EditCard";
import { Floating, type Anchor } from "./Floating";
import { Linked, sourceLabel } from "./links";

export type Picked =
  | { type: "meet"; ev: CalItem }
  | { type: "block"; block: BlockItem }
  | { type: "deadline"; d: DeadlineItem };

const CAME_FROM: Record<string, string> = {
  email: "เลขาลงให้จากอีเมล", calendar: "อยู่ในปฏิทิน Google ของคุณ", you: "คุณเพิ่มจากหน้านี้",
};

/** "พฤ. 12 พ.ย. · 10:00–11:30", or "พฤ. 12 พ.ย. – ศ. 13 พ.ย. · ทั้งวัน". */
function span(startIso: string, endIso: string, allDay: boolean): string {
  const s = new Date(startIso), e = new Date(endIso);
  if (allDay) {
    const last = new Date(e.getTime() - 86_400_000); // the end is the midnight after the last day
    return ymd(s) === ymd(last) ? `${shortDay(s)} · ทั้งวัน` : `${shortDay(s)} – ${shortDay(last)} · ทั้งวัน`;
  }
  return ymd(s) === ymd(e) ? `${shortDay(s)} · ${hm(s)}–${hm(e)}` : `${shortDay(s)} ${hm(s)} – ${shortDay(e)} ${hm(e)}`;
}

function Line({ icon, children }: { icon: IconName; children: ReactNode }) {
  return <div className="flex gap-2.5 items-start text-sm text-ink-2"><Icon name={icon} size={16} className="text-muted mt-0.5 shrink-0" /><div className="min-w-0">{children}</div></div>;
}

function LinkButton({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener"
      className="inline-flex items-center gap-1.5 rounded-full border border-line-2 bg-panel hover:bg-panel-2 text-xs font-medium px-3 py-1 whitespace-nowrap">
      <Icon name="ext" size={14} />{children}</a>
  );
}

export function DetailCard({ picked, task, anchor, onClose, onEdit, onDone, onChanged }: {
  picked: Picked; task: TaskRow | undefined; anchor: Anchor; onClose: () => void;
  onEdit: (t: TaskRow) => void; onDone: (d: Done) => void; onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const finish = async (t: TaskRow) => {
    setBusy(true); setError("");
    try { onDone({ text: `ทำเสร็จแล้ว: ${t.title}`, saved: await api.taskDone(t.id) }); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  let swatch: string, title: string, time: string;
  let body: ReactNode;
  if (picked.type === "meet" && picked.ev.status === "proposed") {
    // waiting for you: the same รับ / ไม่ไป as in the bell and #อนุมัติ (W5 ④ ⑦)
    const e = picked.ev;
    [swatch, title, time] = ["miss", `${e.title}?`, span(e.start, e.end, e.all_day)];
    body = <>
      <Line icon="mail">รอคุณรับ{e.from ? ` · ${e.from} ส่งมา` : ""}{e.location ? ` · ${e.location}` : ""}</Line>
      {e.description && <Line icon="notes"><Linked text={e.description} className="max-h-48 overflow-y-auto text-ink" /></Line>}
      {e.decision_id != null && <AppointmentActions decisionId={e.decision_id} onChange={onChanged} />}
      {e.mail && <div className="pt-1"><LinkButton href={e.mail}>เปิดอีเมล</LinkButton></div>}
    </>;
  } else if (picked.type === "meet") {
    const e = picked.ev;
    [swatch, title, time] = ["meet", e.title, span(e.start, e.end, e.all_day)];
    body = <>
      {e.location && <Line icon="pin">{e.location}</Line>}
      {e.description && <Line icon="notes"><Linked text={e.description} className="max-h-48 overflow-y-auto text-ink" /></Line>}
      <Line icon="calendar">{CAME_FROM[e.source] ?? e.source_name}</Line>
      <Line icon="bell">{e.recurring ? "นัดซ้ำทุกสัปดาห์: เลขาไม่เตือน แต่บล็อกงานจะหลบช่วงนี้" : "เลขาเตือนใน #ด่วน ก่อนถึงเวลา · บล็อกงานจะหลบช่วงนี้"}</Line>
      <div className="flex flex-wrap gap-2 pt-1">
        {e.link && <LinkButton href={e.link}>เปิดใน Google Calendar</LinkButton>}
        {e.mail && <LinkButton href={e.mail}>เปิดอีเมล</LinkButton>}
      </div>
      <p className="text-xs text-muted">แก้เวลาหรือลบนัดได้ใน Google Calendar · เลขาเห็นการเปลี่ยนในรอบซิงก์ถัดไป</p>
    </>;
  } else {
    const b = picked.type === "block" ? picked.block : null;
    const dl = picked.type === "deadline" ? picked.d : null;
    swatch = b ? (b.task_status === "done" ? "done" : "") : "dead";
    title = b?.title ?? dl!.title;
    time = b ? span(b.start, b.end, false) : `ส่ง ${shortDay(new Date(dl!.due))} ${hm(new Date(dl!.due))}`;
    const need = task ? task.est_minutes ?? task.est_default : 0;
    body = <>
      {b && <Line icon="calendar">บล็อกงานในปฏิทิน “เลขา” ·{" "}
        {!b.past ? (b.pinned ? "คุณย้ายมาเอง เลขาจะไม่ย้ายบล็อกนี้" : "เลขาย้ายได้เมื่อตารางเปลี่ยน ถ้าย้ายเองใน Google Calendar เลขาจะไม่ย้ายอีก")
          : b.outcome === "done" ? `ทำแล้ว · ทำจริง ${duration(b.worked ?? 0)} (จาก ActivityWatch)`
          : b.outcome === "missed" ? `หลุดแผน${b.instead ? ` · ช่วงนี้คุณทำ ${b.instead}` : ""} · ทำจริง ${duration(b.worked ?? 0)} ที่เหลือกลับไปที่งานให้หาเวลาใหม่`
          : b.outcome === "away" ? "ไม่ได้ใช้คอมช่วงนี้ · นับว่าทำแล้ว (อาจทำนอกคอม)"
          : b.outcome === "unknown" ? "ช่วงนี้ไม่ได้บันทึกการใช้เวลา · นับว่าทำแล้ว"
          : "ผ่านไปแล้ว นับว่าทำแล้ว"}</Line>}
      {b?.outcome === "missed" && (
        <div className="flex"><Button sm icon="check" disabled={busy} onClick={async () => {
          setBusy(true); setError("");
          try { const r = await api.blockDone(b.id); onDone({ text: `นับว่าทำแล้ว: ${b.title}`, saved: { action_id: r.action_id, plan: null } }); }
          catch (e) { setError((e as Error).message); } finally { setBusy(false); }
        }}>นับว่าทำแล้ว (ทำนอกคอม)</Button></div>
      )}
      {task ? <Line icon="clock">{task.due ? `ส่ง ${when(task.due)}` : "ไม่มีกำหนดส่ง"} · {task.source}
        <span className="block text-muted">จองแล้ว {duration(task.done_minutes + task.booked_minutes)} จาก {duration(need)}</span></Line>
        : <Line icon="clock">{dl?.source ?? "งานนี้ปิดไปแล้ว"}</Line>}
      {task?.details && <Line icon="notes"><Linked text={task.details} className="max-h-48 overflow-y-auto text-ink" /></Line>}
      {task?.status === "open" && (
        <div className="flex flex-wrap gap-2 pt-1">
          <Button sm icon="check" disabled={busy} onClick={() => finish(task)}>ทำเสร็จแล้ว</Button>
          <Button sm icon="edit" onClick={() => onEdit(task)}>แก้งาน</Button>
          {task.link && <LinkButton href={task.link}>{sourceLabel(task.source)}</LinkButton>}
        </div>
      )}
      {!task && dl?.link && <div className="pt-1"><LinkButton href={dl.link}>{sourceLabel(dl.source)}</LinkButton></div>}
    </>;
  }

  return (
    <Floating anchor={anchor} onClose={onClose} width={380}>
      <div className="p-4 pt-3 flex flex-col gap-2.5">
        <div className="flex items-start gap-3">
          <i className={`swatch ${swatch} mt-2 shrink-0`} />
          <div className="grow min-w-0">
            <h3 className="text-lg font-semibold leading-snug break-words">{title}</h3>
            <p className="text-sm text-ink-2">{time}</p>
          </div>
          <button type="button" aria-label="ปิด" onClick={onClose} className="text-muted hover:text-ink cursor-pointer p-1"><Icon name="x" size={16} /></button>
        </div>
        {body}
        {error && <p className="text-sm text-bad">{error}</p>}
      </div>
    </Floating>
  );
}
