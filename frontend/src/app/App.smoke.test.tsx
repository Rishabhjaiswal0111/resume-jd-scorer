import { render, screen } from '@testing-library/react'
import { RouterProvider } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from './providers'
import { router } from './router'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('app shell', () => {
  it('renders the layout and score page like main.tsx does', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ status: 'ok', version: '0.1.0', env: 'dev' })),
        ),
    )
    render(
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>,
    )
    expect(
      await screen.findByRole('heading', { name: 'Match a resume to a job' }),
    ).toBeInTheDocument()
    expect(await screen.findByText(/Service available/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('button', { name: 'Score' })).toBeDisabled()
  })
})
