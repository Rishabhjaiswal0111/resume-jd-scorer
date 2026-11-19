import { Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'

/** A job's background state. Ready jobs show nothing: that is the normal case. */
export function JobStatusBadge({ status }: { status: string }) {
  if (status === 'pending' || status === 'parsing')
    return (
      <Badge tone="accent">
        <Loader2 className="size-3 animate-spin" aria-hidden />
        Reading job description
      </Badge>
    )
  if (status === 'failed') return <Badge tone="danger">Couldn&apos;t read</Badge>
  return null
}

/** A candidate's scoring state on a job (scored ones show their score instead). */
export function CandidateStatusBadge({ status }: { status: string }) {
  if (status === 'queued') return <Badge tone="neutral">Queued</Badge>
  if (status === 'scoring')
    return (
      <Badge tone="accent">
        <Loader2 className="size-3 animate-spin" aria-hidden />
        Scoring
      </Badge>
    )
  if (status === 'failed') return <Badge tone="danger">Not scored</Badge>
  return null
}
