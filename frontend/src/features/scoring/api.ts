import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
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

export function useScoreRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: scoreRun,
    // A new run changes History; refetch it next time it is shown.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.history }),
  })
}
