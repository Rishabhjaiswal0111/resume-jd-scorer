import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
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
  it('shows ok with version when the API responds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: 'ok', version: '0.1.0', env: 'dev' }), {
          status: 200,
        }),
      ),
    )
    renderWithQuery()
    // The version sits in its own span (hidden on phones), so check the badge's full text.
    await screen.findByText(/API: ok/)
    expect(screen.getByRole('status')).toHaveTextContent('API: ok · v0.1.0')
  })

  it('shows unreachable when the API is down', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    renderWithQuery()
    expect(await screen.findByText(/API: unreachable/)).toBeInTheDocument()
  })
})
