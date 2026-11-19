import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from './providers'
import { router } from './router'

/** fetch stub answering by path; anything unlisted is a 404. */
function stubApi(routes: Record<string, { status?: number; body: unknown }>) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path =
        String(input)
          .replace(/^\/api\/v1/, '')
          .split('?')[0] ?? ''
      const hit = routes[path] ?? {
        status: 404,
        body: { error: { code: 'NOT_FOUND', message: 'x' } },
      }
      return new Response(JSON.stringify(hit.body), { status: hit.status ?? 200 })
    }),
  )
}

function renderAt(path: string) {
  const memory = createMemoryRouter(router.routes, { initialEntries: [path] })
  return render(
    <AppProviders>
      <RouterProvider router={memory} />
    </AppProviders>,
  )
}

const UNAUTHENTICATED = {
  status: 401,
  body: { error: { code: 'UNAUTHENTICATED', message: 'Sign in to continue' } },
}

afterEach(() => vi.unstubAllGlobals())

describe('app shell', () => {
  it('sends a signed-out visitor to sign-in and offers the demo account', async () => {
    stubApi({
      '/auth/me': UNAUTHENTICATED,
      '/auth/demo': { body: { email: 'demo@jdscorer.app', password: 'demo1234' } },
    })
    renderAt('/jobs')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /Use the demo account/ })).toBeInTheDocument()
  })

  it('shows a signed-in user their jobs as cards', async () => {
    stubApi({
      '/auth/me': { body: { id: 'u1', email: 'd@x.io', name: 'Demo Recruiter', is_demo: true } },
      '/health': { body: { status: 'ok', version: '0.1.0', env: 'dev' } },
      '/jobs': {
        body: [
          {
            id: 'j1',
            title: 'Backend Engineer',
            status: 'ready',
            source: 'pdf',
            filename: 'jd.pdf',
            counts: { total: 4, scored: 4, in_progress: 0, failed: 0, strong: 2 },
            best_score: '97',
            created_at: '2026-11-19T08:00:00Z',
          },
        ],
      },
    })
    renderAt('/')
    expect(await screen.findByRole('heading', { name: 'Jobs' })).toBeInTheDocument()
    const card = await screen.findByRole('link', { name: /Backend Engineer/ })
    expect(card).toHaveAttribute('href', '/jobs/j1')
    expect(card).toHaveTextContent('4 candidates')
    expect(card).toHaveTextContent('2 strong')
    expect(screen.getByText('Demo')).toBeInTheDocument()
  })
})
