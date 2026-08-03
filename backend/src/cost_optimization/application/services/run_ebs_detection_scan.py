"""Application workflow that persists one read-only EBS detection scan."""

from __future__ import annotations

from datetime import datetime

from cost_optimization.application.services.detect_unattached_ebs_volumes import (
    DetectUnattachedEbsVolumes,
)
from cost_optimization.domain.findings import ScanRun
from cost_optimization.domain.ports import FindingRepository, ScanRunRepository

SCANNER_NAME = "unattached-ebs-volume"


class RunEbsDetectionScan:
    """Run detection, persist candidates, and record an auditable scan outcome."""

    def __init__(
        self,
        detector: DetectUnattachedEbsVolumes,
        findings: FindingRepository,
        scan_runs: ScanRunRepository,
    ) -> None:
        self._detector = detector
        self._findings = findings
        self._scan_runs = scan_runs

    def execute(self, evaluated_at: datetime) -> ScanRun:
        """Persist an EBS scan result or capture its sanitized failure type."""
        scan_run = ScanRun.start(SCANNER_NAME, evaluated_at)
        self._scan_runs.create(scan_run)
        try:
            result = self._detector.execute(evaluated_at)
            for candidate in result.findings:
                self._findings.record_detection(candidate, evaluated_at)
            self._scan_runs.complete(
                scan_run,
                completed_at=evaluated_at,
                evaluated_count=result.evaluated_volume_count,
                finding_count=len(result.findings),
            )
            return scan_run.model_copy(
                update={
                    "status": "completed",
                    "completed_at": evaluated_at,
                    "evaluated_resource_count": result.evaluated_volume_count,
                    "finding_count": len(result.findings),
                }
            )
        except Exception as error:
            self._scan_runs.fail(
                scan_run,
                completed_at=evaluated_at,
                failure_type=type(error).__name__,
            )
            raise
