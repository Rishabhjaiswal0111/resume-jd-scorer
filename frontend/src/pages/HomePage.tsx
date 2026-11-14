import { useState } from 'react'

import { useScoreRun, type ScoreInput } from '@/features/scoring/api'
import { RunResult } from '@/features/scoring/RunResult'
import { ScoreError } from '@/features/scoring/ScoreError'
import { ScoreForm } from '@/features/scoring/ScoreForm'

export function HomePage() {
  const scoring = useScoreRun()
  const [lastInput, setLastInput] = useState<ScoreInput | null>(null)

  function submit(input: ScoreInput) {
    setLastInput(input)
    scoring.mutate(input)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Score a resume against a JD</h1>
        <p className="text-muted-foreground">
          Upload a job description and a resume (PDF) to get a score, pros, cons and the run cost.
        </p>
      </div>
      <ScoreForm onSubmit={submit} pending={scoring.isPending} />
      {scoring.isError && lastInput && (
        <ScoreError error={scoring.error} onRetry={() => scoring.mutate(lastInput)} />
      )}
      {scoring.isSuccess && <RunResult run={scoring.data} />}
    </div>
  )
}
