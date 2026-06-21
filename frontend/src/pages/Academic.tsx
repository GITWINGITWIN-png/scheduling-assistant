import { useEffect, useMemo, useState } from 'react'
import { fetchAssignments, ignoreAssignment, unignoreAssignment, type Assignment } from '../api'
import { Placeholder } from '../components/Placeholder'

// Page 2 (Academic): outstanding to-dos on top (overdue / upcoming / no-deadline,
// kept separate), then every subject with its assignments + live countdowns.
// All data comes from Google Classroom via /academic/assignments (M3).

const DAY_MS = 86_400_000

// A human, ticking countdown. `now` is passed in so all rows update together
// when the page's clock ticks (every minute).
function countdown(dueISO: string, now: number): { text: string; tone: Tone } {
  const diff = new Date(dueISO).getTime() - now
  const days = Math.floor(Math.abs(diff) / DAY_MS)

  if (diff < 0) return { text: days === 0 ? 'overdue' : `${days}d overdue`, tone: 'overdue' }
  if (diff < DAY_MS) {
    const hours = Math.max(1, Math.floor(diff / 3_600_000))
    return { text: `in ${hours}h`, tone: 'soon' }
  }
  return { text: `in ${days}d`, tone: days <= 3 ? 'soon' : 'normal' }
}

type Tone = 'overdue' | 'soon' | 'normal'

const TONE_CLASS: Record<Tone, string> = {
  overdue: 'text-red-600',
  soon: 'text-amber-600',
  normal: 'text-gray-500',
}

function fmtDue(due: string | null): string {
  if (!due) return 'No due date'
  return new Date(due).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

// Small coloured label for the submission state.
function StateBadge({ a }: { a: Assignment }) {
  let label: string
  let cls: string
  if (a.submitted) {
    label = a.state.replace('_', ' ').toLowerCase()
    cls = 'bg-green-100 text-green-700'
  } else if (a.ignored) {
    label = 'ignored'
    cls = 'bg-gray-100 text-gray-500'
  } else if (a.overdue) {
    label = 'overdue'
    cls = 'bg-red-100 text-red-700'
  } else {
    label = 'to do'
    cls = 'bg-blue-100 text-blue-700'
  }
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}>{label}</span>
}

// A row in the per-subject list: title on the left, due + countdown on the right.
// Ignored assignments are greyed with an un-ignore link.
function AssignmentRow({ a, now, onUnignore }: { a: Assignment; now: number; onUnignore: (id: string) => void }) {
  const cd = a.due && !a.submitted && !a.ignored ? countdown(a.due, now) : null
  return (
    <li className="flex items-center justify-between gap-3 py-1.5">
      <div className="flex min-w-0 items-center gap-2">
        <StateBadge a={a} />
        <span
          className={`truncate text-sm ${a.submitted || a.ignored ? 'text-gray-400 line-through' : ''}`}
        >
          {a.title}
        </span>
        {a.ignored && (
          <button onClick={() => onUnignore(a.id)} className="shrink-0 text-xs text-blue-500 hover:underline">
            un-ignore
          </button>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2 text-xs">
        <span className="text-gray-400">{fmtDue(a.due)}</span>
        {cd && <span className={`font-semibold ${TONE_CLASS[cd.tone]}`}>{cd.text}</span>}
      </div>
    </li>
  )
}

// A to-do item at the top of the page (also shows which course it's from).
function TodoItem({ a, now, onIgnore }: { a: Assignment; now: number; onIgnore: (a: Assignment) => void }) {
  const cd = a.due ? countdown(a.due, now) : null
  return (
    <li className="flex items-center justify-between gap-3 rounded-lg border bg-white px-3 py-2 shadow-sm">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium">{a.title}</div>
        <div className="truncate text-xs text-gray-400">{a.course}</div>
      </div>
      <div className="flex shrink-0 items-center gap-3 text-right text-xs">
        <div>
          <div className="text-gray-400">{fmtDue(a.due)}</div>
          {cd && <div className={`font-semibold ${TONE_CLASS[cd.tone]}`}>{cd.text}</div>}
        </div>
        <button
          onClick={() => onIgnore(a)}
          title="Ignore — hide from to-dos, deadlines, and the brief"
          className="text-gray-300 hover:text-red-500"
        >
          ✕
        </button>
      </div>
    </li>
  )
}

function TodoGroup({
  title,
  items,
  now,
  onIgnore,
}: {
  title: string
  items: Assignment[]
  now: number
  onIgnore: (a: Assignment) => void
}) {
  if (items.length === 0) return null
  return (
    <div className="mb-3">
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
        {title} ({items.length})
      </h4>
      <ul className="space-y-1.5">
        {items.map((a) => (
          <TodoItem key={a.id} a={a} now={now} onIgnore={onIgnore} />
        ))}
      </ul>
    </div>
  )
}

export default function Academic() {
  const [assignments, setAssignments] = useState<Assignment[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())

  const reload = () =>
    fetchAssignments()
      .then(setAssignments)
      .catch((e) => setErr((e as Error).message))

  useEffect(() => {
    reload()
  }, [])

  // Tick once a minute so the countdowns stay live without a full refetch.
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60_000)
    return () => clearInterval(id)
  }, [])

  async function onIgnore(a: Assignment) {
    await ignoreAssignment(a)
    reload()
  }

  async function onUnignore(id: string) {
    await unignoreAssignment(id)
    reload()
  }

  // Outstanding work (excluding ignored), split into the three buckets.
  const todo = useMemo(
    () => (assignments ?? []).filter((a) => !a.submitted && !a.ignored),
    [assignments],
  )
  const overdue = todo.filter((a) => a.overdue)
  const upcoming = todo.filter((a) => a.due && !a.overdue)
  const noDeadline = todo.filter((a) => !a.due)

  // All assignments grouped by course for the lower "Subjects" section.
  const byCourse = useMemo(() => {
    const map = new Map<string, Assignment[]>()
    for (const a of assignments ?? []) {
      if (!map.has(a.course)) map.set(a.course, [])
      map.get(a.course)!.push(a)
    }
    return [...map.entries()]
  }, [assignments])

  return (
    <div className="h-full overflow-y-auto p-4">
      <h2 className="mb-4 text-xl font-bold">Academic schedule</h2>

      {err && (
        <p className="mb-4 rounded bg-red-50 p-3 text-sm text-red-600">
          Couldn't load Classroom data: {err}
        </p>
      )}

      {!assignments && !err && (
        <p className="text-sm text-gray-400">Loading your Classroom assignments…</p>
      )}

      {assignments && (
        <>
          {/* Top: suggested to-dos */}
          <section className="mb-6">
            <h3 className="mb-2 text-lg font-semibold">✅ To do</h3>
            {todo.length === 0 ? (
              <Placeholder title="🎉 Nothing outstanding" note="Every assignment is turned in." />
            ) : (
              <>
                <TodoGroup title="Overdue" items={overdue} now={now} onIgnore={onIgnore} />
                <TodoGroup title="Upcoming" items={upcoming} now={now} onIgnore={onIgnore} />
                <TodoGroup title="No deadline / optional" items={noDeadline} now={now} onIgnore={onIgnore} />
              </>
            )}
          </section>

          {/* Bottom: every subject with its assignments */}
          <section>
            <h3 className="mb-2 text-lg font-semibold">📚 Subjects & assignments</h3>
            <div className="space-y-3">
              {byCourse.map(([course, items]) => (
                <div key={course} className="rounded-lg border bg-white p-3 shadow-sm">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="font-semibold">{course}</span>
                    <span className="text-xs text-gray-400">{items.length} assignments</span>
                  </div>
                  <ul className="divide-y">
                    {items.map((a) => (
                      <AssignmentRow key={a.id} a={a} now={now} onUnignore={onUnignore} />
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  )
}
