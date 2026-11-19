import { Plus } from 'lucide-react'
import { Link } from 'react-router'

import { buttonVariants } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { useJobs } from '@/features/jobs/api'
import { JobCard } from '@/features/jobs/JobCard'
import { HowItWorks } from '@/features/scoring/HowItWorks'

export function JobsPage() {
  const jobs = useJobs()
  return (
    <div className="space-y-6">
      <PageHeader
        title="Jobs"
        description="Each job keeps its candidates and their scores."
        actions={
          <Link to="/jobs/new" className={buttonVariants()}>
            <Plus aria-hidden />
            New job
          </Link>
        }
      />
      {jobs.isPending && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-36" />
          <Skeleton className="h-36" />
          <Skeleton className="h-36" />
        </div>
      )}
      {jobs.isError && (
        <p role="alert" className="text-sm text-destructive">
          Couldn&apos;t load your jobs: {jobs.error.message}
        </p>
      )}
      {jobs.isSuccess &&
        (jobs.data.length === 0 ? (
          <div className="space-y-8">
            <EmptyState
              title="No jobs yet"
              description="Add a job description, then upload resumes to score them against it."
              action={
                <Link to="/jobs/new" className={buttonVariants()}>
                  Add your first job
                </Link>
              }
            />
            <HowItWorks />
          </div>
        ) : (
          <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {jobs.data.map((job) => (
              <li key={job.id}>
                <JobCard job={job} />
              </li>
            ))}
          </ul>
        ))}
    </div>
  )
}
