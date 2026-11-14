/**
 * The ONLY place that calls fetch (enforced by ESLint).
 *
 * - Prefixes every path with /api/v1 (Vite proxies /api to the backend in dev).
 * - Turns the backend error shape {error: {code, message, request_id}} into ApiError,
 *   so every error shown in the UI carries a request id you can grep in backend logs.
 */

export const API_BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string | null
  readonly details: unknown

  constructor(opts: {
    status: number
    code: string
    message: string
    requestId: string | null
    details?: unknown
  }) {
    super(opts.message)
    this.name = 'ApiError'
    this.status = opts.status
    this.code = opts.code
    this.requestId = opts.requestId
    this.details = opts.details
  }
}

interface BackendErrorBody {
  error?: { code?: string; message?: string; request_id?: string | null; details?: unknown }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...init.headers },
    })
  } catch (cause) {
    throw new ApiError({
      status: 0,
      code: 'NETWORK_ERROR',
      message: 'Cannot reach the API. Is the backend running (make dev-api)?',
      requestId: null,
      details: cause,
    })
  }

  const requestId = res.headers.get('x-request-id')
  const body: unknown = await res.json().catch(() => null)

  if (!res.ok) {
    const err = (body as BackendErrorBody | null)?.error
    throw new ApiError({
      status: res.status,
      code: err?.code ?? `HTTP_${res.status}`,
      message: err?.message || res.statusText || 'Request failed',
      requestId: err?.request_id ?? requestId,
      details: err?.details,
    })
  }
  return body as T
}
