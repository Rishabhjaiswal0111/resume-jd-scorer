import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HealthBadge } from './HealthBadge'

function renderWithQuery() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <HealthBadge />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('HealthBadge', () => {
  it('stays visually silent (screen-reader text only) when the API responds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: 'ok', version: '0.1.0', env: 'dev' }), {
          status: 200,
        }),
      ),
    )
    renderWithQuery()
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('Service available, version 0.1.0'),
    )
    expect(screen.getByRole('status')).toHaveClass('sr-only')
  })

  it('shows a visible notice when the API is down', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    renderWithQuery()
    expect(await screen.findByText('Service unreachable')).toBeVisible()
  })
})
