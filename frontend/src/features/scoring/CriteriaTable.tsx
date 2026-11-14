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

function typeLabel(c: CriterionView) {
  return [
    OPERATOR_LABEL[c.operator] ?? c.operator,
    c.importance === 'high' && 'high',
    c.knockout && 'knock-out',
  ]
    .filter(Boolean)
    .join(' · ')
}

function Outcome({ c }: { c: CriterionView }) {
  return (
    <span className={OUTCOME_TONE[c.outcome]}>
      {c.outcome === 'Unknown' ? 'Ask in screening' : c.outcome}
      {c.forced && c.forced !== 'unknown_screen' && (
        <span className="block text-xs text-muted-foreground">model said {c.llm_outcome}</span>
      )}
    </span>
  )
}

/** Phones: one card per criterion (a 5-column table doesn't fit). */
function CriteriaCards({ criteria }: { criteria: CriterionView[] }) {
  return (
    <ul className="divide-y md:hidden" aria-label="Criteria">
      {criteria.map((c) => (
        <li key={c.key} className="space-y-1 py-3 text-sm">
          <div className="flex items-start justify-between gap-3">
            <span className="font-medium">{c.name}</span>
            <span className="shrink-0 tabular-nums">
              {c.earned} / {c.weight}
            </span>
          </div>
          <div className="flex flex-wrap gap-x-2 text-xs">
            <span className="text-muted-foreground">{typeLabel(c)}</span>
            <Outcome c={c} />
          </div>
          <p className="text-muted-foreground">{c.reasoning}</p>
        </li>
      ))}
    </ul>
  )
}

export function CriteriaTable({ criteria }: { criteria: CriterionView[] }) {
  return (
    <>
      <CriteriaCards criteria={criteria} />
      <div className="hidden overflow-x-auto md:block">
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
                  {typeLabel(c)}
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  <Outcome c={c} />
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
    </>
  )
}
