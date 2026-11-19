import { Link } from 'react-router'

import { buttonVariants } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="space-y-4 py-16 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <Link to="/jobs" className={buttonVariants({ variant: 'outline' })}>
        Back to jobs
      </Link>
    </div>
  )
}
