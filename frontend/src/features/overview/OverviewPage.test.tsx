import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { DashboardOverview } from '../../api/types'
import { OverviewContent } from './OverviewPage'

describe('OverviewContent', () => {
  it('shows a loading state while the API request is pending', () => {
    render(<OverviewContent data={undefined} error={null} isLoading onRetry={vi.fn()} />)

    expect(screen.getByLabelText('Loading dashboard')).toBeInTheDocument()
  })

  it('shows a reassuring empty state when no open findings exist', () => {
    render(<OverviewContent data={emptyOverview} error={null} isLoading={false} onRetry={vi.fn()} />)

    expect(screen.getByText('No open findings')).toBeInTheDocument()
    expect(screen.getByText('No scan activity has been recorded yet.')).toBeInTheDocument()
  })

  it('shows a useful API error with a retry action', () => {
    const onRetry = vi.fn()
    render(
      <OverviewContent
        data={undefined}
        error={new Error('The API is temporarily unavailable.')}
        isLoading={false}
        onRetry={onRetry}
      />,
    )

    expect(screen.getByText('We could not load the overview.')).toBeInTheDocument()
    screen.getByRole('button', { name: 'Try again' }).click()
    expect(onRetry).toHaveBeenCalledOnce()
  })
})

const emptyOverview: DashboardOverview = {
  open_findings: {
    finding_count: 0,
    findings_with_known_savings_count: 0,
    known_monthly_savings_by_currency: {},
  },
  recent_scans: [],
}
