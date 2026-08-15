import type { DashboardOverview } from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export interface ApiClient {
  getDashboardOverview(): Promise<DashboardOverview>
}

export function createApiClient(options: {
  apiBaseUrl: string
  getAccessToken: () => string | undefined
}): ApiClient {
  const baseUrl = options.apiBaseUrl.replace(/\/+$/, '')

  return {
    async getDashboardOverview(): Promise<DashboardOverview> {
      return request<DashboardOverview>({
        url: `${baseUrl}/dashboard/overview`,
        accessToken: options.getAccessToken(),
      })
    },
  }
}

async function request<T>({ url, accessToken }: { url: string; accessToken: string | undefined }): Promise<T> {
  if (!accessToken) {
    throw new ApiError(401, 'Your session is missing an access token. Please sign in again.')
  }

  const response = await fetch(url, {
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
  })

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response))
  }

  return (await response.json()) as T
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string' && body.detail) {
      return body.detail
    }
  } catch {
    // The API may return an empty or non-JSON error response; use a safe fallback.
  }

  if (response.status === 401) {
    return 'Your session is no longer authorized. Please sign in again.'
  }
  if (response.status === 403) {
    return 'You do not have permission to access this dashboard.'
  }
  return 'The dashboard could not load data from the API.'
}
