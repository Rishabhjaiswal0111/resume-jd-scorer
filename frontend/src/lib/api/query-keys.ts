/**
 * Query keys shared across features, so one feature can refresh data another shows
 * (features never import each other).
 */
export const queryKeys = {
  history: ['history'] as const,
  jds: () => [...queryKeys.history, 'jds'] as const,
  jdRuns: (jdDocumentId: string) => [...queryKeys.history, 'runs', jdDocumentId] as const,
  run: (runId: string) => ['run', runId] as const,
}
