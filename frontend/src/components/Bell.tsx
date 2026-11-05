// The bell in the top bar: what waits for your decision. In B1 that's plans from Opus;
// B4's today page later gathers every kind in one place.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Decision } from "../api";
import { when } from "../format";
import { Icon } from "../icons";
import { useStatus } from "../status";
import { PlanActions } from "./PlanActions";
import { useDismiss } from "./popover";
import { Markdown, Spinner } from "./ui";

export function Bell() {
  const { status } = useStatus();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Decision[] | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const wrap = useRef<HTMLDivElement>(null);
  useDismiss(wrap, open, useCallback(() => setOpen(false), []));
  const count = status?.pending ?? 0;

  useEffect(() => {
    if (open) api.decisions().then((r) => setItems(r.items), () => setItems([]));
  }, [open]);

  return (
    <div ref={wrap} className="relative">
      <button type="button" title="เรื่องที่รอคุณ" onClick={() => setOpen((o) => !o)}
        className="relative size-9 rounded-full border border-line-2 text-ink-2 grid place-items-center cursor-pointer hover:bg-panel-2">
        <Icon name="bell" />
        {count > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-accent text-accent-ink text-[11px] font-semibold grid place-items-center">
            {count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-[calc(100%+10px)] z-20 w-[min(520px,92vw)] max-h-[70vh] overflow-auto bg-panel border border-line rounded-card p-4
          shadow-[0_18px_50px_rgba(0,0,0,0.22)] flex flex-col gap-3">
          <span className="font-semibold">เรื่องที่รอคุณ</span>
          {items === null && <Spinner />}
          {items?.length === 0 && <p className="text-sm text-muted">ไม่มีเรื่องที่รอ</p>}
          {items?.map((d) => (
            <div key={d.id} className="border-t border-line pt-3 flex flex-col gap-2 first-of-type:border-0 first-of-type:pt-0">
              <button type="button" className="text-left cursor-pointer" onClick={() => setExpanded(expanded === d.id ? null : d.id)}>
                <div className="font-medium">{d.title}</div>
                <div className="text-xs text-muted">
                  {["แผน", when(d.created_at), d.model && `${d.model} effort ${d.effort}`, expanded === d.id ? "ซ่อน" : "ดูแผน"].filter(Boolean).join(" · ")}
                </div>
              </button>
              {expanded === d.id && <Markdown text={d.plan} />}
              <PlanActions decisionId={d.id} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
