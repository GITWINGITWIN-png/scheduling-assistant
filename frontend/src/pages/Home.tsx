import { useEffect, useState } from 'react'
import FullCalendar from '@fullcalendar/react'
import timeGridPlugin from '@fullcalendar/timegrid'
import dayGridPlugin from '@fullcalendar/daygrid'
import {
  fetchBrief,
  fetchEventsRange,
  fetchNudges,
  regenerateBrief,
  type Brief,
  type NudgeItem,
  type Nudges,
} from '../api'

function fmtDue(due: string | null): string {
  return due ? new Date(due).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '—'
}

// ☀️ Daily brief card — lazily generated once a day, with a manual refresh.
function BriefCard() {
  const [brief, setBrief] = useState<Brief | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchBrief()
      .then(setBrief)
      .catch((e) => setErr((e as Error).message))
      .finally(() => setLoading(false))
  }, [])

  async function refresh() {
    setLoading(true)
    setErr(null)
    try {
      setBrief(await regenerateBrief())
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full flex-col rounded-lg border bg-white p-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-semibold">☀️ Daily brief</h3>
        <button onClick={refresh} disabled={loading} className="text-xs text-blue-600 hover:underline disabled:opacity-50">
          {loading ? '…' : 'Refresh'}
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto text-sm text-gray-700">
        {err ? (
          <p className="text-red-500">{err}</p>
        ) : loading && !brief ? (
          <p className="text-gray-400">Generating your brief…</p>
        ) : (
          <p className="whitespace-pre-line">{brief?.content}</p>
        )}
      </div>
    </div>
  )
}

function NudgeRow({ item, overdue }: { item: NudgeItem; overdue?: boolean }) {
  return (
    <li className="flex items-center justify-between gap-2 py-1 text-sm">
      <span className="min-w-0 truncate">
        <span className={item.type === 'project' ? 'font-medium text-purple-700' : ''}>{item.label}</span>
        <span className="ml-1 text-xs text-gray-400">{item.sublabel}</span>
      </span>
      <span className={`shrink-0 text-xs ${overdue ? 'text-red-600' : 'text-gray-500'}`}>{fmtDue(item.due)}</span>
    </li>
  )
}

// ⏰ Deadlines card — overdue + due soon + planning suggestions (tokenless).
function DeadlinesCard() {
  const [nudges, setNudges] = useState<Nudges | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    fetchNudges()
      .then(setNudges)
      .catch((e) => setErr((e as Error).message))
  }, [])

  const empty = nudges && nudges.overdue.length === 0 && nudges.due_soon.length === 0

  return (
    <div className="flex h-full flex-col rounded-lg border bg-white p-3 shadow-sm">
      <h3 className="mb-2 font-semibold">⏰ Deadlines</h3>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {err && <p className="text-sm text-red-500">{err}</p>}
        {!nudges && !err && <p className="text-sm text-gray-400">Loading…</p>}
        {empty && <p className="text-sm text-gray-400">Nothing due soon. 🎉</p>}

        {nudges && nudges.overdue.length > 0 && (
          <>
            <h4 className="text-xs font-semibold uppercase text-red-500">Overdue</h4>
            <ul className="mb-2 divide-y">
              {nudges.overdue.map((i, k) => (
                <NudgeRow key={k} item={i} overdue />
              ))}
            </ul>
          </>
        )}
        {nudges && nudges.due_soon.length > 0 && (
          <>
            <h4 className="text-xs font-semibold uppercase text-gray-500">Due soon</h4>
            <ul className="mb-2 divide-y">
              {nudges.due_soon.map((i, k) => (
                <NudgeRow key={k} item={i} />
              ))}
            </ul>
          </>
        )}
        {nudges && nudges.suggestions.length > 0 && (
          <div className="mt-1 rounded bg-amber-50 p-2 text-xs text-amber-700">
            {nudges.suggestions.map((s, k) => (
              <p key={k}>💡 {s}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// Page 1 (Home): big calendar on top; bottom row = daily brief + deadlines.
// (Chat is the global floating chat, available bottom-right on every page.)
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

      {/* Bottom row: live daily brief + deadline nudges */}
      <div className="grid min-h-[180px] flex-1 grid-cols-2 gap-4">
        <BriefCard />
        <DeadlinesCard />
      </div>
    </div>
  )
}
