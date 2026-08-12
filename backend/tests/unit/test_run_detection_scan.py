from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cost_optimization.application.services.run_detection_scan import (
    DetectionScanResult,
    RunDetectionScan,
)
from cost_optimization.domain.findings import Finding, ScanRun
from cost_optimization.domain.models import (
    FindingCandidate,
    FindingSeverity,
    Money,
    ResourceReference,
    ResourceType,
)


def test_generic_scan_workflow_persists_candidates_and_a_terminal_scan_record() -> None:
    findings = FakeFindingRepository()
    scan_runs = FakeScanRunRepository()
    now = datetime(2026, 8, 12, tzinfo=UTC)
    workflow = RunDetectionScan(
        scanner_name="unassociated-elastic-ip",
        detector=lambda _: DetectionScanResult(
            evaluated_resource_count=1, findings=(_candidate(),)
        ),
        findings=findings,
        scan_runs=scan_runs,
    )

    completed = workflow.execute(now)

    assert completed.status == "completed"
    assert findings.recorded == [_candidate().resource.resource_id]
    assert scan_runs.completed == [(1, 1)]


def test_generic_scan_workflow_records_a_sanitized_failure_type() -> None:
    scan_runs = FakeScanRunRepository()
    workflow = RunDetectionScan(
        scanner_name="unassociated-elastic-ip",
        detector=lambda _: _raise_runtime_error(),
        findings=FakeFindingRepository(),
        scan_runs=scan_runs,
    )

    with pytest.raises(RuntimeError, match="simulated"):
        workflow.execute(datetime(2026, 8, 12, tzinfo=UTC))

    assert scan_runs.failed == ["RuntimeError"]


class FakeFindingRepository:
    def __init__(self) -> None:
        self.recorded: list[str] = []

    def record_detection(self, candidate: FindingCandidate, detected_at: datetime) -> Finding:
        assert detected_at.tzinfo is not None
        self.recorded.append(candidate.resource.resource_id)
        return Finding.from_candidate(candidate, detected_at)


class FakeScanRunRepository:
    def __init__(self) -> None:
        self.completed: list[tuple[int, int]] = []
        self.failed: list[str] = []

    def create(self, scan_run: ScanRun) -> None:
        assert scan_run.status == "running"

    def complete(
        self, scan_run: ScanRun, *, completed_at: datetime, evaluated_count: int, finding_count: int
    ) -> None:
        assert scan_run.status == "running"
        assert completed_at.tzinfo is not None
        self.completed.append((evaluated_count, finding_count))

    def fail(self, scan_run: ScanRun, *, completed_at: datetime, failure_type: str) -> None:
        assert scan_run.status == "running"
        assert completed_at.tzinfo is not None
        self.failed.append(failure_type)


def _raise_runtime_error() -> DetectionScanResult:
    raise RuntimeError("simulated detector failure")


def _candidate() -> FindingCandidate:
    return FindingCandidate(
        rule_id="unassociated-elastic-ip",
        resource=ResourceReference(
            resource_type=ResourceType.ELASTIC_IP,
            resource_id="eipalloc-123",
            account_id="123456789012",
            region="ap-south-1",
        ),
        summary="Address is not associated.",
        recommended_action="Review the address.",
        severity=FindingSeverity.LOW,
        estimated_monthly_savings=Money(amount=Decimal("3.60"), currency="USD"),
    )
