import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import run from '@/features/scoring/__fixtures__/run.json'

import { HistoryPage } from './HistoryPage'
import { RunPage } from './RunPage'

const JD = {
  jd_document_id: 'jd-1',
  title: 'Data Platform Engineer',
  source: 'text',
  filename: 'pasted.txt',
  run_count: 2,
  best_score: '89',
  last_scored_at: '2026-11-14T11:13:00Z',
}
const RUNS = [
  {
    id: 'run-2',
    jd_document_id: 'jd-1',
    resume_filename: 'cv_b.pdf',
    score: '89',
    verdict: 'Strong fit',
    created_at: '2026-11-14T11:13:00Z',
  },
  {
    id: 'run-1',
    jd_document_id: 'jd-1',
    resume_filename: 'cv_a.pdf',
    score: '42',
    verdict: 'Weak fit',
    created_at: '2026-11-14T10:00:00Z',
  },
]

function api(routes: Record<string, unknown>) {
  return vi.fn((url: string) => {
    const body = routes[url]
    if (body === undefined) return Promise.resolve(new Response('{}', { status: 404 }))
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
  })
}

function renderAt(path: string) {
  const router = createMemoryRouter(
    [
      { path: '/history', element: <HistoryPage /> },
      { path: '/runs/:runId', element: <RunPage /> },
      { path: '/', element: <p>score page</p> },
    ],
    { initialEntries: [path] },
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('History', () => {
  it('lists JDs and expands one to show its scored resumes', async () => {
    const fetchMock = api({
      '/api/v1/jds': [JD],
      '/api/v1/runs?jd_document_id=jd-1': RUNS,
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/history')

    const toggle = await screen.findByRole('button', { name: /Data Platform Engineer/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(within(toggle).getByText('Pasted text')).toBeInTheDocument()
    expect(within(toggle).getByText(/2 resumes · best 89/)).toBeInTheDocument()

    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    const list = await screen.findByRole('list', { name: 'Scored resumes' })
    const links = within(list).getAllByRole('link')
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['/runs/run-2', '/runs/run-1'])
    expect(within(links[1]!).getByText('Weak fit')).toBeInTheDocument()
    expect(within(links[1]!).getByRole('img', { name: 'Score 42 out of 100' })).toBeInTheDocument()
  })

  it('shows an empty state with a way to score', async () => {
    vi.stubGlobal('fetch', api({ '/api/v1/jds': [] }))
    renderAt('/history')
    expect(await screen.findByText('Nothing scored yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Score a resume' })).toHaveAttribute('href', '/')
  })

  it('opens a past run by its URL without showing admin data', async () => {
    vi.stubGlobal('fetch', api({ [`/api/v1/runs/${run.id}`]: run }))
    renderAt(`/runs/${run.id}`)
    expect(await screen.findByRole('img', { name: 'Score 89 out of 100' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Data Platform Engineer' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute('href', '/history')
    expect(screen.queryByText(/LLM cost|manual\/claude-session/)).toBeNull()
  })
})
