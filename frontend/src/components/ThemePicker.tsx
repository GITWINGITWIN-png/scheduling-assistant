// W11 เลือกธีมสี: the palette button in the top bar of every page.
// Hover a theme to preview it; click to keep it. The choice is saved in the secretary's settings,
// so every device and the Discord bot's message colour follow it.
import { useCallback, useRef, useState } from "react";
import { Icon } from "../icons";
import { useStatus } from "../status";
import { useDismiss } from "./popover";

// The same six as backend/app/core/themes.py
export const THEMES = [
  { id: "c", name: "อิฐนุ่ม", sub: "C เดิม · ครีมกับส้มอิฐ" },
  { id: "cs", name: "ส้มสด", sub: "ค่าเริ่ม · ขาวกับส้มสด" },
  { id: "cb", name: "ฟ้า", sub: "ขาวกับฟ้าสด" },
  { id: "cg", name: "เขียว", sub: "ขาวกับเขียวมรกต" },
  { id: "cp", name: "ม่วง", sub: "ขาวกับม่วง" },
  { id: "cd", name: "มืด", sub: "พื้นมืด ส้มสด" },
];

export function ThemePicker() {
  const { theme, setTheme } = useStatus();
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  useDismiss(wrap, open, useCallback(() => setOpen(false), []));
  const preview = (id: string) => { document.documentElement.dataset.theme = id; };
  const endPreview = () => { document.documentElement.dataset.theme = theme; };

  return (
    <div ref={wrap} className="relative">
      <button type="button" title="เปลี่ยนธีมสี" onClick={() => setOpen((o) => !o)}
        className={`size-9 rounded-full border grid place-items-center cursor-pointer ${open ? "border-accent text-accent-strong" : "border-line-2 text-ink-2 hover:bg-panel-2"}`}>
        <Icon name="palette" />
      </button>
      {open && (
        <div className="absolute right-0 top-[calc(100%+10px)] z-20 w-[440px] bg-panel border border-line rounded-card p-3.5 flex flex-col gap-2.5
          shadow-[0_18px_50px_rgba(0,0,0,0.22),0_2px_6px_rgba(0,0,0,0.12)]">
          <div className="flex items-baseline">
            <span className="font-semibold grow">ธีมสี</span>
            <span className="text-xs text-muted">กดเพื่อเปลี่ยน · ชี้เพื่อดูตัวอย่าง</span>
          </div>
          <div className="grid grid-cols-2 gap-2" onMouseLeave={endPreview}>
            {THEMES.map((t) => (
              <button key={t.id} type="button" onMouseEnter={() => preview(t.id)} onClick={() => setTheme(t.id)}
                className={`flex items-center gap-2.5 p-2 rounded-s border text-left cursor-pointer bg-panel
                  ${t.id === theme ? "border-accent ring-3 ring-accent-soft" : "border-line hover:border-line-2"}`}>
                <span className={`tsw-${t.id} w-[46px] h-[30px] rounded-[9px] border border-black/10 shrink-0`} />
                <span className="flex flex-col grow min-w-0">
                  <span className="text-sm font-semibold">{t.name}</span>
                  <span className="text-xs text-muted truncate">{t.sub}</span>
                </span>
                {t.id === theme && <Icon name="check" size={15} className="text-accent" />}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-ink-2">
            <Icon name="monitor" size={15} /><Icon name="tablet" size={15} /><Icon name="chat" size={15} />
            ใช้กับคอม iPad และสีแถบข้อความใน Discord · เก็บไว้ในตั้งค่าของเลขา
          </div>
        </div>
      )}
    </div>
  );
}
