import { ScoreRing } from '@/components/score/score-ring'
import { VerdictBadge } from '@/components/score/verdict-badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

import type { Point, RunDetail } from './api'
import { CriteriaTable } from './CriteriaTable'
import { ScreeningCard } from './ScreeningCard'

function PointList({ title, points, sign }: { title: string; points: Point[]; sign: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {points.length === 0 ? (
          <p className="text-sm text-muted-foreground">None</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {points.map((p) => (
              <li key={p.source} className="flex gap-2.5">
                <span aria-hidden className="font-medium text-muted-foreground">
                  {sign}
                </span>
                <span>{p.text}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

export function RunResult({ run }: { run: RunDetail }) {
  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-wrap items-center gap-5 pt-6 sm:gap-6">
          <ScoreRing score={run.score} />
          <div className="min-w-0 space-y-2">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Score out of 100
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-semibold">{run.role_title}</h2>
              <VerdictBadge verdict={run.verdict} />
            </div>
            <div className="text-sm text-muted-foreground">
              Role overlap: {run.role_overlap?.level} · Core requirement:{' '}
              {run.core_requirement?.level}
            </div>
          </div>
        </CardContent>
      </Card>

      {run.warnings.length > 0 && (
        <p className="text-sm text-score-medium">Warnings: {run.warnings.join('; ')}</p>
      )}

      <ScreeningCard items={run.screening} />

      <div className="grid gap-6 md:grid-cols-2">
        <PointList title="Pros" points={run.pros} sign="+" />
        <PointList title="Cons" points={run.cons} sign="−" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Criteria</CardTitle>
          <CardDescription>
            Each criterion is graded by the model; the score is computed from these grades.
            {run.group_adjustments.map((g) => (
              <span key={g.group} className="block">
                Overlap adjustment +{g.relief} points: {g.criteria.length} criteria test the same
                experience ({g.group.replaceAll('_', ' ')}), so only the biggest miss counts.
              </span>
            ))}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CriteriaTable criteria={run.criteria} />
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        Run {run.id} · engine {run.engine_version}
      </p>
    </div>
  )
}
