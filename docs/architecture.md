# Architecture

## Scope

The platform detects potentially unused AWS resources, estimates savings,
notifies operators, and executes cleanup only after explicit approval.

The first deployment target is one AWS account and one region. It is designed
so future cross-account discovery can be implemented behind AWS adapters rather
than changing the domain or API layers.

## Components

- **FastAPI API Lambda:** exposes findings, rule management, scan requests, and
  approval operations through API Gateway.
- **Scanner Lambda:** EventBridge invokes scheduled scans. It uses boto3-backed
  discovery adapters, pure rule evaluation, and a cost-estimation service.
- **Cleanup Lambda:** receives approved cleanup events, revalidates resources,
  and performs only supported, idempotent actions.
- **DynamoDB:** system of record for findings, approvals, rule configuration,
  scan executions, and business audit events.
- **EventBridge:** schedules scans and carries internal workflow events.
- **SNS:** emits operator notifications without coupling scanning to a delivery
  channel.
- **CloudWatch:** collects JSON logs, metrics, dashboards, and alarms.

## Backend boundaries

`api` translates HTTP. `application` will coordinate use cases. `domain`
contains pure models and rules. `infrastructure` will isolate boto3, DynamoDB,
SNS, and EventBridge. `workers` will contain thin Lambda handlers.

Domain code must not import boto3 or depend on raw AWS API responses. AWS
adapters translate SDK responses into domain models before evaluation.

## Resource lifecycle

```text
OPEN → APPROVED → CLEANUP_IN_PROGRESS → CLEANED
  ├→ DISMISSED
  ├→ RESOLVED_EXTERNALLY
  └→ CLEANUP_FAILED
```

Every cleanup operation will be approval-gated, revalidated immediately before
execution, and recorded as an audit event. Dry-run will be available for every
cleanup-capable rule.

## Cost estimates

Estimates are not invoices. A future pricing adapter will use AWS public price
data where suitable and record its source, timestamp, currency, and
assumptions. Cost Explorer is useful for aggregate validation but is not a
reliable primary per-resource pricing source.
