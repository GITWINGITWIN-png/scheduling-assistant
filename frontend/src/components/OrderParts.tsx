// What an order in the chat did, and what waits for Do it now (B9): the same list and buttons as under
// the answer in #talk-to-secretary. Revert undoes one thing, and the others stay; Do it now carries out what
// can't be undone, once. A button answered elsewhere (Discord, the bell) says what happened when
// pressed, instead of an error next to buttons that look as if they still work.
import { useState } from "react";
import { answeredAlready, api, type ConfirmItem, type DoneItem } from "../api";
import { useStatus } from "../status";
import { Button } from "./ui";

export function OrderParts({ done = [], confirms = [] }: { done?: DoneItem[]; confirms?: ConfirmItem[] }) {
  if (!done.length && !confirms.length) return null;
  return (
    <div className="flex flex-col gap-2.5 rounded-s border border-line bg-panel-2 px-3 py-2.5 text-sm">
      {confirms.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-semibold text-warn">รอคุณกดยืนยัน (ย้อนกลับไม่ได้)</span>
          {confirms.map((c) => <ConfirmLine key={c.id} item={c} />)}
        </div>
      )}
      {done.length > 0 && (
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold text-ink-2">เลขาทำแล้ว</span>
          {done.map((d, i) => <DoneLine key={d.id} n={i + 1} item={d} />)}
        </div>
      )}
    </div>
  );
}

function DoneLine({ n, item }: { n: number; item: DoneItem }) {
  const { refresh } = useStatus();
  const [state, setState] = useState<"" | "busy" | "undone">("");
  const [error, setError] = useState("");
  const undo = async () => {
    setState("busy"); setError("");
    try { await api.undo(item.id); setState("undone"); refresh(); } catch (e) {
      if (answeredAlready(e)) setState("undone"); // undone already, elsewhere: the same thing
      else { setError((e as Error).message); setState(""); }
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
      <span className={`grow min-w-0 basis-48 ${state === "undone" ? "line-through text-muted" : ""}`}>
        {n}. {item.summary}{item.target && <span className="text-ink-2"> · {item.target}</span>}</span>
      {item.can_undo && (state === "undone"
        ? <span className="text-xs text-muted whitespace-nowrap">↩️ ย้อนแล้ว</span>
        : <Button sm kind="ghost" icon="undo" disabled={state === "busy"} onClick={undo}>ย้อนกลับ</Button>)}
      {error && <span className="basis-full text-xs text-bad">{error}</span>}
    </div>
  );
}

function ConfirmLine({ item }: { item: ConfirmItem }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
      <span className="grow min-w-0 basis-48">{item.title}</span>
      <ConfirmButtons id={item.id} />
    </div>
  );
}

/** Do it now / No thanks for one order (also the bell's row for it). Once pressed, it says what happened. */
export function ConfirmButtons({ id, onDone }: { id: number; onDone?: () => void }) {
  const { refresh } = useStatus();
  const [said, setSaid] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const settle = (text: string) => {
    setSaid(text); refresh();
    if (onDone) setTimeout(onDone, 1500); // the bell drops the row: let the result show first
  };
  const answer = async (yes: boolean) => {
    setBusy(true); setError("");
    try { settle((await api.confirmOrder(id, yes)).text); } catch (e) {
      if (answeredAlready(e)) settle(e.message); // answered elsewhere, or expired: say what happened
      else setError((e as Error).message); // doing it failed: nothing was done, the buttons stay
    }
    setBusy(false);
  };
  if (said) return <span className="text-xs text-ink-2">{said}</span>;
  return (
    <>
      <Button sm kind="p" disabled={busy} onClick={() => answer(true)}>ทำเลย</Button>
      <Button sm disabled={busy} onClick={() => answer(false)}>ไม่เอา</Button>
      {error && <span className="basis-full text-xs text-bad">{error}</span>}
    </>
  );
}
