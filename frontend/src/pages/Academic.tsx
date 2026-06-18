import { Placeholder } from '../components/Placeholder'

// Page 2 (Academic): suggested to-dos on top, then subjects with assignments
// + due dates + countdowns. All placeholder until M3 (Google Classroom).
export default function Academic() {
  return (
    <div className="h-full overflow-y-auto p-4">
      <h2 className="mb-4 text-xl font-bold">Academic schedule</h2>

      <div className="mb-4">
        <Placeholder
          title="✅ Suggested to-dos (across all subjects)"
          note="The secretary will rank what to do next once it can read your assignments (M3)."
        />
      </div>

      <Placeholder
        title="📚 Subjects & assignments"
        note="Each subject with its assignments, due dates, and live countdowns — pulled from Google Classroom (M3), sorted by deadline."
      />
    </div>
  )
}
