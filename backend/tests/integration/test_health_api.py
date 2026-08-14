from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from cost_optimization.api.main import create_app
from cost_optimization.application.services.approve_finding import ApproveFinding
from cost_optimization.config import Environment, Settings
from cost_optimization.domain.findings import AuditEvent, Finding
from cost_optimization.domain.models import (
    FindingCandidate,
    FindingSeverity,
    Money,
    ResourceReference,
    ResourceType,
)


def test_health_endpoint_returns_operational_metadata() -> None:
    settings = Settings(
        service_name="test-service",
        environment=Environment.TESTING,
        version="test-version",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Correlation-ID": "correlation-123"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "test-service",
        "environment": "testing",
        "version": "test-version",
    }
    assert response.headers["X-Correlation-ID"] == "correlation-123"


def test_approval_endpoint_uses_operator_identity_from_trusted_local_header() -> None:
    finding = Finding.from_candidate(_candidate(), datetime(2026, 8, 12, tzinfo=UTC))
    app = create_app(
        Settings(environment=Environment.TESTING),
        approval_service=ApproveFinding(FakeFindingLookup(finding), FakeApprovalRepository()),
    )

    with TestClient(app) as client:
        response = client.post(
            f"/findings/{finding.finding_id}/approval",
            headers={"X-Operator-ID": "operator-123"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["approved_by"] == "operator-123"


def test_approval_endpoint_requires_an_operator_identity() -> None:
    app = create_app(Settings(environment=Environment.TESTING))

    with TestClient(app) as client:
        response = client.post("/findings/finding-123/approval")

    assert response.status_code == 401
    assert response.json()["detail"] == "X-Operator-ID is required in trusted local mode"


def test_cleanup_request_endpoint_needs_a_separate_operator_action() -> None:
    finding = Finding.from_candidate(_candidate(), datetime(2026, 8, 12, tzinfo=UTC))
    app = create_app(
        Settings(environment=Environment.TESTING),
        cleanup_request_service=FakeCleanupRequestService(),
    )

    with TestClient(app) as client:
        response = client.post(
            f"/findings/{finding.finding_id}/cleanup-requests",
            headers={"X-Operator-ID": "operator-123"},
        )

    assert response.status_code == 202
    assert response.json() == {
        "finding_id": finding.finding_id,
        "event_id": "event-123",
        "status": "requested",
    }


class FakeFindingLookup:
    def __init__(self, finding: Finding) -> None:
        self._finding = finding

    def get_by_id(self, finding_id: str) -> Finding | None:
        return self._finding if finding_id == self._finding.finding_id else None


class FakeApprovalRepository:
    def approve(self, finding: Finding, audit_event: AuditEvent) -> None:
        assert finding.status == "approved"
        assert audit_event.actor == "operator-123"


class FakeCleanupRequestService:
    def execute(self, *, finding_id: str, requested_by: str) -> str:
        assert requested_by == "operator-123"
        assert finding_id
        return "event-123"


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
