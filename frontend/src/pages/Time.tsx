// W7 การใช้เวลา (B6), laid out as the plan's mockup (docs/plan-v2/stage2/web.py w7): time per day by
// category (①), by project against the plan (②), what the rules noticed (③), and the privacy card
// (④ ⑤): the recording switch, หยุดบันทึก, and the blocklist. Everything comes from ActivityWatch on
// this computer, through the secretary's filter; nothing here uses a model.
import { useCallback, useEffect, useState } from "react";
import { api, type PrivacyCard, type PrivacyRuleRow, type TimePage } from "../api";
import { Toast, type ToastMsg } from "../components/Toast";
import { Banner, Button, Card, Spinner, Switch } from "../components/ui";
import { hm } from "../format";
import { Icon } from "../icons";
import { useStatus } from "../status";

type Say = (text: string, actionId?: number | null) => void;

/** What the recorder is doing, in one line. */
function recorderLine(p: PrivacyCard): { text: string; bad?: boolean } {
  const r = p.recorder;
  if (!r.installed) return { text: "ยังไม่ได้ติดตั้ง ActivityWatch · ดู docs/setup/ideas-and-time.md", bad: true };
  if (r.paused_until) return { text: `หยุดบันทึกถึง ${hm(new Date(r.paused_until))} แล้วจะบันทึกต่อเอง` };
  if (r.extension === "after_login") return { text: "ติดตั้งแล้ว · ล็อกเอาต์แล้วล็อกอินใหม่ 1 ครั้งก่อน ส่วนเสริม GNOME จึงจะทำงาน", bad: true };
  if (r.extension === "missing") return { text: "ไม่พบส่วนเสริม GNOME “Focused Window D-Bus” · ติดตั้งใหม่ด้วย desktop/activitywatch.py install", bad: true };
  if (!r.enabled) return { text: "ปิดอยู่ · ไม่มีอะไรถูกบันทึก" };
  if (!r.running) return { text: "เปิดไว้แต่ตัวบันทึกไม่ได้ทำงาน · ดู journalctl --user -u awatcher", bad: true };
  const read = p.last_read;
  if (read.error && (!read.at || (read.error_at ?? "") > read.at)) return { text: `อ่าน ActivityWatch ไม่ได้: ${read.error}`, bad: true };
  return { text: read.to ? `บันทึกอยู่ · เลขาอ่านล่าสุด ${hm(new Date(read.to))} (ทุก 15 นาที)` : "บันทึกอยู่ · เลขาจะอ่านรอบแรกภายใน 15 นาที" };
}

/** ④ ⑤ The privacy card. */
function Privacy({ p, set, say, fail }: { p: PrivacyCard; set: (p: PrivacyCard) => void; say: Say; fail: (e: unknown) => void }) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const r = p.recorder;
  const on = r.enabled && r.round_on;
  const line = recorderLine(p);
  const run = async (f: () => Promise<void>) => { setBusy(true); try { await f(); } catch (e) { fail(e); } setBusy(false); };
  const notes = [...new Set(p.rules.filter((x) => x.kind !== "word").map((x) => x.note || x.value))];
  const words = p.rules.filter((x) => x.kind === "word").length;
  return (
    <Card title="ความเป็นส่วนตัว">
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center gap-3">
          <span className="grow text-sm font-semibold">บันทึกกิจกรรม</span>
          <Switch on={on} title={on ? "ปิด: หยุดบันทึก และไม่เปิดเองตอนล็อกอิน" : "เปิด: ActivityWatch บันทึก และเลขาอ่านทุก 15 นาที"}
            onChange={r.installed && !busy ? (v) => run(async () => {
              const out = await api.setRecording(v); set(out);
              say(v ? "เปิดบันทึกกิจกรรมแล้ว · เลขาอ่านทุก 15 นาที" : "ปิดบันทึกกิจกรรมแล้ว", out.action_id);
            }) : undefined} />
        </div>
        <span className={`text-xs ${line.bad ? "text-warn" : "text-ink-2"}`}>{line.text}</span>
        {on && (r.paused_until ? (
          <div className="flex"><Button icon="play" disabled={busy} onClick={() => run(async () => {
            const out = await api.resumeRecording(); set(out); say("บันทึกต่อแล้ว");
          })}>บันทึกต่อเลย</Button></div>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <Button icon="pause" disabled={busy} onClick={() => run(async () => {
              const out = await api.pauseRecording(60); set(out); say(`หยุดบันทึกถึง ${hm(new Date(out.until))} · กดบันทึกต่อเลยเพื่อเลิกหยุด`);
            })}>หยุดบันทึก 1 ชั่วโมง</Button>
            {r.pause_minutes.filter((m) => m !== 60).map((m) => (
              <button key={m} type="button" disabled={busy} className="text-xs text-ink-2 hover:underline cursor-pointer"
                onClick={() => run(async () => { const out = await api.pauseRecording(m); set(out); say(`หยุดบันทึกถึง ${hm(new Date(out.until))} · กดบันทึกต่อเลยเพื่อเลิกหยุด`); })}>
                {m < 60 ? `${m} นาที` : `${m / 60} ชม.`}</button>
            ))}
          </div>
        ))}
        <div className="flex items-start gap-2 text-sm">
          <span className="grow text-ink-2">ห้ามบันทึก: {notes.slice(0, 3).join(", ")}{notes.length > 3 ? ` +${notes.length - 3}` : ""} · ซ่อนชื่อหน้าต่างที่มี {words} คำ</span>
          <button type="button" onClick={() => setEditing(!editing)} className="font-semibold text-accent-strong hover:underline cursor-pointer">
            {editing ? "เสร็จ" : "แก้"}</button>
        </div>
        {editing && <RulesEditor p={p} set={set} say={say} fail={fail} />}
        <span className="flex items-start gap-1.5 text-xs text-muted"><Icon name="lock" size={14} className="mt-0.5" />
          log อยู่บนเครื่องนี้เท่านั้น · หน้าต่างที่ห้ามไม่ถูกส่งเข้า ActivityWatch ตั้งแต่แรก และเลขากรองซ้ำอีกชั้นก่อนเก็บ</span>
        {r.installed && <a href={r.web} target="_blank" rel="noreferrer" className="text-xs text-ink-2 hover:underline">เปิด ActivityWatch ของเครื่องนี้ ({r.web}) ↗</a>}
      </div>
    </Card>
  );
}

const KIND_HINT: Record<PrivacyRuleRow["kind"], string> = {
  app: "ชื่อแอป เช่น keepassxc · ไม่บันทึกเลย",
  title: "ชื่อเว็บหรือคำในชื่อหน้าต่าง เช่น kasikorn · ไม่บันทึกเลย",
  word: "คำในชื่อหน้าต่าง เช่น รหัสผ่าน · เก็บเวลาไว้ แต่ซ่อนชื่อหน้าต่าง",
};

function RulesEditor({ p, set, say, fail }: { p: PrivacyCard; set: (p: PrivacyCard) => void; say: Say; fail: (e: unknown) => void }) {
  return (
    <div className="flex flex-col gap-3 rounded-s border border-line bg-panel-2 p-3">
      {(["app", "title", "word"] as const).map((kind) => (
        <div key={kind} className="flex flex-col gap-1.5">
          <span className="text-xs font-semibold">{p.kinds[kind]} <span className="font-normal text-muted">· {KIND_HINT[kind]}</span></span>
          <div className="flex flex-wrap gap-1">
            {p.rules.filter((x) => x.kind === kind).map((x) => (
              <span key={x.id} title={x.note} className="inline-flex items-center gap-1 rounded-full border border-line-2 bg-panel px-2 py-0.5 text-xs">
                {x.value}
                <button type="button" aria-label={`เลิกห้าม ${x.value}`} className="text-muted hover:text-bad cursor-pointer" onClick={async () => {
                  try { const out = await api.removePrivacyRule(x.id); set(out); say(`เลิกห้าม “${x.value}” แล้ว`, out.action_id); } catch (e) { fail(e); }
                }}><Icon name="x" size={12} /></button>
              </span>
            ))}
            <input placeholder="+ เพิ่ม" className="w-28 rounded-full border border-dashed border-line-2 bg-panel px-2 py-0.5 text-xs outline-none focus:border-accent"
              onKeyDown={async (e) => {
                if (e.key !== "Enter" || !e.currentTarget.value.trim()) return;
                const input = e.currentTarget, value = input.value;
                try { const out = await api.addPrivacyRule(kind, value); set(out); input.value = ""; say(`ห้ามบันทึก “${value.trim()}” แล้ว · ลบของเดิมที่ตรงออกจาก log ด้วย`, out.action_id); }
                catch (err) { fail(err); }
              }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function Time() {
  const { refresh } = useStatus();
  const [page, setPage] = useState<TimePage | null>(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<ToastMsg | null>(null);
  const load = useCallback(() => {
    api.time().then((p) => { setPage(p); setError(""); }, (e) => setError((e as Error).message));
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, [load]);
  const say: Say = (text, actionId = null) => { setToast({ text, actionId, key: Date.now() }); refresh(); };
  const fail = (e: unknown) => setError((e as Error).message);
  const undo = async (id: number) => { await api.undo(id); setToast(null); load(); refresh(); };
  if (page === null) return error ? <p className="text-sm text-bad">{error}</p> : <Spinner />;
  const setPrivacy = (privacy: PrivacyCard) => setPage({ ...page, privacy });
  const r = page.privacy.recorder;
  return (
    <div className="flex flex-col gap-4">
      {error && <p className="text-sm text-bad">{error}</p>}
      {!(r.enabled && r.round_on) && (
        <Banner icon="clock">ยังไม่ได้บันทึกกิจกรรม · เปิด <b>บันทึกกิจกรรม</b> ในการ์ดความเป็นส่วนตัว แล้วหน้านี้จะเริ่มมีเวลาต่อวัน แยกตามหมวดและโปรเจค</Banner>
      )}
      <div className="grid gap-4 items-start xl:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
        <div className="flex flex-col gap-4 min-w-0" />
        <div className="flex flex-col gap-4 min-w-0">
          <Privacy p={page.privacy} set={setPrivacy} say={say} fail={fail} />
        </div>
      </div>
      <Toast msg={toast} onUndo={undo} onClose={() => setToast(null)} />
    </div>
  );
}
