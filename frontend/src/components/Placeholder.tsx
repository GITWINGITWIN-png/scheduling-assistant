// A styled empty-state card for panels whose backend lands in a later milestone.
// Keeps the layout honest now and turns into a real component when data exists.
export function Placeholder({
  title,
  note,
  className = '',
}: {
  title: string
  note: string
  className?: string
}) {
  return (
    <div
      className={`flex min-h-[120px] flex-col rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 ${className}`}
    >
      <h3 className="text-sm font-semibold text-gray-600">{title}</h3>
      <p className="mt-2 text-sm text-gray-400">{note}</p>
    </div>
  )
}
