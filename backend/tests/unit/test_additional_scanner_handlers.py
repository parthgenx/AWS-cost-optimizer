from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cost_optimization.config import Environment, Settings
from cost_optimization.domain.findings import ScanRun
from cost_optimization.workers import ebs_snapshot_scanner, elastic_ip_scanner


@pytest.mark.parametrize(
    ("module", "scanner_name"),
    [
        (elastic_ip_scanner, "unassociated-elastic-ip"),
        (ebs_snapshot_scanner, "old-manual-ebs-snapshot"),
    ],
)
def test_run_scan_returns_a_safe_summary(
    monkeypatch: pytest.MonkeyPatch, module: object, scanner_name: str
) -> None:
    completed = ScanRun(
        scan_id="scan-123",
        scanner_name=scanner_name,
        started_at=datetime(2026, 8, 12, tzinfo=UTC),
        completed_at=datetime(2026, 8, 12, tzinfo=UTC),
        status="completed",
        evaluated_resource_count=2,
        finding_count=1,
    )
    workflow = FakeWorkflow(completed)
    monkeypatch.setattr(module, "build_workflow", lambda _settings, _account_id: workflow)

    result = module.run_scan(
        _settings(), "123456789012", evaluated_at=datetime(2026, 8, 12, tzinfo=UTC)
    )

    assert workflow.executed
    assert result == {
        "scan_id": "scan-123",
        "status": "completed",
        "evaluated_resource_count": 2,
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
