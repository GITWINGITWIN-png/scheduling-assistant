// ใช้แผนนี้ · แก้ · ไม่เอา under a plan from Opus (D7 on the web). Since B9 an approved plan is
// carried out at once: this watches it and shows what was done, with ย้อนกลับ for each thing.
// The same plan can have buttons in several places (under the answer, the bell, the today page,
// Discord). Pressing a copy that was answered elsewhere shows what happened instead of an error.
import { useEffect, useState } from "react";
import { answeredAlready, api, type Answer, type PlanRun } from "../api";
import { useStatus } from "../status";
import { OrderParts } from "./OrderParts";
import { Button, Markdown, Spinner } from "./ui";

const WATCH_MS = 3000; // how often to ask how carrying out the plan is going

export function PlanActions({ decisionId, onRevised }: { decisionId: number; onRevised?: (a: Answer) => void }) {
  const { refresh } = useStatus();
  const [state, setState] = useState<"open" | "approved" | "rejected" | "revised">("open");
  const [actionId, setActionId] = useState<number | null>(null);
  const [run, setRun] = useState<PlanRun | null>(null);
  const [tries, setTries] = useState(0); // a failed look at the run (the service restarting): look again
  const [answered, setAnswered] = useState(""); // answered somewhere else: what happened, in place of the buttons
  const [editing, setEditing] = useState(false);
  const [change, setChange] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Answered already: if it was approved, follow its run here as if it had been approved here
  const showAnswered = async (said: string) => {
    const r = await api.planRun(decisionId).catch(() => null);
    if (r && r.status !== "none") { setRun(r); setState("approved"); } else setAnswered(said);
  };

  const act = async (fn: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await fn(); } catch (e) {
      if (answeredAlready(e)) await showAnswered(e.message); else setError((e as Error).message);
    } finally { setBusy(false); refresh(); }
  };

  // after ใช้แผนนี้: ask every few seconds until the secretary has finished carrying it out
  useEffect(() => {
    if (state !== "approved" || (run && run.status !== "running" && run.status !== "none")) return;
    const t = setTimeout(() => { api.planRun(decisionId).then(setRun, () => setTries((n) => n + 1)); }, WATCH_MS);
    return () => clearTimeout(t);
  }, [state, run, decisionId, tries]);
  useEffect(() => { if (run && (run.status === "done" || run.status === "failed")) refresh(); }, [run, refresh]);

  const decide = (action: "approve" | "reject") => act(async () => {
    const r = await api.decide(decisionId, action);
    setActionId(r.action_id);
    setState(action === "approve" ? "approved" : "rejected");
  });
  const undo = () => act(async () => {
    try { if (actionId) await api.undo(actionId); } catch (e) { if (!answeredAlready(e)) throw e; } // undone elsewhere: the same
    setState("open"); setActionId(null);
  });
  const revise = () => act(async () => {
    const a = await api.revise(decisionId, change);
    setState("revised"); setEditing(false); onRevised?.(a);
  });

  if (answered) return <p className="text-sm text-muted">{answered}</p>;
  if (state === "revised") return <p className="text-sm text-muted">✏️ แก้แล้ว · ดูแผนใหม่ด้านล่าง</p>;
  if (state === "approved") {
    const finished = run && (run.status === "done" || run.status === "failed");
    return (
      <div className="flex flex-col gap-2">
        <span className="text-sm">✅ ใช้แผนนี้แล้ว · {finished ? (run!.status === "done" ? "เลขาทำตามแผนแล้ว" : "เลขาทำตามแผนไม่จบ")
          : "เลขากำลังลงมือทำตามแผน…"}</span>
        {!finished && <Spinner label="Opus กำลังทำตามแผน (ผลจะขึ้นใน #คุยกับเลขา ด้วย)" />}
        {finished && run!.text && <Markdown text={run!.text} />}
        {finished && <OrderParts done={run!.done} confirms={run!.confirms} />}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      {state === "open" && !editing && (
        <div className="flex gap-2 flex-wrap">
          <Button kind="p" sm disabled={busy} onClick={() => decide("approve")}>ใช้แผนนี้</Button>
          <Button sm disabled={busy} onClick={() => setEditing(true)}>แก้</Button>
          <Button sm disabled={busy} onClick={() => decide("reject")}>ไม่เอา</Button>
        </div>
      )}
      {state === "rejected" && (
        <div className="flex items-center gap-2 text-sm">
          <span>ไม่เอาแผนนี้</span>
          <Button sm kind="ghost" icon="undo" disabled={busy} onClick={undo}>ย้อนกลับ</Button>
        </div>
      )}
      {editing && (
        <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); if (change.trim()) revise(); }}>
          <textarea value={change} onChange={(e) => setChange(e.target.value)} rows={3} autoFocus
            placeholder="อยากให้แก้ตรงไหน เช่น ย้ายเวลาทำสไลด์เป็นวันพุธ"
            className="w-full rounded-s border border-line-2 bg-panel px-3 py-2 text-sm outline-none focus:border-accent" />
          <div className="flex gap-2">
            <Button kind="p" sm type="submit" disabled={busy || !change.trim()}>ให้ Opus แก้แผน</Button>
            <Button sm kind="ghost" disabled={busy} onClick={() => setEditing(false)}>ยกเลิก</Button>
          </div>
        </form>
      )}
      {busy && <Spinner label={editing ? "Opus กำลังแก้แผน…" : undefined} />}
      {error && <p className="text-sm text-bad">{error}</p>}
    </div>
  );
}
