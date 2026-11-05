// ใช้แผนนี้ · แก้ · ไม่เอา under a plan from Opus, with ย้อนกลับ after deciding (D7 on the web).
import { useState } from "react";
import { api, type Answer } from "../api";
import { useStatus } from "../status";
import { Button, Spinner } from "./ui";

export function PlanActions({ decisionId, onRevised }: { decisionId: number; onRevised?: (a: Answer) => void }) {
  const { refresh } = useStatus();
  const [state, setState] = useState<"open" | "approved" | "rejected" | "revised">("open");
  const [actionId, setActionId] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [change, setChange] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); refresh(); }
  };

  const decide = (action: "approve" | "reject") => run(async () => {
    const r = await api.decide(decisionId, action);
    setActionId(r.action_id);
    setState(action === "approve" ? "approved" : "rejected");
  });
  const undo = () => run(async () => { if (actionId) await api.undo(actionId); setState("open"); setActionId(null); });
  const revise = () => run(async () => {
    const a = await api.revise(decisionId, change);
    setState("revised"); setEditing(false); onRevised?.(a);
  });

  if (state === "revised") return <p className="text-sm text-muted">✏️ แก้แล้ว · ดูแผนใหม่ด้านล่าง</p>;
  return (
    <div className="flex flex-col gap-2">
      {state === "open" && !editing && (
        <div className="flex gap-2 flex-wrap">
          <Button kind="p" sm disabled={busy} onClick={() => decide("approve")}>ใช้แผนนี้</Button>
          <Button sm disabled={busy} onClick={() => setEditing(true)}>แก้</Button>
          <Button sm disabled={busy} onClick={() => decide("reject")}>ไม่เอา</Button>
        </div>
      )}
      {state !== "open" && (
        <div className="flex items-center gap-2 text-sm">
          <span>{state === "approved" ? "✅ ใช้แผนนี้แล้ว · เลขาเริ่มงานเองได้เมื่อถึง B5" : "ไม่เอาแผนนี้"}</span>
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
