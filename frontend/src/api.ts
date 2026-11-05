// Every call the web page makes to the secretary (backend/app/api/*). One place, typed.

export type Status = { pending: number; tokens_week: number; discord: boolean; theme: string };

export type Task = { task: string; label: string; model: string; effort: string; default_model: string; default_effort: string };
export type Round = { id: string; title: string; when: string; phase: string; active: boolean; enabled: boolean; last_run: string | null; next_run: string | null };
export type Settings = {
  tasks: Task[];
  models: string[];
  efforts: string[];
  planned_tasks: { label: string; model: string; effort: string; phase: string }[];
  theme: string;
  themes: { id: string; name: string; sub: string }[];
  clock: Round[];
  discord: { configured: boolean; connected: boolean; user: string; channels: string[]; problem: string };
  google: { id: string; label: string; does: string; connected: boolean; problem: string }[];
  services: { icon: string; name: string; detail: string; phase: string }[];
};

export type LogItem = {
  id: number; at: string; time: string; date: string; kind: string; summary: string; target: string;
  source_label: string; source_url: string; tokens: number | null; can_undo: boolean; undone_at: string | null;
};

export type Decision = {
  id: number; kind: string; title: string; plan: string; request: string;
  model: string; effort: string; tokens: number | null; created_at: string;
  when: string; from: string; subject: string; // appointment (B2)
};

export type Answer = {
  kind: "answer" | "plan"; text: string; model: string; effort: string; seconds: number; tokens: number;
  sources: string[]; decision_id: number | null; title: string; footer: string;
};

export class ApiError extends Error {}

async function call<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    // The backend explains refusals in plain words ({"detail": "..."}); show that, not the status code
    const detail = await res.json().then((j) => j.detail, () => null);
    throw new ApiError(typeof detail === "string" ? detail : `เกิดข้อผิดพลาด (${res.status})`);
  }
  return res.json();
}

// W2 คนและอีเมล (B2)
export type Level = "important" | "interested" | "ignored";
export type Person = {
  id: number; name: string; level: Level; level_name: string; source: string; until: string | null;
  days_left: number | null; expired: boolean; note: string; demote_reason: string; last_mail_at: string | null;
  addresses: string[]; awaiting: boolean;
};
export type PersonMail = { id: string; sent_at: string; subject: string; from_me: boolean; summary: string; stage: string; link: string; needs_reply: boolean; done: string[] };
export type Followup = { id: number; person_id: number | null; name: string; subject: string; waiting_on: "you" | "them"; since: string; days: number; remind_after_days: number };
export type PersonDetail = Person & { emails: PersonMail[]; followups: Followup[] };
export type MailSettings = {
  keywords: string[]; interests: string[]; followup_days: number; emails_week: number; last_watch: string | null;
  accounts: { id: string; label: string; connected: boolean; problem: string; address: string }[];
};

export const api = {
  status: () => call<Status>("GET", "/api/status"),
  settings: () => call<Settings>("GET", "/api/settings"),
  setTask: (task: string, model: string, effort: string) => call<Task & { action_id: number }>("PUT", `/api/settings/llm/${task}`, { model, effort }),
  setTheme: (theme: string) => call<{ theme: string }>("PUT", "/api/settings/theme", { theme }),
  setRound: (id: string, on: boolean) => call<{ round: string; on: boolean; action_id: number }>("PUT", `/api/settings/rounds/${id}`, { on }),
  log: (range: string, group: string) =>
    call<{ items: LogItem[]; groups: { key: string; label: string }[] }>("GET", `/api/log?range=${range}&group=${group}`),
  undo: (id: number) => call<LogItem>("POST", `/api/log/${id}/undo`),
  decisions: () => call<{ items: Decision[] }>("GET", "/api/decisions?status=pending"),
  people: (level: Level) => call<{ counts: Record<Level | "followups", number>; items: Person[] }>("GET", `/api/people?level=${level}`),
  person: (id: number) => call<PersonDetail>("GET", `/api/people/${id}`),
  setLevel: (id: number, level: Level, opts: { days?: number | null; note?: string; reason?: string } = {}) =>
    call<{ action_id: number }>("POST", `/api/people/${id}/level`, { level, ...opts }),
  setNote: (id: number, note: string) => call<{ ok: boolean }>("PUT", `/api/people/${id}/note`, { note }),
  addPerson: (address: string, name: string, days: number | null, note: string) =>
    call<{ id: number; action_id: number }>("POST", "/api/people", { address, name, days, note }),
  followups: () => call<{ items: Followup[] }>("GET", "/api/followups"),
  answerFollowup: (id: number, act: "done" | "later") => call<{ ok: boolean }>("POST", `/api/followups/${id}`, { act }),
  mailSettings: () => call<MailSettings>("GET", "/api/mail/settings"),
  saveMailSettings: (s: { keywords?: string[]; interests?: string[]; followup_days?: number }) => call<MailSettings>("PUT", "/api/mail/settings", s),
  answerAppointment: (id: number, accept: boolean) =>
    call<{ id: number; status: string; action_id: number | null }>("POST", `/api/appointments/${id}`, { accept }),
  decide: (id: number, action: "approve" | "reject") => call<{ id: number; status: string; action_id: number }>("POST", `/api/decisions/${id}`, { action }),
  revise: (id: number, change: string) => call<Answer>("POST", `/api/decisions/${id}/revise`, { change }),
};

export type AskEvents = {
  onText: (chunk: string) => void;
  onNote: (note: string) => void;
  onDone: (answer: Answer) => void;
  onError: (message: string) => void;
};

/** Ask the secretary and receive the answer as it is written (the backend streams NDJSON lines). */
export async function askStream(text: string, deep: boolean, on: AskEvents, signal?: AbortSignal): Promise<void> {
  let res: Response;
  try {
    res = await fetch("/api/ask", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text, deep }), signal,
    });
  } catch {
    if (!signal?.aborted) on.onError("ติดต่อเลขาไม่ได้ · เซิร์ฟเวอร์เปิดอยู่ไหม");
    return;
  }
  if (!res.ok || !res.body) return on.onError(`ถามไม่สำเร็จ (${res.status})`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let nl: number;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (!line) continue;
      const msg = JSON.parse(line);
      if (msg.type === "text") on.onText(msg.text);
      else if (msg.type === "note") on.onNote(msg.text);
      else if (msg.type === "done") on.onDone(msg.answer);
      else if (msg.type === "error") on.onError(msg.message);
    }
  }
}
