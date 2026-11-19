import { ArrowLeft, Loader2, RotateCcw } from 'lucide-react'
import { Link, useParams } from 'react-router'

import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { DocumentPreview } from '@/components/ui/document-preview'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { resumeUrl, useJobCandidate, useRetryCandidate } from '@/features/jobs/api'
import { RunResult } from '@/features/scoring/RunResult'
import { isNotFound } from '@/lib/api/client'

export function CandidatePage() {
  const { jobId = '', jobCandidateId = '' } = useParams()
  const detail = useJobCandidate(jobId, jobCandidateId)
  const retry = useRetryCandidate(jobId)

  if (detail.isPending)
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-48" />
      </div>
    )
  if (detail.isError)
    return (
      <EmptyState
        title={isNotFound(detail.error) ? 'Candidate not found' : "Couldn't load candidate"}
        description={isNotFound(detail.error) ? undefined : detail.error.message}
        action={
          <Link to={`/jobs/${jobId}`} className={buttonVariants({ variant: 'outline' })}>
            Back to the job
          </Link>
        }
      />
    )

  const c = detail.data
  return (
    <div className="space-y-6">
      <Link
        to={`/jobs/${jobId}`}
        className="inline-flex max-w-full items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4 shrink-0" aria-hidden />
        <span className="truncate">{c.job_title}</span>
      </Link>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold sm:text-3xl">{c.candidate.name}</h1>
        {c.candidate.headline && <p className="text-muted-foreground">{c.candidate.headline}</p>}
      </div>
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <section aria-label="Scorecard" className="min-w-0">
          {c.run && <RunResult run={c.run} />}
          {(c.status === 'queued' || c.status === 'scoring') && (
            <Card>
              <CardContent className="flex items-center gap-3 pt-6 text-sm">
                <Loader2 className="size-5 animate-spin text-primary" aria-hidden />
                <div>
                  <p className="font-medium">
                    {c.status === 'queued' ? 'Waiting to be scored' : 'Scoring this resume'}
                  </p>
                  <p className="text-muted-foreground">
                    The scorecard appears here on its own; you can leave this page.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
          {c.status === 'failed' && (
            <Card>
              <CardContent className="flex flex-wrap items-center gap-3 pt-6 text-sm">
                <p role="alert" className="flex-1 text-destructive">
                  Not scored: {c.error_message}
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => retry.mutate(c.id)}
                  disabled={retry.isPending}
                >
                  <RotateCcw aria-hidden />
                  Retry
                </Button>
              </CardContent>
            </Card>
          )}
        </section>
        <section aria-label="Resume" className="min-w-0 xl:sticky xl:top-20">
          <Card>
            <CardContent className="space-y-2 pt-6">
              <h2 className="text-sm font-medium">Resume · {c.candidate.filename}</h2>
              <DocumentPreview
                title="Resume"
                src={resumeUrl(c.candidate.id)}
                isPdf
                text={c.resume_text}
              />
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  )
}
