// Tiny client for the FastAPI backend. One place to change the base URL.
const BASE = 'http://localhost:8000'

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
export async function fetchEventsRange(start: string, end: string): Promise<CalEvent[]> {
  const url = `${BASE}/calendar/range?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`calendar failed: ${res.status}`)
  const raw: GoogleEvent[] = await res.json()
  return raw.map(mapEvent)
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
  link: string | null
}

// One fetch gives every assignment (with submitted/overdue flags), so the
// Academic page derives both the to-do groups and the per-subject list from it.
export async function fetchAssignments(): Promise<Assignment[]> {
  const res = await fetch(`${BASE}/academic/assignments`)
  if (!res.ok) throw new Error(`assignments failed: ${res.status}`)
  return res.json()
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
