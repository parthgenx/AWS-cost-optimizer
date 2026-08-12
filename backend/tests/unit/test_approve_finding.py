from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cost_optimization.application.services.approve_finding import (
    ApproveFinding,
    FindingNotFoundError,
)
from cost_optimization.domain.findings import AuditEvent, Finding
from cost_optimization.domain.models import (
    FindingCandidate,
    FindingSeverity,
    Money,
    ResourceReference,
    ResourceType,
)


def test_approval_workflow_persists_the_approved_finding_and_audit_event() -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    existing_finding = Finding.from_candidate(_candidate(), now)
    repository = FakeApprovalRepository()
    workflow = ApproveFinding(FakeFindingLookup(existing_finding), repository)

    approved = workflow.execute(
        finding_id=existing_finding.finding_id,
        approved_by="operator-123",
        approved_at=now,
    )

    assert approved.status == "approved"
    assert repository.approvals == [(approved.finding_id, "operator-123", "finding_approved")]


def test_approval_workflow_rejects_a_missing_finding() -> None:
    workflow = ApproveFinding(FakeFindingLookup(None), FakeApprovalRepository())

    with pytest.raises(FindingNotFoundError, match="missing"):
        workflow.execute(
            finding_id="missing",
            approved_by="operator-123",
            approved_at=datetime(2026, 8, 12, tzinfo=UTC),
        )


class FakeFindingLookup:
    def __init__(self, finding: Finding | None) -> None:
        self._finding = finding

    def get_by_id(self, finding_id: str) -> Finding | None:
        if self._finding is not None and self._finding.finding_id == finding_id:
            return self._finding
        return None


class FakeApprovalRepository:
    def __init__(self) -> None:
        self.approvals: list[tuple[str, str, str]] = []

    def approve(self, finding: Finding, audit_event: AuditEvent) -> None:
        self.approvals.append((finding.finding_id, audit_event.actor, audit_event.event_type.value))


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
