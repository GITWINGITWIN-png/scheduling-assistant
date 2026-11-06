// จดไอเดีย on the web (W6 ① and the top bar's button): the same box as the Super+I popup (K1).
// As you type, the rules suggest tags (no model). They're picked already, and a click drops one.
// Enter saves, Shift+Enter starts a new line, and the line below says which group the idea joins
// at the next round.
import { useEffect, useRef, useState } from "react";
import { api, type GroupPreview } from "../api";
import { Icon } from "../icons";

function joined(g: GroupPreview): string {
  if (!g) return "บันทึกแล้ว · ยังไม่มีแท็ก เลขาจัดกลุ่มให้รอบเที่ยงและเที่ยงคืน";
  return g.new ? `บันทึกแล้ว · เริ่มกลุ่มใหม่ “${g.name}”` : `บันทึกแล้ว · เข้ากลุ่ม “${g.name}” (${g.size})`;
}

export function IdeaCapture({ onSaved, autoFocus = false, onEscape }: {
  onSaved?: () => void; autoFocus?: boolean; onEscape?: () => void;
}) {
  const [text, setText] = useState("");
  const [suggested, setSuggested] = useState<string[]>([]);
  const [off, setOff] = useState<string[]>([]); // suggestions you clicked away
  const [extra, setExtra] = useState<string[]>([]); // tags you typed after "+ แท็ก"
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ text: string; bad?: boolean } | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!text.trim()) { setSuggested([]); return; }
    const t = setTimeout(() => api.suggestTags(text).then((r) => setSuggested(r.tags), () => {}), 300);
    return () => clearTimeout(t);
  }, [text]);

  const tags = [...suggested.filter((t) => !off.includes(t)), ...extra.filter((t) => !suggested.includes(t))];

  const save = async () => {
    if (!text.trim() || busy) return;
    setBusy(true);
    try {
      // Nothing suggested and nothing added: leave it to the round's rules (null), which may know
      // more by then. Suggestions you all clicked away: no tags, and that's final ([]).
      const r = await api.addIdea(text, tags.length || suggested.length ? tags : null);
      setNote({ text: joined(r.group) });
      setText(""); setSuggested([]); setOff([]); setExtra([]);
      onSaved?.();
    } catch (e) {
      setNote({ text: (e as Error).message, bad: true });
    }
    setBusy(false);
    box.current?.focus();
  };

  const addTag = (raw: string) => {
    const t = raw.trim().replace(/^#/, "").toLowerCase().replace(/\s+/g, "-");
    if (t && !tags.includes(t)) setExtra((x) => [...x, t]);
    setOff((o) => o.filter((x) => x !== t));
    setAdding(false);
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-start gap-2.5 rounded-s border border-line-2 bg-panel px-3.5 py-2.5 focus-within:border-accent focus-within:ring-2 focus-within:ring-accent-soft">
        <Icon name="idea" className="text-muted mt-0.5" />
        <textarea ref={box} rows={text.includes("\n") ? 3 : 1} value={text} autoFocus={autoFocus} disabled={busy}
          placeholder="จดไอเดีย… หรือกด Super+I จากหน้าจอไหนก็ได้"
          className="grow resize-none bg-transparent text-sm outline-none placeholder:text-muted"
          onChange={(e) => { setText(e.target.value); setNote(null); }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void save(); }
            if (e.key === "Escape") { e.preventDefault(); onEscape?.(); }
          }} />
      </div>
      {(text.trim() || note) && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          {text.trim() ? (
            <>
              <span className="text-muted">แท็กที่น่าจะใช่:</span>
              {suggested.map((t) => {
                const picked = !off.includes(t);
                return (
                  <button key={t} type="button" title={picked ? "คลิกเพื่อไม่ใส่แท็กนี้" : "คลิกเพื่อใส่แท็กนี้"}
                    onClick={() => setOff((o) => (picked ? [...o, t] : o.filter((x) => x !== t)))}
                    className={`rounded-full px-2.5 py-0.5 font-semibold cursor-pointer ${picked ? "bg-accent-soft text-accent-strong" : "border border-line-2 text-muted line-through"}`}>
                    #{t}</button>
                );
              })}
              {extra.filter((t) => !suggested.includes(t)).map((t) => (
                <button key={t} type="button" title="คลิกเพื่อเอาออก" onClick={() => setExtra((x) => x.filter((y) => y !== t))}
                  className="rounded-full px-2.5 py-0.5 font-semibold bg-accent-soft text-accent-strong cursor-pointer">#{t}</button>
              ))}
              {adding ? (
                <input autoFocus placeholder="แท็ก" className="w-28 rounded-full border border-line-2 bg-panel px-2.5 py-0.5 outline-none focus:border-accent"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") { e.preventDefault(); addTag(e.currentTarget.value); box.current?.focus(); }
                    if (e.key === "Escape") { setAdding(false); box.current?.focus(); }
                  }} onBlur={(e) => addTag(e.currentTarget.value)} />
              ) : (
                <button type="button" onClick={() => setAdding(true)}
                  className="rounded-full border border-line-2 px-2.5 py-0.5 font-semibold text-ink-2 hover:bg-panel-2 cursor-pointer">+ แท็ก</button>
              )}
              <span className="grow text-right text-muted">Enter บันทึก · Shift+Enter ขึ้นบรรทัด</span>
            </>
          ) : note && (
            <span className={`inline-flex items-center gap-1.5 ${note.bad ? "text-bad" : "text-ok"}`}>
              <Icon name={note.bad ? "alert" : "check"} size={14} />{note.text}</span>
          )}
        </div>
      )}
    </div>
  );
}
