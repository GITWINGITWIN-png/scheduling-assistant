// ถามเลขา: the ask box in the top bar of every page (P10), and the panel the answer streams into.
// Same flow as the Discord chat: Sonnet answers with its sources; an order or a plan request goes
// to Opus, which does it (B9: listed with ย้อนกลับ, and ทำเลย for what can't be undone) or plans it;
// "ให้ Opus คิดต่อ" asks Opus the same question.
// Claude remembers what this box shows (the last few questions and answers), like the Discord chat
// reads its channel, so "ทำต่อ" carries on the order before it. ล้าง empties the box and its memory.
import { useCallback, useEffect, useRef, useState } from "react";
import { askStream, type Answer, type Said } from "../api";
import { Icon } from "../icons";
import { useStatus } from "../status";
import { OrderParts } from "./OrderParts";
import { PlanActions } from "./PlanActions";
import { useDismiss } from "./popover";
import { Button, Markdown, Spinner } from "./ui";

type Turn = { id: number; question: string; deep: boolean; text: string; note: string; answer: Answer | null; error: string };

let nextId = 1;
const REMEMBER = 3; // questions and answers sent along with a new question (the server trims long ones)

/** The conversation before a question, as Claude should see it: the answer's text and its lists. */
function remembered(turns: Turn[]): Said[] {
  return turns.filter((t) => t.answer).slice(-REMEMBER).flatMap((t): Said[] => [
    { who: "คุณ", text: t.question },
    { who: "เลขา", text: answerText(t.answer!) },
  ]);
}

function answerText(a: Answer): string {
  const lines = [a.kind === "plan" ? `แผน: ${a.title}` : "", a.text];
  if (a.confirms?.length) lines.push("รอคุณกดยืนยัน (ย้อนกลับไม่ได้):", ...a.confirms.map((c) => `- ${c.title}`));
  if (a.done?.length) lines.push("เลขาทำแล้ว:", ...a.done.map((d, i) => `${i + 1}. ${d.summary}${d.target ? ` · ${d.target}` : ""}`));
  return lines.filter(Boolean).join("\n");
}

export function AskBox() {
  const { refresh } = useStatus();
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [open, setOpen] = useState(false);
  const busy = turns.some((t) => !t.answer && !t.error);
  const wrap = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLInputElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  useDismiss(wrap, open, useCallback(() => setOpen(false), []));

  // "/" anywhere focuses the ask box (the kbd hint in the mockup)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
      if (e.key === "/" && !typing) { e.preventDefault(); field.current?.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => { if (open) bottom.current?.scrollIntoView({ block: "end" }); }, [turns, open]);

  const update = (id: number, patch: (t: Turn) => Partial<Turn>) =>
    setTurns((all) => all.map((t) => (t.id === id ? { ...t, ...patch(t) } : t)));

  // before: how many turns came before the question (all of them for a new one; for "ให้ Opus คิดต่อ",
  // the ones before the question it asks again, as on Discord)
  const ask = (question: string, deep = false, before = turns.length) => {
    const id = nextId++;
    const history = remembered(turns.slice(0, before));
    setTurns((all) => [...all, { id, question, deep, text: "", note: "", answer: null, error: "" }]);
    setOpen(true);
    askStream(question, deep, {
      onText: (chunk) => update(id, (t) => ({ text: t.text ? `${t.text}\n\n${chunk}` : chunk })),
      onNote: (note) => update(id, () => ({ note, text: "" })),
      onDone: (answer) => { update(id, () => ({ answer })); refresh(); },
      onError: (error) => update(id, () => ({ error })),
    }, history);
  };

  const addRevised = (a: Answer, question: string) =>
    setTurns((all) => [...all, { id: nextId++, question: `แก้แผน: ${question}`, deep: true, text: a.text, note: "", answer: a, error: "" }]);

  return (
    <div ref={wrap} className="relative">
      <form onSubmit={(e) => { e.preventDefault(); const q = input.trim(); if (q && !busy) { ask(q); setInput(""); } }}
        className="flex items-center gap-2 w-[min(440px,40vw)] rounded-full border border-line-2 bg-panel px-3.5 py-1.5 focus-within:border-accent">
        <Icon name="search" size={16} className="text-muted" />
        <input ref={field} value={input} onChange={(e) => setInput(e.target.value)} onFocus={() => turns.length && setOpen(true)}
          placeholder="ถามเลขา… เช่น “วันนี้เลขาทำอะไรไปบ้าง”" className="grow bg-transparent outline-none text-sm min-w-0" />
        <kbd className="text-[11px] text-muted border border-line-2 rounded px-1.5">/</kbd>
      </form>

      {/* Closed = hidden, not removed: the buttons under each answer keep what you pressed. (Removed
          and built again, they came back as if nothing had been pressed, and a press said 409.) */}
      {turns.length > 0 && (
        <div className={`${open ? "flex" : "hidden"} absolute right-0 top-[calc(100%+10px)] z-20 w-[min(620px,92vw)] max-h-[72vh]
          overflow-auto bg-panel border border-line rounded-card shadow-[0_18px_50px_rgba(0,0,0,0.22)] p-4 flex-col gap-4`}>
          <div className="flex items-center">
            <span className="text-sm font-semibold grow">ถามเลขา</span>
            <Button sm kind="ghost" onClick={() => setTurns([])}>ล้าง</Button>
            <Button sm kind="ghost" icon="x" onClick={() => setOpen(false)} />
          </div>
          {turns.map((t, i) => (
            <article key={t.id} className="flex flex-col gap-2 border-t border-line pt-3 first-of-type:border-0 first-of-type:pt-0">
              <p className="self-end max-w-[85%] rounded-s bg-accent-soft px-3 py-1.5 text-sm">{t.question}</p>
              {t.note && <p className="text-sm text-accent-strong flex items-center gap-1.5"><Icon name="sparkle" size={15} />{t.note}</p>}
              {t.answer?.kind === "plan" && <h3 className="font-semibold">{t.answer.title}</h3>}
              {(t.answer?.text || t.text) && <Markdown text={t.answer?.text || t.text} />}
              {!t.answer && !t.error && <Spinner label={t.note ? "Opus กำลังทำตามคำสั่ง…" : t.deep ? "Opus กำลังคิด…" : "เลขากำลังตอบ…"} />}
              {t.error && <p className="text-sm text-bad">{t.error}</p>}
              {t.answer && (
                <>
                  <p className="text-xs text-muted">{t.answer.footer}</p>
                  <OrderParts done={t.answer.done} confirms={t.answer.confirms} />
                  {t.answer.kind === "plan" && t.answer.decision_id
                    ? <PlanActions decisionId={t.answer.decision_id} onRevised={(a) => addRevised(a, t.question)} />
                    : t.answer.kind === "answer" && t.answer.model !== "Opus" && !t.deep
                      && <div><Button sm disabled={busy} onClick={() => ask(t.question, true, i)}>ให้ Opus คิดต่อ</Button></div>}
                </>
              )}
            </article>
          ))}
          <div ref={bottom} />
        </div>
      )}
    </div>
  );
}
