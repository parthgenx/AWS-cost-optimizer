from __future__ import annotations

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

    settings = Settings.from_environment()

    assert settings.environment is Environment.STAGING
    assert settings.log_level == "WARNING"
