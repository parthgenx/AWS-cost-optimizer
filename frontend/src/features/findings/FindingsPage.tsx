import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Filter, RefreshCw, SearchX, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useMemo, useState } from 'react'

import { ApiError, createApiClient } from '../../api/client'
import type { Finding, FindingSeverity, FindingStatus, ResourceType } from '../../api/types'
import { getDashboardConfiguration } from '../../config'

import { SeverityBadge, StatusBadge } from './FindingBadges'
import {
  findingSeverities,
  findingStatuses,
  formatCurrency,
  formatDateTime,
  humanize,
  resourceTypes,
} from './presentation'

const PAGE_SIZE = 20

export function FindingsPage({ accessToken }: { accessToken: string | undefined }) {
  const configuration = getDashboardConfiguration()
  if (!configuration) {
    throw new Error('Dashboard configuration must exist before rendering findings.')
  }

  const [status, setStatus] = useState<FindingStatus>('open')
  const [resourceType, setResourceType] = useState<ResourceType | undefined>()
  const [severity, setSeverity] = useState<FindingSeverity | undefined>()
  const [cursors, setCursors] = useState<(string | undefined)[]>([undefined])
  const [pageIndex, setPageIndex] = useState(0)
  const currentCursor = cursors[pageIndex]

  const apiClient = useMemo(
    () =>
      createApiClient({
        apiBaseUrl: configuration.apiBaseUrl,
        getAccessToken: () => accessToken,
      }),
    [accessToken, configuration.apiBaseUrl],
  )

  const findingsQuery = useQuery({
    queryKey: ['findings', { status, resourceType, severity, cursor: currentCursor }],
    queryFn: () => apiClient.listFindings({ status, resourceType, severity, cursor: currentCursor, limit: PAGE_SIZE }),
    retry: retryable,
  })

  function resetPagination() {
    setCursors([undefined])
    setPageIndex(0)
  }

  function nextPage() {
    const nextCursor = findingsQuery.data?.next_cursor
    if (!nextCursor) {
      return
    }
    setCursors((current) => [...current.slice(0, pageIndex + 1), nextCursor])
    setPageIndex((current) => current + 1)
  }

  return (
    <section className="findings-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Evidence-backed review queue</p>
          <h1>Review cost findings with context before taking action.</h1>
          <p className="page-subtitle">
            Lifecycle filters are server-side. The dashboard never discovers resources or calculates
            eligibility in the browser.
          </p>
        </div>
        <button className="secondary-button" type="button" onClick={() => void findingsQuery.refetch()}>
          <RefreshCw aria-hidden="true" size={16} />
          Refresh findings
        </button>
      </div>

      <section aria-label="Finding filters" className="filter-bar">
        <div className="filter-label">
          <Filter aria-hidden="true" size={17} />
          <span>Filters</span>
        </div>
        <label>
          <span>Status</span>
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as FindingStatus)
              resetPagination()
            }}
          >
            {findingStatuses.map((value) => (
              <option key={value} value={value}>
                {humanize(value)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Resource</span>
          <select
            value={resourceType ?? ''}
            onChange={(event) => {
              setResourceType((event.target.value || undefined) as ResourceType | undefined)
              resetPagination()
            }}
          >
            <option value="">All supported resources</option>
            {resourceTypes.map((value) => (
              <option key={value} value={value}>
                {humanize(value)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Severity</span>
          <select
            value={severity ?? ''}
            onChange={(event) => {
              setSeverity((event.target.value || undefined) as FindingSeverity | undefined)
              resetPagination()
            }}
          >
            <option value="">All severities</option>
            {findingSeverities.map((value) => (
              <option key={value} value={value}>
                {humanize(value)}
              </option>
            ))}
          </select>
        </label>
      </section>

      <FindingsListContent
        error={findingsQuery.error}
        findings={findingsQuery.data?.items}
        isLoading={findingsQuery.isLoading}
        onRetry={() => void findingsQuery.refetch()}
      />

      {!findingsQuery.isLoading && !findingsQuery.error && findingsQuery.data && (
        <nav aria-label="Findings pagination" className="pagination">
          <p>Page {pageIndex + 1}</p>
          <div>
            <button
              className="secondary-button pagination-button"
              disabled={pageIndex === 0}
              type="button"
              onClick={() => setPageIndex((current) => Math.max(0, current - 1))}
            >
              <ChevronLeft aria-hidden="true" size={16} /> Previous
            </button>
            <button
              className="secondary-button pagination-button"
              disabled={!findingsQuery.data.next_cursor}
              type="button"
              onClick={nextPage}
            >
              Next <ChevronRight aria-hidden="true" size={16} />
            </button>
          </div>
        </nav>
      )}
    </section>
  )
}

export function FindingsListContent({
  error,
  findings,
  isLoading,
  onRetry,
}: {
  error: Error | null
  findings: Finding[] | undefined
  isLoading: boolean
  onRetry: () => void
}) {
  if (isLoading) {
    return <FindingsLoading />
  }
  if (error) {
    const unauthorized = error instanceof ApiError && [401, 403].includes(error.status)
    return (
      <section className="findings-state" role="alert">
        <TriangleAlert aria-hidden="true" size={25} />
        <div>
          <p className="eyebrow">{unauthorized ? 'Access denied' : 'Findings unavailable'}</p>
          <h2>{unauthorized ? 'Your session cannot access the findings API.' : 'We could not load findings.'}</h2>
          <p>{error.message}</p>
        </div>
        <button className="secondary-button" type="button" onClick={onRetry}>
          Try again
        </button>
      </section>
    )
  }
  if (!findings) {
    return null
  }
  if (findings.length === 0) {
    return (
      <section className="findings-state findings-empty">
        <SearchX aria-hidden="true" size={25} />
        <div>
          <p className="eyebrow">No matching findings</p>
          <h2>This lifecycle and filter combination has no results.</h2>
          <p>Try a different status or broaden the resource and severity filters.</p>
        </div>
      </section>
    )
  }

  return (
    <div className="finding-list" aria-label="Findings">
      {findings.map((finding) => (
        <FindingRow finding={finding} key={finding.finding_id} />
      ))}
    </div>
  )
}

function FindingRow({ finding }: { finding: Finding }) {
  return (
    <article className="finding-row">
      <div className="finding-row-main">
        <div className="finding-row-heading">
          <div>
            <p className="finding-resource">{humanize(finding.resource.resource_type)}</p>
            <h2>{finding.summary}</h2>
          </div>
          <div className="finding-badges">
            <SeverityBadge severity={finding.severity} />
            <StatusBadge status={finding.status} />
          </div>
        </div>
        <p className="finding-summary">{finding.recommended_action}</p>
        <div className="finding-metadata">
          <span>{finding.resource.resource_id}</span>
          <span>{finding.resource.region}</span>
          <span>Observed {finding.occurrence_count} time(s)</span>
          <span>Last seen {formatDateTime(finding.last_detected_at)}</span>
        </div>
      </div>
      <div className="finding-row-side">
        <strong>{formatCurrency(finding)}</strong>
        <span>Potential monthly savings</span>
        <Link className="text-link finding-link" to={`/findings/${encodeURIComponent(finding.finding_id)}`}>
          Review finding <ChevronRight aria-hidden="true" size={16} />
        </Link>
      </div>
    </article>
  )
}

function FindingsLoading() {
  return (
    <div aria-busy="true" aria-label="Loading findings" className="finding-list finding-list-loading">
      {[0, 1, 2].map((index) => (
        <div className="skeleton-block skeleton-finding" key={index} />
      ))}
    </div>
  )
}

function retryable(failureCount: number, error: Error): boolean {
  return !(error instanceof ApiError && error.status < 500) && failureCount < 2
}
