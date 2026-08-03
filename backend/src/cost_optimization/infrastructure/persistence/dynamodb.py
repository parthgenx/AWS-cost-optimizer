"""DynamoDB adapters for findings and scan-run records."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol, cast

import boto3

from cost_optimization.domain.findings import Finding, ScanRun, finding_id_for
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


def get_dynamodb_table(table_name: str) -> DynamoDbTable:
    """Create a DynamoDB table handle; application/domain code never calls boto3."""
    dynamodb = boto3.resource("dynamodb")
    return cast(DynamoDbTable, dynamodb.Table(table_name))


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
    )


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
