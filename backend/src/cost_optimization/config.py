"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from decimal import Decimal
from enum import StrEnum
from functools import lru_cache

from pydantic import BaseModel, Field, field_validator


class Environment(StrEnum):
    """Supported application environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class OperatorIdentitySource(StrEnum):
    """Trusted transport mechanisms for the identity recorded in an audit event."""

    TRUSTED_HEADER = "trusted_header"
    API_GATEWAY_JWT = "api_gateway_jwt"


class Settings(BaseModel):
    """Validated settings shared by API and future worker entry points."""

    service_name: str = "cost-optimization-api"
    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    version: str = "0.1.0"
    aws_region: str | None = Field(default=None, min_length=1, max_length=64)
    findings_table_name: str | None = Field(default=None, min_length=3, max_length=255)
    scan_runs_table_name: str | None = Field(default=None, min_length=3, max_length=255)
    audit_events_table_name: str | None = Field(default=None, min_length=3, max_length=255)
    scan_notifications_topic_arn: str | None = Field(default=None, min_length=1, max_length=2048)
    cleanup_dry_run: bool = True
    cleanup_execution_enabled: bool = False
    operator_identity_source: OperatorIdentitySource = OperatorIdentitySource.TRUSTED_HEADER
    required_operator_group: str = Field(
        default="cost-optimizer-operators", min_length=1, max_length=128
    )
    ebs_unattached_minimum_volume_age_days: int = Field(default=14, ge=1, le=3650)
    ebs_reference_gib_monthly_rate_usd: Decimal = Field(default=Decimal("0.08"), gt=Decimal("0"))
    elastic_ip_reference_monthly_rate_usd: Decimal = Field(default=Decimal("3.60"), gt=Decimal("0"))
    ebs_snapshot_minimum_age_days: int = Field(default=90, ge=1, le=3650)
    utilization_lookback_days: int = Field(default=14, ge=1, le=90)
    ec2_maximum_cpu_percent: Decimal = Field(
        default=Decimal("5"), ge=Decimal("0"), le=Decimal("100")
    )
    ec2_maximum_total_network_bytes: Decimal = Field(default=Decimal("1073741824"), ge=Decimal("0"))
    rds_maximum_cpu_percent: Decimal = Field(
        default=Decimal("5"), ge=Decimal("0"), le=Decimal("100")
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Normalise accepted standard-library log level names."""
        normalized = value.upper()
        allowed_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if normalized not in allowed_levels:
            message = f"log_level must be one of {sorted(allowed_levels)}"
            raise ValueError(message)
        return normalized

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_deployment_environment(cls, value: object) -> object:
        """Translate short infrastructure environment labels to canonical values."""
        if isinstance(value, str):
            return {"dev": "development", "prod": "production"}.get(value.lower(), value)
        return value

    @classmethod
    def from_environment(cls) -> Settings:
        """Build settings from the process environment."""
        return cls.model_validate(
            {
                "service_name": os.getenv("COST_OPTIMIZER_SERVICE_NAME", "cost-optimization-api"),
                "environment": os.getenv("COST_OPTIMIZER_ENVIRONMENT", Environment.DEVELOPMENT),
                "log_level": os.getenv("COST_OPTIMIZER_LOG_LEVEL", "INFO"),
                "version": os.getenv("COST_OPTIMIZER_VERSION", "0.1.0"),
                "aws_region": os.getenv("AWS_REGION"),
                "findings_table_name": os.getenv("COST_OPTIMIZER_FINDINGS_TABLE_NAME"),
                "scan_runs_table_name": os.getenv("COST_OPTIMIZER_SCAN_RUNS_TABLE_NAME"),
                "audit_events_table_name": os.getenv("COST_OPTIMIZER_AUDIT_EVENTS_TABLE_NAME"),
                "scan_notifications_topic_arn": os.getenv(
                    "COST_OPTIMIZER_SCAN_NOTIFICATIONS_TOPIC_ARN"
                ),
                "cleanup_dry_run": os.getenv("COST_OPTIMIZER_CLEANUP_DRY_RUN", "true"),
                "cleanup_execution_enabled": os.getenv(
                    "COST_OPTIMIZER_CLEANUP_EXECUTION_ENABLED", "false"
                ),
                "operator_identity_source": os.getenv(
                    "COST_OPTIMIZER_OPERATOR_IDENTITY_SOURCE", "trusted_header"
                ),
                "required_operator_group": os.getenv(
                    "COST_OPTIMIZER_REQUIRED_OPERATOR_GROUP", "cost-optimizer-operators"
                ),
                "ebs_unattached_minimum_volume_age_days": os.getenv(
                    "COST_OPTIMIZER_EBS_UNATTACHED_MINIMUM_VOLUME_AGE_DAYS", "14"
                ),
                "ebs_reference_gib_monthly_rate_usd": os.getenv(
                    "COST_OPTIMIZER_EBS_REFERENCE_GIB_MONTHLY_RATE_USD", "0.08"
                ),
                "elastic_ip_reference_monthly_rate_usd": os.getenv(
                    "COST_OPTIMIZER_ELASTIC_IP_REFERENCE_MONTHLY_RATE_USD", "3.60"
                ),
                "ebs_snapshot_minimum_age_days": os.getenv(
                    "COST_OPTIMIZER_EBS_SNAPSHOT_MINIMUM_AGE_DAYS", "90"
                ),
                "utilization_lookback_days": os.getenv(
                    "COST_OPTIMIZER_UTILIZATION_LOOKBACK_DAYS", "14"
                ),
                "ec2_maximum_cpu_percent": os.getenv("COST_OPTIMIZER_EC2_MAXIMUM_CPU_PERCENT", "5"),
                "ec2_maximum_total_network_bytes": os.getenv(
                    "COST_OPTIMIZER_EC2_MAXIMUM_TOTAL_NETWORK_BYTES", "1073741824"
                ),
                "rds_maximum_cpu_percent": os.getenv("COST_OPTIMIZER_RDS_MAXIMUM_CPU_PERCENT", "5"),
            }
        )

    def require_scanner_configuration(self) -> tuple[str, str, str]:
        """Return the Lambda-only settings required to run a persisted scan."""
        if not self.aws_region:
            raise RuntimeError("AWS_REGION is required for the scanner Lambda")
        if not self.findings_table_name:
            raise RuntimeError("COST_OPTIMIZER_FINDINGS_TABLE_NAME is required")
        if not self.scan_runs_table_name:
            raise RuntimeError("COST_OPTIMIZER_SCAN_RUNS_TABLE_NAME is required")
        return self.aws_region, self.findings_table_name, self.scan_runs_table_name

    def require_approval_configuration(self) -> tuple[str, str]:
        """Return table names required by an approval workflow."""
        if not self.findings_table_name:
            raise RuntimeError("COST_OPTIMIZER_FINDINGS_TABLE_NAME is required")
        if not self.audit_events_table_name:
            raise RuntimeError("COST_OPTIMIZER_AUDIT_EVENTS_TABLE_NAME is required")
        return self.findings_table_name, self.audit_events_table_name

    def require_cleanup_configuration(self) -> tuple[str, str, str]:
        """Return the minimum settings required by the isolated cleanup Lambda."""
        if not self.aws_region:
            raise RuntimeError("AWS_REGION is required for the cleanup Lambda")
        findings_table_name, audit_events_table_name = self.require_approval_configuration()
        return self.aws_region, findings_table_name, audit_events_table_name


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide immutable settings instance."""
    return Settings.from_environment()
