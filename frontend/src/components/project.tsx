import { useState } from "react";

// Small pieces the projects, jobs and today pages share, drawn as the plan's mockups draw them
// (look.css .rank, .urg, .meter): a project's potential letter, its urgency bars, a meter, and the
// quota line's editor (the jobs page and the rule book both change it).

const RANK: Record<string, string> = { S: "#D99A1E", A: "#A855C9", B: "#2F55D4", C: "#1D9A8A", D: "#9AA3B1", F: "#9C8F86" };

/** potential S–F as a coloured letter; "?" while it isn't set. */
export function Rank({ potential, set = true }: { potential: string; set?: boolean }) {
  return (
    <span title={set ? `potential ${potential}` : "ยังไม่ตั้งระดับ"}
      className="size-6 shrink-0 rounded-[7px] grid place-items-center text-[12.5px] font-bold text-white"
      style={{ background: set ? RANK[potential] ?? RANK.D : "#9C8F86" }}>
      {set ? potential : "?"}
    </span>
  );
}

/** Urgency 0–5 (5 = most urgent) as five bars: red from 4, amber 2–3, grey below. */
export function Urgency({ level }: { level: number }) {
  const on = level >= 4 ? "bg-bad" : level >= 2 ? "bg-warn" : "bg-muted";
  return (
    <span title={`ความเร่งด่วน ${level} (5 = เร่งสุด)`} className="inline-flex items-end gap-0.5 shrink-0">
      {[0, 1, 2, 3, 4].map((i) => <i key={i} className={`block w-1 h-3 rounded-sm ${i < level ? on : "bg-line-2"}`} />)}
    </span>
  );
}

/** A bar filled to `value` % (0–100), with an optional mark (the 70% line, the budget's end). */
export function Meter({ value, tone = "accent", mark, thick = false }: { value: number; tone?: "accent" | "ok" | "warn" | "bad"; mark?: number; thick?: boolean }) {
  const fill = { accent: "bg-accent", ok: "bg-ok", warn: "bg-warn", bad: "bg-bad" }[tone];
  return (
    <div className={`relative rounded-full bg-panel-2 border border-line ${thick ? "h-3" : "h-2"}`}>
      <i className={`block h-full rounded-full ${fill}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      {mark !== undefined && <i className="absolute -top-[5px] -bottom-[5px] w-0.5 rounded-sm bg-ink" style={{ left: `${mark}%` }} />}
    </div>
  );
}

/** The quota line (the rule "งานเบื้องหลังทำเองได้เมื่อโควตาเหลือเกิน 70%"): a number and บันทึก. */
export function LineEditor({ line, onSave, onCancel }: { line: number; onSave: (line: number) => void; onCancel: () => void }) {
  const [value, setValue] = useState(String(line));
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5 text-[13px]">
      <span className="text-ink-2">ทำเองได้เมื่อโควตาสัปดาห์เหลือเกิน</span>
      <input type="number" min={10} max={100} value={value} onChange={(e) => setValue(e.target.value)} autoFocus
        onKeyDown={(e) => e.key === "Enter" && onSave(Number(value))}
        className="w-16 h-8 rounded-s border border-line-2 bg-panel px-2 text-right font-mono" />
      <span className="text-ink-2">%</span>
      <button type="button" onClick={() => onSave(Number(value))}
        className="rounded-full bg-accent text-accent-ink hover:bg-accent-strong px-3 py-1 text-xs font-medium cursor-pointer">บันทึก</button>
      <button type="button" onClick={onCancel} className="rounded-full px-3 py-1 text-xs text-ink-2 hover:bg-panel-2 cursor-pointer">ยกเลิก</button>
    </span>
  );
}
