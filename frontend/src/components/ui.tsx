// The small set of building blocks every page uses, styled like the stage-2 mockups (look.css):
// cards, chips, buttons, segmented filters, banners, and Markdown for the secretary's answers.
import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Icon, type IconName } from "../icons";

export function Card({ title, right, children, flush = false, className = "" }:
  { title?: ReactNode; right?: ReactNode; children: ReactNode; flush?: boolean; className?: string }) {
  return (
    <section className={`bg-panel border border-line rounded-card shadow-card min-w-0 ${className}`}>
      {title && (
        <header className="flex items-center gap-2 px-4 pt-3.5 pb-2.5">
          <h2 className="font-semibold text-[15px] grow">{title}</h2>
          {right}
        </header>
      )}
      <div className={flush ? "" : "px-4 pb-4"}>{children}</div>
    </section>
  );
}

const CHIP_TONES = {
  acc: "bg-accent-soft text-accent-strong",
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  muted: "bg-panel-2 text-muted",
} as const;

export function Chip({ children, tone = "muted", title }: { children: ReactNode; tone?: keyof typeof CHIP_TONES; title?: string }) {
  return <span title={title} className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${CHIP_TONES[tone]}`}>{children}</span>;
}

/** A "comes in Bx" chip, for anything planned for a later phase. */
export function Phase({ phase }: { phase: string }) {
  return <Chip tone="muted" title={`มาในช่วง ${phase}`}>{phase}</Chip>;
}

const BTN = {
  p: "bg-accent text-accent-ink hover:bg-accent-strong border-transparent",
  ok: "bg-ok text-white hover:brightness-95 border-transparent", // Accept (the plan's .btn-ok)
  q: "bg-panel text-ink border-line-2 hover:bg-panel-2",
  ghost: "bg-transparent text-ink-2 border-transparent hover:bg-panel-2",
  bad: "bg-bad-soft text-bad border-transparent hover:brightness-95", // Stop (the plan's .btn-d)
} as const;

export function Button({ children, kind = "q", icon, sm = false, disabled = false, onClick, title, type = "button" }: {
  children?: ReactNode; kind?: keyof typeof BTN; icon?: IconName; sm?: boolean; disabled?: boolean;
  onClick?: () => void; title?: string; type?: "button" | "submit";
}) {
  return (
    <button type={type} title={title} disabled={disabled} onClick={onClick}
      className={`inline-flex items-center justify-center gap-1.5 rounded-full border font-medium whitespace-nowrap transition-colors
        disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${sm ? "text-xs px-3 py-1" : "text-sm px-4 py-1.5"} ${BTN[kind]}`}>
      {icon && <Icon name={icon} size={sm ? 14 : 16} />}
      {children}
    </button>
  );
}

/** A row of mutually exclusive options, as the plan's mockups draw it (look.css .seg): one outlined
 *  group, the options split by thin lines, the chosen one tinted with the accent. */
export function Seg<T extends string>({ options, value, onChange }: { options: { key: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex shrink-0 overflow-hidden rounded-full border border-line-2 bg-panel">
      {options.map((o, i) => (
        <button key={o.key} type="button" onClick={() => onChange(o.key)} aria-pressed={o.key === value}
          className={`px-3 py-1 text-xs font-semibold whitespace-nowrap cursor-pointer ${i ? "border-l border-line" : ""}
            ${o.key === value ? "bg-accent-soft text-accent-strong" : "text-ink-2 hover:bg-panel-2"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Tabs along a line, as the plan's mockups draw them (look.css .tabs): the chosen one is underlined
 *  with the accent, and each can carry a count. */
export function Tabs<T extends string>({ options, value, onChange }: {
  options: { key: T; label: string; count?: number }[]; value: T; onChange: (v: T) => void;
}) {
  return (
    <div role="tablist" className="flex gap-0.5 border-b border-line">
      {options.map((o) => (
        <button key={o.key} type="button" role="tab" aria-selected={o.key === value} onClick={() => onChange(o.key)}
          className={`-mb-px flex items-center gap-1.5 px-3 py-2 text-[13px] font-semibold whitespace-nowrap border-b-2 cursor-pointer
            ${o.key === value ? "text-ink border-accent" : "text-muted border-transparent hover:text-ink"}`}>
          {o.label}
          {o.count != null && <span className="font-mono text-[11px] leading-[17px] rounded-full bg-panel-2 px-1.5 text-ink-2">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

/** An on/off switch, as the plan's mockups draw it (look.css .toggle): green when on. Without
 *  `onChange` it only shows the state (a rule that can't be switched off here). */
export function Switch({ on, onChange, title }: { on: boolean; onChange?: (on: boolean) => void; title?: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} title={title} disabled={!onChange} onClick={() => onChange?.(!on)}
      className={`relative shrink-0 w-[34px] h-5 rounded-full transition-colors cursor-pointer disabled:cursor-default
        ${on ? "bg-ok" : "bg-line-2"} ${onChange ? "" : "opacity-60"}`}>
      <span className={`absolute top-0.5 size-4 rounded-full bg-white shadow-[0_1px_2px_rgba(0,0,0,0.25)] transition-[left] ${on ? "left-4" : "left-0.5"}`} />
    </button>
  );
}

// The plan's avatar colours (look.css .av-1 … .av-8): white letters on solid colours, the same
// colour for the same person every time.
const AV = ["#5B7BD5", "#2E9C8A", "#D98E2B", "#A35BC5", "#D25C77", "#64748B", "#4E9B4E", "#B5684A"];

export function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "lg" }) {
  const n = [...name].reduce((h, c) => (h * 31 + c.codePointAt(0)!) >>> 0, 7) % AV.length;
  const box = size === "sm" ? "size-6 text-[11px]" : size === "lg" ? "size-11 text-[17px]" : "size-8 text-[13px]";
  return (
    <span className={`${box} shrink-0 rounded-full grid place-items-center font-semibold text-white`} style={{ background: AV[n] }}>
      {name.trim().charAt(0).toUpperCase() || "?"}
    </span>
  );
}

export function Banner({ icon = "log", children }: { icon?: IconName; children: ReactNode }) {
  return (
    <div className="flex items-start gap-2.5 rounded-s bg-accent-soft/60 border border-line px-4 py-3 text-sm text-ink-2">
      <Icon name={icon} className="text-accent-strong mt-0.5" />
      <div>{children}</div>
    </div>
  );
}

export function Markdown({ text, small = false }: { text: string; small?: boolean }) {
  return (
    <div className={`prose-answer ${small ? "text-[13px]" : "text-[15px]"}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}
        components={{ a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer">{children}</a> }}>
        {text}
      </ReactMarkdown>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted">
      <span className="size-3.5 rounded-full border-2 border-line-2 border-t-accent animate-spin" />
      {label}
    </span>
  );
}
