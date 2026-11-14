import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router'

import { Skeleton } from '@/components/ui/skeleton'
import { useRun } from '@/features/history/api'
import { RunResult } from '@/features/scoring/RunResult'

/** One past run, opened from History (shareable URL: /runs/:runId). */
export function RunPage() {
  const { runId = '' } = useParams()
  const run = useRun(runId)
  return (
    <div className="space-y-6">
      <Link
        to="/history"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden /> History
      </Link>
      {run.isPending && (
        <div className="space-y-4">
          <Skeleton className="h-36" />
          <Skeleton className="h-64" />
        </div>
      )}
      {run.isError && (
        <p role="alert" className="text-sm text-destructive">
          Couldn&apos;t load this run: {run.error.message}
        </p>
      )}
      {run.isSuccess && <RunResult run={run.data} />}
    </div>
  )
}
