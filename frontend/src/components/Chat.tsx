import { useState, type FormEvent } from 'react'
import { sendChat } from '../api'

interface Msg {
  role: 'you' | 'secretary'
  text: string
}

// The reusable chat UI. Used inline on the Home page and inside the
// FloatingChat popover on the other pages.
export function ChatPanel({ className = '' }: { className?: string }) {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return
    setMsgs((m) => [...m, { role: 'you', text }])
    setInput('')
    setLoading(true)
    try {
      const reply = await sendChat(text)
      setMsgs((m) => [...m, { role: 'secretary', text: reply }])
    } catch (err) {
      setMsgs((m) => [...m, { role: 'secretary', text: `Error: ${(err as Error).message}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`flex min-h-0 flex-col ${className}`}>
      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {msgs.length === 0 && (
          <p className="text-sm text-gray-400">Ask me about your schedule…</p>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={m.role === 'you' ? 'text-right' : 'text-left'}>
            <span
              className={`inline-block max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                m.role === 'you' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-800'
              }`}
            >
              {m.text}
            </span>
          </div>
        ))}
        {loading && <p className="text-sm text-gray-400">…thinking</p>}
      </div>
      <form onSubmit={submit} className="flex gap-2 border-t p-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          className="min-w-0 flex-1 rounded border px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  )
}

// Floating chat button (bottom-right) used on the Academic and Projects pages.
export function FloatingChat() {
  const [open, setOpen] = useState(false)
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end">
      {open && (
        <div className="mb-2 flex h-96 w-80 flex-col overflow-hidden rounded-lg border bg-white shadow-xl">
          <ChatPanel className="h-full" />
        </div>
      )}
      <button
        onClick={() => setOpen((o) => !o)}
        className="rounded-full bg-blue-600 px-5 py-3 text-lg text-white shadow-lg"
        aria-label="Toggle chat"
      >
        {open ? '✕' : '💬'}
      </button>
    </div>
  )
}
