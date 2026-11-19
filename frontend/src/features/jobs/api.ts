import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch, API_BASE } from '@/lib/api/client'
import { queryKeys } from '@/lib/api/query-keys'
import type { components } from '@/lib/api/schema'

export type JobSummary = components['schemas']['JobSummary']
export type JobDetail = components['schemas']['JobDetail']
export type JobRequirement = components['schemas']['JobRequirement']
export type JobCandidateItem = components['schemas']['JobCandidateItem']
export type JobCandidateDetail = components['schemas']['JobCandidateDetail']
export type AddCandidatesResult = components['schemas']['AddCandidatesResult']
export type UploadError = components['schemas']['UploadError']

/** Poll while the server is still working on something shown on the page. */
const POLL_MS = 2500

export const jobDocumentUrl = (jobId: string) => `${API_BASE}/jobs/${jobId}/document`
export const resumeUrl = (candidateId: string) => `${API_BASE}/candidates/${candidateId}/resume`

export const isJobBusy = (job: Pick<JobSummary, 'status'>) =>
  job.status === 'pending' || job.status === 'parsing'
export const isCandidateBusy = (c: Pick<JobCandidateItem, 'status'>) =>
  c.status === 'queued' || c.status === 'scoring'

export function useJobs() {
  return useQuery({
    queryKey: queryKeys.jobs,
    queryFn: () => apiFetch<JobSummary[]>('/jobs'),
    refetchInterval: (query) =>
      query.state.data?.some((j) => isJobBusy(j) || j.counts.in_progress > 0) ? POLL_MS : false,
  })
}

export function useJob(jobId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.job(jobId),
    queryFn: () => apiFetch<JobDetail>(`/jobs/${jobId}`),
    enabled: enabled && Boolean(jobId),
    refetchInterval: (query) =>
      query.state.data && (isJobBusy(query.state.data) || query.state.data.counts.in_progress > 0)
        ? POLL_MS
        : false,
  })
}

export function useJobCandidates(jobId: string) {
  return useQuery({
    queryKey: queryKeys.jobCandidates(jobId),
    queryFn: () => apiFetch<JobCandidateItem[]>(`/jobs/${jobId}/candidates`),
    refetchInterval: (query) => (query.state.data?.some(isCandidateBusy) ? POLL_MS : false),
  })
}

export function useJobCandidate(jobId: string, jobCandidateId: string) {
  return useQuery({
    queryKey: queryKeys.jobCandidate(jobId, jobCandidateId),
    queryFn: () => apiFetch<JobCandidateDetail>(`/jobs/${jobId}/candidates/${jobCandidateId}`),
    refetchInterval: (query) =>
      query.state.data && isCandidateBusy(query.state.data) ? POLL_MS : false,
  })
}

export function useCreateJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (jd: File | string) => {
      const body = new FormData()
      if (typeof jd === 'string') body.append('jd_text', jd)
      else body.append('jd', jd)
      return apiFetch<JobDetail>('/jobs', { method: 'POST', body })
    },
    onSuccess: (job) => {
      queryClient.setQueryData(queryKeys.job(job.id), job)
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs, exact: true })
    },
  })
}

/** After anything that changes a job's candidates: refresh the job, its list and the cards. */
function useRefreshJobs() {
  const queryClient = useQueryClient()
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs }),
      queryClient.invalidateQueries({ queryKey: queryKeys.candidates }),
    ])
}

export function useUploadResumes(jobId: string) {
  const refresh = useRefreshJobs()
  return useMutation({
    mutationFn: (files: File[]) => {
      const body = new FormData()
      for (const file of files) body.append('resumes', file)
      return apiFetch<AddCandidatesResult>(`/jobs/${jobId}/candidates`, { method: 'POST', body })
    },
    onSuccess: refresh,
  })
}

export function useAddExisting() {
  const refresh = useRefreshJobs()
  return useMutation({
    mutationFn: ({ jobId, candidateIds }: { jobId: string; candidateIds: string[] }) =>
      apiFetch<JobCandidateItem[]>(`/jobs/${jobId}/candidates/existing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ candidate_ids: candidateIds }),
      }),
    onSuccess: refresh,
  })
}

export function useRetryCandidate(jobId: string) {
  const refresh = useRefreshJobs()
  return useMutation({
    mutationFn: (jobCandidateId: string) =>
      apiFetch<null>(`/jobs/${jobId}/candidates/${jobCandidateId}/retry`, { method: 'POST' }),
    onSuccess: refresh,
  })
}

export function useRemoveCandidate(jobId: string) {
  const refresh = useRefreshJobs()
  return useMutation({
    mutationFn: (jobCandidateId: string) =>
      apiFetch<null>(`/jobs/${jobId}/candidates/${jobCandidateId}`, { method: 'DELETE' }),
    onSuccess: refresh,
  })
}

export function useRetryJob(jobId: string) {
  const refresh = useRefreshJobs()
  return useMutation({
    mutationFn: () => apiFetch<JobDetail>(`/jobs/${jobId}/retry`, { method: 'POST' }),
    onSuccess: refresh,
  })
}

export function useDeleteJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) => apiFetch<null>(`/jobs/${jobId}`, { method: 'DELETE' }),
    // Only the list: removing the job's own query while its page is still mounted makes
    // that page refetch the deleted job (a 404). The page navigates away; the cache
    // entry is garbage-collected once unused.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.jobs, exact: true }),
  })
}
