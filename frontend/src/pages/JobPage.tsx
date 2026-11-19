import { ArrowLeft, Loader2, RotateCcw, Search, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { DocumentPreview } from '@/components/ui/document-preview'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { Stat } from '@/components/ui/stat'
import { Tabs } from '@/components/ui/tabs'
import { AddResumes } from '@/features/jobs/AddResumes'
import {
  jobDocumentUrl,
  useDeleteJob,
  useJob,
  useJobCandidates,
  useRetryJob,
  type JobDetail,
} from '@/features/jobs/api'
import { CandidateList } from '@/features/jobs/CandidateList'
import { Requirements } from '@/features/jobs/Requirements'
import { JobStatusBadge } from '@/features/jobs/StatusBadge'
import { isNotFound } from '@/lib/api/client'
import { formatDate } from '@/lib/format'

type Tab = 'candidates' | 'description'

function JobState({ job }: { job: JobDetail }) {
  const retry = useRetryJob(job.id)
  if (job.status === 'pending' || job.status === 'parsing')
    return (
      <p className="flex items-center gap-2 rounded-lg bg-accent/50 px-4 py-3 text-sm text-accent-foreground">
        <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden />
        Reading the job description. Candidates you add now are scored as soon as it&apos;s ready.
      </p>
    )
  if (job.status === 'failed')
    return (
      <div
        role="alert"
        className="flex flex-wrap items-center gap-3 rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive"
      >
        <span className="flex-1">Couldn&apos;t read this job description: {job.error_message}</span>
        {job.error_code !== 'RUBRIC_EMPTY' && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => retry.mutate()}
            disabled={retry.isPending}
          >
            <RotateCcw aria-hidden />
            Retry
          </Button>
        )}
      </div>
    )
  return null
}

function CandidatesPanel({ job }: { job: JobDetail }) {
  const candidates = useJobCandidates(job.id)
  return (
    <div className="space-y-4">
      <AddResumes jobId={job.id} />
      {candidates.isPending && <Skeleton className="h-40" />}
      {candidates.isError && (
        <p role="alert" className="text-sm text-destructive">
          Couldn&apos;t load candidates: {candidates.error.message}
        </p>
      )}
      {candidates.isSuccess &&
        (candidates.data.length === 0 ? (
          <EmptyState
            title="No candidates yet"
            description="Drop resumes above, or find people already in your database."
            action={
              <Link to={`/search?job=${job.id}`} className={buttonVariants({ variant: 'outline' })}>
                <Search aria-hidden />
                Find in your database
              </Link>
            }
          />
        ) : (
          <CandidateList items={candidates.data} jobId={job.id} />
        ))}
    </div>
  )
}

export function JobPage() {
  const { jobId = '' } = useParams()
  const job = useJob(jobId)
  const remove = useDeleteJob()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('candidates')

  if (job.isPending)
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-24" />
        <Skeleton className="h-64" />
      </div>
    )
  if (job.isError)
    return (
      <EmptyState
        title={isNotFound(job.error) ? 'Job not found' : "Couldn't load this job"}
        description={isNotFound(job.error) ? undefined : job.error.message}
        action={
          <Link to="/jobs" className={buttonVariants({ variant: 'outline' })}>
            All jobs
          </Link>
        }
      />
    )

  const data = job.data
  const { counts } = data
  return (
    <div className="space-y-6">
      <Link
        to="/jobs"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden /> All jobs
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-2">
          <h1 className="text-2xl font-semibold sm:text-3xl">{data.title}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <JobStatusBadge status={data.status} />
            <Badge tone="outline">{data.source === 'pdf' ? 'PDF' : 'Pasted text'}</Badge>
            <span>Added {formatDate(data.created_at)}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={`/search?job=${data.id}`} className={buttonVariants({ variant: 'outline' })}>
            <Search aria-hidden />
            Find in database
          </Link>
          <Button
            variant="ghost"
            aria-label="Delete job"
            title="Delete job"
            disabled={remove.isPending}
            onClick={() => {
              if (
                window.confirm(
                  `Delete "${data.title}"? Its scores go too; the candidates stay in your database.`,
                )
              )
                remove.mutate(data.id, { onSuccess: () => navigate('/jobs') })
            }}
          >
            <Trash2 aria-hidden />
          </Button>
        </div>
      </div>
      <JobState job={data} />
      <Card>
        <CardContent className="pt-6">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Candidates" value={counts.total} />
            <Stat label="Scored" value={counts.scored} />
            <Stat label="Strong fits" value={counts.strong} />
            <Stat label="Best score" value={data.best_score ?? '–'} />
          </dl>
        </CardContent>
      </Card>
      <Tabs
        label="Job sections"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: 'candidates', label: 'Candidates', count: counts.total },
          { value: 'description', label: 'Job description' },
        ]}
      />
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'candidates' ? (
          <CandidatesPanel job={data} />
        ) : (
          <div className="grid gap-6 lg:grid-cols-2">
            {data.requirements.length > 0 ? (
              <Requirements job={data} />
            ) : (
              <EmptyState
                title="Requirements not read yet"
                description="They appear here once the job description has been read."
              />
            )}
            <Card>
              <CardContent className="pt-6">
                <DocumentPreview
                  title="Job description"
                  src={jobDocumentUrl(data.id)}
                  isPdf={data.source === 'pdf'}
                  text={data.jd_text}
                />
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
