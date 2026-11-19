import { ChevronRight, FileText, Type } from 'lucide-react'
import { Link } from 'react-router'

import { ScoreRing } from '@/components/score/score-ring'
import { Card } from '@/components/ui/card'
import { formatDate } from '@/lib/format'

import type { JobSummary } from './api'
import { JobStatusBadge } from './StatusBadge'

function countsLine(job: JobSummary): string {
  const { total, scored, in_progress } = job.counts
  if (total === 0) return 'No candidates yet'
  const parts = [`${total} ${total === 1 ? 'candidate' : 'candidates'}`]
  if (in_progress) parts.push(`${in_progress} scoring`)
  else if (scored < total) parts.push(`${scored} scored`)
  return parts.join(' · ')
}

/** One job in the Jobs grid: title, state, how far its shortlist has got, best score. */
export function JobCard({ job }: { job: JobSummary }) {
  const SourceIcon = job.source === 'pdf' ? FileText : Type
  return (
    <Link
      to={`/jobs/${job.id}`}
      className="group block rounded-xl focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <Card className="flex h-full flex-col gap-4 p-5 transition-colors group-hover:border-primary/40">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1 space-y-1.5">
            <h2 className="line-clamp-2 leading-snug font-semibold">{job.title}</h2>
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <SourceIcon className="size-3.5" aria-hidden />
              {job.source === 'pdf' ? 'PDF' : 'Pasted text'} · Added {formatDate(job.created_at)}
            </p>
          </div>
          {job.best_score !== null && <ScoreRing score={job.best_score} size="sm" />}
        </div>
        <div className="mt-auto flex flex-wrap items-center gap-2 border-t pt-3 text-sm">
          <JobStatusBadge status={job.status} />
          <span className="text-muted-foreground">{countsLine(job)}</span>
          {job.counts.strong > 0 && (
            <span className="text-score-strong">· {job.counts.strong} strong</span>
          )}
          <ChevronRight
            className="ml-auto size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5"
            aria-hidden
          />
        </div>
      </Card>
    </Link>
  )
}
