import { describe, expect, it } from 'vitest'

import type { Finding } from '../../api/types'

import { cleanupAvailability, formatEvidenceKey } from './presentation'

const ebsFinding: Finding = {
  finding_id: 'finding-1',
  rule_id: 'unattached_ebs_volume',
  resource: { resource_type: 'ebs_volume', resource_id: 'vol-123', region: 'ap-south-1', account_id: '123456789012' },
  summary: 'Unattached EBS volume',
  recommended_action: 'Review before cleanup.',
  severity: 'medium',
  status: 'approved',
  estimated_monthly_savings: { amount: '8.40', currency: 'USD' },
  evidence: {},
  first_detected_at: '2026-08-15T12:00:00Z',
  last_detected_at: '2026-08-15T12:00:00Z',
  occurrence_count: 1,
  approval: null,
}

describe('finding presentation safety', () => {
  it('offers a cleanup-request affordance only for approved EBS findings', () => {
    expect(cleanupAvailability(ebsFinding)).toBeNull()
    expect(cleanupAvailability({ ...ebsFinding, status: 'open' })).toMatch(/approved/)
    expect(cleanupAvailability({ ...ebsFinding, resource: { ...ebsFinding.resource, resource_type: 'rds_instance' } })).toMatch(/EBS/)
  })

  it('formats persisted evidence keys without changing their values', () => {
    expect(formatEvidenceKey('average_cpu_utilization_percent')).toBe('Average cpu utilization percent')
  })
})
