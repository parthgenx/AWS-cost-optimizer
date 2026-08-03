"""Ports implemented by infrastructure adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from cost_optimization.domain.findings import Finding, ScanRun
from cost_optimization.domain.models import EbsVolume, FindingCandidate


class EbsVolumeDiscovery(Protocol):
    """Retrieves EBS volumes that could be evaluated by detection rules."""

    def list_unattached_volumes(self) -> list[EbsVolume]:
        """Return only currently unattached EBS volumes."""


class FindingRepository(Protocol):
    """Records an observed finding without exposing persistence details."""

    def record_detection(self, candidate: FindingCandidate, detected_at: datetime) -> Finding:
        """Create or refresh the durable finding for an observed candidate."""


class ScanRunRepository(Protocol):
    """Records execution-level scanner state for auditability and operations."""

    def create(self, scan_run: ScanRun) -> None:
        """Persist a newly started scan run."""

    def complete(
        self, scan_run: ScanRun, *, completed_at: datetime, evaluated_count: int, finding_count: int
    ) -> None:
        """Mark a running scan successful with its outcome counts."""

    def fail(self, scan_run: ScanRun, *, completed_at: datetime, failure_type: str) -> None:
        """Mark a running scan failed without persisting sensitive error details."""
