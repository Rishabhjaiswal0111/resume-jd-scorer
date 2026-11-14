import { cn } from '@/lib/utils'

import { useHealth } from './api'

/** Small header badge proving the frontend can reach the backend. */
export function HealthBadge() {
  const { data, isPending, isError } = useHealth()

  const version = data?.version ?? '?'
  const tone = isPending ? 'bg-muted-foreground' : isError ? 'bg-score-weak' : 'bg-score-strong'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full border p-2 text-xs sm:px-3 sm:py-1',
        'text-muted-foreground',
      )}
      role="status"
      aria-live="polite"
    >
      <span className={cn('size-2 rounded-full', tone)} aria-hidden />
      {/* Phones: the dot alone (text kept for screen readers). */}
      <span className="sr-only sm:not-sr-only">
        API: {isPending ? 'checking…' : isError ? 'unreachable' : 'ok'}
        {/* Version is detail: only where there is room. */}
        {!isPending && !isError && <span className="hidden sm:inline"> · v{version}</span>}
      </span>
    </span>
  )
}
