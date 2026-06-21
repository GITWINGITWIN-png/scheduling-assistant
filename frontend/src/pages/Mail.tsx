import { useEffect, useMemo, useState } from 'react'
import {
  fetchLocalStatus,
  fetchUnread,
  scanMail,
  searchMail,
  type Email,
  type MailItem,
  type MailScan,
} from '../api'
import { Placeholder } from '../components/Placeholder'

// Page 4 (Mail): read-only Gmail (M6). Browse/search the inbox (free Google API),
// and "scan unread" to have the LOCAL model (Ollama) pull out deadlines/meetings.
// Extraction runs off-Claude — no Pro tokens, and mail bodies stay on the machine.
// Everything here is suggestion-only; nothing is written to the calendar.

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

// One extracted schedule suggestion, traceable back to its source email.
function SuggestionRow({ item }: { item: MailItem }) {
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
      <div className="shrink-0 text-right text-xs">
        {item.datetime ? (
          <span className="font-semibold text-gray-700">{fmtDate(item.datetime)}</span>
        ) : (
          <span className="text-gray-300">no date</span>
        )}
      </div>
    </li>
  )
}

// One inbox message (sender, subject, snippet, date), opens in Gmail.
function EmailRow({ e }: { e: Email }) {
  return (
    <a
      href={e.link}
      target="_blank"
      rel="noreferrer"
      className="block rounded-lg border bg-white px-3 py-2 shadow-sm hover:bg-gray-50"
    >
      <div className="flex items-baseline justify-between gap-3">
        <span className={`truncate text-sm ${e.unread ? 'font-semibold' : 'text-gray-700'}`}>
          {senderName(e.from)}
        </span>
        <span className="shrink-0 text-xs text-gray-400">{fmtDate(e.date)}</span>
      </div>
      <div className="truncate text-sm text-gray-800">{e.subject || '(no subject)'}</div>
      <div className="truncate text-xs text-gray-400">{e.snippet}</div>
    </a>
  )
}

export default function Mail() {
  const [emails, setEmails] = useState<Email[] | null>(null)
  const [query, setQuery] = useState('')
  const [err, setErr] = useState<string | null>(null)

  const [scan, setScan] = useState<MailScan | null>(null)
  const [scanning, setScanning] = useState(false)
  const [scanErr, setScanErr] = useState<string | null>(null)
  const [localUp, setLocalUp] = useState<boolean | null>(null)

  // Load unread inbox + check whether the local model is reachable.
  useEffect(() => {
    fetchUnread().then(setEmails).catch((e) => setErr((e as Error).message))
    fetchLocalStatus().then((s) => setLocalUp(s.up)).catch(() => setLocalUp(false))
  }, [])

  async function onSearch(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    setEmails(null)
    try {
      const q = query.trim()
      setEmails(q ? await searchMail(q) : await fetchUnread())
    } catch (e) {
      setErr((e as Error).message)
    }
  }

  async function onScan() {
    setScanning(true)
    setScanErr(null)
    setScan(null)
    try {
      setScan(await scanMail())
    } catch (e) {
      setScanErr((e as Error).message)
    } finally {
      setScanning(false)
    }
  }

  const heading = useMemo(() => (query.trim() ? 'Search results' : 'Unread inbox'), [query])

  return (
    <div className="h-full overflow-y-auto p-4">
      <h2 className="mb-1 text-xl font-bold">Mail</h2>
      <p className="mb-4 text-xs text-gray-400">
        Read-only Gmail. Browsing & search are free; “Scan” runs a local model on your
        machine to pull out deadlines — no Claude tokens, nothing leaves your computer.
      </p>

      {/* Scan panel: local-LLM extraction */}
      <section className="mb-6 rounded-lg border bg-indigo-50/40 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">🔎 Scan unread for schedule items</h3>
            <p className="text-xs text-gray-500">
              {localUp === false ? (
                <span className="text-amber-600">
                  Local model offline — start it with <code>ollama serve</code>.
                </span>
              ) : (
                'Finds deadlines, meetings, and events in your unread mail (suggestions only).'
              )}
            </p>
          </div>
          <button
            onClick={onScan}
            disabled={scanning || localUp === false}
            className="shrink-0 rounded bg-indigo-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            {scanning ? 'Scanning…' : 'Scan unread'}
          </button>
        </div>

        {scanErr && <p className="mt-2 text-sm text-red-600">⚠️ {scanErr}</p>}

        {scan && (
          <div className="mt-3">
            <div className="mb-2 text-xs text-gray-500">
              Scanned {scan.scanned} unread email{scan.scanned === 1 ? '' : 's'} ·{' '}
              {scan.items.length} item{scan.items.length === 1 ? '' : 's'} found ·{' '}
              <span className="text-gray-400">{scan.model}</span>
            </div>
            {scan.items.length === 0 ? (
              <p className="text-sm text-gray-500">No schedule items found in unread mail.</p>
            ) : (
              <ul className="space-y-1.5">
                {scan.items.map((it, i) => (
                  <SuggestionRow key={i} item={it} />
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      {/* Browse / search */}
      <form onSubmit={onSearch} className="mb-3 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Gmail search, e.g. from:registrar newer_than:14d (blank = unread)"
          className="flex-1 rounded border px-3 py-1.5 text-sm"
        />
        <button type="submit" className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white">
          Search
        </button>
      </form>

      {err && <p className="mb-3 rounded bg-red-50 p-3 text-sm text-red-600">{err}</p>}

      <h3 className="mb-2 text-sm font-semibold text-gray-600">{heading}</h3>
      {!emails && !err && <p className="text-sm text-gray-400">Loading mail…</p>}
      {emails && emails.length === 0 && (
        <Placeholder title="📭 Nothing here" note="No messages match — try a different search." />
      )}
      {emails && emails.length > 0 && (
        <div className="space-y-2">
          {emails.map((e) => (
            <EmailRow key={e.id} e={e} />
          ))}
        </div>
      )}
    </div>
  )
}
