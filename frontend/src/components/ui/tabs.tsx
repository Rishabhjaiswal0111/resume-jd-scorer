import { cn } from '@/lib/utils'

/** Page-level tabs (underline style). Panels are rendered by the caller. */
export function Tabs<T extends string>(props: {
  label: string
  value: T
  tabs: { value: T; label: string; count?: number }[]
  onChange: (value: T) => void
}) {
  return (
    <div role="tablist" aria-label={props.label} className="flex gap-1 border-b">
      {props.tabs.map((tab) => {
        const active = tab.value === props.value
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            id={`tab-${tab.value}`}
            aria-selected={active}
            aria-controls={`panel-${tab.value}`}
            onClick={() => props.onChange(tab.value)}
            className={cn(
              '-mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition-colors',
              active
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className="rounded-full bg-muted px-1.5 text-xs text-muted-foreground tabular-nums">
                {tab.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
