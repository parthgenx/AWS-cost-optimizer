# Approval workflow

## Safety boundary

A detected finding is not permission to delete a resource. A finding must move
from `open` to `approved` through an explicit operator action before cleanup can
be requested.

An approval records the approving actor and a timezone-aware timestamp. It also
creates an append-only audit event. The future cleanup worker will require both
the `approved` state and a final live AWS-state revalidation before it can act.

## Lifecycle in this milestone

```text
open → approved → cleanup_in_progress → cleaned
```

The first increment defines and tests the domain transition and audit event.
Subsequent increments add durable DynamoDB persistence, an authenticated API
endpoint, EventBridge dispatch, dry-run cleanup, and final revalidation.
