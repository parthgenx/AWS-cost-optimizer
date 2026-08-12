from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cost_optimization.application.services.request_cleanup import RequestCleanup
from cost_optimization.domain.findings import Finding
from cost_optimization.domain.models import (
    FindingCandidate,
    FindingSeverity,
    Money,
    ResourceReference,
    ResourceType,
)
from cost_optimization.infrastructure.aws.eventbridge_cleanup_requests import (
    EventBridgeCleanupRequestPublisher,
)


def test_request_cleanup_publishes_only_for_an_approved_finding() -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    finding = Finding.from_candidate(_candidate(), now).approve(
        approved_by="operator-123", approved_at=now
    )
    publisher = FakePublisher()

    event_id = RequestCleanup(FakeFindingLookup(finding), publisher).execute(
        finding_id=finding.finding_id, requested_by="operator-123"
    )

    assert event_id == "event-123"
    assert publisher.requests == [(finding.finding_id, "operator-123")]


def test_request_cleanup_rejects_an_open_finding() -> None:
    finding = Finding.from_candidate(_candidate(), datetime(2026, 8, 12, tzinfo=UTC))

    with pytest.raises(ValueError, match="Only approved findings"):
        RequestCleanup(FakeFindingLookup(finding), FakePublisher()).execute(
            finding_id=finding.finding_id, requested_by="operator-123"
        )


def test_eventbridge_publisher_uses_a_typed_cleanup_event() -> None:
    client = FakeEventBridgeClient()

    event_id = EventBridgeCleanupRequestPublisher(client).publish(
        finding_id="finding-123", requested_by="operator-123"
    )

    entry = client.requests[0]["Entries"][0]
    assert event_id == "event-123"
    assert entry["Source"] == "aws-cost-optimizer.cleanup"
    assert entry["DetailType"] == "CleanupRequested"
    assert entry["Detail"] == '{"finding_id":"finding-123","requested_by":"operator-123"}'


class FakeFindingLookup:
    def __init__(self, finding: Finding) -> None:
        self._finding = finding

    def get_by_id(self, finding_id: str) -> Finding | None:
        return self._finding if finding_id == self._finding.finding_id else None


class FakePublisher:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []

    def publish(self, *, finding_id: str, requested_by: str) -> str:
        self.requests.append((finding_id, requested_by))
        return "event-123"


class FakeEventBridgeClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def put_events(self, **kwargs: object) -> dict[str, object]:
        self.requests.append(kwargs)
        return {"FailedEntryCount": 0, "Entries": [{"EventId": "event-123"}]}


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
