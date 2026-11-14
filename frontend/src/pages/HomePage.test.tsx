import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import run from '@/features/scoring/__fixtures__/run.json'

import { HomePage } from './HomePage'

function renderPage() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <HomePage />
    </QueryClientProvider>,
  )
}

function pdf(name: string) {
  return new File(['%PDF-1.4'], name, { type: 'application/pdf' })
}

function chooseFiles() {
  fireEvent.change(screen.getByLabelText('Job description PDF'), {
    target: { files: [pdf('jd.pdf')] },
  })
  fireEvent.change(screen.getByLabelText('Resume (PDF)'), {
    target: { files: [pdf('cv.pdf')] },
  })
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'x-request-id': 'req-1' } })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('HomePage scoring flow', () => {
  it('explains a group adjustment under the criteria table', async () => {
    const withGroup = {
      ...run,
      group_adjustments: [
        { group: 'ecommerce_payments', criteria: ['c_a', 'c_b', 'c_c'], relief: '11.5' },
      ],
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(withGroup)))
    renderPage()
    chooseFiles()
    fireEvent.click(screen.getByRole('button', { name: 'Score' }))
    expect(
      await screen.findByText(
        /Overlap adjustment \+11\.5 points: 3 criteria test the same experience \(ecommerce payments\)/,
      ),
    ).toBeInTheDocument()
  })

  it('sends pasted JD text as jd_text once it is long enough', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(run))
    vi.stubGlobal('fetch', fetchMock)
    renderPage()
    fireEvent.click(screen.getByRole('radio', { name: 'Paste text' }))
    fireEvent.change(screen.getByLabelText('Resume (PDF)'), {
      target: { files: [pdf('cv.pdf')] },
    })
    const textarea = screen.getByLabelText('Job description text')
    const button = screen.getByRole('button', { name: 'Score' })

    fireEvent.change(textarea, { target: { value: 'Python developer' } })
    expect(button).toBeDisabled()
    expect(screen.getByText(/16 \/ 200 characters minimum/)).toBeInTheDocument()

    const jdText = 'Senior Backend Engineer. '.repeat(10)
    fireEvent.change(textarea, { target: { value: jdText } })
    fireEvent.click(button)

    expect(await screen.findByText('89')).toBeInTheDocument()
    const body = (fetchMock.mock.calls[0] as [string, RequestInit])[1].body as FormData
    expect(body.get('jd_text')).toBe(jdText)
    expect(body.get('jd')).toBeNull()
  })

  it('keeps Score disabled until both PDFs are chosen', () => {
    renderPage()
    const button = screen.getByRole('button', { name: 'Score' })
    expect(button).toBeDisabled()
    chooseFiles()
    expect(button).toBeEnabled()
  })

  it('uploads both files and shows score, pros, cons and criteria', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(run))
    vi.stubGlobal('fetch', fetchMock)
    renderPage()
    chooseFiles()
    fireEvent.click(screen.getByRole('button', { name: 'Score' }))

    expect(await screen.findByText('89')).toBeInTheDocument()
    expect(screen.getAllByText('Data Platform Engineer').length).toBeGreaterThan(0)

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/v1/score')
    expect(init.method).toBe('POST')
    const body = init.body as FormData
    expect((body.get('jd') as File).name).toBe('jd.pdf')
    expect((body.get('resume') as File).name).toBe('cv.pdf')

    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(run.criteria.length + 1)
    expect(within(table).getByText('Hands-on Kafka in production')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Pros' })).toBeInTheDocument()
    // Shown in Cons, in the phone cards and in the desktop table (CSS picks which one).
    expect(screen.getAllByText(/Neither dbt nor Airflow is mentioned/)).toHaveLength(3)
    const cards = screen.getByRole('list', { name: 'Criteria' })
    expect(within(cards).getAllByRole('listitem')).toHaveLength(run.criteria.length)
    expect(within(cards).getByText(/Neither dbt nor Airflow is mentioned/)).toBeInTheDocument()
    // Engine 1.1.0: verdict badge and screening questions (silent resume -> ask, not fail).
    expect(screen.getByText('Strong fit')).toBeInTheDocument()
    // Cost and model are admin data: not shown on the scoring page.
    expect(screen.queryByText(/LLM cost|JD parse share|manual\/claude-session/)).toBeNull()
    const screening = screen
      .getByRole('heading', { name: 'Ask in screening' })
      .closest('div')!.parentElement!
    expect(within(screening).getByText('Works from Berlin 2+ days a week')).toBeInTheDocument()
    expect(within(table).getAllByText('Ask in screening')).toHaveLength(2)
    expect(within(table).getByText(/knock-out/)).toBeInTheDocument()
  })

  it('explains manual-mode pending and retries the same files', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        json(
          {
            error: {
              code: 'LLM_RESPONSE_PENDING',
              message: 'Waiting for an answer',
              request_id: 'req-1',
            },
          },
          503,
        ),
      )
      .mockResolvedValueOnce(json(run))
    vi.stubGlobal('fetch', fetchMock)
    renderPage()
    chooseFiles()
    fireEvent.click(screen.getByRole('button', { name: 'Score' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/Manual mode/)
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('89')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
