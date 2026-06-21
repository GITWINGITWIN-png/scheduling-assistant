import { useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchLocalStatus,
  fetchPins,
  fetchToday,
  fetchUnread,
  pinEmail,
  scanMail,
  searchMail,
  timeAgo,
  unpinEmail,
  type Email,
  type MailItem,
  type MailScan,
  type PinInput,
  type ScanScope,
} from '../api'
import { Placeholder } from '../components/Placeholder'

// Page 4 (Mail): read-only Gmail (M6). Browse/search the inbox (free Google API),
// and scan unread OR all of today's mail with the LOCAL model (Ollama) to pull out
// deadlines/meetings. Extraction runs off-Claude — no Pro tokens, mail stays local.
// "Pin" promotes an email to the Projects page; a dated pin is also added to the
// calendar (the only place mail leads to a calendar write, and only on your click).

function fmtDate(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

// "Name <addr>" → "Name" (or the address if no display name).
function senderName(from: string): string {
  const m = from.match(/^\s*"?([^"<]+?)"?\s*<.*>/)
  return (m ? m[1] : from).trim() || from
}

const TYPE_CLASS: Record<MailItem['type'], string> = {
  deadline: 'bg-red-100 text-red-700',
  meeting: 'bg-purple-100 text-purple-700',
  event: 'bg-blue-100 text-blue-700',
  other: 'bg-gray-100 text-gray-600',
}

// Module-level memory so the page restores its results after you navigate away
// and come back (React Router unmounts the page; a module var survives that —
// it only resets on a full reload). Holds the last browse/search + scan state.
interface MailMemory {
  emails: Email[] | null
  browseScope: ScanScope
  fetchedAt: string | null
  query: string
  scan: MailScan | null
  scanScope: ScanScope
}
let saved: MailMemory | null = null

// A tiny two-option segmented toggle (Unread / Today).
function ScopeToggle({ value, onChange }: { value: ScanScope; onChange: (s: ScanScope) => void }) {
  return (
    <div className="inline-flex overflow-hidden rounded border text-xs">
      {(['unread', 'today'] as ScanScope[]).map((s) => (
        <button
          key={s}
          onClick={() => onChange(s)}
          className={`px-2.5 py-1 ${value === s ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
        >
          {s === 'unread' ? 'Unread' : 'Today (all)'}
        </button>
      ))}
    </div>
  )
}

// A pin/unpin button shared by suggestions and email rows.
function PinButton({ pinned, onClick }: { pinned: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title={pinned ? 'Pinned to Projects — click to unpin' : 'Pin to Projects (adds dated items to your calendar)'}
      className={`shrink-0 rounded border px-2 py-0.5 text-xs ${
        pinned ? 'border-amber-300 bg-amber-50 text-amber-700' : 'text-gray-400 hover:bg-gray-50'
      }`}
    >
      {pinned ? '📌 Pinned' : '📌 Pin'}
    </button>
  )
}

// One extracted schedule suggestion, traceable to its source email; pinnable.
function SuggestionRow({
  item,
  pinned,
  onPin,
  onUnpin,
}: {
  item: MailItem
  pinned: boolean
  onPin: (input: PinInput) => void
  onUnpin: (id: string) => void
}) {
  return (
    <li className="flex items-start justify-between gap-3 rounded-lg border bg-white px-3 py-2 shadow-sm">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${TYPE_CLASS[item.type]}`}>
            {item.type}
          </span>
          <span className="truncate text-sm font-medium">{item.title}</span>
        </div>
        {item.note && <div className="mt-0.5 truncate text-xs text-gray-500">{item.note}</div>}
        <a
          href={item.link}
          target="_blank"
          rel="noreferrer"
          className="mt-0.5 block truncate text-xs text-gray-400 hover:text-blue-500 hover:underline"
          title={item.email_subject}
        >
          ✉ {item.email_subject || '(email)'}
        </a>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1 text-right text-xs">
        {item.datetime ? (
          <span className="font-semibold text-gray-700">{fmtDate(item.datetime)}</span>
        ) : (
          <span className="text-gray-300">no date</span>
        )}
        <PinButton
          pinned={pinned}
          onClick={() =>
            pinned
              ? onUnpin(item.email_id)
              : onPin({
                  email_id: item.email_id,
                  subject: item.email_subject,
                  sender: item.email_from,
                  link: item.link,
                  date: item.datetime,
                  note: item.title,
                })
          }
        />
      </div>
    </li>
  )
}

// One inbox message (sender, subject, snippet, date); opens in Gmail, pinnable.
function EmailRow({
  e,
  pinned,
  onPin,
  onUnpin,
}: {
  e: Email
  pinned: boolean
  onPin: (input: PinInput) => void
  onUnpin: (id: string) => void
}) {
  return (
    <div className="flex items-center gap-2 rounded-lg border bg-white px-3 py-2 shadow-sm">
      <a href={e.link} target="_blank" rel="noreferrer" className="min-w-0 flex-1 hover:opacity-80">
        <div className="flex items-baseline justify-between gap-3">
          <span className={`truncate text-sm ${e.unread ? 'font-semibold' : 'text-gray-700'}`}>
            {senderName(e.from)}
          </span>
          <span className="shrink-0 text-xs text-gray-400">{fmtDate(e.date)}</span>
        </div>
        <div className="truncate text-sm text-gray-800">{e.subject || '(no subject)'}</div>
        <div className="truncate text-xs text-gray-400">{e.snippet}</div>
      </a>
      <PinButton
        pinned={pinned}
        onClick={() =>
          pinned
            ? onUnpin(e.id)
            : onPin({ email_id: e.id, subject: e.subject, sender: e.from, link: e.link, date: null })
        }
      />
    </div>
  )
}

export default function Mail() {
  // Initialize from the module-level memory so results survive navigation.
  const [emails, setEmails] = useState<Email[] | null>(saved?.emails ?? null)
  const [browseScope, setBrowseScope] = useState<ScanScope>(saved?.browseScope ?? 'unread')
  const [fetchedAt, setFetchedAt] = useState<string | null>(saved?.fetchedAt ?? null) // null while searching (live)
  const [refreshing, setRefreshing] = useState(false)
  const [query, setQuery] = useState(saved?.query ?? '')
  const [err, setErr] = useState<string | null>(null)

  const [scanScope, setScanScope] = useState<ScanScope>(saved?.scanScope ?? 'unread')
  const [scan, setScan] = useState<MailScan | null>(saved?.scan ?? null)
  const [scanning, setScanning] = useState(false)
  const [scanErr, setScanErr] = useState<string | null>(null)
  const [localUp, setLocalUp] = useState<boolean | null>(null)

  const [pinned, setPinned] = useState<Set<string>>(new Set())

  // Whether we restored a previous session (so we skip the initial auto-fetch).
  const restored = useRef(saved?.emails != null)

  // Persist the meaningful state to module memory whenever it changes.
  useEffect(() => {
    saved = { emails, browseScope, fetchedAt, query, scan, scanScope }
  }, [emails, browseScope, fetchedAt, query, scan, scanScope])

  const reloadPins = () =>
    fetchPins()
      .then((ps) => setPinned(new Set(ps.map((p) => p.email_id))))
      .catch(() => {})

  // On first mount: only fetch the inbox if we didn't restore a previous session
  // (otherwise we'd clobber the remembered search/scan results). Always refresh
  // local-model status + pins, which are cheap and may have changed.
  useEffect(() => {
    if (!restored.current) browse('unread')
    fetchLocalStatus().then((s) => setLocalUp(s.up)).catch(() => setLocalUp(false))
    reloadPins()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Load the unread/today inbox from the snapshot. `refresh` forces a Gmail fetch.
  async function browse(scope: ScanScope, refresh = false) {
    setBrowseScope(scope)
    setQuery('')
    setErr(null)
    if (refresh) setRefreshing(true)
    else setEmails(null)
    try {
      const env = scope === 'today' ? await fetchToday(refresh) : await fetchUnread(refresh)
      setEmails(env.data)
      setFetchedAt(env.fetched_at)
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setRefreshing(false)
    }
  }

  async function onSearch(e: React.FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q) return browse(browseScope)
    setErr(null)
    setEmails(null)
    setFetchedAt(null) // search results are live, not a cached snapshot
    try {
      setEmails(await searchMail(q))
    } catch (e) {
      setErr((e as Error).message)
    }
  }

  async function onScan() {
    setScanning(true)
    setScanErr(null)
    setScan(null)
    try {
      setScan(await scanMail(scanScope))
      // The scan auto-pins schedule-worthy items server-side; refresh pins so the
      // suggestion rows + Projects list reflect what just got pinned.
      reloadPins()
    } catch (e) {
      setScanErr((e as Error).message)
    } finally {
      setScanning(false)
    }
  }

  async function onPin(input: PinInput) {
    await pinEmail(input)
    reloadPins()
  }
  async function onUnpin(id: string) {
    await unpinEmail(id)
    reloadPins()
  }

  const heading = useMemo(() => {
    if (query.trim()) return 'Search results'
    return browseScope === 'today' ? "Today's inbox" : 'Unread inbox'
  }, [query, browseScope])

  return (
    <div className="h-full overflow-y-auto p-4">
      <h2 className="mb-1 text-xl font-bold">Mail</h2>
      <p className="mb-4 text-xs text-gray-400">
        Read-only Gmail. Browsing & search are free; “Scan” runs a local model on your
        machine to pull out deadlines — no Claude tokens, nothing leaves your computer.
        Scans auto-pin dated/meeting/event items to Projects (dated ones go on your
        calendar) — review and unpin anything you don’t want. Pinning an old email
        re-reads it in detail to recover its date.
      </p>

      {/* Scan panel: local-LLM extraction */}
      <section className="mb-6 rounded-lg border bg-indigo-50/40 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">🔎 Scan for schedule items</h3>
            <p className="text-xs text-gray-500">
              {localUp === false ? (
                <span className="text-amber-600">
                  Local model offline — start it with <code>ollama serve</code>.
                </span>
              ) : (
                'Finds deadlines, meetings, and events — schedule-worthy ones are auto-pinned to Projects.'
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <ScopeToggle value={scanScope} onChange={setScanScope} />
            <button
              onClick={onScan}
              disabled={scanning || localUp === false}
              className="shrink-0 rounded bg-indigo-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {scanning ? 'Scanning…' : `Scan ${scanScope === 'today' ? 'today' : 'unread'}`}
            </button>
          </div>
        </div>

        {scanErr && <p className="mt-2 text-sm text-red-600">⚠️ {scanErr}</p>}

        {scan && (
          <div className="mt-3">
            <div className="mb-2 text-xs text-gray-500">
              Scanned {scan.scanned} email{scan.scanned === 1 ? '' : 's'} ·{' '}
              {scan.items.length} item{scan.items.length === 1 ? '' : 's'} found
              {typeof scan.auto_pinned === 'number' && scan.auto_pinned > 0 && (
                <span className="text-amber-600"> · 📌 {scan.auto_pinned} auto-pinned (dated ones added to calendar)</span>
              )}
              {scan.model && <span className="text-gray-400"> · {scan.model}</span>}
            </div>
            {scan.items.length === 0 ? (
              <p className="text-sm text-gray-500">No schedule items found.</p>
            ) : (
              <ul className="space-y-1.5">
                {scan.items.map((it, i) => (
                  <SuggestionRow
                    key={i}
                    item={it}
                    pinned={pinned.has(it.email_id)}
                    onPin={onPin}
                    onUnpin={onUnpin}
                  />
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      {/* Browse / search */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <ScopeToggle value={browseScope} onChange={(s) => browse(s)} />
        <form onSubmit={onSearch} className="flex flex-1 gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Gmail search, e.g. from:registrar newer_than:14d"
            className="min-w-0 flex-1 rounded border px-3 py-1.5 text-sm"
          />
          <button type="submit" className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white">
            Search
          </button>
        </form>
      </div>

      {err && <p className="mb-3 rounded bg-red-50 p-3 text-sm text-red-600">{err}</p>}

      <div className="mb-2 flex items-center gap-2">
        <h3 className="text-sm font-semibold text-gray-600">{heading}</h3>
        {fetchedAt && !query.trim() && (
          <span className="text-xs text-gray-400">
            updated {timeAgo(fetchedAt)}
            <button
              onClick={() => browse(browseScope, true)}
              disabled={refreshing}
              className="ml-2 text-blue-600 hover:underline disabled:opacity-50"
            >
              {refreshing ? 'Refreshing…' : 'Refresh'}
            </button>
          </span>
        )}
      </div>
      {!emails && !err && <p className="text-sm text-gray-400">Loading mail…</p>}
      {emails && emails.length === 0 && (
        <Placeholder title="📭 Nothing here" note="No messages match — try a different search." />
      )}
      {emails && emails.length > 0 && (
        <div className="space-y-2">
          {emails.map((e) => (
            <EmailRow
              key={e.id}
              e={e}
              pinned={pinned.has(e.id)}
              onPin={onPin}
              onUnpin={onUnpin}
            />
          ))}
        </div>
      )}
    </div>
  )
}
