import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CircleCheckBig, LoaderCircle, ShieldAlert, Trash2, TriangleAlert } from 'lucide-react'
import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type RefObject } from 'react'

import type { ApiClient } from '../../api/client'
import type { Finding } from '../../api/types'

import { cleanupAvailability } from './presentation'

type PendingAction = 'approve' | 'cleanup' | null

export function FindingActions({
  apiClient,
  finding,
  isOperator,
}: {
  apiClient: ApiClient
  finding: Finding
  isOperator: boolean
}) {
  const queryClient = useQueryClient()
  const [pendingAction, setPendingAction] = useState<PendingAction>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [cleanupRequested, setCleanupRequested] = useState(false)
  const actionTriggerRef = useRef<HTMLButtonElement | null>(null)

  const approvalMutation = useMutation({
    mutationFn: () => apiClient.approveFinding(finding.finding_id),
    onSuccess: async (approval) => {
      queryClient.setQueryData<Finding>(['finding', finding.finding_id], (current) =>
        current
          ? {
              ...current,
              status: 'approved',
              approval: { approved_by: approval.approved_by, approved_at: approval.approved_at },
            }
          : current,
      )
      setSuccessMessage('Approval recorded. The finding is now eligible for the guarded EBS cleanup-request step.')
      setPendingAction(null)
      await refreshFindingQueries(queryClient, finding.finding_id)
    },
  })
  const cleanupMutation = useMutation({
    mutationFn: () => apiClient.requestEbsCleanup(finding.finding_id),
    onSuccess: async () => {
      setCleanupRequested(true)
      setSuccessMessage(
        'Cleanup request accepted. EventBridge will invoke the isolated EBS worker, which revalidates the volume before any configured action.',
      )
      setPendingAction(null)
      await refreshFindingQueries(queryClient, finding.finding_id)
    },
  })

  if (!isOperator) {
    return (
      <section className="action-panel action-panel-read-only">
        <ShieldAlert aria-hidden="true" size={21} />
        <div>
          <p className="eyebrow">Read-only access</p>
          <h2>Operator approval is required for state changes.</h2>
          <p>Your Cognito session can review evidence but is not in the required operator group.</p>
        </div>
      </section>
    )
  }

  const cleanupMessage = cleanupAvailability(finding)
  const activeMutation = pendingAction === 'approve' ? approvalMutation : cleanupMutation
  const actionError = activeMutation.error instanceof Error ? activeMutation.error.message : null

  return (
    <>
      <section className="action-panel">
        <div>
          <p className="eyebrow">Guarded operator workflow</p>
          <h2>State-changing actions remain server-authorized.</h2>
          <p>
            Approval is an auditable lifecycle transition. It never deletes a resource by itself.
          </p>
        </div>
        <div className="action-controls">
          {finding.status === 'open' && (
            <button className="primary-button" type="button" onClick={(event) => {
              actionTriggerRef.current = event.currentTarget
              setPendingAction('approve')
            }}>
              <CircleCheckBig aria-hidden="true" size={17} /> Approve finding
            </button>
          )}
          {cleanupMessage === null && !cleanupRequested && (
            <button className="danger-button" type="button" onClick={(event) => {
              actionTriggerRef.current = event.currentTarget
              setPendingAction('cleanup')
            }}>
              <Trash2 aria-hidden="true" size={17} /> Request EBS cleanup
            </button>
          )}
          {(cleanupMessage !== null || cleanupRequested) && finding.status !== 'open' && (
            <p className="action-unavailable">
              {cleanupRequested
                ? 'A cleanup request has already been submitted from this page. Refresh later to review the worker outcome.'
                : cleanupMessage}
            </p>
          )}
        </div>
      </section>

      {successMessage && (
        <section aria-live="polite" className="action-success">
          <CircleCheckBig aria-hidden="true" size={18} />
          <span>{successMessage}</span>
        </section>
      )}

      {pendingAction && (
        <ConfirmationDialog
          action={pendingAction}
          error={actionError}
          finding={finding}
          isSubmitting={activeMutation.isPending}
          onCancel={() => {
            setPendingAction(null)
            approvalMutation.reset()
            cleanupMutation.reset()
          }}
          onConfirm={() => {
            if (pendingAction === 'approve') {
              approvalMutation.mutate()
            } else {
              cleanupMutation.mutate()
            }
          }}
          returnFocusTo={actionTriggerRef}
        />
      )}
    </>
  )
}

function ConfirmationDialog({
  action,
  error,
  finding,
  isSubmitting,
  onCancel,
  onConfirm,
  returnFocusTo,
}: {
  action: Exclude<PendingAction, null>
  error: string | null
  finding: Finding
  isSubmitting: boolean
  onCancel: () => void
  onConfirm: () => void
  returnFocusTo: RefObject<HTMLButtonElement | null>
}) {
  const dialogRef = useRef<HTMLElement | null>(null)
  const cancelButtonRef = useRef<HTMLButtonElement | null>(null)
  const onCancelRef = useRef(onCancel)
  onCancelRef.current = onCancel
  const approving = action === 'approve'
  const title = approving ? 'Approve this finding?' : 'Request guarded EBS cleanup?'
  const description = approving
    ? 'This records your approval and creates an audit event. It does not request or perform deletion.'
    : 'This sends an event to the isolated cleanup Lambda. It re-fetches and re-evaluates the EBS volume; the dashboard cannot override dry-run or execution configuration.'

  useEffect(() => {
    const focusedBeforeOpen = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const trigger = returnFocusTo.current
    cancelButtonRef.current?.focus()

    function handleEscape(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCancelRef.current()
      }
    }

    window.addEventListener('keydown', handleEscape)
    return () => {
      window.removeEventListener('keydown', handleEscape)
      trigger?.focus()
      if (!trigger?.isConnected) {
        focusedBeforeOpen?.focus()
      }
    }
  }, [returnFocusTo])

  function trapFocus(event: ReactKeyboardEvent<HTMLElement>) {
    if (event.key !== 'Tab' || !dialogRef.current) {
      return
    }
    const buttons = [...dialogRef.current.querySelectorAll<HTMLButtonElement>('button:not([disabled])')]
    const firstButton = buttons[0]
    const lastButton = buttons.at(-1)
    if (!firstButton || !lastButton) {
      return
    }
    if (event.shiftKey && document.activeElement === firstButton) {
      event.preventDefault()
      lastButton.focus()
    } else if (!event.shiftKey && document.activeElement === lastButton) {
      event.preventDefault()
      firstButton.focus()
    }
  }

  return (
    <div aria-describedby="confirmation-description" aria-labelledby="confirmation-title" aria-modal="true" className="dialog-backdrop" role="dialog" onKeyDown={trapFocus}>
      <section className="confirmation-dialog" ref={dialogRef}>
        <div className="dialog-icon" aria-hidden="true">
          {approving ? <ShieldAlert size={22} /> : <TriangleAlert size={22} />}
        </div>
        <p className="eyebrow">Confirm operator action</p>
        <h2 id="confirmation-title">{title}</h2>
        <p id="confirmation-description">{description}</p>
        <dl className="dialog-finding-summary">
          <div>
            <dt>Resource</dt>
            <dd>{finding.resource.resource_id}</dd>
          </div>
          <div>
            <dt>Rule</dt>
            <dd>{finding.rule_id}</dd>
          </div>
        </dl>
        {error && <p className="dialog-error" role="alert">{error}</p>}
        <div className="dialog-actions">
          <button className="secondary-button" disabled={isSubmitting} ref={cancelButtonRef} type="button" onClick={onCancel}>
            Cancel
          </button>
          <button
            className={approving ? 'primary-button' : 'danger-button'}
            disabled={isSubmitting}
            type="button"
            onClick={onConfirm}
          >
            {isSubmitting && <LoaderCircle aria-hidden="true" className="spin" size={16} />}
            {approving ? 'Confirm approval' : 'Submit cleanup request'}
          </button>
        </div>
      </section>
    </div>
  )
}

async function refreshFindingQueries(queryClient: ReturnType<typeof useQueryClient>, findingId: string) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] }),
    queryClient.invalidateQueries({ queryKey: ['findings'] }),
    queryClient.invalidateQueries({ queryKey: ['finding', findingId] }),
  ])
}
