from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cost_optimization.application.services.detect_unattached_ebs_volumes import (
    UnattachedEbsVolumeDetectionResult,
)
from cost_optimization.application.services.run_ebs_detection_scan import RunEbsDetectionScan
from cost_optimization.domain.findings import Finding, ScanRun
from cost_optimization.domain.models import (
    FindingCandidate,
    FindingSeverity,
    Money,
    ResourceReference,
    ResourceType,
)


def test_scan_workflow_persists_findings_and_completed_scan() -> None:
    candidate = _candidate()
    findings = FakeFindingRepository()
    scan_runs = FakeScanRunRepository()
    workflow = RunEbsDetectionScan(FakeDetector([candidate]), findings, scan_runs)
    now = datetime(2026, 8, 3, tzinfo=UTC)

    completed = workflow.execute(now)

    assert completed.status == "completed"
    assert completed.finding_count == 1
    assert findings.recorded == [(candidate, now)]
    assert scan_runs.created == [completed.scan_id]
    assert scan_runs.completed == [(completed.scan_id, 0, 1)]


def test_scan_workflow_records_failure_type_and_reraises() -> None:
    scan_runs = FakeScanRunRepository()
    workflow = RunEbsDetectionScan(FailingDetector(), FakeFindingRepository(), scan_runs)
    now = datetime(2026, 8, 3, tzinfo=UTC)

    with pytest.raises(RuntimeError, match="simulated"):
        workflow.execute(now)

    assert scan_runs.failed == [("RuntimeError", now)]


class FakeDetector:
    def __init__(self, findings: list[FindingCandidate]) -> None:
        self._findings = findings

    def execute(self, _: datetime) -> UnattachedEbsVolumeDetectionResult:
        return UnattachedEbsVolumeDetectionResult(
            evaluated_volume_count=0, findings=tuple(self._findings)
        )


class FailingDetector:
    def execute(self, _: datetime) -> UnattachedEbsVolumeDetectionResult:
        raise RuntimeError("simulated discovery failure")


class FakeFindingRepository:
    def __init__(self) -> None:
        self.recorded: list[tuple[FindingCandidate, datetime]] = []

    def record_detection(self, candidate: FindingCandidate, detected_at: datetime) -> Finding:
        self.recorded.append((candidate, detected_at))
        return Finding.from_candidate(candidate, detected_at)


class FakeScanRunRepository:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.completed: list[tuple[str, int, int]] = []
        self.failed: list[tuple[str, datetime]] = []

    def create(self, scan_run: ScanRun) -> None:
        self.created.append(scan_run.scan_id)

    def complete(
        self, scan_run: ScanRun, *, completed_at: datetime, evaluated_count: int, finding_count: int
    ) -> None:
        assert completed_at.tzinfo is not None
        self.completed.append((scan_run.scan_id, evaluated_count, finding_count))

    def fail(self, scan_run: ScanRun, *, completed_at: datetime, failure_type: str) -> None:
        assert scan_run.status == "running"
        self.failed.append((failure_type, completed_at))


def _candidate() -> FindingCandidate:
    return FindingCandidate(
        rule_id="unattached-ebs-volume",
        resource=ResourceReference(
            resource_type=ResourceType.EBS_VOLUME,
            resource_id="vol-0123456789abcdef0",
            region="ap-south-1",
            account_id="123456789012",
        ),
        summary="Volume is currently unattached.",
        recommended_action="Review the volume.",
        severity=FindingSeverity.LOW,
        estimated_monthly_savings=Money(amount=Decimal("1.60"), currency="USD"),
        evidence={"state": "available"},
    )
