"""DynamoDB adapters for findings and scan-run records."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol, cast

import boto3

from cost_optimization.domain.findings import (
    AuditEvent,
    Finding,
    FindingApproval,
    ScanRun,
    finding_id_for,
)
from cost_optimization.domain.models import (
    FindingCandidate,
    FindingSeverity,
    FindingStatus,
    Money,
    ResourceReference,
    ResourceType,
)


class DynamoDbTable(Protocol):
    """Minimal table client surface used by the persistence adapters."""

    def put_item(self, **kwargs: object) -> Mapping[str, object]:
        """Write a single item."""

    def update_item(self, **kwargs: object) -> Mapping[str, object]:
        """Update a single item and optionally return its attributes."""

    def get_item(self, **kwargs: object) -> Mapping[str, object]:
        """Read a single item by primary key."""


class DynamoDbClient(Protocol):
    """Minimal DynamoDB client surface required for atomic lifecycle writes."""

    def transact_write_items(self, **kwargs: object) -> Mapping[str, object]:
        """Atomically write one or more DynamoDB items."""


def get_dynamodb_table(table_name: str) -> DynamoDbTable:
    """Create a DynamoDB table handle; application/domain code never calls boto3."""
    dynamodb = boto3.resource("dynamodb")
    return cast(DynamoDbTable, dynamodb.Table(table_name))


def get_dynamodb_client() -> DynamoDbClient:
    """Create the low-level client needed for DynamoDB transactions."""
    return cast(DynamoDbClient, boto3.client("dynamodb"))


class DynamoDbFindingRepository:
    """Idempotently upserts one durable finding per rule/resource identity."""

    def __init__(self, table: DynamoDbTable) -> None:
        self._table = table

    def record_detection(self, candidate: FindingCandidate, detected_at: datetime) -> Finding:
        """Create a finding or refresh its current evidence and observation count."""
        finding_id = finding_id_for(candidate)
        values = _finding_values(candidate, detected_at)
        response = self._table.update_item(
            Key={"finding_id": finding_id},
            UpdateExpression=(
                "SET rule_id = :rule_id, resource_type = :resource_type, "
                "resource_id = :resource_id, "
                "account_id = :account_id, region = :region, summary = :summary, "
                "recommended_action = :recommended_action, severity = :severity, "
                "estimated_monthly_savings_amount = :savings_amount, "
                "estimated_monthly_savings_currency = :savings_currency, evidence = :evidence, "
                "#status = if_not_exists(#status, :open), "
                "first_detected_at = if_not_exists(first_detected_at, :detected_at), "
                "last_detected_at = :detected_at"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues=values,
            Add="occurrence_count :one",
            ReturnValues="ALL_NEW",
        )
        return _finding_from_item(_required_attributes(response))

    def get_by_id(self, finding_id: str) -> Finding | None:
        """Load a finding without exposing DynamoDB response structures."""
        response = self._table.get_item(Key={"finding_id": finding_id}, ConsistentRead=True)
        item = response.get("Item")
        if item is None:
            return None
        if not isinstance(item, Mapping):
            raise ValueError("DynamoDB finding response Item must be a map")
        return _finding_from_item(item)


class DynamoDbFindingApprovalRepository:
    """Atomically persists an approval state change and append-only audit event."""

    def __init__(
        self,
        client: DynamoDbClient,
        *,
        findings_table_name: str,
        audit_events_table_name: str,
    ) -> None:
        self._client = client
        self._findings_table_name = findings_table_name
        self._audit_events_table_name = audit_events_table_name

    def approve(self, finding: Finding, audit_event: AuditEvent) -> None:
        """Commit approval metadata and audit evidence only when finding is open."""
        if finding.status is not FindingStatus.APPROVED or finding.approval is None:
            raise ValueError("Only approved findings can be persisted as approvals")
        if audit_event.finding_id != finding.finding_id:
            raise ValueError("Audit event finding_id must match the approved finding")

        self._client.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": self._findings_table_name,
                        "Key": {"finding_id": {"S": finding.finding_id}},
                        "UpdateExpression": (
                            "SET #status = :approved, approval_approved_by = :approved_by, "
                            "approval_approved_at = :approved_at"
                        ),
                        "ConditionExpression": "#status = :open",
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": {
                            ":approved": {"S": FindingStatus.APPROVED.value},
                            ":approved_by": {"S": finding.approval.approved_by},
                            ":approved_at": {"S": _timestamp(finding.approval.approved_at)},
                            ":open": {"S": FindingStatus.OPEN.value},
                        },
                    }
                },
                {
                    "Put": {
                        "TableName": self._audit_events_table_name,
                        "Item": _audit_event_item(audit_event),
                        "ConditionExpression": "attribute_not_exists(event_id)",
                    }
                },
            ]
        )


class DynamoDbFindingLifecycleRepository:
    """Persists cleanup state transitions with their matching audit records."""

    def __init__(
        self,
        client: DynamoDbClient,
        *,
        findings_table_name: str,
        audit_events_table_name: str,
    ) -> None:
        self._client = client
        self._findings_table_name = findings_table_name
        self._audit_events_table_name = audit_events_table_name

    def transition(
        self,
        *,
        finding: Finding,
        expected_status: FindingStatus,
        audit_event: AuditEvent,
    ) -> None:
        """Update a lifecycle status only from its expected predecessor state."""
        self._write_transaction(
            finding_id=finding.finding_id,
            expected_status=expected_status,
            audit_event=audit_event,
            status_to_set=finding.status,
        )

    def record_event(
        self,
        *,
        finding_id: str,
        expected_status: FindingStatus,
        audit_event: AuditEvent,
    ) -> None:
        """Write a dry-run audit event without changing a finding's lifecycle state."""
        self._write_transaction(
            finding_id=finding_id,
            expected_status=expected_status,
            audit_event=audit_event,
            status_to_set=None,
        )

    def _write_transaction(
        self,
        *,
        finding_id: str,
        expected_status: FindingStatus,
        audit_event: AuditEvent,
        status_to_set: FindingStatus | None,
    ) -> None:
        if audit_event.finding_id != finding_id:
            raise ValueError("Audit event finding_id must match the lifecycle finding")
        finding_key = {"finding_id": {"S": finding_id}}
        status_condition = {
            "TableName": self._findings_table_name,
            "Key": finding_key,
            "ConditionExpression": "#status = :expected",
            "ExpressionAttributeNames": {"#status": "status"},
            "ExpressionAttributeValues": {":expected": {"S": expected_status.value}},
        }
        lifecycle_write: dict[str, object]
        if status_to_set is None:
            lifecycle_write = {"ConditionCheck": status_condition}
        else:
            lifecycle_write = {
                "Update": {
                    **status_condition,
                    "UpdateExpression": "SET #status = :target",
                    "ExpressionAttributeValues": {
                        ":expected": {"S": expected_status.value},
                        ":target": {"S": status_to_set.value},
                    },
                }
            }
        self._client.transact_write_items(
            TransactItems=[
                lifecycle_write,
                {
                    "Put": {
                        "TableName": self._audit_events_table_name,
                        "Item": _audit_event_item(audit_event),
                        "ConditionExpression": "attribute_not_exists(event_id)",
                    }
                },
            ]
        )


class DynamoDbScanRunRepository:
    """Stores scan starts and terminal scan outcomes in a dedicated table."""

    def __init__(self, table: DynamoDbTable) -> None:
        self._table = table

    def create(self, scan_run: ScanRun) -> None:
        """Persist a running scan and reject the extremely unlikely ID collision."""
        self._table.put_item(
            Item={
                "scan_id": scan_run.scan_id,
                "scanner_name": scan_run.scanner_name,
                "started_at": _timestamp(scan_run.started_at),
                "status": "running",
            },
            ConditionExpression="attribute_not_exists(scan_id)",
        )

    def complete(
        self, scan_run: ScanRun, *, completed_at: datetime, evaluated_count: int, finding_count: int
    ) -> None:
        """Transition a running scan to completed exactly once."""
        self._table.update_item(
            Key={"scan_id": scan_run.scan_id},
            UpdateExpression=(
                "SET #status = :completed, completed_at = :completed_at, "
                "evaluated_resource_count = :evaluated_count, finding_count = :finding_count"
            ),
            ConditionExpression="#status = :running",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":completed": "completed",
                ":completed_at": _timestamp(completed_at),
                ":evaluated_count": evaluated_count,
                ":finding_count": finding_count,
                ":running": "running",
            },
        )

    def fail(self, scan_run: ScanRun, *, completed_at: datetime, failure_type: str) -> None:
        """Transition a running scan to failed without storing error messages."""
        self._table.update_item(
            Key={"scan_id": scan_run.scan_id},
            UpdateExpression=(
                "SET #status = :failed, completed_at = :completed_at, failure_type = :failure_type"
            ),
            ConditionExpression="#status = :running",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":failed": "failed",
                ":completed_at": _timestamp(completed_at),
                ":failure_type": failure_type,
                ":running": "running",
            },
        )


def _finding_values(candidate: FindingCandidate, detected_at: datetime) -> dict[str, object]:
    savings = candidate.estimated_monthly_savings
    return {
        ":rule_id": candidate.rule_id,
        ":resource_type": candidate.resource.resource_type,
        ":resource_id": candidate.resource.resource_id,
        ":account_id": candidate.resource.account_id,
        ":region": candidate.resource.region,
        ":summary": candidate.summary,
        ":recommended_action": candidate.recommended_action,
        ":severity": candidate.severity,
        ":savings_amount": savings.amount if savings else None,
        ":savings_currency": savings.currency if savings else None,
        ":evidence": dict(candidate.evidence),
        ":open": FindingStatus.OPEN,
        ":detected_at": _timestamp(detected_at),
        ":one": 1,
    }


def _finding_from_item(item: Mapping[str, object]) -> Finding:
    savings_amount = item.get("estimated_monthly_savings_amount")
    savings_currency = item.get("estimated_monthly_savings_currency")
    savings = None
    if savings_amount is not None and isinstance(savings_currency, str):
        savings = Money(amount=Decimal(str(savings_amount)), currency=savings_currency)
    evidence = item.get("evidence", {})
    if not isinstance(evidence, Mapping):
        raise ValueError("DynamoDB finding evidence must be a map")
    approval = _approval_from_item(item)
    return Finding(
        finding_id=_required_str(item, "finding_id"),
        rule_id=_required_str(item, "rule_id"),
        resource=ResourceReference(
            resource_type=ResourceType(_required_str(item, "resource_type")),
            resource_id=_required_str(item, "resource_id"),
            account_id=_required_str(item, "account_id"),
            region=_required_str(item, "region"),
        ),
        summary=_required_str(item, "summary"),
        recommended_action=_required_str(item, "recommended_action"),
        severity=FindingSeverity(_required_str(item, "severity")),
        status=FindingStatus(_required_str(item, "status")),
        estimated_monthly_savings=savings,
        evidence={str(key): str(value) for key, value in evidence.items()},
        first_detected_at=_parse_timestamp(_required_str(item, "first_detected_at")),
        last_detected_at=_parse_timestamp(_required_str(item, "last_detected_at")),
        occurrence_count=_required_int(item, "occurrence_count"),
        approval=approval,
    )


def _approval_from_item(item: Mapping[str, object]) -> FindingApproval | None:
    approved_by = item.get("approval_approved_by")
    approved_at = item.get("approval_approved_at")
    if approved_by is None and approved_at is None:
        return None
    if not isinstance(approved_by, str) or not approved_by:
        raise ValueError("DynamoDB finding approval_approved_by must be a non-empty string")
    if not isinstance(approved_at, str) or not approved_at:
        raise ValueError("DynamoDB finding approval_approved_at must be a non-empty string")
    return FindingApproval(approved_by=approved_by, approved_at=_parse_timestamp(approved_at))


def _audit_event_item(audit_event: AuditEvent) -> dict[str, object]:
    return {
        "finding_id": {"S": audit_event.finding_id},
        "event_id": {"S": audit_event.event_id},
        "event_type": {"S": audit_event.event_type.value},
        "actor": {"S": audit_event.actor},
        "occurred_at": {"S": _timestamp(audit_event.occurred_at)},
        "details": {
            "M": {key: {"S": value} for key, value in audit_event.details.items()},
        },
    }


def _required_attributes(response: Mapping[str, object]) -> Mapping[str, object]:
    attributes = response.get("Attributes")
    if not isinstance(attributes, Mapping):
        raise ValueError("DynamoDB update response did not contain Attributes")
    return attributes


def _required_str(values: Mapping[str, object], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"DynamoDB finding {name} must be a non-empty string")
    return value


def _required_int(values: Mapping[str, object], name: str) -> int:
    value = values.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"DynamoDB finding {name} must be a positive integer")
    return value


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("DynamoDB timestamps must be timezone-aware")
    return parsed
