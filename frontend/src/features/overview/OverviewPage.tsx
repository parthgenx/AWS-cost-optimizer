import { useQuery } from '@tanstack/react-query'
import {
  ArrowUpRight,
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
      <div className="page-heading">
        <div>
          <p className="eyebrow">Cost operations overview</p>
          <h1>Focus attention where cloud spend can be reduced safely.</h1>
          <p className="page-subtitle">
            Findings are evidence-backed recommendations from scanners running in this AWS account.
          </p>
        </div>
        <button className="secondary-button" type="button" onClick={onRetry}>
          <RefreshCw aria-hidden="true" size={16} />
          Refresh data
        </button>
      </div>

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

      {openFindingCount === 0 ? (
        <EmptyFindings />
      ) : (
        <section className="overview-insight" aria-label="Finding overview">
          <div className="insight-icon" aria-hidden="true">
            <ScanSearch size={20} />
          </div>
          <div>
            <p className="eyebrow">Review queue ready</p>
            <h2>{openFindingCount} finding(s) need human review.</h2>
            <p>
              Review evidence, lifecycle status, and scanner context before deciding whether an
              operator should take action.
            </p>
          </div>
          <Link className="secondary-button" to="/findings">Review findings</Link>
        </section>
      )}

      <section className="activity-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Scanner activity</p>
            <h2>Recent scans</h2>
          </div>
          <span className="read-only-label">Read-only view</span>
        </div>
        {data.recent_scans.length === 0 ? (
          <EmptyScans />
        ) : (
          <div className="scan-list">
            {data.recent_scans.map((scan) => (
              <ScanRow key={scan.scan_id} scan={scan} />
            ))}
          </div>
        )}
      </section>
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
    <section className="empty-panel" aria-label="No open findings">
      <div className="empty-icon" aria-hidden="true">
        <CircleCheckBig size={24} />
      </div>
      <div>
        <p className="eyebrow">No open findings</p>
        <h2>The current scan data has no active cost-review items.</h2>
        <p>A future scheduled scan will refresh this view automatically.</p>
      </div>
    </section>
  )
}

function EmptyScans() {
  return (
    <div className="empty-scans">
      <Clock3 aria-hidden="true" size={22} />
      <div>
        <strong>No scan activity has been recorded yet.</strong>
        <p>Enable the EventBridge schedule or run a scanner manually after deployment.</p>
      </div>
    </div>
  )
}

function OverviewError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const unauthorized = error instanceof ApiError && [401, 403].includes(error.status)

  return (
    <section className="overview-error" role="alert">
      <div className="empty-icon empty-icon-error" aria-hidden="true">
        <TriangleAlert size={24} />
      </div>
      <div>
        <p className="eyebrow">{unauthorized ? 'Access denied' : 'Dashboard unavailable'}</p>
        <h1>{unauthorized ? 'Your session cannot access the API.' : 'We could not load the overview.'}</h1>
        <p>{error.message}</p>
      </div>
      <button className="secondary-button" type="button" onClick={onRetry}>
        Try again <ArrowUpRight aria-hidden="true" size={16} />
      </button>
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
