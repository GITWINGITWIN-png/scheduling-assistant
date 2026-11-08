// W2 คนและอีเมล: the people registry by level, what each person sent (one line each, and what the
// secretary did about it), follow-ups, and setting someone important ahead of time. The mail
// settings (keywords, interests, reminder days) are on the settings page.
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api, type Followup, type Level, type Person, type PersonDetail, type Proposals } from "../api";
import { when } from "../format";
import { Icon } from "../icons";
import { useStatus } from "../status";
import { Avatar, Banner, Button, Card, Chip, Spinner, Tabs } from "../components/ui";

const LEVEL_NAMES: Record<Level, string> = { important: "สำคัญ", interested: "สนใจ", ignored: "ไม่สนใจ" };

type Tab = Level | "followups";
const TABS: { key: Tab; label: string }[] = [
  { key: "important", label: "สำคัญ" }, { key: "interested", label: "สนใจ" },
  { key: "ignored", label: "ไม่สนใจ" }, { key: "followups", label: "เรื่องค้าง" },
];

function sub(p: Person): string {
  if (p.level === "important") {
    const life = p.until ? (p.expired ? "หมดอายุแล้ว · รอคุณตัดสิน" : `สำคัญถึง ${when(p.until)} · เหลือ ${p.days_left} วัน`) : "สำคัญถาวร";
    return [life, p.awaiting && "คุณรอคำตอบ"].filter(Boolean).join(" · ");
  }
  return [p.source, p.awaiting && "คุณรอคำตอบ"].filter(Boolean).join(" · ");
}

export function People() {
  const { refresh } = useStatus();
  // ?tab=interested&p=12 opens a tab and a person directly (links from Discord cards, bookmarks)
  const [params, setParams] = useSearchParams();
  const tab = (TABS.some((t) => t.key === params.get("tab")) ? params.get("tab") : "important") as Tab;
  const selected = params.get("p") ? Number(params.get("p")) : null;
  const go = (next: { tab?: Tab; p?: number | null }) => {
    const q = new URLSearchParams();
    q.set("tab", next.tab ?? tab);
    const person = next.p === undefined ? selected : next.p;
    if (person != null) q.set("p", String(person));
    setParams(q, { replace: true });
  };
  const [counts, setCounts] = useState<Record<Tab, number> | null>(null);
  const [list, setList] = useState<Person[] | null>(null);
  const [fus, setFus] = useState<Followup[] | null>(null);
  const [detail, setDetail] = useState<PersonDetail | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    const lvl: Level = tab === "followups" ? "important" : tab;
    if (tab !== "followups") setList(null); // not the last tab's people while this one loads
    api.people(lvl).then((r) => { setCounts(r.counts); if (tab !== "followups") setList(r.items); }, (e) => setError((e as Error).message));
    if (tab === "followups") api.followups().then((r) => setFus(r.items), (e) => setError((e as Error).message));
  }, [tab]);
  useEffect(load, [load]);
  // As in the plan's W2, someone is always open: the first person, until you pick another.
  useEffect(() => {
    if (selected == null && tab !== "followups" && list?.length) go({ p: list[0].id });
  }, [list]); // eslint-disable-line react-hooks/exhaustive-deps -- only when a list arrives
  useEffect(() => {
    if (selected == null) { setDetail(null); return; }
    api.person(selected).then(setDetail, (e) => setError((e as Error).message));
  }, [selected]);

  const changed = () => { load(); if (selected != null) api.person(selected).then(setDetail, () => setDetail(null)); refresh(); };

  return (
    <div className="flex flex-col gap-4 max-w-6xl">
      <Tabs options={TABS.map((t) => ({ ...t, count: counts?.[t.key] }))} value={tab} onChange={(k) => go({ tab: k, p: null })} />
      <ProposalsCard onChange={changed} />
      {error && <p className="text-sm text-bad">{error}</p>}

      {tab === "followups" ? <Followups items={fus} onChange={changed} /> : (
        <div className="grid gap-4 md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <Card title={`${TABS.find((t) => t.key === tab)?.label} · ${list?.length ?? "…"} คน`} right={<span className="text-xs text-muted">เรียงตามอีเมลล่าสุด</span>} flush>
            {list === null ? <div className="p-4"><Spinner /></div> : list.length === 0 ? (
              <p className="px-4 pb-4 text-sm text-muted">{tab === "important" ? "ยังไม่มีคนสำคัญ · เพิ่มได้ด้านล่าง หรือยกระดับจากแท็บสนใจ" : "ยังไม่มีใครในระดับนี้"}</p>
            ) : (
              <ul className="max-h-[60vh] overflow-auto">
                {list.map((p) => (
                  <li key={p.id}>
                    <button type="button" onClick={() => go({ p: p.id })}
                      className={`w-full text-left flex items-center gap-3 px-4 py-2.5 border-t border-line cursor-pointer hover:bg-panel-2 ${selected === p.id ? "bg-accent-soft" : ""}`}>
                      <Avatar name={p.name} />
                      <span className="grow min-w-0">
                        <span className="block font-medium truncate">{p.name}</span>
                        <span className={`block text-xs truncate ${p.expired ? "text-warn" : "text-muted"}`}>{sub(p)}</span>
                      </span>
                      <span className="text-xs text-muted whitespace-nowrap">{p.last_mail_at ? when(p.last_mail_at) : "ยังไม่เคยส่ง"}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          {detail ? <Detail p={detail} onChange={changed} /> : (
            <Card><p className="pt-4 text-sm text-muted">เลือกคนทางซ้ายเพื่อดูว่าเขาส่งอะไรมา และเปลี่ยนระดับ</p></Card>
          )}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <AddPerson onDone={(id) => { go({ tab: "important", p: id }); changed(); }} />
      </div>
    </div>
  );
}

/** ข้อเสนอปรับระดับรายสัปดาห์ (1.4, B7): renew or let end an important person, raise an ignored
 *  sender whose subjects match your interests. Interested → ignored is never proposed (you do it here). */
function ProposalsCard({ onChange }: { onChange: () => void }) {
  const [data, setData] = useState<Proposals | null>(null);
  const [picked, setPicked] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(() => { api.proposals().then((d) => { setData(d); setPicked({}); }, (e) => setError((e as Error).message)); }, []);
  useEffect(load, [load]);
  if (!data) return null;
  if (data.items.length === 0) {
    return (
      <Banner icon="people">
        <span className="grow">ไม่มีข้อเสนอปรับระดับสัปดาห์นี้ · เลขาเสนอเมื่อคนสำคัญใกล้หมดอายุ หรือคนไม่สนใจส่งเรื่องที่ตรงเรื่องที่สนใจ
          · ลดคนสนใจเป็นไม่สนใจ ทำเองที่หน้านี้</span>
      </Banner>
    );
  }
  const apply = async () => {
    setBusy(true); setError("");
    try {
      await api.answerProposals(data.items.map((i) => ({ person_id: i.person_id, choice: picked[i.person_id] ?? i.choice })), data.decision_id);
      load(); onChange();
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
  };
  return (
    <Card title={`ข้อเสนอปรับระดับรายสัปดาห์ · ${data.items.length} คน`}
      right={<span className="text-xs text-muted">{data.decision_id ? "จากทบทวนรายสัปดาห์ · ตอบที่นี่หรือใน #สรุป ก็ได้" : "ตามข้อมูลตอนนี้"}</span>}>
      <ul className="divide-y divide-line">
        {data.items.map((i) => (
          <li key={i.person_id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-2.5">
            <Avatar name={i.name} />
            <span className="grow min-w-0 basis-56">
              <span className="block font-semibold text-[14px]">{i.name} <span className="font-normal text-muted">({LEVEL_NAMES[i.level]})</span></span>
              <span className="block text-xs text-ink-2">{i.why}</span>
              {i.note && <span className="block text-xs text-muted border-l-2 border-line-2 pl-2 mt-1">โน้ตที่คุณจดไว้: “{i.note}” · ตัดสินแล้วโน้ตนี้จะถูกลบ</span>}
            </span>
            <select value={picked[i.person_id] ?? i.choice} aria-label={`ตัดสิน ${i.name}`}
              onChange={(e) => setPicked({ ...picked, [i.person_id]: e.target.value })}
              className="rounded-full border border-line-2 bg-panel px-2.5 py-1 text-sm">
              {i.choices.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
          </li>
        ))}
      </ul>
      {error && <p className="text-sm text-bad pt-2">{error}</p>}
      <div className="flex justify-end pt-2"><Button kind="p" sm icon="check" disabled={busy} onClick={apply}>ทำตามนี้</Button></div>
    </Card>
  );
}

function Detail({ p, onChange }: { p: PersonDetail; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState(p.note);
  const [days, setDays] = useState(90);
  useEffect(() => { setNote(p.note); setEditing(false); setMsg(""); }, [p.id, p.note]);

  const run = async (fn: () => Promise<unknown>, done: string) => {
    setBusy(true); setMsg("");
    try { await fn(); setMsg(done); onChange(); } catch (e) { setMsg((e as Error).message); } finally { setBusy(false); }
  };
  const level = (lv: Level, extra: { days?: number | null; note?: string; reason?: string } = {}, done = "บันทึกแล้ว · ย้อนกลับได้ในหน้าสิ่งที่เลขาทำ") =>
    run(() => api.setLevel(p.id, lv, extra), done);

  return (
    <Card>
      <div className="pt-4 flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <Avatar name={p.name} size="lg" />
          <div className="grow min-w-0">
            <div className="flex items-center gap-2"><span className="font-semibold text-lg truncate">{p.name}</span>
              <Chip tone={p.level === "important" ? "bad" : p.level === "interested" ? "acc" : "muted"}>{p.level_name}</Chip></div>
            <div className="text-xs text-muted truncate">{p.addresses.join(" · ")}</div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {p.level === "important" && <Button sm disabled={busy} onClick={() => level("important", { days, note: p.note }, `ต่ออายุ ${days} วันแล้ว`)}>ต่ออายุ {days} วัน</Button>}
            {p.level !== "important" && <Button sm kind="p" disabled={busy} onClick={() => level("important", { days, note })}>ยกเป็นสำคัญ {days} วัน</Button>}
            {p.level !== "interested" && <Button sm disabled={busy} onClick={() => level("interested", { reason: p.level === "important" ? "ลดจากหน้าคนและอีเมล" : "" })}>{p.level === "important" ? "ลดเป็นสนใจ" : "ยกเป็นสนใจ"}</Button>}
            {p.level !== "ignored" && <Button sm disabled={busy} onClick={() => level("ignored")}>ไม่สนใจ</Button>}
          </div>
        </div>

        <div className="rounded-xl border border-line bg-panel-2 p-3 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-sm">
            <Icon name="clock" size={16} />
            <span className="font-medium grow">
              {p.level === "important" ? (p.until ? (p.expired ? `หมดอายุแล้ว (${when(p.until)}) · ต่ออายุหรือลดขั้น` : `สำคัญถึง ${when(p.until)} · เหลือ ${p.days_left} วัน`) : "สำคัญถาวร")
                : `ระดับ${p.level_name} · ${p.source}`}
            </span>
            <label className="text-xs text-muted flex items-center gap-1">อายุ
              <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="bg-panel border border-line rounded px-1 py-0.5">
                {[7, 30, 90, 180, 365].map((d) => <option key={d} value={d}>{d} วัน</option>)}
              </select>
            </label>
            {!editing && <Button sm onClick={() => setEditing(true)}>{p.note ? "แก้โน้ต" : "จดโน้ต"}</Button>}
          </div>
          {editing ? (
            <div className="flex gap-2">
              <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="ทำไมคนนี้สำคัญ เช่น ที่ปรึกษาโปรเจค จนส่งเล่มเดือน ม.ค."
                className="grow bg-panel border border-line rounded-lg px-2 py-1 text-sm" />
              <Button sm kind="p" disabled={busy} onClick={() => run(() => api.setNote(p.id, note), "บันทึกโน้ตแล้ว").then(() => setEditing(false))}>บันทึก</Button>
            </div>
          ) : p.note ? <p className="text-sm border-l-2 border-accent pl-2">“{p.note}”</p> : null}
          {p.demote_reason && <p className="text-xs text-muted">เหตุผลที่ลดขั้น: {p.demote_reason}</p>}
          <p className="text-[11px] text-muted">เลขาไม่ใช้โน้ตนี้ตัดสินเอง · ไว้ให้คุณอ่านตอนใกล้หมดอายุ แล้วลบเมื่อคุณตัดสินใหม่</p>
        </div>

        {p.followups.map((f) => (
          <div key={f.id} className="rounded-xl bg-warn-soft text-warn p-3 flex flex-wrap items-center gap-2 text-sm">
            <Icon name="clock" size={16} />
            <span className="grow">{f.waiting_on === "you" ? `คุณยังไม่ตอบ “${f.subject}” มา ${f.days} วัน` : `รอเขาตอบ “${f.subject}” มา ${f.days} วัน`}</span>
            <Button sm onClick={() => api.answerFollowup(f.id, "done").then(onChange)}>ตอบแล้ว</Button>
          </div>
        ))}

        <div className="flex flex-col gap-1">
          <span className="font-semibold text-sm">ส่งอะไรมาบ้าง</span>
          {p.emails.length === 0 && <p className="text-sm text-muted">ยังไม่มีอีเมล</p>}
          <ul className="flex flex-col">
            {p.emails.map((e) => (
              <li key={e.id} className="flex gap-3 py-2 border-t border-line first:border-0">
                <span className="font-mono text-xs text-muted whitespace-nowrap pt-0.5 w-24 shrink-0">{when(e.sent_at)}</span>
                <span className="grow min-w-0">
                  <span className="block font-medium truncate">{e.from_me ? "↪ คุณส่ง: " : ""}{e.subject || "(ไม่มีหัวข้อ)"}</span>
                  {e.summary && <span className="block text-sm text-ink-2">{e.summary}</span>}
                  {!e.summary && !e.from_me && <span className="block text-xs text-muted">{e.stage === "seen" ? "รออ่านในรอบ 00:00 / 12:00" : e.stage === "skimmed" ? "อ่านแค่หัวข้อ" : e.stage === "old" ? "ก่อนเลขาเริ่มอ่าน" : ""}</span>}
                </span>
                <span className="flex flex-col items-end gap-1 shrink-0">
                  {e.done.map((d) => <Chip key={d} tone={d === "นัดรอคุณรับ" ? "warn" : "ok"}>{d}</Chip>)}
                  {e.needs_reply && <Chip tone="warn">ต้องตอบ</Chip>}
                  <a href={e.link} target="_blank" rel="noreferrer" className="text-xs text-accent-strong inline-flex items-center gap-1 hover:underline">Gmail<Icon name="ext" size={12} /></a>
                </span>
              </li>
            ))}
          </ul>
        </div>
        {msg && <p className="text-sm text-muted">{msg}</p>}
      </div>
    </Card>
  );
}

function Followups({ items, onChange }: { items: Followup[] | null; onChange: () => void }) {
  if (items === null) return <Card><div className="pt-4"><Spinner /></div></Card>;
  return (
    <Card title={`เรื่องค้าง · ${items.length}`} right={<span className="text-xs text-muted">เตือนใน #ด่วน ตอน 12:00 เมื่อเกินจำนวนวันที่ตั้ง</span>} flush>
      {items.length === 0 ? <p className="px-4 pb-4 text-sm text-muted">ไม่มีเรื่องค้าง</p> : (
        <ul>
          {items.map((f) => (
            <li key={f.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 border-t border-line">
              <Avatar name={f.name} />
              <span className="grow min-w-0">
                <span className="block font-medium truncate">{f.waiting_on === "you" ? `คุณยังไม่ตอบ ${f.name}` : `รอ ${f.name} ตอบ`} · {f.days} วัน</span>
                <span className="block text-xs text-muted truncate">เรื่อง: {f.subject || "(ไม่มีหัวข้อ)"}</span>
              </span>
              <Button sm onClick={() => api.answerFollowup(f.id, "done").then(onChange)}>{f.waiting_on === "you" ? "ตอบแล้ว" : "ไม่ต้องตามแล้ว"}</Button>
              <Button sm onClick={() => api.answerFollowup(f.id, "later").then(onChange)}>เตือนพรุ่งนี้</Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function AddPerson({ onDone }: { onDone: (id: number) => void }) {
  const [address, setAddress] = useState("");
  const [name, setName] = useState("");
  const [days, setDays] = useState(90);
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState("");
  const add = async () => {
    setMsg("");
    try {
      const r = await api.addPerson(address, name, days || null, note);
      setAddress(""); setName(""); setNote(""); onDone(r.id);
    } catch (e) { setMsg((e as Error).message); }
  };
  const input = "bg-panel border border-line rounded-lg px-2 py-1.5 text-sm";
  return (
    <Card title="ตั้งคนสำคัญล่วงหน้า">
      <div className="flex flex-col gap-2">
        <p className="text-xs text-muted">เช่น “อีเมลนี้สำคัญ รอเลย 3 เดือน” · ถ้าเขาส่งมา เลขาแจ้ง #ด่วน ทันที อ่านละเอียด และลงนัดในปฏิทินให้เลย</p>
        <div className="grid grid-cols-2 gap-2">
          <input className={input} value={address} onChange={(e) => setAddress(e.target.value)} placeholder="อีเมล" />
          <input className={input} value={name} onChange={(e) => setName(e.target.value)} placeholder="ชื่อ (ไม่ใส่ก็ได้)" />
        </div>
        <input className={input} value={note} onChange={(e) => setNote(e.target.value)} placeholder="โน้ตเหตุผล (อ่านเองตอนใกล้หมดอายุ)" />
        <div className="flex items-center gap-2">
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} className={input}>
            {[30, 90, 180, 365].map((d) => <option key={d} value={d}>สำคัญ {d} วัน</option>)}
            <option value={0}>ไม่มีวันหมดอายุ</option>
          </select>
          <Button kind="p" sm disabled={!address.includes("@")} onClick={add}>เพิ่ม</Button>
          {msg && <span className="text-xs text-bad">{msg}</span>}
        </div>
        <Link to="/settings#mail" className="text-xs text-muted hover:text-ink pt-1">
          คีย์เวิร์ดที่แจ้งทันที เรื่องที่สนใจ และวันเตือนเรื่องค้าง: <span className="font-semibold text-accent-strong whitespace-nowrap">ตั้งค่าอีเมล →</span></Link>
      </div>
    </Card>
  );
}
