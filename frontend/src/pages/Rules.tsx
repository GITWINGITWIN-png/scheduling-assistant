// W8 สมุดกติกา (B5), laid out as the plan's mockup (docs/plan-v2/stage2/web.py w8): your rules (the
// ones that live in your settings first, then the ones you added), what the secretary learned from
// your answers (not used until you accept it), and the high-risk work that always asks first.
// A rule can be typed as a sentence: the secretary turns it into a rule and you check it before
// it's saved (W8 ⑤). Every change shows a toast with เลิกทำ, and is in สิ่งที่เลขาทำ.
import { useCallback, useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { Link } from "react-router";
import { api, type Part, type Proposal, type RiskRow, type RuleRow, type RulesPage, type SystemRule } from "../api";
import { Toast, type ToastMsg } from "../components/Toast";
import { Button, Card, Chip, Spinner, Switch, Tabs } from "../components/ui";
import { Icon } from "../icons";
import { useStatus } from "../status";

type Tab = "mine" | "learned" | "risks";
type Done = (text: string, actionId: number | null) => void;
type Fail = (e: unknown) => void;
type Ctx = { parts: (p: Part[]) => string; done: Done; fail: Fail };

const NOTE_PARTS: { key: Part; label: string }[] = [{ key: "ask", label: "ถามเลขา" }, { key: "jobs", label: "ตัวคุมงานเบื้องหลัง" }];

/** One rule as the mockup draws it: a switch, the rule, who uses it, and แก้ on the right. */
function Line({ toggle, text, sub, side, children, title }: {
  toggle: ReactNode; text: ReactNode; sub: ReactNode; side?: ReactNode; children?: ReactNode; title?: string;
}) {
  return (
    <li className="py-2.5" title={title}>
      <div className="flex items-center gap-3">
        {toggle}
        <span className="grow min-w-0">
          <span className="block font-semibold text-[14px] leading-snug">{text}</span>
          <span className="block text-xs text-muted">{sub}</span>
        </span>
        {side}
      </div>
      {children}
    </li>
  );
}

function EditLink({ to }: { to: string }) {
  return <Link to={to} className="inline-flex items-center rounded-full border border-line-2 bg-panel hover:bg-panel-2 text-xs font-medium px-3 py-1">แก้</Link>;
}

// ------------------------------------------------------------------ rules that live in your settings
function SystemLine({ r, ctx }: { r: SystemRule; ctx: Ctx }) {
  const [editing, setEditing] = useState(false);
  const [line, setLine] = useState(String(r.line ?? 70));
  if (r.key === "jobs") {
    const save = () => api.setJobsRule({ line: Number(line) }).then((x) => { setEditing(false); ctx.done(`เส้นโควตาเป็น ${x.line}% แล้ว`, x.action_id); }, ctx.fail);
    return (
      <Line toggle={<Switch on={!!r.enabled} title={r.enabled ? "เปิดอยู่: แผนเสี่ยงต่ำเริ่มเองได้เมื่อโควตาเกินเส้น" : "ปิดอยู่: ทุกแผนถามคุณก่อน"}
        onChange={(on) => api.setJobsRule({ auto: on }).then((x) => ctx.done(on ? "เปิดให้งานเบื้องหลังทำเองได้" : "ปิดแล้ว · ทุกแผนจะถามคุณก่อน", x.action_id), ctx.fail)} />}
        text={r.text} sub={r.enabled ? ctx.parts(r.used_by) : `${ctx.parts(r.used_by)} · ปิดอยู่: ทุกแผนถามคุณก่อน`}
        side={<Button sm onClick={() => setEditing((e) => !e)}>แก้</Button>}>
        {editing && (
          <div className="mt-2 ml-[46px] flex flex-wrap items-center gap-2 text-sm">
            <span className="text-ink-2">ทำเองได้เมื่อโควตาสัปดาห์เหลือเกิน</span>
            <input type="number" min={10} max={100} value={line} onChange={(e) => setLine(e.target.value)}
              className="w-16 h-8 rounded-s border border-line-2 bg-panel px-2 text-right" />
            <span className="text-ink-2">%</span>
            <Button sm kind="p" onClick={save}>บันทึก</Button>
            <Button sm kind="ghost" onClick={() => setEditing(false)}>ยกเลิก</Button>
          </div>
        )}
      </Line>
    );
  }
  if (r.fixed) {
    return <Line toggle={<Switch on title="ปิดไม่ได้" />} text={r.text} sub={ctx.parts(r.used_by)} title={r.note}
      side={<span className="text-xs text-muted whitespace-nowrap" title={r.note}>ปิดไม่ได้ · ทำไม?</span>} />;
  }
  return <Line toggle={<Switch on title="ใช้อยู่เสมอ · ค่าตั้งในหน้าตั้งค่า" />} text={r.text} sub={`${ctx.parts(r.used_by)} · ตั้งในหน้าตั้งค่า`}
    side={r.edit ? <EditLink to={r.edit} /> : null} />;
}

// ------------------------------------------------------------------ rules you added, and learned ones you accepted
function RuleLine({ r, ctx }: { r: RuleRow; ctx: Ctx }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(r.text);
  const [used, setUsed] = useState<Part[]>(r.used_by);
  const note = r.effect === null;
  const save = () => api.editRule(r.id, note ? { text, used_by: used } : { text })
    .then((x) => { setEditing(false); ctx.done("แก้กติกาแล้ว", x.action_id); }, ctx.fail);
  const sub = [ctx.parts(r.used_by), r.kind === "learned" ? "เรียนรู้จากการตัดสินของคุณ" : "", r.enabled ? "" : "ปิดอยู่"].filter(Boolean).join(" · ");
  return (
    <Line toggle={<Switch on={r.enabled} onChange={(on) => api.editRule(r.id, { enabled: on })
      .then((x) => ctx.done(on ? "เปิดกติกาแล้ว" : "ปิดกติกาแล้ว", x.action_id), ctx.fail)} />}
      text={<span className={r.enabled ? "" : "text-muted"}>{r.text}</span>} sub={sub}
      side={<Button sm onClick={() => { setEditing((e) => !e); setText(r.text); setUsed(r.used_by); }}>แก้</Button>}>
      {editing && (
        <div className="mt-2 ml-[46px] flex flex-col gap-2">
          <input value={text} onChange={(e) => setText(e.target.value)} className="h-9 rounded-s border border-line-2 bg-panel px-2.5 text-sm" />
          {note && (
            <div className="flex flex-wrap items-center gap-3 text-xs text-ink-2">
              <span>ใช้โดย</span>
              {NOTE_PARTS.map((p) => (
                <label key={p.key} className="inline-flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={used.includes(p.key)}
                    onChange={(e) => setUsed((u) => (e.target.checked ? [...u, p.key] : u.filter((k) => k !== p.key)))} />
                  {p.label}
                </label>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <Button sm kind="p" onClick={save} disabled={!text.trim() || (note && !used.length)}>บันทึก</Button>
            <Button sm kind="ghost" onClick={() => setEditing(false)}>ยกเลิก</Button>
            {r.kind === "yours" && (
              <span className="ml-auto"><Button sm kind="ghost" icon="x"
                onClick={() => api.deleteRule(r.id).then((x) => ctx.done("ลบกติกาแล้ว", x.action_id), ctx.fail)}>ลบกติกา</Button></span>
            )}
          </div>
        </div>
      )}
    </Line>
  );
}

// ------------------------------------------------------------------ a rule typed as a sentence (W8 ⑤)
function Sentence({ inputRef, ctx }: { inputRef: RefObject<HTMLInputElement | null>; ctx: Ctx }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [p, setP] = useState<Proposal | null>(null);
  const [wording, setWording] = useState("");
  const read = () => {
    if (!text.trim() || busy) return;
    setBusy(true);
    setP(null);
    api.parseRule(text).then((x) => { setP(x); setWording(x.text); }, ctx.fail).finally(() => setBusy(false));
  };
  const apply = () => {
    if (!p) return;
    api.addRule({ kind: p.kind, text: wording, used_by: p.used_by, effect: p.effect, change: p.change })
      .then((x) => { ctx.done(`ใช้กติกานี้แล้ว · ${x.why}`, x.action_id); setP(null); setText(""); }, ctx.fail);
  };
  return (
    <div className="flex flex-col gap-2">
      <label className="flex items-center gap-2 h-10 rounded-s border border-line-2 bg-panel px-3 focus-within:border-accent focus-within:shadow-[0_0_0_3px_var(--color-accent-soft)]">
        <Icon name="plus" size={16} className="text-muted" />
        <input ref={inputRef} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && read()}
          placeholder="เพิ่มกติกาด้วยคำพูดธรรมดา… เช่น “ไม่นัดวันอาทิตย์”" className="grow min-w-0 bg-transparent outline-none text-sm" />
        {text.trim() && !busy && <Button sm kind="p" onClick={read}>แปลงเป็นกติกา</Button>}
        {busy && <Spinner label="เลขากำลังอ่าน…" />}
      </label>
      {p && (
        <div className={`rounded-card border px-4 py-3 flex flex-col gap-2 ${p.ok ? "border-line bg-panel" : "border-warn/40 bg-warn-soft"}`}>
          {p.ok ? (
            <>
              <span className="text-xs text-muted">เลขาเข้าใจว่า{p.kind === "high_risk" ? " · งานเสี่ยงสูง" : ""}</span>
              <input value={wording} onChange={(e) => setWording(e.target.value)}
                className="h-9 rounded-s border border-line-2 bg-panel px-2.5 text-sm font-semibold" />
              <span className="text-xs text-muted">{ctx.parts(p.used_by)}</span>
              <span className="text-[13px] text-ink-2">{p.why}</span>
              <div className="flex flex-wrap items-center gap-2">
                <Button sm kind="ok" onClick={apply} disabled={!wording.trim()}>ใช้กติกานี้</Button>
                <Button sm kind="ghost" onClick={() => setP(null)}>ยกเลิก</Button>
                <span className="ml-auto text-[11px] text-muted">อ่านด้วย Sonnet · {p.tokens.toLocaleString("th-TH")} โทเคน</span>
              </div>
            </>
          ) : (
            <div className="flex items-start gap-2 text-sm">
              <Icon name="alert" size={16} className="text-warn mt-0.5" />
              <span className="grow">{p.why}</span>
              <Button sm kind="ghost" onClick={() => setP(null)}>ปิด</Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ what the secretary learned (W8 ③)
function LearnedItem({ r, ctx }: { r: RuleRow; ctx: Ctx }) {
  return (
    <li className="py-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5">
      <Icon name="sparkle" size={16} className="text-muted" />
      <span className="grow min-w-0 basis-40">
        <span className="block font-semibold text-[14px]">{r.text}</span>
        <span className="block text-xs text-muted">{r.evidence}</span>
      </span>
      {r.status === "pending" ? (
        <span className="flex gap-1.5">
          <Button sm kind="ok" onClick={() => api.answerLearned(r.id, true).then((x) => ctx.done("ใช้เป็นกติกาแล้ว", x.action_id), ctx.fail)}>ใช้เป็นกติกา</Button>
          <Button sm onClick={() => api.answerLearned(r.id, false).then((x) => ctx.done("ไม่ใช้ · จะไม่เสนออีก", x.action_id), ctx.fail)}>ไม่ใช่</Button>
        </span>
      ) : r.status === "active" ? <Chip tone="ok">ใช้อยู่</Chip> : <Chip>คุณบอกว่าไม่ใช่</Chip>}
    </li>
  );
}

const LEARN_EMPTY = "ยังไม่เจอรูปแบบใหม่ · เลขานับจากการตอบนัดและแผนงานเบื้องหลังของคุณ เจอแล้วจะขึ้นที่นี่ให้คุณยืนยันก่อนใช้";

// ------------------------------------------------------------------ high-risk work (W8 ④)
function AddRisk({ ctx }: { ctx: Ctx }) {
  const [text, setText] = useState("");
  const add = () => text.trim() && api.addRule({ kind: "high_risk", text })
    .then((x) => { ctx.done(`เพิ่มงานเสี่ยงสูงแล้ว · ${x.why}`, x.action_id); setText(""); }, ctx.fail);
  return (
    <label className="flex items-center gap-2 h-9 rounded-s border border-line-2 bg-panel px-3 focus-within:border-accent">
      <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()}
        placeholder="เพิ่มงานเสี่ยงสูง… เช่น ลบไฟล์" className="grow min-w-0 bg-transparent outline-none text-sm" />
      {text.trim() && <Button sm kind="p" onClick={add}>เพิ่ม</Button>}
    </label>
  );
}

function RiskChips({ risks, ctx }: { risks: RiskRow[]; ctx: Ctx }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {risks.map((r) => (
        <span key={r.id} title={r.hint || "งานแบบนี้ถามคุณก่อนทุกครั้ง"}
          className="inline-flex items-center gap-1 rounded-full bg-bad-soft text-bad px-2.5 py-0.5 text-xs font-medium">
          {r.text}
          {!r.fixed && (
            <button type="button" aria-label={`ลบ ${r.text}`} className="opacity-70 hover:opacity-100 cursor-pointer"
              onClick={() => api.deleteRule(r.id).then((x) => ctx.done("ลบงานเสี่ยงสูงแล้ว", x.action_id), ctx.fail)}>✕</button>
          )}
        </span>
      ))}
    </div>
  );
}

const RISK_NOTE = "เพิ่มได้ระหว่างใช้งาน · ทุกงานยังมีงบโทเคน เกินงบหยุดเสมอ";

// ------------------------------------------------------------------ the page
export function Rules() {
  const { refresh } = useStatus();
  const [page, setPage] = useState<RulesPage | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("mine");
  const [toast, setToast] = useState<ToastMsg | null>(null);
  const sentence = useRef<HTMLInputElement>(null);

  const load = useCallback(() => { api.ruleBook().then(setPage, (e) => setError((e as Error).message)); }, []);
  useEffect(load, [load]);
  const done: Done = (text, actionId) => { setToast({ text, actionId, key: Date.now() }); load(); refresh(); };
  const fail: Fail = (e) => setToast({ text: (e as Error).message, actionId: null, key: Date.now() });
  const undo = async (id: number) => { await api.undo(id); setToast(null); load(); refresh(); };

  if (error) return <p className="text-sm text-bad">{error}</p>;
  if (!page) return <Spinner label="กำลังโหลด…" />;
  const ctx: Ctx = { parts: (p) => "ใช้โดย: " + p.map((k) => page.parts[k] ?? k).join(" · "), done, fail };
  const waiting = page.learned.filter((r) => r.status === "pending");
  // the learned tab: waiting first, then the ones in use, then the ones you said no to
  const history = [...waiting, ...page.yours.filter((r) => r.kind === "learned"), ...page.learned.filter((r) => r.status === "dismissed")];

  return (
    <div className="flex flex-col gap-4">
      <Tabs value={tab} onChange={setTab} options={[
        { key: "mine", label: "กติกาของคุณ", count: page.counts.yours },
        { key: "learned", label: "ที่เลขาเรียนรู้", count: page.counts.learned },
        { key: "risks", label: "งานเสี่ยงสูง", count: page.counts.risks },
      ]} />

      {tab === "mine" && (
        <div className="grid gap-4 items-start lg:grid-cols-2">
          <div className="flex flex-col gap-3 min-w-0">
            <Card title="กติกาของคุณ" right={<Button kind="p" sm icon="plus" onClick={() => sentence.current?.focus()}>เพิ่มกติกา</Button>}>
              <ul className="divide-y divide-line">
                {page.system.map((r) => <SystemLine key={r.key} r={r} ctx={ctx} />)}
                {page.yours.map((r) => <RuleLine key={`${r.id}-${r.updated_at}`} r={r} ctx={ctx} />)}
              </ul>
            </Card>
            <Sentence inputRef={sentence} ctx={ctx} />
          </div>
          <div className="flex flex-col gap-3 min-w-0">
            <Card title="เลขาเรียนรู้จากการตัดสินของคุณ">
              {waiting.length ? <ul className="divide-y divide-line">{waiting.map((r) => <LearnedItem key={r.id} r={r} ctx={ctx} />)}</ul>
                : <p className="text-sm text-muted">{LEARN_EMPTY}</p>}
            </Card>
            <Card title="งานเสี่ยงสูง (ถามคุณทุกครั้ง)">
              <div className="flex flex-col gap-2.5">
                <RiskChips risks={page.risks} ctx={ctx} />
                <span className="text-xs text-muted">{RISK_NOTE}</span>
                <AddRisk ctx={ctx} />
              </div>
            </Card>
          </div>
        </div>
      )}

      {tab === "learned" && (
        <Card title="ที่เลขาเรียนรู้">
          <p className="text-sm text-ink-2 pb-1">เลขานับจากการตัดสินของคุณเอง ไม่ใช้โมเดล · ไม่ใช้จนกว่าคุณกด “ใช้เป็นกติกา” · กด “ไม่ใช่” แล้วจะไม่เสนอเรื่องเดิมอีก</p>
          {history.length ? <ul className="divide-y divide-line">{history.map((r) => <LearnedItem key={r.id} r={r} ctx={ctx} />)}</ul>
            : <p className="text-sm text-muted">{LEARN_EMPTY}</p>}
        </Card>
      )}

      {tab === "risks" && (
        <Card title="งานเสี่ยงสูง (ถามคุณทุกครั้ง)">
          <p className="text-sm text-ink-2 pb-1">แผนงานเบื้องหลังที่มีงานแบบใดแบบหนึ่งในนี้ ถามคุณใน #อนุมัติ ก่อนเสมอ แม้โควตาจะเหลือเยอะ · เลขาตรวจ 2 ชั้น: คนวางแผนติดป้ายเอง และเลขาหาคำที่เข้าข่ายในแผน · {RISK_NOTE}</p>
          <ul className="divide-y divide-line">
            {page.risks.map((r) => (
              <li key={r.id} className="py-2.5 flex items-center gap-3">
                <Icon name="alert" size={16} className="text-bad" />
                <span className="grow min-w-0">
                  <span className="block font-semibold text-[14px]">{r.text}</span>
                  <span className="block text-xs text-muted">{r.hint || "งานที่คุณเพิ่มเอง · คนวางแผนติดป้ายนี้เมื่อแผนมีงานแบบนี้"}</span>
                </span>
                {r.fixed ? <Chip>ตกลงไว้ในแผน</Chip>
                  : <Button sm kind="ghost" icon="x" onClick={() => api.deleteRule(r.id).then((x) => ctx.done("ลบงานเสี่ยงสูงแล้ว", x.action_id), ctx.fail)}>ลบ</Button>}
              </li>
            ))}
          </ul>
          <div className="pt-2"><AddRisk ctx={ctx} /></div>
        </Card>
      )}

      <Toast msg={toast} onUndo={undo} onClose={() => setToast(null)} />
    </div>
  );
}
