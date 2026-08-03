from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from cost_optimization.domain.findings import Finding, finding_id_for
from cost_optimization.domain.models import (
    FindingCandidate,
    FindingSeverity,
    Money,
    ResourceReference,
    ResourceType,
)


def test_finding_identity_is_stable_for_the_same_rule_and_resource() -> None:
    candidate = _candidate()

    assert finding_id_for(candidate) == finding_id_for(candidate)


def test_finding_from_candidate_starts_open_with_first_observation_data() -> None:
    detected_at = datetime(2026, 8, 3, tzinfo=UTC)

    finding = Finding.from_candidate(_candidate(), detected_at)

    assert finding.status == "open"
    assert finding.occurrence_count == 1
    assert finding.first_detected_at == detected_at
    assert finding.last_detected_at == detected_at


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
