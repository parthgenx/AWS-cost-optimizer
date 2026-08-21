import { useQuery } from '@tanstack/react-query'
import {
  CircleCheckBig,
  Clock3,
  DollarSign,
  RefreshCw,
  ScanSearch,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { ApiError, createApiClient } from '../../api/client'
import type { DashboardOverview, ScanRun } from '../../api/types'
import { ConsolePageHeader } from '../../components/ConsolePageHeader'
import { OperationalStatePanel } from '../../components/OperationalStatePanel'
import { getDashboardConfiguration } from '../../config'

export function OverviewPage({ accessToken }: { accessToken: string | undefined }) {
  const configuration = getDashboardConfiguration()
  if (!configuration) {
    throw new Error('Dashboard configuration must exist before rendering the overview.')
  }

  const overviewQuery = useQuery({
    queryKey: ['dashboard-overview'],
    queryFn: () =>
      createApiClient({
        apiBaseUrl: configuration.apiBaseUrl,
        getAccessToken: () => accessToken,
      }).getDashboardOverview(),
    retry: (failureCount, error) => !(error instanceof ApiError && error.status < 500) && failureCount < 2,
  })

  return (
    <OverviewContent
      data={overviewQuery.data}
      error={overviewQuery.error}
      isLoading={overviewQuery.isLoading}
      onRetry={() => void overviewQuery.refetch()}
    />
  )
}

export interface OverviewContentProps {
  data: DashboardOverview | undefined
  error: Error | null
  isLoading: boolean
  onRetry: () => void
}

export function OverviewContent({ data, error, isLoading, onRetry }: OverviewContentProps) {
  if (isLoading) {
    return <OverviewLoading />
  }

  if (error) {
    return <OverviewError error={error} onRetry={onRetry} />
  }

  if (!data) {
    return <OverviewError error={new Error('The API did not return dashboard data.')} onRetry={onRetry} />
  }

  const openFindingCount = data.open_findings.finding_count
  const knownSavings = formatKnownSavings(data)
  const latestScan = data.recent_scans[0]

  return (
    <section className="overview-page">
      <ConsolePageHeader
        action={<button className="secondary-button" type="button" onClick={onRetry}>
          <RefreshCw aria-hidden="true" size={16} />
          Refresh data
        </button>}
        eyebrow="Cost operations"
        summary="Evidence-backed findings from scanners running in this AWS account."
        title="Overview"
      />

      <section aria-label="Overview metrics" className="metric-grid">
        <MetricCard
          detail="Current lifecycle status: open"
          icon={<TriangleAlert aria-hidden="true" size={19} />}
          label="Open findings"
          tone="warning"
          value={String(openFindingCount)}
        />
        <MetricCard
          detail={`${data.open_findings.findings_with_known_savings_count} finding(s) with estimates`}
          icon={<DollarSign aria-hidden="true" size={19} />}
          label="Known potential savings"
          tone="positive"
          value={knownSavings}
        />
        <MetricCard
          detail={latestScan ? formatScannerName(latestScan.scanner_name) : 'Waiting for first scan'}
          icon={<ScanSearch aria-hidden="true" size={19} />}
          label="Latest scanner state"
          tone={latestScan?.status === 'failed' ? 'danger' : 'neutral'}
          value={latestScan ? humanizeStatus(latestScan.status) : 'No scans yet'}
        />
        <MetricCard
          detail="Approval and revalidation required"
          icon={<ShieldCheck aria-hidden="true" size={19} />}
          label="EBS cleanup safety"
          tone="neutral"
          value="Guarded"
        />
      </section>

      <div className="overview-workspace">
        <section className="overview-panel overview-panel-activity">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Scan activity</p>
              <h2>Recent scanner runs</h2>
            </div>
            <span className="read-only-label">Read-only</span>
          </div>
          {data.recent_scans.length === 0 ? <EmptyScans /> : <div className="scan-list">
            {data.recent_scans.map((scan) => <ScanRow key={scan.scan_id} scan={scan} />)}
          </div>}
        </section>

        <aside className="overview-panel overview-panel-queue">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Review queue</p>
              <h2>Prioritized findings</h2>
            </div>
            <TriangleAlert aria-hidden="true" className="panel-heading-icon" size={18} />
          </div>
          {openFindingCount === 0 ? <EmptyFindings /> : (
            <div className="review-queue-summary">
              <strong>{openFindingCount}</strong>
              <p>open finding(s) are awaiting evidence review before any operator action.</p>
              <Link className="primary-button" to="/findings">Open review queue</Link>
            </div>
          )}
          <div className="overview-safety-context">
            <ShieldCheck aria-hidden="true" size={16} />
            <span>EBS cleanup remains approval-gated and revalidated by a separate worker.</span>
          </div>
        </aside>
      </div>
    </section>
  )
}

function MetricCard({
  detail,
  icon,
  label,
  tone,
  value,
}: {
  detail: string
  icon: React.ReactNode
  label: string
  tone: 'danger' | 'neutral' | 'positive' | 'warning'
  value: string
}) {
  return (
    <article className={`metric-card metric-card-${tone}`}>
      <div className="metric-icon">{icon}</div>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  )
}

function ScanRow({ scan }: { scan: ScanRun }) {
  const statusClass = `status-badge status-${scan.status}`
  const outcome =
    scan.status === 'completed'
      ? `${scan.evaluated_resource_count ?? 0} resources evaluated · ${scan.finding_count ?? 0} findings`
      : scan.status === 'failed'
        ? 'Scanner failed safely; review operational alerts.'
        : 'Scanner execution is in progress.'

  return (
    <article className="scan-row">
      <div className="scan-row-icon" aria-hidden="true">
        {scan.status === 'completed' ? <CircleCheckBig size={18} /> : <Clock3 size={18} />}
      </div>
      <div className="scan-row-copy">
        <strong>{formatScannerName(scan.scanner_name)}</strong>
        <span>{outcome}</span>
      </div>
      <time dateTime={scan.started_at}>{formatDateTime(scan.started_at)}</time>
      <span className={statusClass}>{humanizeStatus(scan.status)}</span>
    </article>
  )
}

function EmptyFindings() {
  return (
    <OperationalStatePanel title="No open findings" tone="empty">
      <p>The current scan data has no active cost-review items.</p>
    </OperationalStatePanel>
  )
}

function EmptyScans() {
  return (
    <OperationalStatePanel title="No scan activity has been recorded yet." tone="info">
      <p>Enable the EventBridge schedule or run a scanner manually after deployment.</p>
    </OperationalStatePanel>
  )
}

function OverviewError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const unauthorized = error instanceof ApiError && [401, 403].includes(error.status)

  return (
    <section className="overview-page overview-state-page">
      <OperationalStatePanel
        action={<button className="secondary-button" type="button" onClick={onRetry}>Try again</button>}
        title={unauthorized ? 'Your session cannot access the API.' : 'We could not load the overview.'}
        tone="error"
      >
        <p>{error.message}</p>
      </OperationalStatePanel>
    </section>
  )
}

function OverviewLoading() {
  return (
    <section aria-label="Loading dashboard" className="overview-page" aria-busy="true">
      <div className="skeleton-block skeleton-heading" />
      <div className="metric-grid">
        {[0, 1, 2, 3].map((index) => (
          <div className="skeleton-block skeleton-metric" key={index} />
        ))}
      </div>
      <div className="skeleton-block skeleton-activity" />
    </section>
  )
}

function formatKnownSavings(overview: DashboardOverview): string {
  const estimates = Object.values(overview.open_findings.known_monthly_savings_by_currency)
  if (estimates.length === 0) {
    return 'Not available'
  }

  return estimates
    .map((estimate) =>
      new Intl.NumberFormat(undefined, {
        style: 'currency',
        currency: estimate.currency,
        maximumFractionDigits: 2,
      }).format(Number(estimate.amount)),
    )
    .join(' + ')
}

function formatScannerName(scannerName: string): string {
  return scannerName
    .split('-')
    .map((part) => `${part[0]?.toUpperCase() ?? ''}${part.slice(1)}`)
    .join(' ')
}

function humanizeStatus(status: string): string {
  return `${status[0]?.toUpperCase() ?? ''}${status.slice(1).replaceAll('_', ' ')}`
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}
