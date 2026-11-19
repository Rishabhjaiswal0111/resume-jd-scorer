import { ChevronRight, RotateCcw, Search, X } from 'lucide-react'
import { Link } from 'react-router'

import { ScoreRing } from '@/components/score/score-ring'
import { VerdictBadge } from '@/components/score/verdict-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

import { type JobCandidateItem, useRemoveCandidate, useRetryCandidate } from './api'
import { CandidateStatusBadge } from './StatusBadge'

function Row({ item, jobId }: { item: JobCandidateItem; jobId: string }) {
  const retry = useRetryCandidate(jobId)
  const remove = useRemoveCandidate(jobId)
  const scored = item.status === 'scored'
  return (
    <li className="flex items-center gap-3 p-4 sm:gap-4 sm:px-5">
      {scored ? (
        <ScoreRing score={item.score} size="sm" />
      ) : (
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-muted text-sm font-medium text-muted-foreground">
          {item.candidate.name.slice(0, 1).toUpperCase()}
        </span>
      )}
      <Link
        to={`/jobs/${jobId}/candidates/${item.id}`}
        className="group min-w-0 flex-1 space-y-1 focus-visible:outline-none"
      >
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-medium group-hover:text-primary group-focus-visible:underline">
            {item.candidate.name}
          </span>
          <VerdictBadge verdict={item.verdict} />
          <CandidateStatusBadge status={item.status} />
          {item.source === 'search' && (
            <Badge tone="outline">
              <Search className="size-3" aria-hidden />
              From search
            </Badge>
          )}
        </div>
        {item.candidate.headline && (
          <p className="line-clamp-2 text-sm text-muted-foreground sm:line-clamp-1">
            {item.candidate.headline}
          </p>
        )}
        {scored && item.summary && (
          <p className="line-clamp-2 text-sm text-muted-foreground sm:line-clamp-1">
            {item.summary}
          </p>
        )}
        {item.status === 'failed' && item.error_message && (
          <p className="text-sm text-destructive">{item.error_message}</p>
        )}
      </Link>
      <div className="flex shrink-0 items-center gap-1">
        {item.status === 'failed' && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => retry.mutate(item.id)}
            disabled={retry.isPending}
          >
            <RotateCcw aria-hidden />
            Retry
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Remove ${item.candidate.name} from this job`}
          title="Remove from this job"
          disabled={remove.isPending || item.status === 'scoring'}
          onClick={() => {
            if (window.confirm(`Remove ${item.candidate.name} from this job?`))
              remove.mutate(item.id)
          }}
        >
          <X aria-hidden />
        </Button>
        <ChevronRight className="hidden size-4 text-muted-foreground sm:block" aria-hidden />
      </div>
    </li>
  )
}

/** The job's candidates, best score first, then those still being scored. */
export function CandidateList({ items, jobId }: { items: JobCandidateItem[]; jobId: string }) {
  return (
    <Card>
      <ul className="divide-y">
        {items.map((item) => (
          <Row key={item.id} item={item} jobId={jobId} />
        ))}
      </ul>
    </Card>
  )
}
