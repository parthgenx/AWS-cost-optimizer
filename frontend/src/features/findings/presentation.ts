import type { Finding, FindingSeverity, FindingStatus, ResourceType } from '../../api/types'

export const findingStatuses: readonly FindingStatus[] = [
  'open',
  'approved',
  'cleanup_in_progress',
  'cleaned',
  'dismissed',
  'resolved_externally',
  'cleanup_failed',
]

export const resourceTypes: readonly ResourceType[] = [
  'ec2_instance',
  'ebs_volume',
  'elastic_ip',
  'ebs_snapshot',
  'rds_instance',
  'application_load_balancer',
]

export const findingSeverities: readonly FindingSeverity[] = ['low', 'medium', 'high', 'critical']

export function humanize(value: string): string {
  return value
    .split('_')
    .map((part) => `${part[0]?.toUpperCase() ?? ''}${part.slice(1)}`)
    .join(' ')
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function formatCurrency(finding: Finding): string {
  const estimate = finding.estimated_monthly_savings
  if (!estimate) {
    return 'Estimate unavailable'
  }

  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: estimate.currency,
    maximumFractionDigits: 2,
  }).format(Number(estimate.amount))
}

export function formatEvidenceKey(key: string): string {
  return key
    .replaceAll(/([a-z])([A-Z])/g, '$1 $2')
    .replaceAll(/[_-]/g, ' ')
    .replaceAll(/\s+/g, ' ')
    .replace(/^./, (character) => character.toUpperCase())
}

export function cleanupAvailability(finding: Finding): string | null {
  if (finding.resource.resource_type !== 'ebs_volume') {
    return 'Cleanup requests are available only for unattached EBS volume findings.'
  }
  if (finding.status !== 'approved') {
    return 'An EBS finding must be approved before a cleanup request can be submitted.'
  }
  return null
}
