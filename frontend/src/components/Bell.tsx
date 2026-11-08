// The bell in the top bar: what waits for your decision: plans from Opus (B1), appointments
// from email (B2), Classroom courses to follow (B3). B4's today page later gathers them in one place.
import { useCallback, useEffect, useRef, useState } from "react";
import { answeredAlready, api, type Decision } from "../api";
import { Icon } from "../icons";
import { useStatus } from "../status";
import { DecisionRow } from "./Decisions";
import { useDismiss } from "./popover";
import { Button, Spinner } from "./ui";

// รับ · ไม่ไป for an appointment from someone who isn't important (B2), with ย้อนกลับ after รับ.
// onChange: the page around it re-reads what it shows (the schedule redraws the calendar).
// Answered elsewhere (#อนุมัติ, the chat, another copy of these buttons): a press shows how instead.
export function AppointmentActions({ decisionId, onChange }: { decisionId: number; onChange?: () => void }) {
  const { refresh } = useStatus();
  const [state, setState] = useState<"open" | "placed" | "declined" | "undone">("open");
  const [actionId, setActionId] = useState<number | null>(null);
  const [answered, setAnswered] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await fn(); onChange?.(); } catch (e) {
      if (answeredAlready(e)) { setAnswered(e.message); if (onChange) setTimeout(onChange, 1500); } // let it be read first
      else setError((e as Error).message); // couldn't be done (the calendar): the buttons stay
    } finally { setBusy(false); refresh(); }
  };
  const answer = (accept: boolean) => run(async () => {
    const r = await api.answerAppointment(decisionId, accept);
    setActionId(r.action_id); setState(accept ? "placed" : "declined");
  });
  const undo = () => run(async () => {
    try { if (actionId) await api.undo(actionId); } catch (e) { if (!answeredAlready(e)) throw e; } // undone elsewhere: the same
    setState("undone");
  });
  if (answered) return <p className="text-sm text-muted">{answered}</p>;
  return (
    <div className="flex flex-col gap-1.5">
      {state === "open" && (
        <div className="flex gap-2">
          <Button kind="ok" sm disabled={busy} onClick={() => answer(true)}>รับ</Button>
          <Button sm disabled={busy} onClick={() => answer(false)}>ไม่ไป</Button>
        </div>
      )}
      {state === "placed" && <div className="flex gap-2 items-center text-sm">✅ ลงปฏิทินแล้ว <Button sm disabled={busy} onClick={undo}>ย้อนกลับ</Button></div>}
      {state === "declined" && <p className="text-sm text-muted">ไม่ไปนัดนี้</p>}
      {state === "undone" && <p className="text-sm text-muted">↩️ เอาออกจากปฏิทินแล้ว</p>}
      {error && <p className="text-xs text-bad">{error}</p>}
    </div>
  );
}

// ติดตาม · ไม่ติดตาม for a Classroom course (B3). The folder can be changed before following.
export function CourseActions({ decisionId, folder: proposed, exists }: { decisionId: number; folder: string; exists: boolean }) {
  const { refresh } = useStatus();
  const [folder, setFolder] = useState(proposed);
  const [state, setState] = useState<"open" | "followed" | "ignored" | "undone">("open");
  const [actionId, setActionId] = useState<number | null>(null);
  const [answered, setAnswered] = useState(""); // answered elsewhere: how, in place of the buttons
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await fn(); } catch (e) {
      if (answeredAlready(e)) setAnswered(e.message); else setError((e as Error).message);
    } finally { setBusy(false); refresh(); }
  };
  const answer = (follow: boolean) => run(async () => {
    const r = await api.answerCourse(decisionId, follow, follow ? folder : undefined);
    setActionId(r.action_id); setState(follow ? "followed" : "ignored");
  });
  const undo = () => run(async () => {
    try { if (actionId) await api.undo(actionId); } catch (e) { if (!answeredAlready(e)) throw e; } // undone elsewhere: the same
    setState("undone");
  });
  if (answered) return <p className="text-sm text-muted">{answered}</p>;
  return (
    <div className="flex flex-col gap-1.5">
      {state === "open" && (
        <>
          <label className="text-xs text-muted flex flex-col gap-1">เก็บสื่อที่{!exists && folder === proposed && " (โฟลเดอร์ใหม่ สร้างเมื่อกดติดตาม)"}
            <input value={folder} onChange={(e) => setFolder(e.target.value)}
              className="bg-panel border border-line-2 rounded-lg px-2 py-1 text-ink text-xs font-mono" />
          </label>
          <div className="flex gap-2">
            <Button kind="p" sm disabled={busy || !folder.trim()} onClick={() => answer(true)}>ติดตาม</Button>
            <Button sm disabled={busy} onClick={() => answer(false)}>ไม่ติดตาม</Button>
          </div>
        </>
      )}
      {state === "followed" && <div className="flex gap-2 items-center text-sm">✅ ติดตามแล้ว <Button sm disabled={busy} onClick={undo}>ย้อนกลับ</Button></div>}
      {state === "ignored" && <div className="flex gap-2 items-center text-sm text-muted">ไม่ติดตามวิชานี้ <Button sm disabled={busy} onClick={undo}>ย้อนกลับ</Button></div>}
      {state === "undone" && <p className="text-sm text-muted">↩️ ย้อนกลับแล้ว · ยังรอคำตอบอยู่</p>}
      {error && <p className="text-xs text-bad">{error}</p>}
    </div>
  );
}

export function Bell() {
  const { status } = useStatus();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Decision[] | null>(null);
  const wrap = useRef<HTMLDivElement>(null);
  useDismiss(wrap, open, useCallback(() => setOpen(false), []));
  const count = status?.pending ?? 0;
  const load = useCallback(() => { api.decisions().then((r) => setItems(r.items), () => setItems([])); }, []);

  useEffect(() => { if (open) load(); }, [open, load]);

  return (
    <div ref={wrap} className="relative">
      <button type="button" title="เรื่องที่รอคุณ" onClick={() => setOpen((o) => !o)}
        className="relative size-9 rounded-full border border-line-2 text-ink-2 grid place-items-center cursor-pointer hover:bg-panel-2">
        <Icon name="bell" />
        {count > 0 && (
          // the plan's .ibx .n: a red number
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-bad text-white font-mono text-[10.5px] font-semibold grid place-items-center">
            {count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-[calc(100%+10px)] z-20 w-[min(520px,92vw)] max-h-[70vh] overflow-auto bg-panel border border-line rounded-card p-4
          shadow-[0_18px_50px_rgba(0,0,0,0.22)] flex flex-col gap-1">
          <span className="font-semibold">เรื่องที่รอคุณ</span>
          {items === null && <Spinner />}
          {items?.length === 0 && <p className="text-sm text-muted">ไม่มีเรื่องที่รอ</p>}
          {!!items?.length && <ul className="divide-y divide-line">{items.map((d) => <DecisionRow key={d.id} d={d} />)}</ul>}
        </div>
      )}
    </div>
  );
}
