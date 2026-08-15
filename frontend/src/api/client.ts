import type {
  CleanupRequestResponse,
  DashboardOverview,
  Finding,
  FindingApprovalResponse,
  FindingFilters,
  FindingListResponse,
} from './types'

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
  listFindings(filters: FindingFilters): Promise<FindingListResponse>
  getFinding(findingId: string): Promise<Finding>
  approveFinding(findingId: string): Promise<FindingApprovalResponse>
  requestEbsCleanup(findingId: string): Promise<CleanupRequestResponse>
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
    async listFindings(filters: FindingFilters): Promise<FindingListResponse> {
      const parameters = new URLSearchParams({
        status: filters.status,
        limit: String(filters.limit),
      })
      if (filters.resourceType) {
        parameters.set('resource_type', filters.resourceType)
      }
      if (filters.severity) {
        parameters.set('severity', filters.severity)
      }
      if (filters.cursor) {
        parameters.set('cursor', filters.cursor)
      }

      return request<FindingListResponse>({
        url: `${baseUrl}/findings?${parameters.toString()}`,
        accessToken: options.getAccessToken(),
      })
    },
    async getFinding(findingId: string): Promise<Finding> {
      return request<Finding>({
        url: `${baseUrl}/findings/${encodeURIComponent(findingId)}`,
        accessToken: options.getAccessToken(),
      })
    },
    async approveFinding(findingId: string): Promise<FindingApprovalResponse> {
      return request<FindingApprovalResponse>({
        url: `${baseUrl}/findings/${encodeURIComponent(findingId)}/approval`,
        accessToken: options.getAccessToken(),
        method: 'POST',
      })
    },
    async requestEbsCleanup(findingId: string): Promise<CleanupRequestResponse> {
      return request<CleanupRequestResponse>({
        url: `${baseUrl}/findings/${encodeURIComponent(findingId)}/cleanup-requests`,
        accessToken: options.getAccessToken(),
        method: 'POST',
      })
    },
  }
}

async function request<T>({
  url,
  accessToken,
  method = 'GET',
}: {
  url: string
  accessToken: string | undefined
  method?: 'GET' | 'POST'
}): Promise<T> {
  if (!accessToken) {
    throw new ApiError(401, 'Your session is missing an access token. Please sign in again.')
  }

  const response = await fetch(url, {
    method,
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
