import { useState } from 'react'
import FullCalendar from '@fullcalendar/react'
import timeGridPlugin from '@fullcalendar/timegrid'
import dayGridPlugin from '@fullcalendar/daygrid'
import { fetchEventsRange } from '../api'
import { Placeholder } from '../components/Placeholder'

// Page 1 (Home): big calendar on top; bottom row = brief + deadlines.
// (Chat is now the global floating chat, available bottom-right on every page.)
export default function Home() {
  const [err, setErr] = useState<string | null>(null)

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      {/* Calendar (live). The events function fetches exactly the visible range
          and re-runs when you navigate weeks/months. */}
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
          events={(info, success, failure) => {
            fetchEventsRange(info.startStr, info.endStr)
              .then((evs) => {
                setErr(null)
                success(evs)
              })
              .catch((e) => {
                setErr((e as Error).message)
                failure(e as Error)
              })
          }}
          height={460}
          nowIndicator
        />
      </div>

      {/* Bottom row: placeholders for now */}
      <div className="grid min-h-[180px] flex-1 grid-cols-2 gap-4">
        <Placeholder
          title="☀️ Daily brief"
          note="Your morning summary will appear here (M5)."
          className="h-full"
        />
        <Placeholder
          title="⏰ Deadlines per subject"
          note="Counts per course once Google Classroom is connected (M3)."
          className="h-full"
        />
      </div>
    </div>
  )
}
