import { ListChecks, Search, UserPlus } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { FilesDropzone } from '@/components/ui/files-dropzone'
import { Textarea } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { useAddExisting, useJob, useJobs, type JobDetail } from '@/features/jobs/api'
import { useCandidates, useSearch, useUploadToDatabase } from '@/features/search/api'
import { SearchHitRow } from '@/features/search/SearchHitRow'
import { formatDate } from '@/lib/format'

/** A job's skill requirements as search keywords (location / screening items left out). */
function requirementsQuery(job: JobDetail): string {
  const words = job.requirements
    .filter(
      (r) =>
        ['must_have', 'preferred'].includes(r.operator) &&
        !r.verify_in_screening &&
        !['location', 'other'].includes(r.attribute),
    )
    .flatMap((r) => (r.values.length ? r.values : [r.name]))
  return [...new Set(words)].join(', ')
}

function UploadToDatabase() {
  const upload = useUploadToDatabase()
  return (
    <div className="space-y-2">
      <FilesDropzone
        label="Add resumes to your database"
        hint="PDFs · they become searchable at once, without scoring"
        accept="application/pdf,.pdf"
        onFiles={(files) => upload.mutate(files)}
        disabled={upload.isPending}
        compact
      />
      <div aria-live="polite" className="text-sm">
        {upload.isPending && <p className="text-muted-foreground">Uploading…</p>}
        {upload.data && !upload.isPending && (
          <>
            {upload.data.added.length > 0 && (
              <p className="text-muted-foreground">
                Added {upload.data.added.length} to your database.
              </p>
            )}
            {upload.data.errors.map((e) => (
              <p key={e.filename} role="alert" className="text-destructive">
                {e.filename}: {e.message}
              </p>
            ))}
          </>
        )}
      </div>
    </div>
  )
}

function AllCandidates() {
  const all = useCandidates()
  if (all.isPending) return <Skeleton className="h-40" />
  if (all.isError)
    return (
      <p role="alert" className="text-sm text-destructive">
        {all.error.message}
      </p>
    )
  if (all.data.length === 0)
    return (
      <EmptyState
        title="Your database is empty"
        description="Resumes you upload to jobs, or above, are kept here and searchable."
      />
    )
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium">
        Everyone in your database <span className="text-muted-foreground">({all.data.length})</span>
      </h2>
      <Card>
        <ul className="divide-y">
          {all.data.map((c) => (
            <li key={c.id} className="flex items-center gap-3 px-4 py-3 sm:px-5">
              <span className="grid size-8 shrink-0 place-items-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
                {c.name.slice(0, 1).toUpperCase()}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{c.name}</p>
                <p className="truncate text-xs text-muted-foreground">{c.headline ?? c.filename}</p>
              </div>
              <span className="hidden text-xs text-muted-foreground sm:block">
                {formatDate(c.created_at)}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  )
}

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const jobId = params.get('job') ?? ''
  const [draft, setDraft] = useState(q)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const search = useSearch(q)
  const jobs = useJobs()
  const job = useJob(jobId)
  const targetJob = jobId ? job.data : undefined
  const add = useAddExisting()

  useEffect(() => setDraft(q), [q])
  useEffect(() => setSelected(new Set()), [q])

  function update(next: { q?: string; job?: string }) {
    const merged = { q, job: jobId, ...next }
    const out = new URLSearchParams()
    if (merged.q.trim()) out.set('q', merged.q.trim())
    if (merged.job) out.set('job', merged.job)
    setParams(out, { replace: next.q === undefined })
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    update({ q: draft })
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const hits = search.data?.hits ?? []
  const onTarget = new Set(
    hits.filter((h) => h.jobs.some((j) => j.job_id === jobId)).map((h) => h.candidate.id),
  )
  const toAdd = [...selected].filter((id) => !onTarget.has(id))

  return (
    <div className="space-y-6 pb-24">
      <PageHeader
        title="Search candidates"
        description="Find the closest resumes in your database by keywords, or paste any text, even a whole job description."
      />
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={submit} className="space-y-3">
            <Textarea
              aria-label="Keywords or text to search for"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  update({ q: draft })
                }
              }}
              placeholder="e.g. React TypeScript accessibility, or paste a job description"
              rows={3}
            />
            <div className="flex flex-wrap items-center gap-2">
              <Select
                aria-label="Job to add candidates to"
                value={jobId}
                onChange={(e) => update({ job: e.target.value })}
                className="min-w-0 flex-1 sm:max-w-xs"
              >
                <option value="">Add results to… (choose a job)</option>
                {jobs.data?.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title}
                  </option>
                ))}
              </Select>
              {targetJob && targetJob.requirements.length > 0 && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    const query = requirementsQuery(targetJob)
                    setDraft(query)
                    update({ q: query })
                  }}
                >
                  <ListChecks aria-hidden />
                  Use job&apos;s requirements
                </Button>
              )}
              <Button type="submit" disabled={!draft.trim()} className="ml-auto">
                <Search aria-hidden />
                Search
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {!q && (
        <div className="space-y-6">
          <UploadToDatabase />
          <AllCandidates />
        </div>
      )}

      {q && search.isPending && <Skeleton className="h-64" />}
      {q && search.isError && (
        <p role="alert" className="text-sm text-destructive">
          {search.error.message}
        </p>
      )}
      {q && search.data && (
        <section className="space-y-3" aria-label="Search results">
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {hits.length === 0
              ? `No resumes in your database (${search.data.total_candidates}) contain these terms.`
              : `${hits.length} of ${search.data.total_candidates} resumes match, closest first.`}
          </p>
          {hits.length > 0 && (
            <Card>
              <ul className="divide-y">
                {hits.map((hit) => (
                  <SearchHitRow
                    key={hit.candidate.id}
                    hit={hit}
                    selected={selected.has(hit.candidate.id)}
                    onToggle={() => toggle(hit.candidate.id)}
                  />
                ))}
              </ul>
            </Card>
          )}
        </section>
      )}

      {(selected.size > 0 || add.isSuccess || add.isError) && (
        <div className="fixed inset-x-0 bottom-0 z-10 border-t bg-card/95 backdrop-blur">
          <div
            className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3"
            aria-live="polite"
          >
            {add.isSuccess && selected.size === 0 ? (
              <p className="flex-1 text-sm">
                Added {add.data.length} to {targetJob?.title ?? 'the job'}; scoring has started.{' '}
                <Link to={`/jobs/${add.variables.jobId}`} className="font-medium text-primary">
                  View job
                </Link>
              </p>
            ) : (
              <>
                <p className="text-sm font-medium">{selected.size} selected</p>
                {add.isError && (
                  <p role="alert" className="text-sm text-destructive">
                    {add.error.message}
                  </p>
                )}
                <div className="ml-auto flex flex-wrap items-center gap-2">
                  {!jobId && (
                    <span className="text-sm text-muted-foreground">Choose a job above</span>
                  )}
                  {jobId && toAdd.length < selected.size && (
                    <span className="text-xs text-muted-foreground">
                      {selected.size - toAdd.length} already on this job
                    </span>
                  )}
                  <Button variant="ghost" onClick={() => setSelected(new Set())}>
                    Clear
                  </Button>
                  <Button
                    disabled={!jobId || toAdd.length === 0 || add.isPending}
                    onClick={() =>
                      add.mutate(
                        { jobId, candidateIds: toAdd },
                        { onSuccess: () => setSelected(new Set()) },
                      )
                    }
                  >
                    <UserPlus aria-hidden />
                    {add.isPending ? 'Adding…' : `Add ${toAdd.length || ''} to job`}
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
