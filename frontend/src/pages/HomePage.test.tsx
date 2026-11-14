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

    expect(await screen.findByText('90.88')).toBeInTheDocument()
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

    expect(await screen.findByText('90.88')).toBeInTheDocument()
    expect(screen.getAllByText('Senior Backend Engineer (Python)').length).toBeGreaterThan(0)

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/v1/score')
    expect(init.method).toBe('POST')
    const body = init.body as FormData
    expect((body.get('jd') as File).name).toBe('jd.pdf')
    expect((body.get('resume') as File).name).toBe('cv.pdf')

    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(run.criteria.length + 1)
    expect(within(table).getByText('Works in EU time zones')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Pros' })).toBeInTheDocument()
    // Shown in Cons and in the criteria table's reasoning column.
    expect(screen.getAllByText(/No open-source contributions mentioned/)).toHaveLength(2)
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
    expect(await screen.findByText('90.88')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
