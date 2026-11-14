import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

import type { Point, RunDetail } from './api'
import { CriteriaTable } from './CriteriaTable'
import { ScreeningCard } from './ScreeningCard'

const VERDICT_TONE: Record<string, string> = {
  'Strong fit': 'bg-score-strong',
  'Possible fit': 'bg-score-medium',
  'Weak fit': 'bg-score-weak',
  'Not eligible': 'bg-destructive',
}

function scoreTone(score: number) {
  if (score >= 75) return 'text-score-strong'
  if (score >= 50) return 'text-score-medium'
  return 'text-score-weak'
}

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
              <li key={p.source} className="flex gap-2">
                <span aria-hidden className="text-muted-foreground">
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
  const score = Number(run.score ?? 0)
  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-wrap items-center gap-6 pt-6">
          <div className={cn('text-4xl font-semibold tabular-nums sm:text-5xl', scoreTone(score))}>
            {run.score}
            <span className="text-lg text-muted-foreground"> / 100</span>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-lg font-medium">{run.role_title}</span>
              {run.verdict && (
                <span
                  className={cn(
                    'rounded-full px-2 py-0.5 text-xs font-medium text-white',
                    VERDICT_TONE[run.verdict] ?? 'bg-muted-foreground',
                  )}
                >
                  {run.verdict}
                </span>
              )}
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
