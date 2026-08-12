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
    RDS_INSTANCE = "rds_instance"
    APPLICATION_LOAD_BALANCER = "application_load_balancer"


class EbsVolumeState(StrEnum):
    """Relevant EBS volume states returned by the EC2 API."""

    CREATING = "creating"
    AVAILABLE = "available"
    IN_USE = "in-use"
    DELETING = "deleting"
    DELETED = "deleted"
    ERROR = "error"


class EbsSnapshotState(StrEnum):
    """Relevant snapshot states returned by the EC2 API."""

    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"
    RECOVERABLE = "recoverable"
    RECOVERING = "recovering"


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


class ElasticIpAddress(BaseModel):
    """Provider-neutral Elastic IP fields needed by the unassociated-address rule."""

    resource: ResourceReference
    public_ip: str = Field(min_length=1, max_length=64)
    allocation_id: str = Field(min_length=1, max_length=128)
    association_id: str | None = None
    network_interface_id: str | None = None
    instance_id: str | None = None
    tags: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("resource")
    @classmethod
    def require_elastic_ip_resource(cls, value: ResourceReference) -> ResourceReference:
        """Prevent evaluating a non-address resource with this rule."""
        if value.resource_type is not ResourceType.ELASTIC_IP:
            raise ValueError("ElasticIpAddress.resource.resource_type must be elastic_ip")
        return value


class EbsSnapshot(BaseModel):
    """Provider-neutral EBS snapshot fields required for conservative review findings."""

    resource: ResourceReference
    state: EbsSnapshotState
    started_at: datetime
    volume_id: str = Field(min_length=1, max_length=128)
    volume_size_gib: int = Field(gt=0)
    description: str = Field(default="", max_length=1024)
    storage_tier: str = Field(default="standard", min_length=1, max_length=32)
    tags: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("resource")
    @classmethod
    def require_ebs_snapshot_resource(cls, value: ResourceReference) -> ResourceReference:
        """Prevent evaluating a non-snapshot resource with this rule."""
        if value.resource_type is not ResourceType.EBS_SNAPSHOT:
            raise ValueError("EbsSnapshot.resource.resource_type must be ebs_snapshot")
        return value


class Ec2Instance(BaseModel):
    """Provider-neutral EC2 fields needed for utilization recommendations."""

    resource: ResourceReference
    instance_type: str = Field(min_length=1, max_length=64)
    launched_at: datetime
    tags: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("resource")
    @classmethod
    def require_ec2_instance_resource(cls, value: ResourceReference) -> ResourceReference:
        """Prevent evaluating another resource type with the EC2 recommendation rule."""
        if value.resource_type is not ResourceType.EC2_INSTANCE:
            raise ValueError("Ec2Instance.resource.resource_type must be ec2_instance")
        return value


class RdsInstance(BaseModel):
    """Provider-neutral RDS fields used for conservative utilization recommendations."""

    resource: ResourceReference
    instance_class: str = Field(min_length=1, max_length=64)
    engine: str = Field(min_length=1, max_length=64)
    created_at: datetime
    multi_az: bool
    db_cluster_identifier: str | None = None
    read_replica_source_identifier: str | None = None
    tags: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("resource")
    @classmethod
    def require_rds_instance_resource(cls, value: ResourceReference) -> ResourceReference:
        """Prevent evaluating another resource type with the RDS recommendation rule."""
        if value.resource_type is not ResourceType.RDS_INSTANCE:
            raise ValueError("RdsInstance.resource.resource_type must be rds_instance")
        return value


class ApplicationLoadBalancer(BaseModel):
    """Provider-neutral ALB fields used for request-volume recommendations."""

    resource: ResourceReference
    name: str = Field(min_length=1, max_length=128)
    cloudwatch_dimension_value: str = Field(min_length=1, max_length=512)
    scheme: str = Field(min_length=1, max_length=32)
    created_at: datetime
    tags: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("resource")
    @classmethod
    def require_application_load_balancer_resource(
        cls, value: ResourceReference
    ) -> ResourceReference:
        """Prevent evaluating another resource type with the ALB recommendation rule."""
        if value.resource_type is not ResourceType.APPLICATION_LOAD_BALANCER:
            raise ValueError(
                "ApplicationLoadBalancer.resource.resource_type must be application_load_balancer"
            )
        return value


class MetricWindow(BaseModel):
    """A complete CloudWatch metric observation window, free of AWS SDK structures."""

    metric_name: str = Field(min_length=1, max_length=128)
    statistic: MetricStatistic
    sample_count: int = Field(ge=0)
    expected_sample_count: int = Field(gt=0)
    value: Decimal | None = None

    @property
    def is_complete(self) -> bool:
        """Require every expected daily observation before drawing a utilization conclusion."""
        return self.sample_count >= self.expected_sample_count

    @property
    def has_values(self) -> bool:
        """Return whether CloudWatch returned one or more usable values for the metric."""
        return self.value is not None


class MetricStatistic(StrEnum):
    """CloudWatch aggregate statistic required by a metric observation query."""

    MAXIMUM = "Maximum"
    SUM = "Sum"


class MetricQuery(BaseModel):
    """Provider-neutral description of a daily CloudWatch metric observation query."""

    namespace: str = Field(min_length=1, max_length=256)
    metric_name: str = Field(min_length=1, max_length=128)
    statistic: MetricStatistic
    dimensions: Mapping[str, str] = Field(min_length=1)
    start_at: datetime
    end_at: datetime
    expected_sample_count: int = Field(gt=0, le=3660)

    @field_validator("end_at")
    @classmethod
    def require_timezone_aware_end(cls, value: datetime) -> datetime:
        """Avoid ambiguous CloudWatch request boundaries."""
        if value.tzinfo is None:
            raise ValueError("end_at must be timezone-aware")
        return value

    @field_validator("start_at")
    @classmethod
    def require_timezone_aware_start(cls, value: datetime) -> datetime:
        """Avoid ambiguous CloudWatch request boundaries."""
        if value.tzinfo is None:
            raise ValueError("start_at must be timezone-aware")
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
