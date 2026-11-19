import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { useState, type ReactNode } from 'react'

import { uiConfig } from '@/config/ui'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/api/query-keys'

function makeQueryClient() {
  // Any 401 means the session ended (expired or signed out elsewhere): re-check "me",
  // and the auth guard sends the user to the sign-in page.
  const onError = (error: unknown) => {
    if (error instanceof ApiError && error.status === 401 && error.code === 'UNAUTHENTICATED')
      void client.invalidateQueries({ queryKey: queryKeys.me })
  }
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        // Don't retry client errors (4xx); retry network / 5xx up to twice.
        retry: (failureCount, error) =>
          !(error instanceof ApiError && error.status >= 400 && error.status < 500) &&
          failureCount < 2,
      },
    },
  })
  return client
}

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(makeQueryClient)
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {uiConfig.showQueryDevtools && <ReactQueryDevtools buttonPosition="bottom-left" />}
    </QueryClientProvider>
  )
}
