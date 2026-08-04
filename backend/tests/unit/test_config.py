from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cost_optimization.config import Environment, Settings


def test_settings_normalize_log_level() -> None:
    settings = Settings(log_level="debug")

    assert settings.log_level == "DEBUG"


def test_settings_reject_unknown_log_level() -> None:
    with pytest.raises(ValidationError, match="log_level must be one of"):
        Settings(log_level="verbose")


def test_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COST_OPTIMIZER_ENVIRONMENT", "staging")
    monkeypatch.setenv("COST_OPTIMIZER_LOG_LEVEL", "warning")
    monkeypatch.setenv("COST_OPTIMIZER_EBS_UNATTACHED_MINIMUM_VOLUME_AGE_DAYS", "21")
    monkeypatch.setenv("COST_OPTIMIZER_EBS_REFERENCE_GIB_MONTHLY_RATE_USD", "0.10")

    settings = Settings.from_environment()

    assert settings.environment is Environment.STAGING
    assert settings.log_level == "WARNING"
    assert settings.ebs_unattached_minimum_volume_age_days == 21
    assert settings.ebs_reference_gib_monthly_rate_usd == Decimal("0.10")


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        (Settings(), "AWS_REGION"),
        (Settings(aws_region="ap-south-1"), "FINDINGS_TABLE_NAME"),
        (
            Settings(aws_region="ap-south-1", findings_table_name="findings-table"),
            "SCAN_RUNS_TABLE_NAME",
        ),
    ],
)
def test_settings_reject_incomplete_scanner_configuration(settings: Settings, message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        settings.require_scanner_configuration()
