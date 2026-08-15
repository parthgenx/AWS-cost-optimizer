import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, createApiClient } from './client'

describe('createApiClient', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends the Cognito access token to the dashboard API', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          open_findings: {
            finding_count: 0,
            findings_with_known_savings_count: 0,
            known_monthly_savings_by_currency: {},
          },
          recent_scans: [],
        }),
        { status: 200 },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const overview = await createApiClient({
      apiBaseUrl: 'https://api.example.com/',
      getAccessToken: () => 'access-token',
    }).getDashboardOverview()

    expect(overview.open_findings.finding_count).toBe(0)
    expect(fetchMock).toHaveBeenCalledWith('https://api.example.com/dashboard/overview', {
      headers: {
        Accept: 'application/json',
        Authorization: 'Bearer access-token',
      },
    })
  })

  it('does not issue an unauthenticated API request', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      createApiClient({
        apiBaseUrl: 'https://api.example.com',
        getAccessToken: () => undefined,
      }).getDashboardOverview(),
    ).rejects.toEqual(new ApiError(401, 'Your session is missing an access token. Please sign in again.'))

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
