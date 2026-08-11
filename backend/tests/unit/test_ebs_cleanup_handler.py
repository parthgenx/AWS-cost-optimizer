from __future__ import annotations

from datetime import datetime

import pytest

from cost_optimization.application.services.run_approved_ebs_cleanup import CleanupExecutionResult
from cost_optimization.config import Environment, Settings
from cost_optimization.workers import ebs_cleanup


def test_run_cleanup_forces_dry_run_when_execution_is_not_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = FakeWorkflow()
    monkeypatch.setattr(ebs_cleanup, "build_workflow", lambda _settings, _account_id: workflow)

    result = ebs_cleanup.run_cleanup(
        {"detail": {"finding_id": "finding-123"}},
        _cleanup_settings(cleanup_dry_run=False, cleanup_execution_enabled=False),
        "123456789012",
    )

    assert workflow.call == ("finding-123", True)
    assert result == {"finding_id": "finding-123", "outcome": "dry_run_ready", "dry_run": True}


def test_cleanup_event_requires_a_finding_id() -> None:
    with pytest.raises(ValueError, match="finding_id"):
        ebs_cleanup._finding_id_from_event({"detail": {}})


class FakeWorkflow:
    def __init__(self) -> None:
        self.call: tuple[str, bool] | None = None

    def execute(
        self, *, finding_id: str, executed_at: datetime, dry_run: bool
    ) -> CleanupExecutionResult:
        assert executed_at.tzinfo is not None
        self.call = (finding_id, dry_run)
        return CleanupExecutionResult(
            finding_id=finding_id, outcome="dry_run_ready", dry_run=dry_run
        )


def _cleanup_settings(*, cleanup_dry_run: bool, cleanup_execution_enabled: bool) -> Settings:
    return Settings(
        environment=Environment.TESTING,
        aws_region="ap-south-1",
        findings_table_name="findings-table",
        audit_events_table_name="audit-events-table",
        cleanup_dry_run=cleanup_dry_run,
        cleanup_execution_enabled=cleanup_execution_enabled,
    )
