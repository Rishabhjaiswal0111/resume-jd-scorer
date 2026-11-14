import { cn } from '@/lib/utils'

import { useHealth } from './api'

/** Small header badge proving the frontend can reach the backend. */
export function HealthBadge() {
  const { data, isPending, isError } = useHealth()

  const version = data?.version ?? '?'
  const label = isPending ? 'checking…' : isError ? 'unreachable' : `ok · v${version}`
  const tone = isPending ? 'bg-muted-foreground' : isError ? 'bg-score-weak' : 'bg-score-strong'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs',
        'text-muted-foreground',
      )}
      role="status"
      aria-live="polite"
    >
      <span className={cn('size-2 rounded-full', tone)} aria-hidden />
      API: {label}
    </span>
  )
}
