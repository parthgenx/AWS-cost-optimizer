"""Durable finding and scan-run records independent of DynamoDB."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from uuid import uuid4

from pydantic import BaseModel, Field

from cost_optimization.domain.models import (
    FindingCandidate,
    FindingSeverity,
    FindingStatus,
    Money,
    ResourceReference,
)


class Finding(BaseModel):
    """A stable, repeatedly observed potential cost-saving opportunity."""

    finding_id: str = Field(min_length=1, max_length=64)
    rule_id: str
    resource: ResourceReference
    summary: str
    recommended_action: str
    severity: FindingSeverity
    status: FindingStatus
    estimated_monthly_savings: Money | None
    evidence: dict[str, str]
    first_detected_at: datetime
    last_detected_at: datetime
    occurrence_count: int = Field(ge=1)

    @classmethod
    def from_candidate(cls, candidate: FindingCandidate, detected_at: datetime) -> Finding:
        """Create the deterministic first-observation representation of a candidate."""
        return cls(
            finding_id=finding_id_for(candidate),
            rule_id=candidate.rule_id,
            resource=candidate.resource,
            summary=candidate.summary,
            recommended_action=candidate.recommended_action,
            severity=candidate.severity,
            status=FindingStatus.OPEN,
            estimated_monthly_savings=candidate.estimated_monthly_savings,
            evidence=dict(candidate.evidence),
            first_detected_at=detected_at,
            last_detected_at=detected_at,
            occurrence_count=1,
        )


class ScanRun(BaseModel):
    """Audit-friendly record of one resource-detection execution."""

    scan_id: str = Field(min_length=1, max_length=64)
    scanner_name: str = Field(min_length=1, max_length=128)
    started_at: datetime
    completed_at: datetime | None = None
    status: str = Field(pattern=r"^(running|completed|failed)$")
    evaluated_resource_count: int | None = Field(default=None, ge=0)
    finding_count: int | None = Field(default=None, ge=0)
    failure_type: str | None = Field(default=None, max_length=128)

    @classmethod
    def start(cls, scanner_name: str, started_at: datetime) -> ScanRun:
        """Create a new running scan with a collision-resistant identifier."""
        return cls(
            scan_id=str(uuid4()), scanner_name=scanner_name, started_at=started_at, status="running"
        )


def finding_id_for(candidate: FindingCandidate) -> str:
    """Return a stable ID for the rule/resource combination within one account/region."""
    identity = "|".join(
        (
            candidate.rule_id,
            candidate.resource.account_id,
            candidate.resource.region,
            candidate.resource.resource_type,
            candidate.resource.resource_id,
        )
    )
    return sha256(identity.encode("utf-8")).hexdigest()
