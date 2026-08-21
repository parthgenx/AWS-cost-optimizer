import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, DatabaseZap, ScanSearch, ShieldCheck } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { useMemo } from 'react'

import { ApiError, createApiClient } from '../../api/client'
import type { Finding } from '../../api/types'
import { OperationalStatePanel } from '../../components/OperationalStatePanel'
import { getDashboardConfiguration } from '../../config'

import { FindingActions } from './FindingActions'
import { SeverityBadge, StatusBadge } from './FindingBadges'
import { formatCurrency, formatDateTime, formatEvidenceKey, humanize } from './presentation'

export function FindingDetailPage({
  accessToken,
  isOperator,
}: {
  accessToken: string | undefined
  isOperator: boolean
}) {
  const { findingId } = useParams()
  const configuration = getDashboardConfiguration()
  if (!configuration || !findingId) {
    throw new Error('A dashboard configuration and finding identifier are required.')
  }
  const apiClient = useMemo(
    () =>
      createApiClient({
        apiBaseUrl: configuration.apiBaseUrl,
        getAccessToken: () => accessToken,
      }),
    [accessToken, configuration.apiBaseUrl],
  )
  const findingQuery = useQuery({
    queryKey: ['finding', findingId],
    queryFn: () => apiClient.getFinding(findingId),
    retry: (failureCount, error) => !(error instanceof ApiError && error.status < 500) && failureCount < 2,
  })

  return (
    <FindingDetailContent
      apiClient={apiClient}
      error={findingQuery.error}
      finding={findingQuery.data}
      isLoading={findingQuery.isLoading}
      isOperator={isOperator}
      onRetry={() => void findingQuery.refetch()}
    />
  )
}

export function FindingDetailContent({
  apiClient,
  error,
  finding,
  isLoading,
  isOperator,
  onRetry,
}: {
  apiClient: ReturnType<typeof createApiClient>
  error: Error | null
  finding: Finding | undefined
  isLoading: boolean
  isOperator: boolean
  onRetry: () => void
}) {
  if (isLoading) {
    return <FindingDetailLoading />
  }
  if (error) {
    const missing = error instanceof ApiError && error.status === 404
    const unauthorized = error instanceof ApiError && [401, 403].includes(error.status)
    return (
      <section className="detail-state">
        <OperationalStatePanel
          action={<div className="detail-state-actions">
          <Link className="secondary-button" to="/findings">Return to findings</Link>
          {!missing && <button className="secondary-button" type="button" onClick={onRetry}>Try again</button>}
          </div>}
          title={missing ? 'This finding no longer exists.' : unauthorized ? 'Your session cannot access this finding.' : 'We could not load this finding.'}
          tone="error"
        >
          <p>{error.message}</p>
        </OperationalStatePanel>
      </section>
    )
  }
  if (!finding) {
    return null
  }

  return (
    <section className="finding-detail-page">
      <Link className="back-link" to="/findings">
        <ArrowLeft aria-hidden="true" size={16} /> Back to findings
      </Link>
      <div className="detail-heading">
        <div>
          <p className="eyebrow">Finding control record</p>
          <h1>{finding.summary}</h1>
          <p>{finding.recommended_action}</p>
          <div className="detail-resource-meta">
            <span className="resource-type-badge">{humanize(finding.resource.resource_type)}</span>
            <span className="monospace-value">{finding.resource.resource_id}</span>
            <span>{finding.resource.region}</span>
          </div>
        </div>
        <div className="detail-heading-badges">
          <SeverityBadge severity={finding.severity} />
          <StatusBadge status={finding.status} />
        </div>
      </div>

      <section className="detail-highlight-grid" aria-label="Finding summary">
        <DetailHighlight icon={<DatabaseZap aria-hidden="true" size={18} />} label="Rule" value={finding.rule_id} />
        <DetailHighlight icon={<ScanSearch aria-hidden="true" size={18} />} label="Potential monthly savings" value={formatCurrency(finding)} />
        <DetailHighlight icon={<ShieldCheck aria-hidden="true" size={18} />} label="Lifecycle state" value={humanize(finding.status)} />
      </section>

      <div className="detail-layout">
        <div className="detail-primary">
          <DetailSection title="Evidence" subtitle="Scanner-derived values that support this recommendation.">
            {Object.keys(finding.evidence).length === 0 ? (
              <p className="empty-detail-copy">No rule evidence was retained for this finding.</p>
            ) : (
              <dl className="evidence-list">
                {Object.entries(finding.evidence).map(([key, value]) => (
                  <div key={key}>
                    <dt>{formatEvidenceKey(key)}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            )}
          </DetailSection>

          <DetailSection title="Lifecycle and scan context" subtitle="A durable record of when this finding was observed and reviewed.">
            <dl className="lifecycle-list">
              <div><dt>First detected</dt><dd>{formatDateTime(finding.first_detected_at)}</dd></div>
              <div><dt>Last detected</dt><dd>{formatDateTime(finding.last_detected_at)}</dd></div>
              <div><dt>Observed by scans</dt><dd>{finding.occurrence_count} time(s)</dd></div>
              <div><dt>Finding ID</dt><dd className="monospace-value">{finding.finding_id}</dd></div>
              {finding.approval && (
                <>
                  <div><dt>Approved by</dt><dd>{finding.approval.approved_by}</dd></div>
                  <div><dt>Approved at</dt><dd>{formatDateTime(finding.approval.approved_at)}</dd></div>
                </>
              )}
            </dl>
          </DetailSection>
        </div>

        <aside className="detail-sidebar">
          <DetailSection title="Resource reference" subtitle="The AWS identity evaluated by the scanner.">
            <dl className="resource-list">
              <div><dt>Type</dt><dd>{humanize(finding.resource.resource_type)}</dd></div>
              <div><dt>Resource ID</dt><dd className="monospace-value">{finding.resource.resource_id}</dd></div>
              <div><dt>Region</dt><dd>{finding.resource.region}</dd></div>
              <div><dt>Account</dt><dd className="monospace-value">{finding.resource.account_id}</dd></div>
            </dl>
          </DetailSection>
          <FindingActions apiClient={apiClient} finding={finding} isOperator={isOperator} />
          <section className="safety-note">
            <ShieldCheck aria-hidden="true" size={18} />
            <p>Viewing a finding never changes AWS resources. The API and isolated cleanup worker enforce every lifecycle guard.</p>
          </section>
        </aside>
      </div>
    </section>
  )
}

function DetailSection({ children, subtitle, title }: { children: React.ReactNode; subtitle: string; title: string }) {
  return (
    <section className="detail-section">
      <div className="detail-section-heading">
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      {children}
    </section>
  )
}

function DetailHighlight({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <article className="detail-highlight">
      <span>{icon}</span>
      <p>{label}</p>
      <strong>{value}</strong>
    </article>
  )
}

function FindingDetailLoading() {
  return (
    <section aria-busy="true" aria-label="Loading finding" className="finding-detail-page">
      <div className="skeleton-block skeleton-detail-heading" />
      <div className="detail-highlight-grid">
        {[0, 1, 2].map((index) => <div className="skeleton-block skeleton-detail-highlight" key={index} />)}
      </div>
      <div className="skeleton-block skeleton-detail-body" />
    </section>
  )
}
