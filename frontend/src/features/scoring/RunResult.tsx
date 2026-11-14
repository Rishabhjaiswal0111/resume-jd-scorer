import type { RunDetail } from './api'
import { CriteriaSection } from './CriteriaSection'
import { ScoringDetails } from './ScoringDetails'
import { ScreeningCard } from './ScreeningCard'
import { SummaryCard } from './SummaryCard'
import { Takeaways } from './Takeaways'

/** A scored run as a recruiter scorecard: headline, takeaways, open questions, evidence. */
export function RunResult({ run }: { run: RunDetail }) {
  // The role-overlap sentence is the headline summary; don't repeat it as a takeaway.
  const pros = run.pros.filter((p) => p.source !== 'role_overlap')
  const cons = run.cons.filter((p) => p.source !== 'role_overlap')
  return (
    <div className="space-y-6">
      <SummaryCard run={run} strengths={pros.length} />
      {run.warnings.length > 0 && (
        <p className="text-sm text-score-medium">Note: {run.warnings.join('; ')}</p>
      )}
      <Takeaways pros={pros} cons={cons} />
      <ScreeningCard items={run.screening} />
      <CriteriaSection criteria={run.criteria} />
      <ScoringDetails run={run} />
    </div>
  )
}
