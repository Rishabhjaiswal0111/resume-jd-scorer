import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router'

import { ScoreRing } from '@/components/score/score-ring'
import { VerdictBadge } from '@/components/score/verdict-badge'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateTime } from '@/lib/format'

import { useJdRuns } from './api'

/** The resumes scored against one JD, newest first. Each row opens the full result. */
export function JdRuns({ jdDocumentId }: { jdDocumentId: string }) {
  const runs = useJdRuns(jdDocumentId, true)

  if (runs.isPending) {
    return (
      <div className="space-y-2 p-4">
        <Skeleton className="h-10" />
        <Skeleton className="h-10" />
      </div>
    )
  }
  if (runs.isError) {
    return (
      <p className="p-4 text-sm text-destructive">Couldn&apos;t load runs: {runs.error.message}</p>
    )
  }

  return (
    <ul className="divide-y" aria-label="Scored resumes">
      {runs.data.map((run) => (
        <li key={run.id}>
          <Link
            to={`/runs/${run.id}`}
            className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/60 focus-visible:bg-muted/60 focus-visible:outline-none sm:px-5"
          >
            <ScoreRing score={run.score} size="sm" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{run.resume_filename}</p>
              <p className="text-xs text-muted-foreground">{formatDateTime(run.created_at)}</p>
            </div>
            <VerdictBadge verdict={run.verdict} />
            <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
          </Link>
        </li>
      ))}
    </ul>
  )
}
