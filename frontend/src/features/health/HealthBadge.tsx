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
        'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs',
        'text-muted-foreground',
      )}
      role="status"
      aria-live="polite"
    >
      <span className={cn('size-2 rounded-full', tone)} aria-hidden />
      <span>
        API: {isPending ? 'checking…' : isError ? 'unreachable' : 'ok'}
        {/* Version is detail: only where there is room. */}
        {!isPending && !isError && <span className="hidden sm:inline"> · v{version}</span>}
      </span>
    </span>
  )
}
