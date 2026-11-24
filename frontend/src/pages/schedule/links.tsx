// Links inside task details: found in the text you typed (or that came from Classroom) and
// made clickable wherever the details are shown.
import { Fragment } from "react";

const LINK = /https?:\/\/[^\s<>"']+/g;

/** Every link in the text, without the punctuation that usually follows one ("…/x)." -> "…/x"). */
export function findLinks(text: string): string[] {
  return [...new Set((text.match(LINK) ?? []).map((u) => u.replace(/[.,!?;:)\]]+$/, "")))];
}

/** "classroom.google.com/c/…/details" — short enough for a chip. */
export function shortLink(url: string): string {
  try {
    const u = new URL(url);
    const path = u.pathname.length > 22 ? `${u.pathname.slice(0, 10)}…${u.pathname.slice(-10)}` : u.pathname;
    return u.hostname.replace(/^www\./, "") + (path === "/" ? "" : path);
  } catch {
    return url;
  }
}

/** The text as written (line breaks kept), with its links clickable. */
export function Linked({ text, className = "" }: { text: string; className?: string }) {
  const parts: (string | { url: string })[] = [];
  let last = 0;
  for (const m of text.matchAll(LINK)) {
    const url = m[0].replace(/[.,!?;:)\]]+$/, "");
    parts.push(text.slice(last, m.index), { url });
    last = m.index! + url.length;
  }
  parts.push(text.slice(last));
  return (
    <div className={`whitespace-pre-wrap break-words ${className}`}>
      {parts.map((p, i) => typeof p === "string" ? <Fragment key={i}>{p}</Fragment>
        : <a key={i} href={p.url} target="_blank" rel="noopener" className="text-accent-strong underline break-all">{p.url}</a>)}
    </div>
  );
}

/** What the button to a task's source says: for Classroom, that's where you hand it in. */
export function sourceLabel(source: string): string {
  return source === "Classroom" ? "ส่งงานใน Classroom" : source === "อีเมล" ? "เปิดอีเมล" : "เปิดที่มา";
}
