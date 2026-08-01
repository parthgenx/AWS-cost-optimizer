"""Read-only use case for evaluating unattached EBS volumes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cost_optimization.domain.models import FindingCandidate
from cost_optimization.domain.ports import EbsVolumeDiscovery
from cost_optimization.domain.rules.unattached_ebs_volume import UnattachedEbsVolumeRule


@dataclass(frozen=True)
class UnattachedEbsVolumeDetectionResult:
    """Outcome of one deterministic, read-only EBS detection run."""

    evaluated_volume_count: int
    findings: tuple[FindingCandidate, ...]


class DetectUnattachedEbsVolumes:
    """Coordinates discovery and pure rule evaluation without persistence."""

    def __init__(self, discovery: EbsVolumeDiscovery, rule: UnattachedEbsVolumeRule) -> None:
        self._discovery = discovery
        self._rule = rule

    def execute(self, evaluated_at: datetime) -> UnattachedEbsVolumeDetectionResult:
        """Evaluate all discovered unattached volumes at a supplied point in time."""
        volumes = self._discovery.list_unattached_volumes()
        findings = tuple(
            candidate
            for volume in volumes
            if (candidate := self._rule.evaluate(volume, evaluated_at)) is not None
        )
        return UnattachedEbsVolumeDetectionResult(
            evaluated_volume_count=len(volumes), findings=findings
        )
