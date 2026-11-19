import { Loader2 } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * Shown while a score is running. Describes the work honestly; no fake percentages.
 * `waitingFor` (manual LLM mode): the step whose prompt is waiting for an answer file.
 */
export function ScoringProgress({ waitingFor }: { waitingFor?: string }) {
  return (
    <Card aria-busy="true">
      <CardContent className="space-y-5 pt-6" role="status">
        <div className="flex items-start gap-3">
          <Loader2 className="mt-0.5 size-5 shrink-0 animate-spin text-primary" aria-hidden />
          <div>
            {waitingFor ? (
              <>
                <p className="font-medium">Waiting for the answer… ({waitingFor})</p>
                <p className="text-sm text-muted-foreground">
                  Manual mode: the prompt was saved for Claude Code to answer. This page keeps
                  checking and continues on its own; no need to click anything.
                </p>
              </>
            ) : (
              <>
                <p className="font-medium">Analysing the match…</p>
                <p className="text-sm text-muted-foreground">
                  Reading both documents, turning the job description into criteria and grading the
                  resume against each one. This usually takes under a minute.
                </p>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-5">
          <Skeleton className="size-24 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
