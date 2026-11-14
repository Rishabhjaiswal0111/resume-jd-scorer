import { CircleAlert } from 'lucide-react'

import { useHealth } from './api'

/**
 * Backend status. Silent while everything works (clients don't need to see "API: ok");
 * shows a clear notice when the frontend can't reach the API.
 */
export function HealthBadge() {
  const { data, isError } = useHealth()
  if (isError) {
    return (
      <span
        role="status"
        aria-live="polite"
        className="inline-flex items-center gap-1.5 rounded-full bg-destructive/10 px-3 py-1 text-xs font-medium text-destructive"
      >
        <CircleAlert className="size-3.5" aria-hidden />
        Service unreachable
      </span>
    )
  }
  return (
    <span role="status" aria-live="polite" className="sr-only">
      {data ? `Service available, version ${data.version}` : 'Checking service'}
    </span>
  )
}
