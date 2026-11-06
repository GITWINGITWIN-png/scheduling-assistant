// W1 วันนี้ (B4), laid out as the plan's mockup (docs/plan-v2/stage2/web.py w1): the morning's
// numbers (the same line as the brief in #สรุป, with the brief in full behind a link), the day as
// rows (แผน · ทำจริง · เลขา), what waits for you, and today's important mail. Background work
// and project news come with B5, the ทำจริง row with B6 (ActivityWatch).
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router";
import { api, type BriefView, type Decision, type DayItem, type RoundMark, type TodayPage } from "../api";
import { DecisionRow } from "../components/Decisions";
import { Avatar, Card, Phase, Spinner } from "../components/ui";
import { hm } from "../format";
import { Icon } from "../icons";
import { useStatus } from "../status";
import { Floating } from "./schedule/Floating";

/** The brief's text as sent: lines kept, **bold** bold. */
function Rich({ text }: { text: string }) {
  return (
    <div className="text-sm text-ink-2 leading-relaxed">
      {text.split("\n").map((line, i) => (
        <p key={i}>{line.split(/\*\*(.+?)\*\*/g).map((part, j) => (j % 2 ? <b key={j} className="text-ink">{part}</b> : part))}</p>
      ))}
    </div>
  );
}

function FullBrief({ b, onClose }: { b: BriefView; onClose: () => void }) {
  return (
    <Floating anchor={null} onClose={onClose} width={560}>
      <div className="p-5 flex flex-col gap-3">
        <div className="flex items-start gap-2">
          <div className="grow">
            <div className="text-xs text-muted">สรุปเช้า · {hm(new Date(b.made_at))}{b.sent ? " · ส่งเข้า #สรุป แล้ว" : ""}</div>
            <h3 className="text-lg font-semibold">{b.title}</h3>
            <p className="text-sm text-ink-2">{b.headline}</p>
          </div>
          <button type="button" aria-label="ปิด" onClick={onClose} className="text-muted hover:text-ink cursor-pointer p-1"><Icon name="x" size={16} /></button>
        </div>
        {b.fields.map(([name, text]) => (
          <div key={name} className="flex flex-col gap-0.5">
            <span className="text-[13px] font-semibold">{name}</span>
            <Rich text={text} />
          </div>
        ))}
        <p className="text-xs text-muted border-t border-line pt-2">{b.footer}</p>
        {b.link && <a href={b.link} target="_blank" rel="noopener" className="text-xs font-semibold text-accent-strong hover:underline w-fit">เปิดใน Discord →</a>}
      </div>
    </Floating>
  );
}

// ------------------------------------------------------------------ the day as rows (W1 ③)
const KIND = { meet: "meet", block: "work", dead: "dead", allday: "meet" } as const;

function DayRows({ plan, secretary, hours }: { plan: DayItem[]; secretary: RoundMark[]; hours: [number, number] }) {
  const [h0, h1] = hours;
  const cols = (h1 - h0) * 2; // half hours
  const col = (iso: string) => {
    const d = new Date(iso);
    return Math.max(0, Math.min(cols, Math.round(((d.getHours() - h0) * 60 + d.getMinutes()) / 30)));
  };
  const at = (a: number, b: number, row: number) => ({ gridColumn: `${a + 2} / span ${Math.max(1, b - a)}`, gridRow: row });
  // only what falls inside the hours shown: a round at 00:02 would otherwise be squeezed under 07:00's
  const minutes = (iso: string) => { const d = new Date(iso); return d.getHours() * 60 + d.getMinutes(); };
  const inside = (start: string, end: string) => minutes(end) > h0 * 60 && minutes(start) < h1 * 60;
  const timed = plan.filter((i) => i.kind !== "allday" && inside(i.kind === "dead" ? i.end : i.start, i.end));
  const marks = secretary.filter((r) => minutes(r.at) >= h0 * 60 && minutes(r.at) < h1 * 60); // 07:00 itself is in
  const allDay = plan.filter((i) => i.kind === "allday");
  const now = new Date();
  const nowCol = (now.getHours() - h0) * 2 + (now.getMinutes() >= 30 ? 1 : 0);
  return (
    <div className="flex flex-col gap-2">
      {allDay.length > 0 && <p className="text-xs text-ink-2">ทั้งวัน: {allDay.map((i) => i.title).join(" · ")}</p>}
      <div className="day-rows" style={{ gridTemplateColumns: `64px repeat(${cols}, minmax(0, 1fr))` }}>
        {Array.from({ length: (h1 - h0) / 2 }, (_, k) => h0 + k * 2).map((h) => (
          <span key={h} className="dr-h" style={{ gridColumn: (h - h0) * 2 + 2, gridRow: 1 }}>{String(h).padStart(2, "0")}:00</span>
        ))}
        {["แผน", "ทำจริง", "เลขา"].map((lane, k) => <span key={lane} className="dr-lane" style={{ gridRow: k + 2 }}>{lane}</span>)}
        {timed.map((i) => {
          const a = col(i.kind === "dead" ? i.end : i.start);
          const b = i.kind === "dead" ? a + 2 : col(i.end);
          return (
            <span key={`${i.kind}${i.start}${i.title}`} className={`blk ${KIND[i.kind]}`} style={at(a, b, 2)}
              title={`${hm(new Date(i.start))}${i.kind === "dead" ? "" : "–" + hm(new Date(i.end))} ${i.title}${i.sub ? ` · ${i.sub}` : ""}`}>
              {i.kind === "dead" ? `ส่ง ${i.title}` : i.title}</span>
          );
        })}
        <span className="dr-later" style={{ gridColumn: `2 / span ${cols}`, gridRow: 3 }}>
          เทียบกับที่ทำจริงจาก ActivityWatch <Phase phase="B6" /></span>
        {marks.map((r) => {
          const a = col(r.at);
          return <span key={r.at + r.title} className={`blk ${r.done ? "bg" : "miss"}`} style={at(a, a + 2, 4)}
            title={`${hm(new Date(r.at))} ${r.title}${r.line ? ` · ${r.line}` : r.done ? "" : " · จะทำ"}`}>{r.title}</span>;
        })}
        {nowCol >= 0 && nowCol < cols && <span className="dr-now" style={{ gridColumn: nowCol + 2, gridRow: "2 / span 3" }} />}
      </div>
    </div>
  );
}

function Later({ title, phase, children }: { title: string; phase: string; children: ReactNode }) {
  return <Card title={title} right={<Phase phase={phase} />}><p className="text-sm text-muted">{children}</p></Card>;
}

// ------------------------------------------------------------------ the page
export function Today() {
  const { refresh } = useStatus();
  const [page, setPage] = useState<TodayPage | null>(null);
  const [waiting, setWaiting] = useState<Decision[] | null>(null);
  const [full, setFull] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    api.today().then(setPage, (e) => setError((e as Error).message));
    api.decisions().then((r) => setWaiting(r.items), () => setWaiting([]));
  }, []);
  useEffect(load, [load]);
  const changed = () => { load(); refresh(); };

  if (error) return <p className="text-sm text-bad">{error}</p>;
  if (!page) return <Spinner label="กำลังโหลด…" />;
  const keys: [string, string][] = [["bg-accent", "บล็อกงาน"], ["bg-bad", "นัด"], ["bg-warn", "เดดไลน์"], ["bg-muted", "งานของเลขา"]];
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <div className="grow min-w-0">
          <h2 className="text-[22px] font-semibold leading-tight">{page.greeting}</h2>
          <p className="text-[13.5px] text-ink-2">{page.brief ? "เช้านี้: " : "ตอนนี้: "}{page.headline}</p>
        </div>
        {page.brief ? (
          <button type="button" onClick={() => setFull(true)} className="text-[12.5px] font-semibold text-accent-strong hover:underline cursor-pointer">
            ดูสรุปเช้าฉบับเต็ม →</button>
        ) : (
          <span className="text-xs text-muted">ยังไม่มีสรุปเช้าวันนี้ · {page.morning_on ? "ส่งทุกวัน 07:00 ใน #สรุป" : <>รอบสรุปเช้ายังปิดอยู่ · <Link to="/settings" className="underline">เปิดในหน้าตั้งค่า</Link></>}</span>
        )}
      </div>

      <Card title={<span className="flex items-baseline gap-2">ตารางวันนี้<span className="text-xs text-muted font-normal">แผนเทียบกับที่ทำจริง</span></span>}
        right={<div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
          {keys.map(([c, label]) => <span key={label} className="inline-flex items-center gap-1.5"><i className={`size-2 rounded-full ${c}`} />{label}</span>)}
          <Link to="/schedule" className="font-semibold text-accent-strong hover:underline">ทั้งสัปดาห์ →</Link>
        </div>}>
        <DayRows plan={page.plan} secretary={page.secretary} hours={page.hours} />
      </Card>

      <div className="grid gap-4 items-start lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card title={<span className="flex items-baseline gap-2">รอคุณตัดสิน<span className="text-xs text-muted font-normal">{waiting ? `${waiting.length} เรื่อง` : ""}</span></span>}>
          {waiting === null ? <Spinner /> : waiting.length === 0 ? <p className="text-sm text-muted">ไม่มีเรื่องที่รอ</p> : (
            <ul className="divide-y divide-line">{waiting.map((d) => <DecisionRow key={d.id} d={d} onChange={changed} />)}</ul>
          )}
        </Card>
        <Later title="งานเบื้องหลัง" phase="B5">งานที่เลขากำลังทำต่อในโปรเจค พร้อมงบโทเคนที่ใช้ไป คิวงาน และงานที่อนุมัติไว้</Later>
      </div>

      <div className="grid gap-4 items-start lg:grid-cols-2">
        <Card title="เรื่องสำคัญ" right={<Link to="/people" className="text-[12.5px] font-semibold text-accent-strong hover:underline">คนและอีเมล →</Link>}>
          {page.important.length === 0 ? <p className="text-sm text-muted">วันนี้ยังไม่มีอีเมลจากคนสำคัญหรือที่ตรงคีย์เวิร์ด</p> : (
            <ul className="divide-y divide-line">
              {page.important.map((m) => (
                <li key={m.id} className="py-2.5 flex items-center gap-2.5">
                  <Avatar name={m.who} size="sm" />
                  <span className="grow min-w-0">
                    <span className="block font-semibold text-[13.5px] truncate">{m.who}: {m.summary}</span>
                    {m.done.length > 0 && <span className="block text-xs text-ink-2">{m.done.join(" · ")}</span>}
                  </span>
                  <span className="text-[11.5px] text-muted whitespace-nowrap">{hm(new Date(m.at))}</span>
                  {m.link && <a href={m.link} target="_blank" rel="noopener" title="เปิดใน Gmail" className="text-muted hover:text-ink"><Icon name="ext" size={15} /></a>}
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Later title="ข่าวโปรเจค" phase="B5">ข่าวสั้นจากโปรเจคที่รันอัตโนมัติ เรียงตาม potential · กดแล้วไปหน้าโปรเจค</Later>
      </div>
      {full && page.brief && <FullBrief b={page.brief} onClose={() => setFull(false)} />}
    </div>
  );
}
