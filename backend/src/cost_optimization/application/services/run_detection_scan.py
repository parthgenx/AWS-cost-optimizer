"""Shared persistence workflow for a single resource-specific detection result."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from cost_optimization.domain.findings import ScanRun
from cost_optimization.domain.models import FindingCandidate
from cost_optimization.domain.ports import FindingRepository, ScanRunRepository


@dataclass(frozen=True)
class DetectionScanResult:
    """Uniform result shape emitted by individual resource detection services."""

    evaluated_resource_count: int
    findings: tuple[FindingCandidate, ...]


class RunDetectionScan:
    """Persist one scanner run while keeping the resource-specific detector pure."""

    def __init__(
        self,
        *,
        scanner_name: str,
        detector: Callable[[datetime], DetectionScanResult],
        findings: FindingRepository,
        scan_runs: ScanRunRepository,
    ) -> None:
        self._scanner_name = scanner_name
        self._detector = detector
        self._findings = findings
        self._scan_runs = scan_runs

    def execute(self, evaluated_at: datetime) -> ScanRun:
        """Persist candidates and a terminal scan record, or a sanitized failure type."""
        scan_run = ScanRun.start(self._scanner_name, evaluated_at)
        self._scan_runs.create(scan_run)
        try:
            result = self._detector(evaluated_at)
            for candidate in result.findings:
                self._findings.record_detection(candidate, evaluated_at)
            self._scan_runs.complete(
                scan_run,
                completed_at=evaluated_at,
                evaluated_count=result.evaluated_resource_count,
                finding_count=len(result.findings),
            )
            return scan_run.model_copy(
                update={
                    "status": "completed",
                    "completed_at": evaluated_at,
                    "evaluated_resource_count": result.evaluated_resource_count,
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
