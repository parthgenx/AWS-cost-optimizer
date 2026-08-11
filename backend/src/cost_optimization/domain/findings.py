"""Durable finding and scan-run records independent of DynamoDB."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

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
    approval: FindingApproval | None = None

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

    def approve(self, *, approved_by: str, approved_at: datetime) -> Finding:
        """Return an approved copy only when the finding is currently open."""
        if self.status is not FindingStatus.OPEN:
            raise ValueError("Only open findings can be approved")
        return self.model_copy(
            update={
                "status": FindingStatus.APPROVED,
                "approval": FindingApproval(approved_by=approved_by, approved_at=approved_at),
            }
        )


class FindingApproval(BaseModel):
    """Immutable approval metadata needed before a cleanup workflow may start."""

    approved_by: str = Field(min_length=1, max_length=256)
    approved_at: datetime

    @field_validator("approved_at")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        """Prevent ambiguous audit timestamps."""
        if value.tzinfo is None:
            raise ValueError("approved_at must be timezone-aware")
        return value.astimezone(UTC)


class AuditEventType(StrEnum):
    """Business events recorded for security-sensitive finding lifecycle changes."""

    FINDING_APPROVED = "finding_approved"


class AuditEvent(BaseModel):
    """An append-only audit record independent of its eventual persistence store."""

    event_id: str = Field(min_length=1, max_length=64)
    finding_id: str = Field(min_length=1, max_length=64)
    event_type: AuditEventType
    actor: str = Field(min_length=1, max_length=256)
    occurred_at: datetime
    details: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def finding_approved(cls, finding: Finding) -> AuditEvent:
        """Create a durable-friendly event from a successfully approved finding."""
        if finding.status is not FindingStatus.APPROVED or finding.approval is None:
            raise ValueError("Only approved findings can produce an approval audit event")
        return cls(
            event_id=str(uuid4()),
            finding_id=finding.finding_id,
            event_type=AuditEventType.FINDING_APPROVED,
            actor=finding.approval.approved_by,
            occurred_at=finding.approval.approved_at,
            details={"rule_id": finding.rule_id, "resource_id": finding.resource.resource_id},
        )

    @field_validator("occurred_at")
    @classmethod
    def require_timezone_aware_occurrence(cls, value: datetime) -> datetime:
        """Prevent ambiguous audit timestamps."""
        if value.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value.astimezone(UTC)


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
