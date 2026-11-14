import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
import { queryKeys } from '@/lib/api/query-keys'
import type { components } from '@/lib/api/schema'

export type JdHistoryItem = components['schemas']['JdHistoryItem']
export type RunHistoryItem = components['schemas']['RunHistoryItem']
export type RunDetail = components['schemas']['RunDetail']

export function useJds() {
  return useQuery({
    queryKey: queryKeys.jds(),
    queryFn: () => apiFetch<JdHistoryItem[]>('/jds'),
  })
}

export function useJdRuns(jdDocumentId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.jdRuns(jdDocumentId),
    queryFn: () =>
      apiFetch<RunHistoryItem[]>(`/runs?jd_document_id=${encodeURIComponent(jdDocumentId)}`),
    enabled,
  })
}

export function useRun(runId: string) {
  return useQuery({
    queryKey: queryKeys.run(runId),
    queryFn: () => apiFetch<RunDetail>(`/runs/${encodeURIComponent(runId)}`),
  })
}
