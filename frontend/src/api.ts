// Every call the web page makes to the secretary (backend/app/api/*). One place, typed.

export type Status = {
  pending: number; tokens_week: number; discord: boolean; theme: string;
  stale?: boolean; // the backend code on disk is newer than the running one: restart (older backends don't send it)
  counts?: { people?: number; decisions?: number; jobs?: number; projects?: number }; // the side menu's numbers (people: today's เรื่องสำคัญ; decisions: what waits for you; jobs: plans waiting for you; projects: on the go)
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
  services: { icon: string; name: string; detail: string; phase: string; state?: string; tone?: "ok" | "warn" | "muted" }[]; // B6: state is live
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
  job_id?: number | null; budget?: number | null; risks?: string[]; why?: string; stuck_at?: string; // background plan (B5)
  project_id?: number | null; // new project (B5)
  group_id?: number | null; size?: number | null; about?: string; // a grown idea group (B6)
  topic?: string; label?: string; what?: string; acts?: [string, string][]; // a weekly review topic (B7)
};

export type Answer = {
  kind: "answer" | "plan" | "done"; text: string; model: string; effort: string; seconds: number; tokens: number;
  sources: string[]; decision_id: number | null; title: string; footer: string;
  done: DoneItem[]; confirms: ConfirmItem[]; // B9: what an order did, and what waits for ทำเลย
};
// B9 สั่งงานผ่านแชท: one thing an order did (ย้อนกลับ when can_undo), one that waits for ทำเลย
export type DoneItem = { id: number; summary: string; target: string; can_undo: boolean };
export type ConfirmItem = { id: number; title: string };
// how carrying out an approved plan is going
export type PlanRun = { status: "none" | "running" | "done" | "failed"; text?: string; done?: DoneItem[]; confirms?: ConfirmItem[] };

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
  outcome?: "" | "done" | "missed" | "away" | "unknown"; worked?: number | null; instead?: string; // B6: what really happened
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
  actual?: { start: string; end: string; what: string; category: string; project: string }[]; recording?: boolean; // B6: ทำจริง
  important: { id: string; who: string; summary: string; at: string; done: string[]; link: string }[];
  news: { id: number; project: string; title: string; body: string; at: string; potential: string; urgent: boolean; failed: boolean; needs_you: boolean; link: string }[];
  jobs: {
    running: { id: number; project: string; title: string; used: number; budget: number; started_at: string; model: string; effort: string } | null;
    queue: { id: number; project: string; title: string; status: string; approved_until: string | null }[];
    runs: { id: number; project: string; title: string; status: string; start: string; end: string; line: string }[];
    round_on: boolean;
  };
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

// W4 งานเบื้องหลัง · W3 โปรเจค (B5)
export type JobStatus = "queued" | "asking" | "ready" | "running" | "done" | "stopped" | "failed" | "rejected" | "dropped" | "paused";
export type JobRow = {
  id: number; project_id: number; project: string; potential: string; source: "progress" | "you"; stuck_at: string; note: string; status: JobStatus;
  title: string; steps: string[]; model: string; effort: string; estimate: number; budget: number; used: number;
  risks: string[]; high_risk: boolean; rule_ok: boolean | null; rule_why: string; decision_id: number | null; why: string;
  approved_until: string | null; branch: string; result: string; plan_tokens: number;
  planned_at: string | null; started_at: string | null; finished_at: string | null;
  efforts: Record<string, number>; // the budget at each effort (the − + stepper)
  start_from?: string; // waiting jobs: where the job will start (the secretary's unmerged branch, or your HEAD)
};
export type JobsPage = {
  quota: { week_left?: number; week_resets_at?: string | null; five_left?: number | null; at?: string; line: number; auto: boolean };
  kpi: { auto: number; asking: number; over_budget: number };
  usage: { today: number; jobs_today: number; week: number }; // tokens the secretary itself used (they move with every job)
  running: JobRow | null; queue: JobRow[]; recent: JobRow[]; projects: { id: number; name: string }[];
  round_on: boolean; window: string; approval_days: number;
};
export type ProjectRow = {
  id: number; name: string; path: string; status: string; status_name: string; potential: string; urgency: number;
  level_set: boolean; hidden: boolean; allow_jobs: boolean; can_work: boolean; is_self: boolean; is_git: boolean;
  last_activity: string | null; commits_14d: number; missing: boolean; decision_id: number | null;
  progress: { next?: string; done?: number; todo?: number };
  news: { title: string; at: string; urgent: boolean; kind: string } | null;
  job: { id: number; status: JobStatus; title: string } | null;
  secretary?: { branch: string; ahead: number } | null; // the secretary's work waiting for you to merge
  connected: boolean | null; // B10: sends its news to the secretary (null: can't, e.g. the secretary itself)
};
export type ConnectGuide = { text: string; inbox: string; example: string; command: boolean; inbox_on: boolean };
export type Advice = { project_id: number; project: string; kind: "stale" | "short"; title: string; detail: string; next: string };
export type ProjectsPage = { items: ProjectRow[]; advice: Advice[]; root: string; scanned: boolean };

export class ApiError extends Error {
  constructor(message: string, readonly status = 0) { super(message); }
}

/** For the buttons under a chat answer (ใช้แผนนี้, ทำเลย, ย้อนกลับ): 409 means it was answered or
 *  undone already, somewhere else or on another copy of the same buttons. The message says what
 *  happened, and the page shows it in place of the buttons, since nothing is left to press. */
export const answeredAlready = (e: unknown): e is ApiError => e instanceof ApiError && e.status === 409;

async function call<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    // The backend explains refusals in plain words ({"detail": "..."}); show that, not the status code
    const detail = await res.json().then((j) => j.detail, () => null);
    throw new ApiError(typeof detail === "string" ? detail : `เกิดข้อผิดพลาด (${res.status})`, res.status);
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

// W6 ไอเดีย (B6)
export type IdeaRow = {
  id: number; text: string; source: "key" | "discord" | "web"; source_name: string; tags: string[];
  tagged: "" | "you" | "rules"; group_id: number | null; group: string; at: string;
};
export type GroupPreview = { name: string; size: number; new: boolean; tag: string } | null;
export type IdeaGroupRow = {
  id: number; name: string; tag: string; status: "open" | "asked" | "later" | "project" | "task"; status_name: string;
  size: number; week: number; grew: string; last: string | null; about: string; tags: string[];
  decision_id: number | null; waiting: boolean; project_id: number | null; task_id: number | null;
  ideas: { id: number; text: string; source: IdeaRow["source"]; at: string }[];
};
export type IdeasPage = { recent: IdeaRow[]; total: number; ungrouped: number; groups: IdeaGroupRow[]; grown: number; round_on: boolean };
export type SavedIdea = { id: number; tags: string[]; group: GroupPreview };

// W2 ข้อเสนอปรับระดับรายสัปดาห์ (B7): from the weekly review while it waits, else as things stand now
export type ProposalItem = {
  person_id: number; name: string; level: Level; to: Level; choice: string; choices: [string, string][];
  why: string; note: string; until: string | null;
};
export type Proposals = { decision_id: number | null; items: ProposalItem[] };

// W5 ⑤ ⑥ ทำตามแผนได้ · ข้อสังเกต (B6)
export type Followed = {
  label: string; percent: number | null; checked: number; target: number; recording: boolean;
  days: { label: string; done: number; missed: number }[];
  notes: { title: string; sub: string; weekday: number; part: string; weeks: number; avoided: boolean }[];
};

// W7 การใช้เวลา (B6)
export type PrivacyRuleRow = { id: number; kind: "app" | "title" | "word"; kind_name: string; value: string; note: string };
export type Recorder = {
  installed: boolean; running: boolean; enabled: boolean; extension: "on" | "after_login" | "missing"; round_on: boolean;
  paused_until: string | null; web: string; pause_minutes: number[];
};
export type PrivacyCard = {
  recorder: Recorder; rules: PrivacyRuleRow[]; kinds: Record<PrivacyRuleRow["kind"], string>;
  last_read: { to?: string; at?: string; error?: string; error_at?: string };
};
export type TimeBar = { label: string; start: string; minutes: Record<string, number> };
export type TimeProject = { name: string; minutes: number; planned: number; short: number };
export type Behaviour = { icon: "bolt" | "eye" | "trend" | "clock"; title: string; sub: string; link?: string };
export type TimeRange = "today" | "week" | "month";
export type TimePage = {
  privacy: PrivacyCard; range: TimeRange; label: string; start: string; end: string;
  categories: Record<string, string>; bars: TimeBar[]; projects: TimeProject[]; behaviours: Behaviour[];
  unsorted: { app: string; title: string; minutes: number }[]; total: number; days_with_data: number;
  rules: { field: "app" | "title"; match: string; category: string; project: string }[];
};

export const api = {
  // D4 ทบทวนรายสัปดาห์ (B7)
  weeklyNow: () => call<{ title: string }>("POST", "/api/weekly/run"),
  answerWeekly: (decisionId: number, act: string) => call<{ text: string }>("POST", `/api/weekly/decisions/${decisionId}`, { act }),
  // W2 ข้อเสนอปรับระดับรายสัปดาห์ (B7)
  proposals: () => call<Proposals>("GET", "/api/proposals/people"),
  answerProposals: (items: { person_id: number; choice: string }[], decision_id: number | null) =>
    call<{ action_ids: number[] }>("POST", "/api/proposals/people", { items, decision_id }),
  // W7 การใช้เวลา (B6)
  time: (range: TimeRange = "week") => call<TimePage>("GET", `/api/time?range=${range}`),
  sortTime: (field: "app" | "title", match: string, category: string, project = "") =>
    call<{ action_id: number }>("POST", "/api/time/categories", { field, match, category, project }),
  setRecording: (on: boolean) => call<PrivacyCard & { action_id: number }>("PUT", "/api/time/recording", { on }),
  pauseRecording: (minutes: number) => call<PrivacyCard & { until: string; action_id: number }>("POST", "/api/time/pause", { minutes }),
  resumeRecording: () => call<PrivacyCard & { action_id: number }>("POST", "/api/time/resume"),
  addPrivacyRule: (kind: string, value: string, note = "") => call<PrivacyCard & { action_id: number }>("POST", "/api/time/privacy", { kind, value, note }),
  removePrivacyRule: (id: number) => call<PrivacyCard & { action_id: number }>("DELETE", `/api/time/privacy/${id}`),
  // W6 ไอเดีย (B6)
  ideas: () => call<IdeasPage>("GET", "/api/ideas"),
  addIdea: (text: string, tags: string[] | null) => call<SavedIdea>("POST", "/api/ideas", { text, tags, source: "web" }),
  suggestTags: (text: string) => call<{ tags: string[]; group: GroupPreview }>("GET", `/api/ideas/suggest?text=${encodeURIComponent(text)}`),
  setIdeaTags: (id: number, tags: string[]) => call<SavedIdea>("PUT", `/api/ideas/${id}/tags`, { tags }),
  removeIdea: (id: number) => call<{ action_id: number | null }>("DELETE", `/api/ideas/${id}`),
  groupFolder: (id: number) => call<{ name: string }>("GET", `/api/ideas/groups/${id}/folder`),
  groupProject: (id: number, name: string) => call<{ project_id: number; action_id: number }>("POST", `/api/ideas/groups/${id}/project`, { name }),
  groupTask: (id: number) => call<{ task_id: number; action_id: number }>("POST", `/api/ideas/groups/${id}/task`),
  groupLater: (id: number) => call<{ action_id: number }>("POST", `/api/ideas/groups/${id}/later`),
  renameGroup: (id: number, name: string) => call<{ action_id: number }>("PUT", `/api/ideas/groups/${id}/name`, { name }),
  ideasRound: () => call<{ line: string }>("POST", "/api/ideas/round"),
  // W1 วันนี้ (B4)
  today: () => call<TodayPage>("GET", "/api/today"),
  // W5 ตาราง (B3)
  followed: () => call<Followed>("GET", "/api/schedule/followed"),
  setFollowTarget: (target: number) => call<{ target: number; action_id: number }>("PUT", "/api/schedule/followed/target", { target }),
  blockDone: (id: number) => call<{ action_id: number }>("POST", `/api/blocks/${id}/done`),
  avoidHours: (weekday: number, part: string) => call<{ action_id: number; line: string }>("POST", "/api/schedule/avoid", { weekday, part }),
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
  confirmOrder: (id: number, yes: boolean) => call<{ text: string }>("POST", `/api/orders/${id}`, { yes }),
  planRun: (id: number) => call<PlanRun>("GET", `/api/plans/${id}/run`),
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
  // W4 งานเบื้องหลัง (B5)
  jobs: () => call<JobsPage>("GET", "/api/jobs"),
  readQuota: () => call<{ quota: JobsPage["quota"] | null }>("POST", "/api/quota/read"),
  // ทำต่อ: queued and planned at once (go: may start · false: waits for you in #อนุมัติ · null: the plan failed)
  addJob: (projectId: number, note: string) =>
    call<{ id: number; action_id: number; go: boolean | null; why: string }>("POST", "/api/jobs", { project_id: projectId, note }),
  planJob: (id: number) => call<{ go: boolean; why: string }>("POST", `/api/jobs/${id}/plan`),
  setJobEffort: (id: number, model: string, effort: string) => call<JobRow>("PUT", `/api/jobs/${id}/effort`, { model, effort }),
  setJobBudget: (id: number, budget: number) => call<JobRow>("PUT", `/api/jobs/${id}/budget`, { budget }),
  answerJob: (decisionId: number, approve: boolean) =>
    call<{ job: JobRow; action_id: number }>("POST", `/api/jobs/decisions/${decisionId}`, { approve }),
  reviseJob: (decisionId: number, change: string) => call<{ go: boolean; why: string }>("POST", `/api/jobs/decisions/${decisionId}/revise`, { change }),
  dropJob: (id: number) => call<{ action_id: number }>("DELETE", `/api/jobs/${id}`),
  runJob: (id: number) => call<{ line: string }>("POST", `/api/jobs/${id}/run`),
  stopJob: (id: number) => call<{ ok: boolean }>("POST", `/api/jobs/${id}/stop`),
  // W3 โปรเจค (B5)
  projects: () => call<ProjectsPage>("GET", "/api/projects"),
  editProject: (id: number, change: Partial<Pick<ProjectRow, "status" | "potential" | "urgency" | "hidden" | "allow_jobs">>) =>
    call<{ action_id: number }>("PATCH", `/api/projects/${id}`, change),
  scanProjects: () => call<{ line: string | null }>("POST", "/api/projects/scan"),
  connect: () => call<ConnectGuide>("GET", "/api/projects/connect"),
  connectAll: () => call<{ connected: string[]; failed: string[]; action_id: number | null }>("POST", "/api/projects/connect"),
  connectProject: (id: number) => call<{ action_id: number | null }>("POST", `/api/projects/${id}/connect`),
  disconnectProject: (id: number) => call<{ action_id: number | null }>("DELETE", `/api/projects/${id}/connect`),
  bookProject: (id: number, minutes = 120) => call<{ task_id: number; action_id?: number }>("POST", `/api/projects/${id}/book`, { minutes }),
  answerLevel: (decisionId: number, potential: string, urgency: number) =>
    call<{ ok: boolean }>("POST", `/api/projects/decisions/${decisionId}`, { potential, urgency }),
};

export type AskEvents = {
  onText: (chunk: string) => void;
  onNote: (note: string) => void;
  onDone: (answer: Answer) => void;
  onError: (message: string) => void;
};

/** Ask the secretary and receive the answer as it is written (the backend streams NDJSON lines). */
/** One earlier message in the ask box, sent along so a follow-up ("ทำต่อ") makes sense. */
export type Said = { who: "คุณ" | "เลขา"; text: string };

export async function askStream(text: string, deep: boolean, on: AskEvents, history: Said[] = [],
                                signal?: AbortSignal): Promise<void> {
  let res: Response;
  try {
    res = await fetch("/api/ask", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text, deep, history }), signal,
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
