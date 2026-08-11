from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

from cost_optimization.domain.findings import (
    AuditEvent,
    AuditEventType,
    Finding,
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
from cost_optimization.infrastructure.persistence.dynamodb import (
    DynamoDbFindingApprovalRepository,
    DynamoDbFindingLifecycleRepository,
    DynamoDbFindingRepository,
    DynamoDbScanRunRepository,
)


def test_finding_repository_builds_idempotent_update_and_maps_returned_item() -> None:
    candidate = _candidate()
    now = datetime(2026, 8, 3, tzinfo=UTC)
    table = FakeTable(
        update_response={
            "Attributes": {
                "finding_id": finding_id_for(candidate),
                "rule_id": candidate.rule_id,
                "resource_type": "ebs_volume",
                "resource_id": candidate.resource.resource_id,
                "account_id": candidate.resource.account_id,
                "region": candidate.resource.region,
                "summary": candidate.summary,
                "recommended_action": candidate.recommended_action,
                "severity": "low",
                "status": "open",
                "estimated_monthly_savings_amount": Decimal("1.60"),
                "estimated_monthly_savings_currency": "USD",
                "evidence": {"state": "available"},
                "first_detected_at": now.isoformat(),
                "last_detected_at": now.isoformat(),
                "occurrence_count": 2,
            }
        }
    )

    finding = DynamoDbFindingRepository(table).record_detection(candidate, now)

    request = table.update_requests[0]
    assert request["Key"] == {"finding_id": finding.finding_id}
    assert "if_not_exists(first_detected_at, :detected_at)" in str(request["UpdateExpression"])
    assert request["ExpressionAttributeValues"][":one"] == 1
    assert finding.occurrence_count == 2
    assert finding.estimated_monthly_savings == Money(amount=Decimal("1.60"), currency="USD")


def test_scan_run_repository_uses_conditional_state_transitions() -> None:
    table = FakeTable(update_response={})
    repository = DynamoDbScanRunRepository(table)
    started_at = datetime(2026, 8, 3, tzinfo=UTC)
    scan_run = ScanRun.start("unattached-ebs-volume", started_at)

    repository.create(scan_run)
    repository.complete(scan_run, completed_at=started_at, evaluated_count=4, finding_count=2)

    assert table.put_requests[0]["ConditionExpression"] == "attribute_not_exists(scan_id)"
    complete_request = table.update_requests[0]
    assert complete_request["ConditionExpression"] == "#status = :running"
    assert complete_request["ExpressionAttributeValues"][":finding_count"] == 2


def test_approval_repository_commits_finding_and_audit_event_in_one_transaction() -> None:
    candidate = _candidate()
    now = datetime(2026, 8, 12, tzinfo=UTC)
    approved_finding = Finding.from_candidate(candidate, now).approve(
        approved_by="operator-123", approved_at=now
    )
    audit_event = AuditEvent.finding_approved(approved_finding)
    client = FakeDynamoDbClient()

    DynamoDbFindingApprovalRepository(
        client,
        findings_table_name="findings",
        audit_events_table_name="audit-events",
    ).approve(approved_finding, audit_event)

    transaction = client.transaction_requests[0]["TransactItems"]
    finding_update = transaction[0]["Update"]
    audit_put = transaction[1]["Put"]
    assert finding_update["TableName"] == "findings"
    assert finding_update["ConditionExpression"] == "#status = :open"
    assert finding_update["ExpressionAttributeValues"][":approved"]["S"] == "approved"
    assert finding_update["ExpressionAttributeValues"][":approved_by"]["S"] == "operator-123"
    assert audit_put["TableName"] == "audit-events"
    assert audit_put["Item"]["finding_id"]["S"] == approved_finding.finding_id
    assert audit_put["Item"]["actor"]["S"] == "operator-123"


def test_lifecycle_repository_guards_transition_and_persists_its_audit_event() -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    approved_finding = Finding.from_candidate(_candidate(), now).approve(
        approved_by="operator-123", approved_at=now
    )
    in_progress = approved_finding.begin_cleanup()
    client = FakeDynamoDbClient()

    DynamoDbFindingLifecycleRepository(
        client,
        findings_table_name="findings",
        audit_events_table_name="audit-events",
    ).transition(
        finding=in_progress,
        expected_status=FindingStatus.APPROVED,
        audit_event=AuditEvent.lifecycle_event(
            finding=in_progress,
            event_type=AuditEventType.CLEANUP_STARTED,
            actor="ebs-cleanup-worker",
            occurred_at=now,
        ),
    )

    update = client.transaction_requests[0]["TransactItems"][0]["Update"]
    assert update["ConditionExpression"] == "#status = :expected"
    assert update["ExpressionAttributeValues"][":expected"]["S"] == "approved"
    assert update["ExpressionAttributeValues"][":target"]["S"] == "cleanup_in_progress"


class FakeTable:
    def __init__(self, *, update_response: Mapping[str, object]) -> None:
        self._update_response = update_response
        self.put_requests: list[dict[str, object]] = []
        self.update_requests: list[dict[str, object]] = []

    def put_item(self, **kwargs: object) -> Mapping[str, object]:
        self.put_requests.append(kwargs)
        return {}

    def update_item(self, **kwargs: object) -> Mapping[str, object]:
        self.update_requests.append(kwargs)
        return self._update_response

    def get_item(self, **kwargs: object) -> Mapping[str, object]:
        del kwargs
        return {}


class FakeDynamoDbClient:
    def __init__(self) -> None:
        self.transaction_requests: list[dict[str, object]] = []

    def transact_write_items(self, **kwargs: object) -> Mapping[str, object]:
        self.transaction_requests.append(kwargs)
        return {}


def _candidate() -> FindingCandidate:
    return FindingCandidate(
        rule_id="unattached-ebs-volume",
        resource=ResourceReference(
            resource_type=ResourceType.EBS_VOLUME,
            resource_id="vol-0123456789abcdef0",
            region="ap-south-1",
            account_id="123456789012",
        ),
        summary="Volume is currently unattached.",
        recommended_action="Review the volume.",
        severity=FindingSeverity.LOW,
        estimated_monthly_savings=Money(amount=Decimal("1.60"), currency="USD"),
        evidence={"state": "available"},
    )
