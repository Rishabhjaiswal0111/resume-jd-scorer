import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

/** Text input. Same border, radius and focus ring as every other field. */
export function Input({ className, ...props }: ComponentProps<'input'>) {
  return (
    <input
      className={cn(
        'h-9 w-full rounded-md border bg-card px-3 text-sm font-normal placeholder:text-muted-foreground focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:outline-none disabled:opacity-60',
        className,
      )}
      {...props}
    />
  )
}

/** Multi-line text field, styled like Input. */
export function Textarea({ className, ...props }: ComponentProps<'textarea'>) {
  return (
    <textarea
      className={cn(
        'w-full rounded-lg border bg-card p-3 text-sm placeholder:text-muted-foreground focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:outline-none disabled:opacity-60',
        className,
      )}
      {...props}
    />
  )
}
