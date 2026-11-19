import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
import { queryKeys } from '@/lib/api/query-keys'
import type { components } from '@/lib/api/schema'

export type SearchResult = components['schemas']['SearchResult']
export type SearchHit = components['schemas']['SearchHit']
export type CandidateBrief = components['schemas']['CandidateBrief']
export type CandidateUploadResult = components['schemas']['CandidateUploadResult']

export function useSearch(q: string) {
  return useQuery({
    queryKey: queryKeys.search(q),
    queryFn: () => apiFetch<SearchResult>(`/candidates/search?q=${encodeURIComponent(q)}&limit=50`),
    enabled: q.trim().length > 0,
    placeholderData: keepPreviousData,
  })
}

export function useCandidates() {
  return useQuery({
    queryKey: [...queryKeys.candidates, 'all'],
    queryFn: () => apiFetch<CandidateBrief[]>('/candidates?limit=200'),
  })
}

export function useUploadToDatabase() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (files: File[]) => {
      const body = new FormData()
      for (const file of files) body.append('resumes', file)
      return apiFetch<CandidateUploadResult>('/candidates', { method: 'POST', body })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.candidates }),
  })
}
