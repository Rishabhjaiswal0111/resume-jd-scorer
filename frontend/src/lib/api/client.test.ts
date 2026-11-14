import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from './client'

function mockFetch(response: Response | Error) {
  const fn =
    response instanceof Error
      ? vi.fn().mockRejectedValue(response)
      : vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('apiFetch', () => {
  it('prefixes the API base and returns parsed JSON', async () => {
    const fn = mockFetch(new Response(JSON.stringify({ status: 'ok' }), { status: 200 }))

    await expect(apiFetch('/healthz')).resolves.toEqual({ status: 'ok' })
    expect(fn).toHaveBeenCalledWith('/api/v1/healthz', expect.any(Object))
  })

  it('maps the backend error shape to ApiError with request id', async () => {
    mockFetch(
      new Response(
        JSON.stringify({
          error: { code: 'NOT_FOUND', message: 'Run not found', request_id: 'r-1' },
        }),
        { status: 404 },
      ),
    )

    const err = await apiFetch('/runs/x').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 404, code: 'NOT_FOUND', requestId: 'r-1' })
  })

  it('falls back to the response header request id for non-JSON errors', async () => {
    mockFetch(new Response('Bad gateway', { status: 502, headers: { 'x-request-id': 'hdr-9' } }))

    await expect(apiFetch('/healthz')).rejects.toMatchObject({
      code: 'HTTP_502',
      requestId: 'hdr-9',
    })
  })

  it('reports network failures as NETWORK_ERROR', async () => {
    mockFetch(new TypeError('Failed to fetch'))

    await expect(apiFetch('/healthz')).rejects.toMatchObject({ status: 0, code: 'NETWORK_ERROR' })
  })
})
