import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
import { uiConfig } from '@/config/ui'

export interface HealthResponse {
  status: 'ok'
  version: string
  env: string
}

export const healthKeys = {
  all: ['health'] as const,
}

export function useHealth() {
  return useQuery({
    queryKey: healthKeys.all,
    queryFn: () => apiFetch<HealthResponse>('/healthz'),
    refetchInterval: uiConfig.healthPollMs,
    retry: false,
  })
}
