import { cn } from '@/lib/utils'

import type { CriterionView } from './api'

const OUTCOME_TONE: Record<string, string> = {
  'Full Pass': 'text-score-strong',
  'Partial Pass': 'text-score-medium',
  Fail: 'text-score-weak',
  Unknown: 'text-muted-foreground',
}

const OPERATOR_LABEL: Record<string, string> = {
  must_have: 'Must have',
  preferred: 'Preferred',
  nice_to_have: 'Nice to have',
  must_avoid: 'Must avoid',
  may_avoid: 'May avoid',
}

export function CriteriaTable({ criteria }: { criteria: CriterionView[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-muted-foreground">
          <tr className="border-b">
            <th className="py-2 pr-4 font-medium">Criterion</th>
            <th className="py-2 pr-4 font-medium">Type</th>
            <th className="py-2 pr-4 font-medium">Outcome</th>
            <th className="py-2 pr-4 text-right font-medium">Points</th>
            <th className="py-2 font-medium">Why</th>
          </tr>
        </thead>
        <tbody>
          {criteria.map((c) => (
            <tr key={c.key} className="border-b align-top last:border-0">
              <td className="py-2 pr-4 font-medium">{c.name}</td>
              <td className="py-2 pr-4 whitespace-nowrap text-muted-foreground">
                {OPERATOR_LABEL[c.operator] ?? c.operator}
                {c.importance === 'high' && ' · high'}
                {c.knockout && ' · knock-out'}
              </td>
              <td className={cn('py-2 pr-4 whitespace-nowrap', OUTCOME_TONE[c.outcome])}>
                {c.outcome === 'Unknown' ? 'Ask in screening' : c.outcome}
                {c.forced && c.forced !== 'unknown_screen' && (
                  <span className="block text-xs text-muted-foreground">
                    model said {c.llm_outcome}
                  </span>
                )}
              </td>
              <td className="py-2 pr-4 text-right whitespace-nowrap tabular-nums">
                {c.earned} / {c.weight}
              </td>
              <td className="py-2 text-muted-foreground">{c.reasoning}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
