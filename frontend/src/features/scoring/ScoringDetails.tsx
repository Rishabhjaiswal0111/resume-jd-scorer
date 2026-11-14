import { ChevronDown } from 'lucide-react'

import { Card } from '@/components/ui/card'

import type { RunDetail } from './api'
import { CriteriaTable } from './CriteriaTable'

/** How the number was computed: per-criterion points, adjustments and run identifiers.
 *  Collapsed by default so the scorecard reads cleanly; open it to audit a score. */
export function ScoringDetails({ run }: { run: RunDetail }) {
  return (
    <Card className="overflow-hidden">
      <details className="group/details">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 p-4 text-sm font-medium sm:px-6 [&::-webkit-details-marker]:hidden">
          Scoring details
          <ChevronDown
            className="size-4 text-muted-foreground transition-transform group-open/details:rotate-180"
            aria-hidden
          />
        </summary>
        <div className="space-y-4 border-t p-4 sm:px-6">
          <p className="text-sm text-muted-foreground">
            The model grades each requirement; the score is computed from those grades with fixed
            weights.
            {run.group_adjustments.map((g) => (
              <span key={g.group} className="block">
                Overlap adjustment +{g.relief} points: {g.criteria.length} criteria test the same
                experience ({g.group.replaceAll('_', ' ')}), so only the biggest miss counts.
              </span>
            ))}
          </p>
          <CriteriaTable criteria={run.criteria} />
          <p className="text-xs text-muted-foreground">
            Run {run.id} · scoring engine {run.engine_version}
          </p>
        </div>
      </details>
    </Card>
  )
}
