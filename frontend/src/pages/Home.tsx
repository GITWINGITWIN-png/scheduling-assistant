import { useEffect, useState } from 'react'
import FullCalendar from '@fullcalendar/react'
import timeGridPlugin from '@fullcalendar/timegrid'
import dayGridPlugin from '@fullcalendar/daygrid'
import { fetchEvents, type CalEvent } from '../api'
import { ChatPanel } from '../components/Chat'
import { Placeholder } from '../components/Placeholder'

// Page 1 (Home): big calendar on top; bottom row = brief (left) and a
// right column split into deadlines-per-subject (top) over chat (bottom).
export default function Home() {
  const [events, setEvents] = useState<CalEvent[]>([])
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    fetchEvents()
      .then(setEvents)
      .catch((e) => setErr((e as Error).message))
  }, [])

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      {/* Calendar (live) */}
      <div className="rounded-lg border bg-white p-3 shadow-sm">
        {err && <p className="mb-2 text-sm text-red-500">Calendar error: {err}</p>}
        <FullCalendar
          plugins={[timeGridPlugin, dayGridPlugin]}
          initialView="timeGridWeek"
          headerToolbar={{
            left: 'prev,next today',
            center: 'title',
            right: 'timeGridWeek,dayGridMonth',
          }}
          events={events}
          height={460}
          nowIndicator
        />
      </div>

      {/* Bottom row */}
      <div className="grid min-h-[280px] flex-1 grid-cols-2 gap-4">
        <Placeholder
          title="☀️ Daily brief"
          note="Your morning summary will appear here (M5)."
          className="h-full"
        />
        <div className="grid grid-rows-2 gap-4">
          <Placeholder
            title="⏰ Deadlines per subject"
            note="Counts per course once Google Classroom is connected (M3)."
            className="h-full"
          />
          <div className="flex min-h-0 flex-col rounded-lg border bg-white shadow-sm">
            <h3 className="border-b p-2 text-sm font-semibold">💬 Chat</h3>
            <ChatPanel className="flex-1" />
          </div>
        </div>
      </div>
    </div>
  )
}
