import { cn } from '@/lib/utils'

import { RATINGS, type Rating } from './rating'

/** Colour-coded rating for one criterion (green / amber / red / grey). */
export function RatingIcon({ outcome, className }: { outcome: string; className?: string }) {
  const rating = RATINGS[outcome as Rating] ?? RATINGS.Unknown
  const { Icon } = rating
  return (
    <Icon
      className={cn('size-5 shrink-0', rating.className, className)}
      aria-label={rating.label}
      role="img"
    />
  )
}
