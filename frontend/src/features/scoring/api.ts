import { useMutation, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/lib/api/client'
import { queryKeys } from '@/lib/api/query-keys'
import type { components } from '@/lib/api/schema'

export type RunDetail = components['schemas']['RunDetail']
export type CriterionView = components['schemas']['CriterionView']
export type Point = components['schemas']['Point']

export interface ScoreInput {
  /** A PDF file, or the job description pasted as text. */
  jd: File | string
  resume: File
}

export function scoreRun({ jd, resume }: ScoreInput): Promise<RunDetail> {
  const body = new FormData()
  if (typeof jd === 'string') body.append('jd_text', jd)
  else body.append('jd', jd)
  body.append('resume', resume)
  // No Content-Type header: the browser sets the multipart boundary itself.
  return apiFetch<RunDetail>('/score', { method: 'POST', body })
}

/** Manual LLM mode: the prompt is waiting for an answer file. Not a failure: keep retrying. */
export function isManualPending(error: unknown): error is ApiError {
  return error instanceof ApiError && error.code === 'LLM_RESPONSE_PENDING'
}

/** Which step a pending manual prompt belongs to, for the waiting message. */
export function pendingStep(error: ApiError): string {
  const purpose = (error.details as { purpose?: string } | undefined)?.purpose
  if (purpose === 'jd_parse') return 'Step 1 of 2: reading the job description'
  if (purpose === 'evaluate') return 'Step 2 of 2: grading the resume'
  return 'Fixing up the previous answer'
}

// The server already waits ~20 s per attempt for the answer file, so 45 retries ~ 15 min.
export const MANUAL_MAX_RETRIES = 45
const MANUAL_RETRY_DELAY_MS = 1500

export function useScoreRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: scoreRun,
    retry: (failureCount, error) => isManualPending(error) && failureCount < MANUAL_MAX_RETRIES,
    retryDelay: MANUAL_RETRY_DELAY_MS,
    // A new run changes History; refetch it next time it is shown.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.history }),
  })
}
