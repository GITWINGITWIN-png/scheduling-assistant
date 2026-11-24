// W9 What the secretary did: everything the secretary did, where it came from, and Revert where possible.
import { useCallback, useEffect, useState } from "react";
import { api, type LogItem } from "../api";
import { tokens } from "../format";
import { Icon } from "../icons";
import { useStatus } from "../status";
import { Banner, Button, Card, Chip, Seg } from "../components/ui";

const RANGES = [
  { key: "today", label: "วันนี้" },
  { key: "7d", label: "7 วัน" },
  { key: "all", label: "ทั้งหมด" },
] as const;
type Range = (typeof RANGES)[number]["key"];

export function Log() {
  const { refresh } = useStatus();
  const [range, setRange] = useState<Range>("today");
  const [group, setGroup] = useState("all");
  const [items, setItems] = useState<LogItem[] | null>(null);
  const [groups, setGroups] = useState([{ key: "all", label: "ทุกชนิด" }]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(() => {
    api.log(range, group).then((r) => { setItems(r.items); setGroups(r.groups); setError(""); },
      (e) => setError((e as Error).message));
  }, [range, group]);

  useEffect(() => {
    load();
    const t = setInterval(load, 15_000); // new rows appear without reloading
    return () => clearInterval(t);
  }, [load]);

  const undo = async (id: number) => {
    setBusy(id);
    try { await api.undo(id); } catch (e) { setError((e as Error).message); }
    setBusy(null); load(); refresh();
  };

  const label = RANGES.find((r) => r.key === range)!.label;
  return (
    <div className="flex flex-col gap-4 max-w-6xl">
      <div className="flex flex-wrap gap-3">
        <Seg options={[...RANGES]} value={range} onChange={setRange} />
        <Seg options={groups} value={group} onChange={setGroup} />
      </div>
      {error && <p className="text-sm text-bad">{error}</p>}
      <Card title={`${label} · ${items?.length ?? "…"} อย่าง`} flush>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted border-y border-line">
              {["เวลา", "ทำอะไร", "กับอะไร", "ที่มา", ""].map((h) => <th key={h} className="font-normal px-4 py-2">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {items?.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-muted">ยังไม่มีอะไรในช่วงนี้ · ลองถามเลขาที่ช่องด้านบน</td></tr>
            )}
            {items?.map((a) => (
              <tr key={a.id} className={`border-b border-line last:border-0 align-top ${a.undone_at ? "opacity-55" : ""}`}>
                <td className="px-4 py-2.5 font-mono whitespace-nowrap text-ink-2">{range === "today" ? a.time : `${a.date} ${a.time}`}</td>
                <td className="px-4 py-2.5 font-semibold">{a.summary}</td>
                <td className="px-4 py-2.5 text-ink-2 max-w-[340px]"><span className="line-clamp-2">{a.target || "—"}</span></td>
                <td className="px-4 py-2.5">
                  {a.source_url
                    ? <a href={a.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent-strong hover:underline">{a.source_label}<Icon name="ext" size={13} /></a>
                    : <span className="text-muted">{a.source_label || "—"}</span>}
                  {a.tokens ? <span className="block text-xs text-muted">{tokens(a.tokens)} โทเคน</span> : null}
                </td>
                <td className="px-4 py-2.5 text-right whitespace-nowrap">
                  {a.can_undo
                    ? <Button sm icon="undo" disabled={busy === a.id} onClick={() => undo(a.id)}>ย้อนกลับ</Button>
                    : a.undone_at ? <Chip>ย้อนแล้ว</Chip> : <span className="text-muted">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Banner>สคริปต์จดทุกครั้งที่เลขาทำเอง ไม่ใช้โทเคน · ย้อนกลับได้: นัดที่ลงเอง การเปลี่ยนระดับคน คำสั่งที่ยังไม่เริ่ม</Banner>
    </div>
  );
}
