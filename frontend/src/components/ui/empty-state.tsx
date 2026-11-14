import type { ReactNode } from 'react'

/** Shown when a list has nothing in it yet. */
export function EmptyState(props: { title: string; description?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-12 text-center">
      <p className="font-medium">{props.title}</p>
      {props.description && (
        <p className="max-w-sm text-sm text-muted-foreground">{props.description}</p>
      )}
      {props.action && <div className="pt-2">{props.action}</div>}
    </div>
  )
}
