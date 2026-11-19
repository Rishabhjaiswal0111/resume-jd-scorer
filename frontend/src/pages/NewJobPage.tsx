import { ArrowLeft } from 'lucide-react'
import { Link, useNavigate } from 'react-router'

import { PageHeader } from '@/components/ui/page-header'
import { useCreateJob } from '@/features/jobs/api'
import { JobForm } from '@/features/jobs/JobForm'

export function NewJobPage() {
  const create = useCreateJob()
  const navigate = useNavigate()
  return (
    <div className="space-y-6">
      <Link
        to="/jobs"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden /> All jobs
      </Link>
      <PageHeader
        title="New job"
        description="Upload the job description or paste it, check the preview, then add it."
      />
      <JobForm
        pending={create.isPending}
        error={create.error?.message}
        onSubmit={(jd) => create.mutate(jd, { onSuccess: (job) => navigate(`/jobs/${job.id}`) })}
      />
    </div>
  )
}
