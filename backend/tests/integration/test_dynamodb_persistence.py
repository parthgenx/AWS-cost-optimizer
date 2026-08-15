from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

import pytest

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
    assert table.put_requests[0]["Item"]["dashboard_partition"] == "all"
    complete_request = table.update_requests[0]
    assert complete_request["ConditionExpression"] == "#status = :running"
    assert complete_request["ExpressionAttributeValues"][":finding_count"] == 2


def test_finding_repository_queries_status_index_with_optional_filters_and_cursor() -> None:
    candidate = _candidate()
    now = datetime(2026, 8, 3, tzinfo=UTC)
    table = FakeTable(
        update_response={},
        query_responses=[
            {
                "Items": [
                    {
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
                        "occurrence_count": 1,
                    }
                ],
                "LastEvaluatedKey": {
                    "finding_id": finding_id_for(candidate),
                    "status": "open",
                    "last_detected_at": now.isoformat(),
                },
            }
        ],
    )

    page = DynamoDbFindingRepository(table).list_by_status(
        status=FindingStatus.OPEN,
        resource_type=ResourceType.EBS_VOLUME,
        severity=FindingSeverity.LOW,
        limit=25,
        cursor=None,
    )

    request = table.query_requests[0]
    assert request["IndexName"] == "FindingsByStatusLastDetectedAtIndex"
    assert request["KeyConditionExpression"] == "#status = :status"
    assert request["FilterExpression"] == (
        "#resource_type = :resource_type AND #severity = :severity"
    )
    assert request["ScanIndexForward"] is False
    assert page.items[0].finding_id == finding_id_for(candidate)
    assert page.next_cursor is not None


def test_finding_summary_accumulates_each_status_index_page() -> None:
    table = FakeTable(
        update_response={},
        query_responses=[
            {
                "Items": [
                    {
                        "estimated_monthly_savings_amount": Decimal("1.60"),
                        "estimated_monthly_savings_currency": "USD",
                    },
                    {},
                ],
                "LastEvaluatedKey": {
                    "finding_id": "finding-1",
                    "status": "open",
                    "last_detected_at": "2026-08-03T00:00:00+00:00",
                },
            },
            {
                "Items": [
                    {
                        "estimated_monthly_savings_amount": Decimal("2.40"),
                        "estimated_monthly_savings_currency": "USD",
                    }
                ]
            },
        ],
    )

    summary = DynamoDbFindingRepository(table).summarize_by_status(status=FindingStatus.OPEN)

    assert summary.finding_count == 3
    assert summary.findings_with_known_savings_count == 2
    assert summary.known_monthly_savings_by_currency["USD"] == Money(
        amount=Decimal("4.00"), currency="USD"
    )
    assert table.query_requests[1]["ExclusiveStartKey"] == {
        "finding_id": "finding-1",
        "status": "open",
        "last_detected_at": "2026-08-03T00:00:00+00:00",
    }


def test_finding_repository_rejects_a_malformed_pagination_cursor() -> None:
    table = FakeTable(update_response={})

    with pytest.raises(ValueError, match="Pagination cursor is invalid"):
        DynamoDbFindingRepository(table).list_by_status(
            status=FindingStatus.OPEN,
            resource_type=None,
            severity=None,
            limit=25,
            cursor="not-a-valid-cursor",
        )

    assert table.query_requests == []


def test_scan_run_repository_queries_dashboard_activity_index() -> None:
    started_at = datetime(2026, 8, 3, tzinfo=UTC)
    table = FakeTable(
        update_response={},
        query_responses=[
            {
                "Items": [
                    {
                        "scan_id": "scan-123",
                        "scanner_name": "unattached-ebs-volume",
                        "started_at": started_at.isoformat(),
                        "status": "completed",
                        "completed_at": started_at.isoformat(),
                        "evaluated_resource_count": Decimal("0"),
                        "finding_count": Decimal("0"),
                    }
                ]
            }
        ],
    )

    page = DynamoDbScanRunRepository(table).list_recent(limit=25, cursor=None)

    assert table.query_requests[0]["IndexName"] == "ScanRunsByStartedAtIndex"
    assert table.query_requests[0]["ExpressionAttributeValues"] == {":partition": "all"}
    assert page.items[0].evaluated_resource_count == 0


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
    def __init__(
        self,
        *,
        update_response: Mapping[str, object],
        query_responses: list[Mapping[str, object]] | None = None,
    ) -> None:
        self._update_response = update_response
        self._query_responses = list(query_responses or [])
        self.put_requests: list[dict[str, object]] = []
        self.update_requests: list[dict[str, object]] = []
        self.query_requests: list[dict[str, object]] = []

    def put_item(self, **kwargs: object) -> Mapping[str, object]:
        self.put_requests.append(kwargs)
        return {}

    def update_item(self, **kwargs: object) -> Mapping[str, object]:
        self.update_requests.append(kwargs)
        return self._update_response

    def get_item(self, **kwargs: object) -> Mapping[str, object]:
        del kwargs
        return {}

    def query(self, **kwargs: object) -> Mapping[str, object]:
        self.query_requests.append(kwargs)
        return self._query_responses.pop(0)


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
