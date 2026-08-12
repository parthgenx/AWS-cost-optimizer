from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cost_optimization.config import Environment, Settings
from cost_optimization.domain.findings import ScanRun
from cost_optimization.workers import (
    application_load_balancer_scanner,
    ec2_utilization_scanner,
    rds_utilization_scanner,
)


@pytest.mark.parametrize(
    ("module", "scanner_name"),
    [
        (ec2_utilization_scanner, "sustained-low-utilization-ec2-instance"),
        (rds_utilization_scanner, "sustained-low-utilization-rds-instance"),
        (application_load_balancer_scanner, "no-request-application-load-balancer"),
    ],
)
def test_utilization_scanner_returns_safe_completion_summary(
    monkeypatch: pytest.MonkeyPatch, module: object, scanner_name: str
) -> None:
    workflow = FakeWorkflow(
        ScanRun(
            scan_id="scan-123",
            scanner_name=scanner_name,
            started_at=datetime(2026, 8, 12, tzinfo=UTC),
            completed_at=datetime(2026, 8, 12, tzinfo=UTC),
            status="completed",
            evaluated_resource_count=1,
            finding_count=1,
        )
    )
    monkeypatch.setattr(module, "build_workflow", lambda _settings, _account_id: workflow)

    result = module.run_scan(
        _settings(), "123456789012", evaluated_at=datetime(2026, 8, 12, tzinfo=UTC)
    )

    assert workflow.executed
    assert result == {
        "scan_id": "scan-123",
        "status": "completed",
        "evaluated_resource_count": 1,
        "finding_count": 1,
    }


class FakeWorkflow:
    def __init__(self, scan_run: ScanRun) -> None:
        self._scan_run = scan_run
        self.executed = False

    def execute(self, evaluated_at: datetime) -> ScanRun:
        assert evaluated_at.tzinfo is not None
        self.executed = True
        return self._scan_run


def _settings() -> Settings:
    return Settings(
        environment=Environment.TESTING,
        aws_region="ap-south-1",
        findings_table_name="findings-table",
        scan_runs_table_name="scan-runs-table",
    )
