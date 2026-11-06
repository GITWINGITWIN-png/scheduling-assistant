// The frame around every page (stage 2's W screens): the left menu and the top bar.
import { NavLink, Outlet, useLocation } from "react-router";
import { thaiDate, tokens } from "../format";
import { Icon } from "../icons";
import { NAV, PAGES } from "../nav";
import { useStatus } from "../status";
import { AskBox } from "./AskBox";
import { Bell } from "./Bell";
import { ThemePicker } from "./ThemePicker";

function Dot({ ok }: { ok: boolean }) {
  return <span className={`size-2 rounded-full shrink-0 ${ok ? "bg-ok" : "bg-bad"}`} />;
}

const COUNT_TITLE = { people: "เรื่องสำคัญวันนี้", decisions: "เรื่องที่รอคุณตัดสิน" } as const;

function Side() {
  const { status, online } = useStatus();
  return (
    <aside className="bg-side border-r border-line flex flex-col min-h-0">
      <div className="flex items-center gap-2.5 px-5 pt-5 pb-4">
        <span className="size-8 rounded-[10px] bg-accent text-accent-ink grid place-items-center font-bold">ล</span>
        <span className="flex flex-col leading-tight">
          <span className="font-semibold">เลขา</span>
          <span className="text-xs text-muted">my_secretary v2</span>
        </span>
      </div>
      <nav className="flex flex-col gap-0.5 px-3 overflow-auto grow">
        {NAV.map((n) =>
          "group" in n ? (
            <div key={n.group} className="text-xs text-muted px-3 pt-4 pb-1">{n.group}</div>
          ) : (
            <NavLink key={n.path} to={n.path} end
              className={({ isActive }) => `flex items-center gap-2.5 px-3 py-2 rounded-s text-sm
                ${isActive ? "bg-accent-soft text-accent-strong font-medium" : "text-ink-2 hover:bg-panel-2"}`}>
              <Icon name={n.icon} />
              <span className="grow">{n.label}</span>
              {!n.ready && <span className="text-[11px] text-muted" title={`มาในช่วง ${n.phase}`}>{n.phase}</span>}
              {n.ready && n.count && !!status?.counts?.[n.count] && (
                // the plan's .cnt: a red number for what needs a look
                <span title={`${COUNT_TITLE[n.count]} ${status.counts[n.count]} ${n.count === "people" ? "ฉบับ" : "เรื่อง"}`}
                  className="min-w-[18px] rounded-full bg-bad px-[5px] text-center font-mono text-[11px] font-semibold leading-[18px] text-white">
                  {status.counts[n.count]}</span>
              )}
            </NavLink>
          ),
        )}
      </nav>
      <div className="border-t border-line px-5 py-4 flex flex-col gap-2 text-xs">
        <Quota />
        <span className="flex items-center gap-1.5 text-ink-2"><Dot ok={online} />{online ? "เลขาทำงานอยู่บนเครื่องนี้" : "ติดต่อเลขาไม่ได้"}</span>
        <span className="flex items-center gap-1.5 text-ink-2"><Dot ok={!!status?.discord} />{status?.discord ? "Discord เชื่อมแล้ว" : "Discord ยังไม่เชื่อม"}</span>
      </div>
    </aside>
  );
}

/** The plan's quota block (W1 ⑧): what's left of your Claude week, with the 70% line. */
function Quota() {
  const { status } = useStatus();
  const q = status?.quota;
  const left = q ? Math.round(q.week_left) : null;
  const above = q ? q.week_left > q.line : false;
  return (
    <div className="flex flex-col gap-1" title={`เลขาใช้ไป ${tokens(status?.tokens_week)} โทเคนใน 7 วัน${q ? ` · อ่านเมื่อ ${new Date(q.at).toLocaleString("th-TH")}` : ""}`}>
      <div className="flex"><span className="text-muted grow">โควตา Claude สัปดาห์นี้</span><b>{left === null ? "—" : `เหลือ ${left}%`}</b></div>
      <div className="relative h-2 rounded-full bg-panel-2 border border-line">
        {left !== null && <i className={`block h-full rounded-full ${above ? "bg-ok" : "bg-warn"}`} style={{ width: `${left}%` }} />}
        <i className="absolute -top-[5px] -bottom-[5px] w-0.5 rounded-sm bg-ink" style={{ left: `${q?.line ?? 70}%` }} />
      </div>
      <span className="text-muted">{left === null ? "ยังไม่ได้อ่านโควตา · ทุกแผนงานเบื้องหลังต้องถามคุณ"
        : q?.auto === false ? "ปิดการทำเองไว้ · ทุกแผนถามคุณก่อน"
        : above ? `เกินเส้น ${q!.line}% งานเบื้องหลังทำเองได้` : `ไม่เกินเส้น ${q!.line}% · ทุกแผนถามคุณก่อน`}</span>
    </div>
  );
}

function Top() {
  const { pathname } = useLocation();
  const page = PAGES.find((p) => p.path === pathname);
  return (
    <header className="bg-top border-b border-line flex items-center gap-4 px-6 py-3">
      <div className="flex items-baseline gap-3 grow min-w-0">
        <h1 className="text-[19px] font-semibold truncate">{page?.label ?? "เลขา"}</h1>
        <span className="text-[13px] text-muted whitespace-nowrap">{thaiDate()}</span>
      </div>
      <AskBox />
      <Bell />
      <ThemePicker />
      <button type="button" disabled title="จดไอเดียด้วยคีย์ลัด มาในช่วง B6"
        className="hidden xl:inline-flex items-center gap-1.5 rounded-full border border-line-2 px-3.5 py-1.5 text-sm text-muted opacity-60 cursor-not-allowed">
        <Icon name="idea" size={16} />จดไอเดีย<kbd className="text-[11px] border border-line-2 rounded px-1">Super+I</kbd>
      </button>
    </header>
  );
}

/** The page is read from disk on every visit, the backend only when it starts: after new code
 *  arrives, the page can be newer than the running backend, and new fields are lost. Say so. */
function Restart() {
  const { status } = useStatus();
  if (!status?.stale) return null;
  return (
    <div className="flex items-start gap-2.5 rounded-s border border-warn/40 bg-warn-soft px-4 py-3 mb-4 text-sm text-ink">
      <Icon name="refresh" className="text-warn mt-0.5 shrink-0" />
      <span><b>เลขากำลังรันโค้ดรุ่นก่อน</b> โค้ดบนเครื่องใหม่กว่า สิ่งที่เพิ่งเพิ่มในหน้านี้อาจยังไม่ทำงานหรือไม่ถูกบันทึก ·
        รีสตาร์ทเลขา: <code className="font-mono text-[13px] bg-panel rounded px-1.5 py-0.5 whitespace-nowrap">systemctl --user restart my-secretary</code></span>
    </div>
  );
}

export function Shell() {
  return (
    <div className="h-screen grid grid-cols-[236px_minmax(0,1fr)]">
      <Side />
      <div className="flex flex-col min-w-0 min-h-0">
        <Top />
        <main className="flex-1 overflow-auto p-6"><Restart /><Outlet /></main>
      </div>
    </div>
  );
}
