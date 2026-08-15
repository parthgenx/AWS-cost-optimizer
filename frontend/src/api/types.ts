export type FindingStatus =
  | 'open'
  | 'approved'
  | 'cleanup_in_progress'
  | 'cleaned'
  | 'dismissed'
  | 'resolved_externally'
  | 'cleanup_failed'

export type ResourceType =
  | 'ec2_instance'
  | 'ebs_volume'
  | 'elastic_ip'
  | 'ebs_snapshot'
  | 'rds_instance'
  | 'application_load_balancer'

export type FindingSeverity = 'low' | 'medium' | 'high' | 'critical'

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

export interface ResourceReference {
  resource_type: ResourceType
  resource_id: string
  region: string
  account_id: string
}

export interface FindingApproval {
  approved_by: string
  approved_at: string
}

export interface Finding {
  finding_id: string
  rule_id: string
  resource: ResourceReference
  summary: string
  recommended_action: string
  severity: FindingSeverity
  status: FindingStatus
  estimated_monthly_savings: Money | null
  evidence: Record<string, string>
  first_detected_at: string
  last_detected_at: string
  occurrence_count: number
  approval: FindingApproval | null
}

export interface FindingListResponse {
  items: Finding[]
  next_cursor: string | null
}

export interface FindingFilters {
  status: FindingStatus
  resourceType?: ResourceType
  severity?: FindingSeverity
  limit: number
  cursor?: string
}

export interface FindingApprovalResponse {
  finding_id: string
  status: 'approved'
  approved_by: string
  approved_at: string
}

export interface CleanupRequestResponse {
  finding_id: string
  event_id: string
  status: 'requested'
}
