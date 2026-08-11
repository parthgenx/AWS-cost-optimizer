# Approval workflow

## Safety boundary

A detected finding is not permission to delete a resource. A finding must move
from `open` to `approved` through an explicit operator action before cleanup can
be requested.

An approval records the approving actor and a timezone-aware timestamp. It also
creates an append-only audit event. The cleanup worker requires both the
`approved` state and a final live AWS-state revalidation before it can act.

## Lifecycle in this milestone

```text
open → approved → cleanup_in_progress → cleaned
```

`resolved_externally` is used when revalidation shows that the resource no
longer qualifies. `cleanup_failed` records a deletion failure without claiming
the volume was removed.

## Implemented safety controls

- DynamoDB transactions save approval state and its audit event together.
- `POST /findings/{finding_id}/approval` records approval. It cannot delete a
  resource.
- A separate `POST /findings/{finding_id}/cleanup-requests` action publishes an
  EventBridge event only when the finding is still approved.
- EventBridge invokes an isolated EBS cleanup Lambda. Duplicate events are
  harmless because its first state transition is conditional.
- The worker re-fetches the exact EBS volume and evaluates the same rule again.
- Dry-run is the default. Actual deletion requires both
  `CleanupDryRun=false` and `CleanupExecutionEnabled=true` at deployment.

The current HTTP transport uses `X-Operator-ID` only for local development and
tests. It must be replaced by a verified Cognito/API Gateway identity before
the API is exposed outside a trusted environment.
