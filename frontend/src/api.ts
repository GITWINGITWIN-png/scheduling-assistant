// Every call the web page makes to the secretary (backend/app/api/*). One place, typed.

export type Status = {
  pending: number; tokens_week: number; discord: boolean; theme: string;
  stale?: boolean; // the backend code on disk is newer than the running one: restart (older backends don't send it)
  counts?: { people?: number; decisions?: number }; // the side menu's red numbers (people: today's เรื่องสำคัญ; decisions: what waits for you)
  quota?: { week_left: number; at: string; line: number; auto?: boolean } | null; // B5: what's left of your Claude week (null: not read yet); line and auto: the rule book's rule
};

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
  google: { id: string; label: string; does: string; connected: boolean; problem: string; address: string }[];
  services: { icon: string; name: string; detail: string; phase: string }[];
  jobs_rule: { auto: boolean; line: number; approval_days: number }; // B5: อนุมัติเอง (set in the rule book)
};

export type LogItem = {
  id: number; at: string; time: string; date: string; kind: string; summary: string; target: string;
  source_label: string; source_url: string; tokens: number | null; can_undo: boolean; undone_at: string | null;
};

export type Decision = {
  id: number; kind: string; title: string; plan: string; request: string;
  model: string; effort: string; tokens: number | null; created_at: string;
  when: string; from: string; subject: string; // appointment (B2)
  folder: string; exists: boolean; link: string; // course (B3)
  clash?: string | null; // appointment: what else is at that time ("" = nothing), null for other kinds
  rule?: string; // appointment: a rule in your rule book it goes against ("" = none) (B5)
};

export type Answer = {
  kind: "answer" | "plan"; text: string; model: string; effort: string; seconds: number; tokens: number;
  sources: string[]; decision_id: number | null; title: string; footer: string;
};

// W5 ตาราง (B3)
export type CalItem = {
  id: number; title: string; start: string; end: string; all_day: boolean; location: string;
  description: string; // รายละเอียด: what you typed, or its description in Google Calendar
  source: string; source_name: string; recurring: boolean; link: string; mail: string; // link: Google Calendar · mail: the email it came from
  status: "placed" | "proposed"; decision_id: number | null; from: string; // proposed: waiting for you to รับ (who asked)
};
export type BlockItem = {
  id: number; task_id: number; title: string; start: string; end: string; pinned: boolean; past: boolean;
  running: boolean; task_status: "open" | "done" | "dropped";
};
export type DeadlineItem = { task_id: number; title: string; due: string; source: string; link: string };
export type Week = { events: CalItem[]; blocks: BlockItem[]; deadlines: DeadlineItem[]; plan: { planned_at: string | null; short: { task_id: number; title: string; minutes: number }[] } };
export type PlanMode = "early" | "late";
export type TaskRow = {
  id: number; title: string; due: string | null; status: "open" | "done" | "dropped"; source: string;
  est_minutes: number | null; est_default: number; plan_mode: PlanMode; done_minutes: number; booked_minutes: number; link: string;
  block_minutes: number | null; daily_minutes: number | null; // null: the rules' (กติกาตาราง)
  details: string; // รายละเอียดงาน: what, where, where to hand it in (links allowed)
};
export type NewTask = {
  title: string; due: string | null; est_minutes: number | null; plan_mode: PlanMode;
  block_minutes: number | null; daily_minutes: number | null; details: string;
};
export type NewEvent = { title: string; start: string; end: string; all_day: boolean; location: string; description: string };
export type Saved = { action_id: number; plan: string | null };
export type ScheduleRules = {
  rules: { day_start: string; day_end: string; min_block: number; max_block: number; gap: number; per_task_per_day: number; horizon_days: number };
  estimates: Record<string, number>;
  reminders: string[];
};
export type CourseRow = {
  id: string; name: string; state: "asking" | "followed" | "ended" | "ignored"; state_name: string; folder: string; link: string;
  decision_id: number | null; files: { name: string; path: string }[]; file_count: number;
};

// W1 วันนี้ (B4)
export type DayItem = { start: string; end: string; title: string; kind: "meet" | "block" | "dead" | "allday"; sub: string };
export type RoundMark = { at: string; title: string; done: boolean; line: string };
export type BriefView = { made_at: string; title: string; headline: string; fields: [string, string][]; footer: string; sent: boolean; link: string };
export type TodayPage = {
  greeting: string; brief: BriefView | null; headline: string; morning_on: boolean;
  plan: DayItem[]; secretary: RoundMark[]; hours: [number, number];
  important: { id: string; who: string; summary: string; at: string; done: string[]; link: string }[];
};

// W8 สมุดกติกา (B5)
export type Part = "planner" | "mail" | "jobs" | "ask" | "clock" | "all";
/** A rule that lives in your settings, shown in the rule book (its value is set where `edit` points). */
export type SystemRule = {
  key: "schedule" | "mail" | "jobs" | "never"; text: string; used_by: Part[];
  edit?: string; enabled?: boolean; line?: number; fixed?: boolean; note?: string;
};
export type RuleRow = {
  id: number; kind: "yours" | "learned" | "high_risk"; text: string; used_by: Part[]; enabled: boolean;
  status: "active" | "pending" | "dismissed"; effect: { type: string } | null; evidence: string; fixed: boolean; updated_at: string | null;
};
export type RiskRow = { id: number; key: string; text: string; fixed: boolean; hint: string };
export type RulesPage = {
  system: SystemRule[]; yours: RuleRow[]; learned: RuleRow[]; risks: RiskRow[]; parts: Record<Part, string>;
  counts: { yours: number; learned: number; risks: number };
};
/** What a sentence would become (nothing saved yet). kind "unsupported": `why` says why not. */
export type Proposal = {
  kind: string; text: string; used_by: Part[]; why: string; ok: boolean; tokens: number;
  effect: Record<string, unknown> | null; change: Record<string, unknown> | null;
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
  // W1 วันนี้ (B4)
  today: () => call<TodayPage>("GET", "/api/today"),
  // W5 ตาราง (B3)
  week: (start: string, end: string) => call<Week>("GET", `/api/schedule?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`),
  replan: () => call<{ line: string }>("POST", "/api/schedule/replan"),
  tasks: () => call<{ items: TaskRow[] }>("GET", "/api/tasks"),
  addTask: (t: NewTask) => call<Saved & { id: number }>("POST", "/api/tasks", t),
  // Only the fields sent change; null puts one back to its default.
  editTask: (id: number, change: Partial<NewTask>) => call<Saved>("PATCH", `/api/tasks/${id}`, change),
  taskDone: (id: number) => call<Saved>("POST", `/api/tasks/${id}/done`),
  addEvent: (e: NewEvent) => call<Saved & { id: number }>("POST", "/api/events", e),
  rules: () => call<ScheduleRules>("GET", "/api/schedule/rules"),
  saveRules: (r: { day_start: string; day_end: string; max_block: number; per_task_per_day: number; gap: number; estimates: Record<string, number>; reminders: string[] }) =>
    call<{ action_id: number }>("PUT", "/api/schedule/rules", r),
  courses: () => call<{ items: CourseRow[] }>("GET", "/api/courses"),
  answerCourse: (decisionId: number, follow: boolean, folder?: string) =>
    call<{ status: string; action_id: number }>("POST", `/api/courses/decisions/${decisionId}`, { follow, folder }),
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
  // W8 สมุดกติกา (B5)
  ruleBook: () => call<RulesPage>("GET", "/api/rules"),
  parseRule: (text: string) => call<Proposal>("POST", "/api/rules/parse", { text }),
  addRule: (r: { kind: string; text: string; used_by?: Part[]; effect?: Record<string, unknown> | null; change?: Record<string, unknown> | null }) =>
    call<{ rule_id?: number; action_id: number; why: string }>("POST", "/api/rules", r),
  editRule: (id: number, change: { text?: string; used_by?: Part[]; enabled?: boolean }) =>
    call<RuleRow & { action_id: number }>("PATCH", `/api/rules/${id}`, change),
  deleteRule: (id: number) => call<{ action_id: number }>("DELETE", `/api/rules/${id}`),
  answerLearned: (id: number, accept: boolean) => call<RuleRow & { action_id: number }>("POST", `/api/rules/${id}/answer`, { accept }),
  setJobsRule: (r: { auto?: boolean; line?: number }) => call<{ auto: boolean; line: number; action_id: number }>("PUT", "/api/rules/jobs", r),
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
