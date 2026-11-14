import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

// Small status label. Tones map to tokens; never pass raw colours.
const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap',
  {
    variants: {
      tone: {
        neutral: 'bg-secondary text-secondary-foreground',
        accent: 'bg-accent text-accent-foreground',
        strong: 'bg-score-strong/12 text-score-strong',
        medium: 'bg-score-medium/15 text-score-medium',
        weak: 'bg-score-weak/12 text-score-weak',
        danger: 'bg-destructive/12 text-destructive',
        outline: 'border text-muted-foreground',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
)

export type BadgeProps = ComponentProps<'span'> & VariantProps<typeof badgeVariants>

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />
}
