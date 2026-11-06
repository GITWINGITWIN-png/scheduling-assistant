// The "บันทึกแล้ว · เลิกทำ" bar at the bottom after a change (first made for the schedule page,
// now used by every page that changes something): it says what was done and offers to undo it.
import { useEffect, useState } from "react";

export type ToastMsg = { text: string; actionId: number | null; key: number };

export function Toast({ msg, onUndo, onClose }: { msg: ToastMsg | null; onUndo: (actionId: number) => Promise<void>; onClose: () => void }) {
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(onClose, 10_000);
    return () => clearTimeout(t);
  }, [msg, onClose]);
  if (!msg) return null;
  return (
    <div className="fixed z-50 left-4 bottom-4 max-w-[min(520px,calc(100vw-32px))] flex items-center gap-3 rounded-s bg-ink text-panel px-4 py-2.5 text-sm shadow-[0_8px_30px_rgba(0,0,0,0.3)]">
      <span className="grow">{msg.text}</span>
      {msg.actionId !== null && (
        <button type="button" disabled={busy} className="font-semibold text-accent-soft hover:underline cursor-pointer disabled:opacity-50"
          onClick={async () => { setBusy(true); try { await onUndo(msg.actionId!); } finally { setBusy(false); } }}>เลิกทำ</button>
      )}
      <button type="button" aria-label="ปิด" className="opacity-70 hover:opacity-100 cursor-pointer" onClick={onClose}>✕</button>
    </div>
  );
}
