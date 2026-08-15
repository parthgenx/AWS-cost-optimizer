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

The dashboard uses `FindingsByStatusLastDetectedAtIndex` with:

```text
status (partition key) + last_detected_at (sort key, newest first)
```

The API requires one lifecycle status per query, defaulting to `open`. Resource
type and severity are bounded filters on that result set. This supports the
dashboard's principal access pattern without maintaining an index for every
possible filter combination. The index projects all finding fields so a list
page requires one DynamoDB query instead of one query plus many point reads.

The overview calculates an exact count and total of only rule-provided savings
estimates by traversing the `open` index with a narrow projection. It does not
claim to be an AWS billing total. If a future account has enough findings for
that read to become expensive, the next step is a transactionally maintained
summary record—not a DynamoDB table scan.

## ScanRuns table

Primary key: `scan_id` (String UUID)

The table records scanner name, start/end time, terminal status, evaluated
resource count, finding count, and sanitized failure type. It intentionally
does not persist arbitrary exception messages, which may contain sensitive AWS
details.

Scan starts use a conditional `PutItem`; terminal updates require the existing
state to be `running`. This prevents duplicate completion transitions.

The dashboard uses `ScanRunsByStartedAtIndex`:

```text
dashboard_partition = "all" (partition key) + started_at (sort key, newest first)
```

Each new scan run writes the constant partition value. This intentionally
supports a single deployment's recent-activity feed; historical records from
before the index was introduced do not have this attribute and will appear
only after a subsequent scan writes new records.

## Required IAM permissions

The scanner Lambdas have only:

```text
dynamodb:PutItem       ScanRuns table
dynamodb:UpdateItem    Findings and ScanRuns tables
```

The API Lambda has `GetItem` and `Query` permissions only for the findings and
scan-runs tables and their indexes. It does not share a scanner role and it
cannot delete EBS volumes. Cleanup workers use a separate, tightly scoped role.

## Dashboard read contract

The API exposes JWT-protected overview, findings, finding detail, and scan-run
reads. The browser never receives DynamoDB permissions or table access.
Approval and cleanup requests remain separate operator-only write operations.
