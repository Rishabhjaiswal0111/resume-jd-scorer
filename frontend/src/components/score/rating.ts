import { CircleCheck, CircleHelp, CircleMinus, CircleX } from 'lucide-react'

/** Criterion outcomes as recruiter-facing ratings (icon, colour token, words). */
export const RATINGS = {
  'Full Pass': { Icon: CircleCheck, className: 'text-score-strong', label: 'Meets' },
  'Partial Pass': { Icon: CircleMinus, className: 'text-score-medium', label: 'Partly meets' },
  Fail: { Icon: CircleX, className: 'text-score-weak', label: 'Does not meet' },
  Unknown: { Icon: CircleHelp, className: 'text-muted-foreground', label: 'Ask in screening' },
} as const

export type Rating = keyof typeof RATINGS

export function ratingLabel(outcome: string): string {
  return RATINGS[outcome as Rating]?.label ?? outcome
}
