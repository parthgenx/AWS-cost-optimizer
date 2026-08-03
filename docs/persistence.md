# Finding and scan-run persistence

## Why two DynamoDB tables

The platform uses a `Findings` table and a `ScanRuns` table. A single-table
design is not justified yet: the access patterns are simple, the records have
different lifecycles, and separate tables make permissions and operations easy
to explain.

## Findings table

Primary key: `finding_id` (String)

`finding_id` is a SHA-256 hash of:

```text
rule_id | account_id | region | resource_type | resource_id
```

This provides stable deduplication: a repeated scan refreshes the same finding
instead of creating duplicate records. The adapter uses one atomic
`UpdateItem` request that:

- retains the first-observed timestamp;
- updates last-observed time, evidence, severity, and cost estimate;
- increments `occurrence_count`;
- preserves the existing lifecycle status rather than reopening a dismissed or
  approved finding.

Later, add a GSI for the API query pattern `status + last_detected_at`. Do not
add it until the list-findings endpoint is implemented and its query details
are fixed.

## ScanRuns table

Primary key: `scan_id` (String UUID)

The table records scanner name, start/end time, terminal status, evaluated
resource count, finding count, and sanitized failure type. It intentionally
does not persist arbitrary exception messages, which may contain sensitive AWS
details.

Scan starts use a conditional `PutItem`; terminal updates require the existing
state to be `running`. This prevents duplicate completion transitions.

## Required IAM permissions

The future scanner Lambda should have only:

```text
dynamodb:PutItem       ScanRuns table
dynamodb:UpdateItem    Findings and ScanRuns tables
```

The API Lambda will need read/query permissions later, but it should not share
the scanner role. Cleanup workers will use different, tightly scoped roles.

## Current limitation

The adapters exist but are not wired to deployed Lambda handlers yet. The next
deployment/infrastructure milestone must create the two tables, inject table
names into the scanner runtime, and grant the above permissions.
