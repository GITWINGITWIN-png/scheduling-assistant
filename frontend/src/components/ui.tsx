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
  q: "bg-panel text-ink border-line-2 hover:bg-panel-2",
  ghost: "bg-transparent text-ink-2 border-transparent hover:bg-panel-2",
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

/** A row of mutually exclusive options (the mockups' "seg" filter). */
export function Seg<T extends string>({ options, value, onChange }: { options: { key: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex bg-panel-2 border border-line rounded-full p-0.5">
      {options.map((o) => (
        <button key={o.key} type="button" onClick={() => onChange(o.key)}
          className={`px-3.5 py-1 text-sm rounded-full cursor-pointer ${o.key === value ? "bg-panel text-ink shadow-card font-medium" : "text-muted hover:text-ink"}`}>
          {o.label}
        </button>
      ))}
    </div>
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

export function Markdown({ text }: { text: string }) {
  return (
    <div className="prose-answer text-[15px]">
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
