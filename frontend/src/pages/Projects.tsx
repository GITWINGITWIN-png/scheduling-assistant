import { useEffect, useState } from 'react'
import { fetchProjects, type Project } from '../api'
import { Placeholder } from '../components/Placeholder'

// Page 3 (Projects): an index of projects (name, last commit, description,
// status). Reads /projects (empty for now); full data arrives at M4.
export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([])

  useEffect(() => {
    fetchProjects()
      .then(setProjects)
      .catch(() => setProjects([]))
  }, [])

  return (
    <div className="h-full overflow-y-auto p-4">
      <h2 className="mb-4 text-xl font-bold">Projects</h2>

      {projects.length === 0 ? (
        <Placeholder
          title="📁 No projects yet"
          note="Name, last commit date, description, and status will list here once the planner (M4) is built."
        />
      ) : (
        <ul className="space-y-2">
          {projects.map((p) => (
            <li key={p.id} className="rounded-lg border bg-white p-3 shadow-sm">
              <div className="font-semibold">{p.name}</div>
              {p.goal && <div className="text-sm text-gray-500">{p.goal}</div>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
