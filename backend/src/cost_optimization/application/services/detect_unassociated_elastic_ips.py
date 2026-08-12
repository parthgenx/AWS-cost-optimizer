"""Application service for pure unassociated Elastic IP detection."""

from __future__ import annotations

from dataclasses import dataclass

from cost_optimization.domain.models import FindingCandidate
from cost_optimization.domain.ports import ElasticIpDiscovery
from cost_optimization.domain.rules.unassociated_elastic_ip import UnassociatedElasticIpRule


@dataclass(frozen=True)
class UnassociatedElasticIpDetectionResult:
    """Counts and finding candidates generated from one Elastic IP discovery pass."""

    evaluated_resource_count: int
    findings: tuple[FindingCandidate, ...]


class DetectUnassociatedElasticIps:
    """Discover addresses and evaluate them without depending on AWS SDK types."""

    def __init__(self, discovery: ElasticIpDiscovery, rule: UnassociatedElasticIpRule) -> None:
        self._discovery = discovery
        self._rule = rule

    def execute(self) -> UnassociatedElasticIpDetectionResult:
        """Return candidates for all currently unassociated, non-excluded addresses."""
        addresses = self._discovery.list_addresses()
        findings = tuple(
            candidate
            for address in addresses
            if (candidate := self._rule.evaluate(address)) is not None
        )
        return UnassociatedElasticIpDetectionResult(
            evaluated_resource_count=len(addresses), findings=findings
        )
