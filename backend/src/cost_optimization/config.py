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


class Settings(BaseModel):
    """Validated settings shared by API and future worker entry points."""

    service_name: str = "cost-optimization-api"
    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    version: str = "0.1.0"
    aws_region: str | None = Field(default=None, min_length=1, max_length=64)
    findings_table_name: str | None = Field(default=None, min_length=3, max_length=255)
    scan_runs_table_name: str | None = Field(default=None, min_length=3, max_length=255)
    ebs_unattached_minimum_volume_age_days: int = Field(default=14, ge=1, le=3650)
    ebs_reference_gib_monthly_rate_usd: Decimal = Field(default=Decimal("0.08"), gt=Decimal("0"))

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
                "ebs_unattached_minimum_volume_age_days": os.getenv(
                    "COST_OPTIMIZER_EBS_UNATTACHED_MINIMUM_VOLUME_AGE_DAYS", "14"
                ),
                "ebs_reference_gib_monthly_rate_usd": os.getenv(
                    "COST_OPTIMIZER_EBS_REFERENCE_GIB_MONTHLY_RATE_USD", "0.08"
                ),
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


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide immutable settings instance."""
    return Settings.from_environment()
