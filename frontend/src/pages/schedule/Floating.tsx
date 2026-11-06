// Two pieces the schedule page shares, both modelled on Google Calendar:
// - Floating: a card that opens next to where you clicked (the quick-create card and the
//   event card), in the middle of the screen when there is no click to sit next to, and as
//   a sheet along the bottom on a phone. A click outside it or Esc closes it.
// - Toast: the "บันทึกแล้ว · เลิกทำ" bar at the bottom after a change.
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useDismiss } from "../../components/popover";

export type Anchor = { x: number; y: number } | null;

const GAP = 16; // from the click, and from the window's edges

export function Floating({ anchor, onClose, children, width = 400 }: {
  anchor: Anchor; onClose: () => void; children: ReactNode; width?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const [narrow, setNarrow] = useState(() => window.innerWidth < 640);
  useDismiss(ref, true, onClose);

  // Place it beside the click (right of it, or left when there's no room), kept inside the
  // window. It is measured again whenever its height changes (switching กิจกรรม/งาน).
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const place = () => {
      const vw = window.innerWidth, vh = window.innerHeight;
      setNarrow(vw < 640);
      const w = el.offsetWidth, h = el.offsetHeight;
      const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(v, hi));
      if (!anchor) {
        setPos({ left: (vw - w) / 2, top: clamp((vh - h) / 2, GAP, vh - h - GAP) });
        return;
      }
      let left = anchor.x + GAP;
      if (left + w > vw - GAP) left = anchor.x - w - GAP;
      setPos({ left: clamp(left, GAP, vw - w - GAP), top: clamp(anchor.y - 60, GAP, Math.max(GAP, vh - h - GAP)) });
    };
    place();
    const watch = new ResizeObserver(place);
    watch.observe(el);
    window.addEventListener("resize", place);
    return () => { watch.disconnect(); window.removeEventListener("resize", place); };
  }, [anchor]);

  const style = narrow ? undefined : { left: pos?.left ?? 0, top: pos?.top ?? 0, width, visibility: pos ? undefined : "hidden" as const };
  return (
    <div ref={ref} role="dialog" style={style}
      className={`float-card fixed z-50 bg-panel border border-line text-ink shadow-[0_14px_44px_rgba(0,0,0,0.28)]
        ${narrow ? "inset-x-0 bottom-0 rounded-t-card max-h-[85vh] overflow-y-auto" : "rounded-card max-h-[calc(100vh-32px)] overflow-y-auto"}`}>
      {children}
    </div>
  );
}

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
