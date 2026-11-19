import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'

import { Skeleton } from '@/components/ui/skeleton'

import { useMe } from './api'

/** Renders children only for a signed-in user; otherwise goes to /login and back after. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe()
  const location = useLocation()
  if (me.isPending) {
    return (
      <div className="mx-auto max-w-6xl space-y-3 p-6" aria-busy="true">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32" />
      </div>
    )
  }
  if (me.isError) {
    return (
      <p role="alert" className="p-6 text-sm text-destructive">
        Couldn&apos;t reach the server: {me.error.message}
      </p>
    )
  }
  if (!me.data) {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  return children
}
