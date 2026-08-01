"""Core domain models used by detection rules and workflows."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class ResourceType(StrEnum):
    """AWS resources supported by the platform's initial roadmap."""

    EC2_INSTANCE = "ec2_instance"
    EBS_VOLUME = "ebs_volume"
    ELASTIC_IP = "elastic_ip"
    EBS_SNAPSHOT = "ebs_snapshot"


class EbsVolumeState(StrEnum):
    """Relevant EBS volume states returned by the EC2 API."""

    CREATING = "creating"
    AVAILABLE = "available"
    IN_USE = "in-use"
    DELETING = "deleting"
    DELETED = "deleted"
    ERROR = "error"


class FindingStatus(StrEnum):
    """Lifecycle states for a potentially wasteful resource."""

    OPEN = "open"
    APPROVED = "approved"
    CLEANUP_IN_PROGRESS = "cleanup_in_progress"
    CLEANED = "cleaned"
    DISMISSED = "dismissed"
    RESOLVED_EXTERNALLY = "resolved_externally"
    CLEANUP_FAILED = "cleanup_failed"


class FindingSeverity(StrEnum):
    """Severity is driven by expected savings and operational context."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Money(BaseModel):
    """A monetary estimate represented exactly rather than as a float."""

    amount: Decimal = Field(ge=Decimal("0"))
    currency: str = Field(min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Store ISO-style currency codes consistently."""
        return value.upper()


class ResourceReference(BaseModel):
    """Stable, provider-neutral identity for a discovered resource."""

    resource_type: ResourceType
    resource_id: str = Field(min_length=1, max_length=512)
    region: str = Field(min_length=1, max_length=64)
    account_id: str = Field(pattern=r"^\d{12}$")


class EbsVolume(BaseModel):
    """Provider-neutral representation of the EBS fields needed by the rule."""

    resource: ResourceReference
    state: EbsVolumeState
    size_gib: int = Field(gt=0)
    created_at: datetime
    volume_type: str = Field(min_length=1, max_length=32)
    tags: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("resource")
    @classmethod
    def require_ebs_resource(cls, value: ResourceReference) -> ResourceReference:
        """Prevent accidentally evaluating another AWS resource as an EBS volume."""
        if value.resource_type is not ResourceType.EBS_VOLUME:
            raise ValueError("EbsVolume.resource.resource_type must be ebs_volume")
        return value


class FindingCandidate(BaseModel):
    """Result emitted by a rule before a repository assigns a finding identity."""

    rule_id: str = Field(min_length=1, max_length=128)
    resource: ResourceReference
    summary: str = Field(min_length=1, max_length=512)
    recommended_action: str = Field(min_length=1, max_length=512)
    severity: FindingSeverity
    estimated_monthly_savings: Money | None = None
    evidence: Mapping[str, str] = Field(default_factory=dict)
