import { Link } from 'react-router'

import { buttonVariants } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { useJds } from '@/features/history/api'
import { JdHistoryList } from '@/features/history/JdHistoryList'

export function HistoryPage() {
  const jds = useJds()
  return (
    <div className="space-y-6">
      <PageHeader
        title="History"
        description="Every job description you've scored against, with the resumes scored for it."
      />
      {jds.isPending && (
        <div className="space-y-3">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      )}
      {jds.isError && (
        <p role="alert" className="text-sm text-destructive">
          Couldn&apos;t load history: {jds.error.message}
        </p>
      )}
      {jds.isSuccess &&
        (jds.data.length === 0 ? (
          <EmptyState
            title="Nothing scored yet"
            description="Scores you run appear here, grouped by job description."
            action={
              <Link to="/" className={buttonVariants()}>
                Score a resume
              </Link>
            }
          />
        ) : (
          <JdHistoryList jds={jds.data} />
        ))}
    </div>
  )
}
