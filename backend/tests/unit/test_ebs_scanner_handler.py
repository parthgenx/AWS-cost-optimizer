from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cost_optimization.config import Environment, Settings
from cost_optimization.domain.findings import ScanRun
from cost_optimization.workers import ebs_scanner


def test_run_scan_composes_workflow_and_returns_safe_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed_scan = ScanRun(
        scan_id="scan-123",
        scanner_name="unattached-ebs-volume",
        started_at=datetime(2026, 8, 4, tzinfo=UTC),
        completed_at=datetime(2026, 8, 4, tzinfo=UTC),
        status="completed",
        evaluated_resource_count=3,
        finding_count=1,
    )
    workflow = FakeWorkflow(completed_scan)
    captured: dict[str, object] = {}

    def build_workflow(settings: Settings, account_id: str) -> FakeWorkflow:
        captured["settings"] = settings
        captured["account_id"] = account_id
        return workflow

    monkeypatch.setattr(ebs_scanner, "build_workflow", build_workflow)
    settings = _scanner_settings()
    now = datetime(2026, 8, 4, tzinfo=UTC)

    result = ebs_scanner.run_scan(FakeContext(), settings, evaluated_at=now)

    assert captured["account_id"] == "123456789012"
    assert workflow.evaluated_at == now
    assert result == {
        "scan_id": "scan-123",
        "status": "completed",
        "evaluated_resource_count": 3,
        "finding_count": 1,
    }


def test_account_id_from_lambda_arn_rejects_invalid_arns() -> None:
    with pytest.raises(ValueError, match="valid Lambda ARN"):
        ebs_scanner.account_id_from_lambda_arn("not-an-arn")


def test_settings_require_scanner_configuration() -> None:
    assert _scanner_settings().require_scanner_configuration() == (
        "ap-south-1",
        "findings-table",
        "scan-runs-table",
    )


class FakeContext:
    invoked_function_arn = "arn:aws:lambda:ap-south-1:123456789012:function:ebs-scanner"


class FakeWorkflow:
    def __init__(self, completed_scan: ScanRun) -> None:
        self._completed_scan = completed_scan
        self.evaluated_at: datetime | None = None

    def execute(self, evaluated_at: datetime) -> ScanRun:
        self.evaluated_at = evaluated_at
        return self._completed_scan


def _scanner_settings() -> Settings:
    return Settings(
        environment=Environment.TESTING,
        aws_region="ap-south-1",
        findings_table_name="findings-table",
        scan_runs_table_name="scan-runs-table",
    )
