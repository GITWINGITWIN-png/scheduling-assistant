import { useEffect, useRef, useState, type FormEvent } from 'react'
import { sendChat } from '../api'

interface Msg {
  role: 'you' | 'secretary'
  text: string
}

// The chat conversation UI. Kept mounted (never conditionally unmounted) so the
// message history survives open/close and page navigation.
export function ChatPanel({ className = '' }: { className?: string }) {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to the newest message.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs, loading])

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
      {/* min-h-0 here is what lets this area actually scroll inside a flex parent */}
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {msgs.length === 0 && (
          <p className="text-sm text-gray-400">Ask me about your schedule…</p>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={m.role === 'you' ? 'text-right' : 'text-left'}>
            <span
              className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-left text-sm ${
                m.role === 'you' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-800'
              }`}
            >
              {m.text}
            </span>
          </div>
        ))}
        {loading && <p className="text-sm text-gray-400">…thinking</p>}
        <div ref={endRef} />
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

// ONE global, persistent chat. Mounted once in App (outside the router), and the
// panel is hidden with CSS (not unmounted) when closed — so it's the SAME
// conversation on every page and survives navigation and open/close.
export function FloatingChat() {
  const [open, setOpen] = useState(false)
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end">
      <div
        className={`mb-2 h-[28rem] w-96 flex-col overflow-hidden rounded-lg border bg-white shadow-xl ${
          open ? 'flex' : 'hidden'
        }`}
      >
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="text-sm font-semibold">💬 Secretary</span>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close chat"
            className="text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>
        <ChatPanel className="flex-1" />
      </div>
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
