import { useEffect, useState } from 'react'
import {
  commitPlan,
  deleteProject,
  discoverRepos,
  fetchProjects,
  planProject,
  updateProject,
  type PlanPreview,
  type Project,
  type ProjectStatus,
} from '../api'
import { Placeholder } from '../components/Placeholder'

// Page 3 (Projects): the planner's home. Discover git repos, set a deadline +
// effort per project, then "Plan now" to book work blocks toward the deadline.

const STATUSES: ProjectStatus[] = ['active', 'waiting', 'done', 'dropped']

const STATUS_CLASS: Record<ProjectStatus, string> = {
  active: 'bg-green-100 text-green-700',
  waiting: 'bg-amber-100 text-amber-700',
  done: 'bg-gray-200 text-gray-600',
  dropped: 'bg-red-100 text-red-600',
}

function relativeDate(iso: string | null): string {
  if (!iso) return 'no commits'
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

// datetime-local needs "YYYY-MM-DDTHH:mm"; trim an ISO string to that.
function toLocalInput(iso: string | null): string {
  return iso ? iso.slice(0, 16) : ''
}

function fmtBlock(b: { start: string; end: string }): string {
  const s = new Date(b.start)
  const e = new Date(b.end)
  const day = s.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
  const t = (d: Date) => d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  return `${day}  ${t(s)}–${t(e)}`
}

function ProjectCard({ project, onChanged }: { project: Project; onChanged: () => void }) {
  const [editing, setEditing] = useState(false)
  const [goal, setGoal] = useState(project.goal)
  const [deadline, setDeadline] = useState(toLocalInput(project.deadline))
  const [hours, setHours] = useState(project.estimated_hours)
  const [status, setStatus] = useState<ProjectStatus>(project.status)

  const [plan, setPlan] = useState<PlanPreview | null>(null)
  const [planning, setPlanning] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  async function save() {
    await updateProject(project.id, {
      goal,
      deadline: deadline ? deadline : null,
      estimated_hours: Number(hours),
      status,
    })
    setEditing(false)
    onChanged()
  }

  async function remove() {
    if (!confirm(`Remove "${project.name}" from the planner? (your repo is untouched)`)) return
    await deleteProject(project.id)
    onChanged()
  }

  async function runPlan() {
    setPlanning(true)
    setMsg(null)
    setPlan(null)
    try {
      setPlan(await planProject(project.id))
    } catch (e) {
      setMsg((e as Error).message)
    } finally {
      setPlanning(false)
    }
  }

  async function book() {
    if (!plan) return
    const { created } = await commitPlan(project.id, plan.blocks)
    setPlan(null)
    setMsg(`✓ Added ${created} work block${created === 1 ? '' : 's'} to your calendar.`)
  }

  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold">{project.name}</span>
            <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${STATUS_CLASS[project.status]}`}>
              {project.status}
            </span>
          </div>
          <div className="mt-0.5 text-xs text-gray-400">
            last commit {relativeDate(project.last_commit_at)}
            {project.repo_path && <span className="ml-2 text-gray-300">· {project.repo_path}</span>}
          </div>
          {project.goal && <p className="mt-1 text-sm text-gray-600">{project.goal}</p>}
        </div>
        <div className="flex shrink-0 gap-2 text-sm">
          <button onClick={runPlan} disabled={planning} className="rounded bg-blue-600 px-3 py-1 text-white disabled:opacity-50">
            {planning ? 'Planning…' : 'Plan now'}
          </button>
          <button onClick={() => setEditing((e) => !e)} className="rounded border px-3 py-1 text-gray-600 hover:bg-gray-50">
            {editing ? 'Close' : 'Edit'}
          </button>
        </div>
      </div>

      {/* Deadline + effort summary (display mode) */}
      {!editing && (
        <div className="mt-2 flex gap-4 text-xs text-gray-500">
          <span>📅 {project.deadline ? new Date(project.deadline).toLocaleString() : 'no deadline'}</span>
          <span>⏱ {project.estimated_hours || 0}h to schedule</span>
        </div>
      )}

      {/* Edit form */}
      {editing && (
        <div className="mt-3 grid grid-cols-1 gap-3 border-t pt-3 sm:grid-cols-2">
          <label className="text-xs text-gray-500">
            Description
            <input value={goal} onChange={(e) => setGoal(e.target.value)} className="mt-1 w-full rounded border px-2 py-1 text-sm text-gray-800" />
          </label>
          <label className="text-xs text-gray-500">
            Status
            <select value={status} onChange={(e) => setStatus(e.target.value as ProjectStatus)} className="mt-1 w-full rounded border px-2 py-1 text-sm text-gray-800">
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-gray-500">
            Deadline
            <input type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} className="mt-1 w-full rounded border px-2 py-1 text-sm text-gray-800" />
          </label>
          <label className="text-xs text-gray-500">
            Hours of work remaining
            <input type="number" min={0} step={0.5} value={hours} onChange={(e) => setHours(Number(e.target.value))} className="mt-1 w-full rounded border px-2 py-1 text-sm text-gray-800" />
          </label>
          <div className="flex gap-2 sm:col-span-2">
            <button onClick={save} className="rounded bg-blue-600 px-3 py-1 text-sm text-white">Save</button>
            <button onClick={remove} className="rounded border border-red-200 px-3 py-1 text-sm text-red-600 hover:bg-red-50">Delete</button>
          </div>
        </div>
      )}

      {msg && <p className="mt-2 text-sm text-gray-600">{msg}</p>}

      {/* Plan preview */}
      {plan && (
        <div className="mt-3 rounded-lg border bg-blue-50/50 p-3">
          {plan.error ? (
            <p className="text-sm text-amber-700">⚠️ {plan.error}</p>
          ) : (
            <>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium">
                  Proposed: {plan.hours_scheduled}h in {plan.blocks.length} blocks
                  {plan.hours_unscheduled > 0 && (
                    <span className="text-amber-600"> · {plan.hours_unscheduled}h won't fit before the deadline</span>
                  )}
                </span>
                <div className="flex gap-2">
                  <button onClick={book} className="rounded bg-green-600 px-3 py-1 text-sm text-white">Add to calendar</button>
                  <button onClick={() => setPlan(null)} className="rounded border px-3 py-1 text-sm text-gray-600">Dismiss</button>
                </div>
              </div>
              <ul className="max-h-48 space-y-0.5 overflow-y-auto text-sm text-gray-600">
                {plan.blocks.map((b, i) => (
                  <li key={i}>· {fmtBlock(b)}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [root, setRoot] = useState('~/Projects')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const load = () =>
    fetchProjects()
      .then(setProjects)
      .catch((e) => setErr((e as Error).message))

  useEffect(() => {
    load()
  }, [])

  async function onDiscover() {
    setBusy(true)
    setErr(null)
    try {
      await discoverRepos(root)
      await load()
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-bold">Projects</h2>
        <div className="flex items-center gap-2">
          <input
            value={root}
            onChange={(e) => setRoot(e.target.value)}
            placeholder="~/Projects"
            className="w-48 rounded border px-2 py-1 text-sm"
          />
          <button onClick={onDiscover} disabled={busy} className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">
            {busy ? 'Scanning…' : 'Discover repos'}
          </button>
        </div>
      </div>

      {/* Cross-project smart planning lives in chat now — ask the secretary, e.g.
          "plan project A for next week, mornings only, leave project B alone". */}
      <p className="mb-3 text-xs text-gray-400">
        💬 Tip: ask the chat to plan across projects — e.g. “plan my week, leave research_labs alone”.
      </p>

      {err && <p className="mb-3 rounded bg-red-50 p-3 text-sm text-red-600">{err}</p>}

      {projects.length === 0 ? (
        <Placeholder
          title="📁 No projects yet"
          note="Point the box above at a folder of git repos and click “Discover repos”, then set a deadline and effort per project to start planning."
        />
      ) : (
        <div className="space-y-3">
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} onChanged={load} />
          ))}
        </div>
      )}
    </div>
  )
}
