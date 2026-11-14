import { ratingLabel } from '@/components/score/rating'
import { RatingIcon } from '@/components/score/rating-icon'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

import type { CriterionView } from './api'

const GROUPS: { operator: string; title: string; avoid?: boolean }[] = [
  { operator: 'must_have', title: 'Must have' },
  { operator: 'preferred', title: 'Preferred' },
  { operator: 'nice_to_have', title: 'Nice to have' },
  { operator: 'must_avoid', title: 'Red flags checked', avoid: true },
  { operator: 'may_avoid', title: 'Mild red flags checked', avoid: true },
]

/** "3 of 4 met · 1 to verify" (or "1 clear" for red flags). Unknowns are counted apart,
 *  matching the headline stat, because they are not part of the score yet. */
function groupSummary(items: CriterionView[], avoid: boolean) {
  const toVerify = items.filter((c) => c.outcome === 'Unknown').length
  const graded = items.length - toVerify
  const passed = items.filter((c) => c.outcome === 'Full Pass').length
  const parts = []
  if (graded > 0) parts.push(avoid ? `${passed} clear` : `${passed} of ${graded} met`)
  if (toVerify > 0) parts.push(`${toVerify} to verify`)
  return parts.join(' · ')
}

function CriterionRow({ c }: { c: CriterionView }) {
  return (
    <li className="flex gap-3 py-3">
      <RatingIcon outcome={c.outcome} className="mt-0.5" />
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-sm font-medium">{c.name}</span>
          {c.importance === 'high' && <Badge tone="accent">Key</Badge>}
          {c.knockout && <Badge tone="outline">Knock-out</Badge>}
        </div>
        <p className="text-sm text-muted-foreground">{c.reasoning}</p>
      </div>
      <span className="hidden shrink-0 text-xs text-muted-foreground sm:block">
        {ratingLabel(c.outcome)}
      </span>
    </li>
  )
}

/** Every requirement from the JD, grouped by how much it matters, with the evidence. */
export function CriteriaSection({ criteria }: { criteria: CriterionView[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Requirements</CardTitle>
        <CardDescription>
          Each requirement from the job description, graded against the resume.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {GROUPS.map((group) => {
          const items = criteria.filter((c) => c.operator === group.operator)
          if (items.length === 0) return null
          return (
            <section key={group.operator} aria-label={group.title}>
              <h3 className="flex items-baseline justify-between border-b pb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {group.title}
                <span className="normal-case">{groupSummary(items, !!group.avoid)}</span>
              </h3>
              <ul className="divide-y">
                {items.map((c) => (
                  <CriterionRow key={c.key} c={c} />
                ))}
              </ul>
            </section>
          )
        })}
      </CardContent>
    </Card>
  )
}
