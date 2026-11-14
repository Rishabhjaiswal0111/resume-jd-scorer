import { useState } from 'react'

import { PageHeader } from '@/components/ui/page-header'

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
      <PageHeader
        title="Score a resume against a JD"
        description="Add a job description (PDF or pasted text) and a resume PDF to get a score, pros and cons."
      />
      <ScoreForm onSubmit={submit} pending={scoring.isPending} />
      {scoring.isError && lastInput && (
        <ScoreError error={scoring.error} onRetry={() => scoring.mutate(lastInput)} />
      )}
      {scoring.isSuccess && <RunResult run={scoring.data} />}
    </div>
  )
}
