/**
 * Query keys shared across features, so one feature can refresh data another shows
 * (features never import each other).
 */
export const queryKeys = {
  me: ['auth', 'me'] as const,
  demo: ['auth', 'demo'] as const,
  jobs: ['jobs'] as const,
  job: (jobId: string) => [...queryKeys.jobs, jobId] as const,
  jobCandidates: (jobId: string) => [...queryKeys.jobs, jobId, 'candidates'] as const,
  jobCandidate: (jobId: string, jobCandidateId: string) =>
    [...queryKeys.jobs, jobId, 'candidates', jobCandidateId] as const,
  candidates: ['candidates'] as const,
  search: (q: string) => [...queryKeys.candidates, 'search', q] as const,
}
