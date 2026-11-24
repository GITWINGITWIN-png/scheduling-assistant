// W6 Ideas (B6), laid out as the plan's mockup (docs/plan-v2/stage2/web.py w6): the box to jot an
// idea down (①), the groups (②, the noon and midnight rounds make them), the ones grown enough to
// become a project or a task (③), and what you jotted down lately, where from and which group (④).
// Until OmniRoute is connected there's no model: a group is one tag (the user's choice at the plan).
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api, type IdeaGroupRow, type IdeaRow, type IdeasPage } from "../api";
import { IdeaCapture } from "../components/IdeaCapture";
import { Toast, type ToastMsg } from "../components/Toast";
import { Button, Card, Spinner } from "../components/ui";
import { ago } from "../format";
import { Icon, type IconName } from "../icons";
import { useStatus } from "../status";

type Say = (text: string, actionId?: number | null) => void;

/** ③ The ripe group's question: open a project (the folder's name first), a task, or not yet. */
function Ripe({ g, say, fail }: { g: IdeaGroupRow; say: Say; fail: (e: unknown) => void }) {
  const [naming, setNaming] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async (f: () => Promise<void>) => { setBusy(true); try { await f(); } catch (e) { fail(e); } setBusy(false); };
  return (
    <div className="rounded-s border border-warn/40 bg-warn-soft px-3 py-2.5 flex flex-col gap-2">
      <span className="flex items-center gap-1.5 text-[13px] font-semibold"><Icon name="sparkle" size={15} className="text-warn" />
        โตพอแล้ว · เปิดเป็นโปรเจคใหม่ไหม</span>
      {naming === null ? (
        <div className="flex flex-wrap gap-1.5">
          <Button kind="p" sm disabled={busy} onClick={() => run(async () => setNaming((await api.groupFolder(g.id)).name))}>เปิดโปรเจค</Button>
          <Button sm disabled={busy} onClick={() => run(async () => {
            const r = await api.groupTask(g.id); say(`ทำ “${g.name}” เป็นงานแล้ว · เลขาจะหาเวลาในตารางให้`, r.action_id);
          })}>ทำเป็นงาน</Button>
          <Button kind="ghost" sm disabled={busy} onClick={() => run(async () => {
            const r = await api.groupLater(g.id); say(`ยังก่อน · จะถามใหม่เมื่อ “${g.name}” โตขึ้นอีก`, r.action_id);
          })}>ยังก่อน</Button>
        </div>
      ) : (
        <form className="flex flex-col gap-1.5" onSubmit={(e) => { e.preventDefault(); void run(async () => {
          await api.groupProject(g.id, naming); say(`เปิดโปรเจค ~/Projects/${naming.trim()} แล้ว · README และ PROGRESS มาจากไอเดียในกลุ่ม`);
        }); }}>
          <label className="text-xs text-ink-2">ชื่อโฟลเดอร์ใน ~/Projects
            <input autoFocus value={naming} onChange={(e) => setNaming(e.target.value)}
              className="mt-1 w-full rounded-s border border-line-2 bg-panel px-2.5 py-1 text-sm outline-none focus:border-accent" /></label>
          <div className="flex gap-1.5">
            <Button kind="p" sm type="submit" disabled={busy || !naming.trim()}>เปิดโปรเจค</Button>
            <Button kind="ghost" sm onClick={() => setNaming(null)}>ยกเลิก</Button>
          </div>
        </form>
      )}
    </div>
  );
}

/** ② One group: its name (click to rename), size, how it grew, its tags, and what it can become. */
function GroupCard({ g, focus, say, fail }: { g: IdeaGroupRow; focus: boolean; say: Say; fail: (e: unknown) => void }) {
  const [open, setOpen] = useState(focus);
  const [renaming, setRenaming] = useState(false);
  const ref = useRef<HTMLElement>(null);
  useEffect(() => { if (focus) ref.current?.scrollIntoView({ block: "center" }); }, [focus]);
  const rename = async (name: string) => {
    setRenaming(false);
    if (!name.trim() || name.trim() === g.name) return;
    try { const r = await api.renameGroup(g.id, name); say(`ตั้งชื่อกลุ่มเป็น “${name.trim()}” แล้ว`, r.action_id); } catch (e) { fail(e); }
  };
  return (
    <section ref={ref} className={`bg-panel border rounded-card shadow-card p-4 flex flex-col gap-2 min-w-0 ${g.waiting ? "border-accent" : "border-line"}`}>
      <div className="flex items-start gap-2">
        {renaming ? (
          <input autoFocus defaultValue={g.name} className="grow min-w-0 rounded-s border border-line-2 px-2 py-0.5 font-semibold outline-none focus:border-accent"
            onKeyDown={(e) => { if (e.key === "Enter") void rename(e.currentTarget.value); if (e.key === "Escape") setRenaming(false); }}
            onBlur={(e) => void rename(e.currentTarget.value)} />
        ) : (
          <button type="button" title="คลิกเพื่อตั้งชื่อกลุ่ม" onClick={() => setRenaming(true)}
            className="grow min-w-0 text-left font-semibold text-[15px] leading-snug hover:underline cursor-pointer">{g.name}</button>
        )}
        <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${g.waiting ? "bg-accent-soft text-accent-strong" : "bg-panel-2 text-ink-2"}`}>{g.size} ไอเดีย</span>
      </div>
      <span className="text-xs text-muted">{[g.grew, g.about && `เกี่ยวกับ ${g.about}`].filter(Boolean).join(" · ")}</span>
      <div className="flex flex-wrap gap-1">{g.tags.map((t) => <span key={t} className="rounded-full border border-line-2 px-2 py-0.5 text-xs font-medium text-ink-2">#{t}</span>)}</div>
      {g.waiting && <Ripe g={g} say={say} fail={fail} />}
      {g.status === "task" && <Link to="/schedule" className="text-xs font-semibold text-accent-strong hover:underline">เป็นงานในตารางแล้ว →</Link>}
      {g.status === "later" && <span className="text-xs text-muted">ยังก่อน · เลขาจะถามใหม่เมื่อกลุ่มโตขึ้นอีก</span>}
      {g.status === "open" && (
        <Button sm onClick={async () => {
          try { const r = await api.groupTask(g.id); say(`ทำ “${g.name}” เป็นงานแล้ว · เลขาจะหาเวลาในตารางให้`, r.action_id); } catch (e) { fail(e); }
        }}>เสนอเป็นงานในตาราง</Button>
      )}
      <button type="button" onClick={() => setOpen(!open)} className="self-start text-xs text-ink-2 hover:underline cursor-pointer">
        {open ? "ซ่อนไอเดีย" : `ดูไอเดีย ${g.size} อัน`}</button>
      {open && (
        <ul className="flex flex-col gap-1 text-[13px] text-ink-2">
          {g.ideas.map((i) => <li key={i.id} className="flex gap-1.5"><Icon name={SOURCE_ICON[i.source]} size={14} className="mt-0.5 text-muted" />{i.text}</li>)}
        </ul>
      )}
    </section>
  );
}

const SOURCE_ICON: Record<IdeaRow["source"], IconName> = { key: "key", discord: "chat", web: "monitor" };
const FROM: Record<IdeaRow["source"], string> = { key: "จากคีย์ลัด", discord: "จาก #ไอเดีย", web: "จากหน้าเว็บ" };

function Recent({ items, onRemove, onTags }: { items: IdeaRow[]; onRemove: (i: IdeaRow) => void; onTags: (i: IdeaRow, tags: string[]) => void }) {
  const [editing, setEditing] = useState<number | null>(null);
  return (
    <Card title="จดล่าสุด">
      {items.length === 0 ? (
        <p className="text-sm text-muted">ยังไม่มีไอเดีย · พิมพ์ในช่องด้านบน กด Super+I หรือพิมพ์ใน #ไอเดีย ของ Discord</p>
      ) : (
        <ul className="divide-y divide-line">
          {items.map((i) => (
            <li key={i.id} className="group flex items-start gap-3 py-2.5">
              <Icon name={SOURCE_ICON[i.source]} className="text-ink-2 mt-0.5" />
              <span className="grow min-w-0">
                <span className="block font-semibold text-[14px] leading-snug truncate" title={i.text}>{i.text}</span>
                {editing === i.id ? (
                  <input autoFocus defaultValue={i.tags.map((t) => "#" + t).join(" ")} placeholder="#แท็ก #อีกแท็ก"
                    className="mt-0.5 w-full rounded-s border border-line-2 bg-panel px-2 py-0.5 text-xs outline-none focus:border-accent"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") { setEditing(null); onTags(i, e.currentTarget.value.split(/[\s,]+/).filter(Boolean)); }
                      if (e.key === "Escape") setEditing(null);
                    }} onBlur={() => setEditing(null)} />
                ) : (
                  <button type="button" title="คลิกเพื่อแก้แท็ก" onClick={() => setEditing(i.id)}
                    className="block w-full text-left text-xs text-muted truncate hover:text-ink-2 cursor-pointer">
                    {FROM[i.source]} · {i.group ? `เข้ากลุ่ม “${i.group}”` : i.tags.length ? `${i.tags.map((t) => "#" + t).join(" ")} · รอจัดกลุ่ม` : "ยังไม่มีแท็ก · คลิกเพื่อใส่"}</button>
                )}
              </span>
              <span className="text-xs text-muted whitespace-nowrap">{ago(i.at)}</span>
              <button type="button" title="ลบไอเดียนี้" onClick={() => onRemove(i)}
                className="opacity-0 group-hover:opacity-100 text-muted hover:text-bad cursor-pointer"><Icon name="x" size={14} /></button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function Ideas() {
  const { refresh } = useStatus();
  const [page, setPage] = useState<IdeasPage | null>(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<ToastMsg | null>(null);
  const [grouping, setGrouping] = useState(false);
  const [params] = useSearchParams();
  const focus = Number(params.get("group")) || null; // from the bell's View group

  const load = useCallback(() => {
    api.ideas().then((p) => { setPage(p); setError(""); }, (e) => setError((e as Error).message));
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 20_000); // ideas from #ideas and the popup appear by themselves
    return () => clearInterval(t);
  }, [load]);

  const remove = async (i: IdeaRow) => {
    try {
      const r = await api.removeIdea(i.id);
      setToast({ text: `ลบไอเดียแล้ว: ${i.text.slice(0, 40)}`, actionId: r.action_id, key: Date.now() });
    } catch (e) { setError((e as Error).message); }
    load();
  };
  const undo = async (id: number) => { await api.undo(id); setToast(null); load(); refresh(); };
  const say: Say = (text, actionId = null) => { setToast({ text, actionId, key: Date.now() }); load(); refresh(); };
  const fail = (e: unknown) => setError((e as Error).message);
  const groupNow = async () => {
    setGrouping(true);
    try { say((await api.ideasRound()).line); } catch (e) { fail(e); }
    setGrouping(false);
  };

  return (
    <div className="flex flex-col gap-4">
      <IdeaCapture onSaved={load} />
      {error && <p className="text-sm text-bad">{error}</p>}
      {page === null ? <Spinner /> : (
        <div className="grid gap-4 items-start xl:grid-cols-[minmax(0,3fr)_minmax(300px,1fr)]">
          <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3 items-start">
            {page.groups.map((g) => <GroupCard key={g.id} g={g} focus={g.id === focus} say={say} fail={fail} />)}
            {(page.ungrouped > 0 || page.groups.length === 0) && (
              <div className="rounded-card border border-dashed border-line-2 px-4 py-6 text-center text-sm text-muted flex flex-col items-center gap-2">
                <span>{page.ungrouped > 0 ? `ยังไม่จัดกลุ่ม ${page.ungrouped} ไอเดีย · ` : "ยังไม่มีกลุ่ม · "}
                  {page.round_on ? "เลขาจัดรอบเที่ยงและเที่ยงคืน" : <>รอบจัดกลุ่มยังปิดอยู่ · <Link to="/settings" className="underline">เปิดในหน้าตั้งค่า</Link></>}</span>
                <span className="text-xs">กลุ่มคือแท็ก: ใส่ #แท็ก ในไอเดีย หรือเอ่ยชื่อโปรเจค · โตถึง {page.grown} ไอเดียแล้วเลขาเสนอให้เปิดเป็นโปรเจคหรืองาน</span>
                {page.ungrouped > 0 && <Button sm icon="refresh" disabled={grouping} onClick={groupNow}>จัดกลุ่มเลย</Button>}
              </div>
            )}
          </div>
          <Recent items={page.recent} onRemove={remove} onTags={async (i, tags) => {
            try {
              const r = await api.setIdeaTags(i.id, tags);
              say(r.group ? `แท็กใหม่แล้ว · อยู่ในกลุ่ม “${r.group.name}”` : "เอาแท็กออกแล้ว");
            } catch (e) { fail(e); }
          }} />
        </div>
      )}
      <Toast msg={toast} onUndo={undo} onClose={() => setToast(null)} />
    </div>
  );
}
