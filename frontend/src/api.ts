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
