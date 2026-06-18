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

// The backend returns raw Google events; map them to FullCalendar's shape.
export async function fetchEvents(days = 14): Promise<CalEvent[]> {
  const res = await fetch(`${BASE}/calendar/upcoming?days=${days}`)
  if (!res.ok) throw new Error(`calendar failed: ${res.status}`)
  const raw = await res.json()
  return raw.map((e: { id: string; summary?: string; start: Record<string, string>; end?: Record<string, string> }) => ({
    id: e.id,
    title: e.summary ?? '(no title)',
    start: e.start.dateTime ?? e.start.date,
    end: e.end?.dateTime ?? e.end?.date,
  }))
}

// --- Projects ---
export interface Project {
  id: number
  name: string
  goal: string
  deadline: string | null
}

export async function fetchProjects(): Promise<Project[]> {
  const res = await fetch(`${BASE}/projects`)
  if (!res.ok) throw new Error(`projects failed: ${res.status}`)
  return res.json()
}
