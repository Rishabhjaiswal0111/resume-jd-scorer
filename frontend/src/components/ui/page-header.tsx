import type { ReactNode } from 'react'

/** Title block at the top of every page. */
export function PageHeader(props: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold sm:text-3xl">{props.title}</h1>
        {props.description && <p className="text-muted-foreground">{props.description}</p>}
      </div>
      {props.actions}
    </div>
  )
}
