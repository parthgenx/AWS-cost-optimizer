import type { FindingSeverity, FindingStatus } from '../../api/types'

import { humanize } from './presentation'

export function StatusBadge({ status }: { status: FindingStatus }) {
  return <span className={`status-badge status-finding-${status}`}>{humanize(status)}</span>
}

export function SeverityBadge({ severity }: { severity: FindingSeverity }) {
  return <span className={`severity-badge severity-${severity}`}>{humanize(severity)}</span>
}
