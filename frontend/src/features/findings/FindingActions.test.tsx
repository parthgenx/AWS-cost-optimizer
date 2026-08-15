import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { ApiClient } from '../../api/client'
import type { Finding } from '../../api/types'

import { FindingActions } from './FindingActions'

const openEbsFinding: Finding = {
  finding_id: 'finding-1',
  rule_id: 'unattached_ebs_volume',
  resource: { resource_type: 'ebs_volume', resource_id: 'vol-123', region: 'ap-south-1', account_id: '123456789012' },
  summary: 'Unattached EBS volume',
  recommended_action: 'Review before cleanup.',
  severity: 'medium',
  status: 'open',
  estimated_monthly_savings: { amount: '8.40', currency: 'USD' },
  evidence: {},
  first_detected_at: '2026-08-15T12:00:00Z',
  last_detected_at: '2026-08-15T12:00:00Z',
  occurrence_count: 1,
  approval: null,
}

function renderActions({ finding = openEbsFinding, isOperator = true }: { finding?: Finding; isOperator?: boolean } = {}) {
  const apiClient: ApiClient = {
    getDashboardOverview: vi.fn(),
    listFindings: vi.fn(),
    getFinding: vi.fn(),
    approveFinding: vi.fn().mockResolvedValue({
      finding_id: finding.finding_id,
      status: 'approved',
      approved_by: 'operator-subject',
      approved_at: '2026-08-15T12:05:00Z',
    }),
    requestEbsCleanup: vi.fn(),
  }

  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <FindingActions apiClient={apiClient} finding={finding} isOperator={isOperator} />
    </QueryClientProvider>,
  )

  return apiClient
}

describe('FindingActions', () => {
  it('does not render state-changing controls for a non-operator session', () => {
    renderActions({ isOperator: false })

    expect(screen.getByText('Operator approval is required for state changes.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approve finding' })).not.toBeInTheDocument()
  })

  it('requires confirmation before calling the existing approval endpoint', async () => {
    const apiClient = renderActions()

    screen.getByRole('button', { name: 'Approve finding' }).click()
    expect(await screen.findByRole('dialog', { name: 'Approve this finding?' })).toBeInTheDocument()
    expect(apiClient.approveFinding).not.toHaveBeenCalled()

    screen.getByRole('button', { name: 'Confirm approval' }).click()

    expect(await screen.findByText(/Approval recorded/)).toBeInTheDocument()
    expect(apiClient.approveFinding).toHaveBeenCalledWith('finding-1')
  })
})
