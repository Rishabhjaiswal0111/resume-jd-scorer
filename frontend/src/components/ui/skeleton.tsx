import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

/** Placeholder block while data loads. Size it with className (h-*, w-*). */
export function Skeleton({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div aria-hidden className={cn('animate-pulse rounded-md bg-muted', className)} {...props} />
  )
}
