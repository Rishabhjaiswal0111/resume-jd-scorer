import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

import type { Point, RunDetail } from './api'
import { CriteriaTable } from './CriteriaTable'

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
  const providerCost = run.cost.provider_reported_usd
  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-wrap items-center gap-6 pt-6">
          <div className={cn('text-5xl font-semibold tabular-nums', scoreTone(score))}>
            {run.score}
            <span className="text-lg text-muted-foreground"> / 100</span>
          </div>
          <div className="space-y-1">
            <div className="text-lg font-medium">{run.role_title}</div>
            <div className="text-sm text-muted-foreground">
              Role overlap: {run.role_overlap?.level} · Core requirement:{' '}
              {run.core_requirement?.level}
            </div>
          </div>
          <dl className="ml-auto grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted-foreground">LLM cost</dt>
            <dd className="tabular-nums">${run.cost.run_llm_cost_usd}</dd>
            <dt className="text-muted-foreground">JD parse share</dt>
            <dd className="tabular-nums">${run.cost.rubric_cost_share_usd}</dd>
            <dt className="text-muted-foreground">Model</dt>
            <dd>{run.model}</dd>
            {providerCost !== null && (
              <>
                <dt className="text-muted-foreground">Provider-reported</dt>
                <dd className="tabular-nums">${providerCost}</dd>
              </>
            )}
          </dl>
        </CardContent>
      </Card>

      {run.warnings.length > 0 && (
        <p className="text-sm text-score-medium">Warnings: {run.warnings.join('; ')}</p>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <PointList title="Pros" points={run.pros} sign="+" />
        <PointList title="Cons" points={run.cons} sign="−" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Criteria</CardTitle>
          <CardDescription>
            Each criterion is graded by the model; the score is computed from these grades.
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
