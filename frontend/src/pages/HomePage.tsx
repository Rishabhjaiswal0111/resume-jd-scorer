import { useEffect, useRef, useState } from 'react'

import { PageHeader } from '@/components/ui/page-header'
import { isManualPending, pendingStep, useScoreRun, type ScoreInput } from '@/features/scoring/api'
import { HowItWorks } from '@/features/scoring/HowItWorks'
import { RunResult } from '@/features/scoring/RunResult'
import { ScoreError } from '@/features/scoring/ScoreError'
import { ScoreForm } from '@/features/scoring/ScoreForm'
import { ScoringProgress } from '@/features/scoring/ScoringProgress'

export function HomePage() {
  const scoring = useScoreRun()
  const [lastInput, setLastInput] = useState<ScoreInput | null>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  // Bring the result into view when it arrives (it renders below the form).
  useEffect(() => {
    if (scoring.isSuccess)
      resultRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }, [scoring.isSuccess])

  function submit(input: ScoreInput) {
    setLastInput(input)
    scoring.mutate(input)
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Match a resume to a job"
        description="Add a job description and a resume. Get a score, the strengths and gaps behind it, and what to ask next."
      />
      <ScoreForm onSubmit={submit} pending={scoring.isPending} />
      {scoring.isIdle && <HowItWorks />}
      {scoring.isPending && (
        <ScoringProgress
          waitingFor={
            isManualPending(scoring.failureReason) ? pendingStep(scoring.failureReason) : undefined
          }
        />
      )}
      {scoring.isError && lastInput && (
        <ScoreError error={scoring.error} onRetry={() => scoring.mutate(lastInput)} />
      )}
      {scoring.isSuccess && (
        <div ref={resultRef} className="scroll-mt-20">
          <RunResult run={scoring.data} />
        </div>
      )}
    </div>
  )
}
