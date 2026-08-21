import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Filter, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useMemo, useState } from 'react'

import { ApiError, createApiClient } from '../../api/client'
import type { Finding, FindingSeverity, FindingStatus, ResourceType } from '../../api/types'
import { ConsolePageHeader } from '../../components/ConsolePageHeader'
import { OperationalStatePanel } from '../../components/OperationalStatePanel'
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
      <ConsolePageHeader
        action={<button className="secondary-button" type="button" onClick={() => void findingsQuery.refetch()}>
          <RefreshCw aria-hidden="true" size={16} />
          Refresh findings
        </button>}
        eyebrow="Evidence-backed review queue"
        summary="Filter results server-side and review the retained scanner evidence before an operator takes action."
        title="Findings"
      />

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
      <OperationalStatePanel
        action={<button className="secondary-button" type="button" onClick={onRetry}>Try again</button>}
        title={unauthorized ? 'Your session cannot access the findings API.' : 'We could not load findings.'}
        tone="error"
      >
        <p>{error.message}</p>
      </OperationalStatePanel>
    )
  }
  if (!findings) {
    return null
  }
  if (findings.length === 0) {
    return (
      <OperationalStatePanel title="No matching findings" tone="empty">
        <p>Try a different lifecycle status or broaden the resource and severity filters.</p>
      </OperationalStatePanel>
    )
  }

  return (
    <div className="findings-table-scroll">
      <table className="findings-table">
        <caption className="sr-only">Cost optimization findings</caption>
        <thead>
          <tr>
            <th scope="col">Resource</th>
            <th scope="col">Recommendation</th>
            <th scope="col">State</th>
            <th scope="col">Savings</th>
            <th scope="col">Last detected</th>
            <th className="findings-table-action-heading" scope="col"><span className="sr-only">Action</span></th>
          </tr>
        </thead>
        <tbody>
          {findings.map((finding) => <FindingRow finding={finding} key={finding.finding_id} />)}
        </tbody>
      </table>
    </div>
  )
}

function FindingRow({ finding }: { finding: Finding }) {
  return (
    <tr>
      <th className="finding-resource-cell" scope="row">
        <span className="resource-type-badge">{humanize(finding.resource.resource_type)}</span>
        <strong className="monospace-value">{finding.resource.resource_id}</strong>
        <span>{finding.resource.region}</span>
      </th>
      <td className="finding-recommendation-cell">
        <strong>{finding.summary}</strong>
        <span>{finding.recommended_action}</span>
      </td>
      <td>
        <div className="finding-badges">
          <SeverityBadge severity={finding.severity} />
          <StatusBadge status={finding.status} />
        </div>
      </td>
      <td className="finding-savings-cell">
        <strong>{formatCurrency(finding)}</strong>
        <span>monthly estimate</span>
      </td>
      <td className="finding-date-cell">
        <time dateTime={finding.last_detected_at}>{formatDateTime(finding.last_detected_at)}</time>
        <span>Observed {finding.occurrence_count} time(s)</span>
      </td>
      <td className="finding-action-cell">
        <Link className="secondary-button review-link" to={`/findings/${encodeURIComponent(finding.finding_id)}`}>
          Review <ChevronRight aria-hidden="true" size={15} />
        </Link>
      </td>
    </tr>
  )
}

function FindingsLoading() {
  return (
    <div aria-busy="true" aria-label="Loading findings" className="findings-table-scroll">
      <div className="findings-loading-table">
        {[0, 1, 2, 3].map((index) => <div className="skeleton-block skeleton-finding" key={index} />)}
      </div>
    </div>
  )
}

function retryable(failureCount: number, error: Error): boolean {
  return !(error instanceof ApiError && error.status < 500) && failureCount < 2
}
