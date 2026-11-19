import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/lib/api/client'
import { queryKeys } from '@/lib/api/query-keys'
import type { components } from '@/lib/api/schema'

export type User = components['schemas']['UserView']
export type DemoInfo = components['schemas']['DemoInfo']

/** The signed-in user; `null` when signed out (401), so callers can redirect. */
export function useMe() {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: async (): Promise<User | null> => {
      try {
        return await apiFetch<User>('/auth/me')
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null
        throw error
      }
    },
    staleTime: 5 * 60_000,
  })
}

/** Demo credentials (not offered in production). */
export function useDemoInfo() {
  return useQuery({
    queryKey: queryKeys.demo,
    queryFn: async (): Promise<DemoInfo | null> => {
      try {
        return await apiFetch<DemoInfo>('/auth/demo')
      } catch {
        return null
      }
    },
    staleTime: Infinity,
  })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      apiFetch<User>('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    onSuccess: (user) => {
      queryClient.clear() // nothing from a previous account survives
      queryClient.setQueryData(queryKeys.me, user)
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<null>('/auth/logout', { method: 'POST' }),
    onSettled: () => {
      queryClient.clear()
      queryClient.setQueryData(queryKeys.me, null)
    },
  })
}
