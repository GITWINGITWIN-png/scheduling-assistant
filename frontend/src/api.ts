// Tiny client for the FastAPI backend. One place to change the base URL.
// In dev (`npm run dev`) the Vite server and the API are on different ports, so
// we point at the backend explicitly. In the production build the backend
// SERVES this app, so API calls are same-origin (relative) — which is what lets
// it work over Tailscale from a phone (no hardcoded "localhost", no CORS).
const BASE = import.meta.env.DEV ? 'http://localhost:8000' : ''

// Some reads are served from a DB snapshot for instant skimming. The backend
// wraps them in this envelope: `data` plus when it was fetched and whether that
// snapshot is stale (a background refresh was kicked off, so reload soon for fresh).
export interface Cached<T> {
  data: T
  fetched_at: string
  stale: boolean
}

// "updated just now / 4m ago / 2h ago" for a snapshot's fetched_at timestamp.
export function timeAgo(iso: string): string {
  const secs = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (secs < 45) return 'just now'
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`
  if (secs < 86_400) return `${Math.round(secs / 3600)}h ago`
  return `${Math.round(secs / 86_400)}d ago`
}

// --- Chat ---
export async function sendChat(message: string): Promise<string> {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!res.ok) throw new Error(`chat failed: ${res.status}`)
  const data = await res.json()
  return data.reply as string
}

// --- Calendar ---
export interface CalEvent {
  id: string
  title: string
  start: string
  end?: string
}

interface GoogleEvent {
  id: string
  summary?: string
  start: { dateTime?: string; date?: string }
  end?: { dateTime?: string; date?: string }
}

function mapEvent(e: GoogleEvent): CalEvent {
  return {
    id: e.id,
    title: e.summary ?? '(no title)',
    start: e.start.dateTime ?? e.start.date ?? '',
    end: e.end?.dateTime ?? e.end?.date,
  }
}

// Fetch events for an explicit time range (ISO 8601). FullCalendar calls this
// for whatever range is currently visible, and again whenever you navigate.
// Served from a per-range DB snapshot (instant); pass refresh=true to force-fetch.
export async function fetchEventsRange(start: string, end: string, refresh = false): Promise<CalEvent[]> {
  const url = `${BASE}/calendar/range?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}${refresh ? '&refresh=true' : ''}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`calendar failed: ${res.status}`)
  const env: Cached<GoogleEvent[]> = await res.json()
  return env.data.map(mapEvent)
}

// --- Projects (M4) ---
export type ProjectStatus = 'active' | 'waiting' | 'done' | 'dropped'

export interface Project {
  id: number
  name: string
  goal: string
  deadline: string | null
  status: ProjectStatus
  estimated_hours: number
  repo_path: string | null
  last_commit_at: string | null
}

export interface PlanBlock {
  title: string
  start: string
  end: string
}

export interface PlanPreview {
  blocks: PlanBlock[]
  hours_scheduled: number
  hours_unscheduled: number
  deadline: string
  error?: string
}

export async function fetchProjects(): Promise<Project[]> {
  const res = await fetch(`${BASE}/projects`)
  if (!res.ok) throw new Error(`projects failed: ${res.status}`)
  return res.json()
}

export async function discoverRepos(root: string): Promise<Project[]> {
  const res = await fetch(`${BASE}/projects/discover`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ root }),
  })
  if (!res.ok) throw new Error(`discover failed: ${res.status}`)
  return res.json()
}

// Send only the fields you want to change.
export async function updateProject(id: number, patch: Partial<Project>): Promise<Project> {
  const res = await fetch(`${BASE}/projects/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error(`update failed: ${res.status}`)
  return res.json()
}

export async function deleteProject(id: number): Promise<void> {
  const res = await fetch(`${BASE}/projects/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`delete failed: ${res.status}`)
}

// Preview a plan (no calendar writes).
export async function planProject(id: number): Promise<PlanPreview> {
  const res = await fetch(`${BASE}/projects/${id}/plan`, { method: 'POST' })
  if (!res.ok) throw new Error(`plan failed: ${res.status}`)
  return res.json()
}

// Book the approved blocks into the calendar.
export async function commitPlan(id: number, blocks: PlanBlock[]): Promise<{ created: number }> {
  const res = await fetch(`${BASE}/projects/${id}/plan/commit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ blocks }),
  })
  if (!res.ok) throw new Error(`commit failed: ${res.status}`)
  return res.json()
}

// --- Academic (Google Classroom) ---
export interface Assignment {
  course: string
  course_id: string
  id: string
  title: string
  due: string | null // ISO 8601, or null when the assignment has no due date
  state: string // NEW | CREATED | TURNED_IN | RETURNED | RECLAIMED_BY_STUDENT
  late: boolean
  submitted: boolean // already turned in or returned/graded
  overdue: boolean // not submitted and past its due date
  ignored: boolean // user chose to ignore it (e.g. old un-submittable homework)
  link: string | null
}

// One fetch gives every assignment (with submitted/overdue/ignored flags), so the
// Academic page derives both the to-do groups and the per-subject list from it.
// Served from a DB snapshot (instant); pass refresh=true to force a Google fetch.
export async function fetchAssignments(refresh = false): Promise<Cached<Assignment[]>> {
  const res = await fetch(`${BASE}/academic/assignments${refresh ? '?refresh=true' : ''}`)
  if (!res.ok) throw new Error(`assignments failed: ${res.status}`)
  return res.json()
}

// Ignore an assignment so it stops showing in to-dos, nudges, and the brief.
export async function ignoreAssignment(assignment: Assignment): Promise<void> {
  const res = await fetch(`${BASE}/academic/ignore`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assignment_id: assignment.id, title: assignment.title, course: assignment.course }),
  })
  if (!res.ok) throw new Error(`ignore failed: ${res.status}`)
}

export async function unignoreAssignment(assignmentId: string): Promise<void> {
  const res = await fetch(`${BASE}/academic/ignore/${assignmentId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`un-ignore failed: ${res.status}`)
}

// --- Proactive (M5): daily brief + deadline nudges ---
export interface Brief {
  for_date: string
  content: string
  created_at: string
}

// Today's brief — generated + cached on the first call of the day (one Claude call).
export async function fetchBrief(): Promise<Brief> {
  const res = await fetch(`${BASE}/brief/today`)
  if (!res.ok) throw new Error(`brief failed: ${res.status}`)
  return res.json()
}

export async function regenerateBrief(): Promise<Brief> {
  const res = await fetch(`${BASE}/brief/regenerate`, { method: 'POST' })
  if (!res.ok) throw new Error(`brief regenerate failed: ${res.status}`)
  return res.json()
}

export interface NudgeItem {
  type: 'assignment' | 'project'
  label: string
  sublabel: string
  due: string | null
}

export interface Nudges {
  overdue: NudgeItem[]
  due_soon: NudgeItem[]
  suggestions: string[]
}

// Tokenless: overdue items, things due soon, and replan suggestions.
export async function fetchNudges(): Promise<Nudges> {
  const res = await fetch(`${BASE}/nudges`)
  if (!res.ok) throw new Error(`nudges failed: ${res.status}`)
  return res.json()
}

// --- Mail (M6): Gmail read-only + local-LLM schedule extraction ---
export interface Email {
  id: string
  thread_id: string
  from: string
  subject: string
  date: string | null
  snippet: string
  body: string
  unread: boolean
  link: string
}

// Browse unread inbox (free Google API call). Served from a DB snapshot (instant);
// pass refresh=true to force a fresh Gmail fetch.
export async function fetchUnread(refresh = false, limit = 20): Promise<Cached<Email[]>> {
  const res = await fetch(`${BASE}/mail/unread?limit=${limit}${refresh ? '&refresh=true' : ''}`)
  if (!res.ok) throw new Error(`unread failed: ${res.status}`)
  return res.json()
}

// Browse today's inbox, read + unread (free Google API call). Snapshot-served.
export async function fetchToday(refresh = false, limit = 40): Promise<Cached<Email[]>> {
  const res = await fetch(`${BASE}/mail/today?limit=${limit}${refresh ? '&refresh=true' : ''}`)
  if (!res.ok) throw new Error(`today failed: ${res.status}`)
  return res.json()
}

// Search mail with Gmail query syntax (free Google API call — no tokens).
export async function searchMail(q: string, limit = 20): Promise<Email[]> {
  const res = await fetch(`${BASE}/mail/search?q=${encodeURIComponent(q)}&limit=${limit}`)
  if (!res.ok) throw new Error(`search failed: ${res.status}`)
  return res.json()
}

// A schedule item the LOCAL model pulled out of an email (a suggestion only —
// nothing is added to the calendar until you ask).
export interface MailItem {
  type: 'deadline' | 'meeting' | 'event' | 'other'
  title: string
  datetime: string | null
  note: string
  email_id: string
  email_subject: string
  email_from: string
  link: string
  pinned?: boolean // auto-pinned by the scan (dated/deadline/meeting/event)
}

export interface MailScan {
  items: MailItem[]
  scanned: number
  scope?: string
  model?: string
  for_date?: string
  auto_pinned?: number // how many items the scan auto-pinned
}

export type ScanScope = 'unread' | 'today'

// Run the local model over mail to extract deadlines/meetings/events.
// 'unread' always runs fresh; 'today' reads the once-a-day cached scan (the
// scheduler pre-warms it each morning), with `force` to re-run it.
export async function scanMail(scope: ScanScope = 'unread', force = false): Promise<MailScan> {
  const url =
    scope === 'today'
      ? `${BASE}/mail/scan/today${force ? '?force=true' : ''}`
      : `${BASE}/mail/scan?scope=unread`
  const res = await fetch(url, { method: scope === 'today' ? 'GET' : 'POST' })
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail ?? `scan failed: ${res.status}`)
  }
  return res.json()
}

// --- Pinned emails (show on the Projects page; dated pins → calendar) ---
export interface Pin {
  email_id: string
  subject: string
  sender: string
  link: string
  note: string
  date: string | null
  on_calendar: boolean
  created_at: string | null
}

export async function fetchPins(): Promise<Pin[]> {
  const res = await fetch(`${BASE}/mail/pins`)
  if (!res.ok) throw new Error(`pins failed: ${res.status}`)
  return res.json()
}

export interface PinInput {
  email_id: string
  subject?: string
  sender?: string
  link?: string
  date?: string | null
  note?: string
}

// Pin an email. If `date` is set, the backend also adds it to your calendar.
export async function pinEmail(input: PinInput): Promise<Pin> {
  const res = await fetch(`${BASE}/mail/pins`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  if (!res.ok) throw new Error(`pin failed: ${res.status}`)
  return res.json()
}

export async function unpinEmail(emailId: string): Promise<void> {
  const res = await fetch(`${BASE}/mail/pins/${encodeURIComponent(emailId)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`unpin failed: ${res.status}`)
}

export interface LocalStatus {
  up: boolean
  model: string
}

// Is the local model server (Ollama) reachable? Used to warn before scanning.
export async function fetchLocalStatus(): Promise<LocalStatus> {
  const res = await fetch(`${BASE}/mail/local-status`)
  if (!res.ok) throw new Error(`local-status failed: ${res.status}`)
  return res.json()
}
