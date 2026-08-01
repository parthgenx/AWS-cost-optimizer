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
                "ebs_unattached_minimum_volume_age_days": os.getenv(
                    "COST_OPTIMIZER_EBS_UNATTACHED_MINIMUM_VOLUME_AGE_DAYS", "14"
                ),
                "ebs_reference_gib_monthly_rate_usd": os.getenv(
                    "COST_OPTIMIZER_EBS_REFERENCE_GIB_MONTHLY_RATE_USD", "0.08"
                ),
            }
        )


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide immutable settings instance."""
    return Settings.from_environment()
