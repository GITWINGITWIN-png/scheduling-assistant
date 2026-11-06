// W6 ไอเดีย (B6), laid out as the plan's mockup (docs/plan-v2/stage2/web.py w6): the box to jot an
// idea down (①), the groups (②, the noon and midnight rounds make them), the ones grown enough to
// become a project or a task (③), and what you jotted down lately, where from and which group (④).
// Until OmniRoute is connected there's no model: a group is one tag (the user's choice at the plan).
import { useCallback, useEffect, useState } from "react";
import { api, type IdeaRow, type IdeasPage } from "../api";
import { IdeaCapture } from "../components/IdeaCapture";
import { Toast, type ToastMsg } from "../components/Toast";
import { Card, Spinner } from "../components/ui";
import { ago } from "../format";
import { Icon, type IconName } from "../icons";
import { useStatus } from "../status";

const SOURCE_ICON: Record<IdeaRow["source"], IconName> = { key: "key", discord: "chat", web: "monitor" };
const FROM: Record<IdeaRow["source"], string> = { key: "จากคีย์ลัด", discord: "จาก #ไอเดีย", web: "จากหน้าเว็บ" };

function Recent({ items, onRemove }: { items: IdeaRow[]; onRemove: (i: IdeaRow) => void }) {
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
                <span className="block text-xs text-muted truncate">
                  {FROM[i.source]} · {i.group ? `เข้ากลุ่ม “${i.group}”` : i.tags.length ? `${i.tags.map((t) => "#" + t).join(" ")} · รอจัดกลุ่ม` : "รอจัดกลุ่ม"}</span>
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

  const load = useCallback(() => {
    api.ideas().then((p) => { setPage(p); setError(""); }, (e) => setError((e as Error).message));
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 20_000); // ideas from #ไอเดีย and the popup appear by themselves
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

  return (
    <div className="flex flex-col gap-4">
      <IdeaCapture onSaved={load} />
      {error && <p className="text-sm text-bad">{error}</p>}
      {page === null ? <Spinner /> : (
        <div className="grid gap-4 items-start xl:grid-cols-[minmax(0,3fr)_minmax(300px,1fr)]">
          <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3 items-start">
            {page.ungrouped > 0 && (
              <div className="rounded-card border border-dashed border-line-2 px-4 py-6 text-center text-sm text-muted">
                ยังไม่จัดกลุ่ม {page.ungrouped} ไอเดีย · เลขาจัดรอบเที่ยงและเที่ยงคืน</div>
            )}
          </div>
          <Recent items={page.recent} onRemove={remove} />
        </div>
      )}
      <Toast msg={toast} onUndo={undo} onClose={() => setToast(null)} />
    </div>
  );
}
