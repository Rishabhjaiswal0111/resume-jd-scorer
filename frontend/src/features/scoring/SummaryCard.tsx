import { ScoreRing } from '@/components/score/score-ring'
import { VerdictBadge } from '@/components/score/verdict-badge'
import { Card, CardContent } from '@/components/ui/card'
import { Stat } from '@/components/ui/stat'

import type { RunDetail } from './api'

/** The headline: score, role, verdict, one-line summary and a few counts. */
export function SummaryCard({ run, strengths }: { run: RunDetail; strengths: number }) {
  const mustHaves = run.criteria.filter(
    (c) => c.operator === 'must_have' && c.outcome !== 'Unknown',
  )
  const met = mustHaves.filter((c) => c.outcome === 'Full Pass').length
  return (
    <Card>
      <CardContent className="flex flex-col gap-6 pt-6 sm:flex-row sm:items-center">
        <ScoreRing score={run.score} />
        <div className="min-w-0 flex-1 space-y-3">
          <div className="space-y-1">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Match score
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-semibold">{run.role_title}</h2>
              <VerdictBadge verdict={run.verdict} />
            </div>
            {run.role_overlap && (
              <p className="text-sm text-muted-foreground">{run.role_overlap.summary}</p>
            )}
          </div>
          <dl className="grid grid-cols-3 gap-4 border-t pt-3 sm:max-w-md">
            <Stat label="Must-haves" value={`${met} / ${mustHaves.length}`} />
            <Stat label="Strengths" value={strengths} />
            <Stat label="To verify" value={run.screening.length} />
          </dl>
        </div>
      </CardContent>
    </Card>
  )
}
