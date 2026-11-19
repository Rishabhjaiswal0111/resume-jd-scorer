import { ChevronDown } from 'lucide-react'
import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

/** Native <select> (best on phones and for screen readers), styled like Input. */
export function Select({ className, children, ...props }: ComponentProps<'select'>) {
  return (
    <span className={cn('relative inline-flex', className)}>
      <select
        className="h-9 w-full appearance-none truncate rounded-md border bg-card py-0 pr-8 pl-3 text-sm focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:outline-none disabled:opacity-60"
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
    </span>
  )
}
