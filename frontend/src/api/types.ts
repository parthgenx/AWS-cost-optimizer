export type FindingStatus =
  | 'open'
  | 'approved'
  | 'cleanup_in_progress'
  | 'cleaned'
  | 'dismissed'
  | 'resolved_externally'
  | 'cleanup_failed'

export type ScanRunStatus = 'running' | 'completed' | 'failed'

export interface Money {
  amount: string
  currency: string
}

export interface FindingSummary {
  finding_count: number
  findings_with_known_savings_count: number
  known_monthly_savings_by_currency: Record<string, Money>
}

export interface ScanRun {
  scan_id: string
  scanner_name: string
  started_at: string
  completed_at: string | null
  status: ScanRunStatus
  evaluated_resource_count: number | null
  finding_count: number | null
  failure_type: string | null
}

export interface DashboardOverview {
  open_findings: FindingSummary
  recent_scans: ScanRun[]
}
