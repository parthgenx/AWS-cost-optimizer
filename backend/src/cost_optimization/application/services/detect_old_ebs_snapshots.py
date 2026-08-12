"""Application service for pure old-manual EBS snapshot detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cost_optimization.domain.models import FindingCandidate
from cost_optimization.domain.ports import EbsSnapshotDiscovery
from cost_optimization.domain.rules.old_ebs_snapshot import OldManualEbsSnapshotRule


@dataclass(frozen=True)
class OldEbsSnapshotDetectionResult:
    """Counts and finding candidates generated from one snapshot discovery pass."""

    evaluated_resource_count: int
    findings: tuple[FindingCandidate, ...]


class DetectOldEbsSnapshots:
    """Discover account-owned snapshots and evaluate them without AWS SDK types."""

    def __init__(self, discovery: EbsSnapshotDiscovery, rule: OldManualEbsSnapshotRule) -> None:
        self._discovery = discovery
        self._rule = rule

    def execute(self, evaluated_at: datetime) -> OldEbsSnapshotDetectionResult:
        """Return review candidates for snapshots that satisfy conservative rule conditions."""
        snapshots = self._discovery.list_owned_snapshots()
        findings = tuple(
            candidate
            for snapshot in snapshots
            if (candidate := self._rule.evaluate(snapshot, evaluated_at)) is not None
        )
        return OldEbsSnapshotDetectionResult(
            evaluated_resource_count=len(snapshots), findings=findings
        )
