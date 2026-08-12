"""Detection rule for Elastic IP addresses not associated with a resource."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from cost_optimization.domain.models import (
    ElasticIpAddress,
    FindingCandidate,
    FindingSeverity,
    Money,
)
from cost_optimization.domain.policies.resource_exclusion import is_excluded_from_optimization

RULE_ID = "unassociated-elastic-ip"


@dataclass(frozen=True)
class UnassociatedElasticIpRuleConfig:
    """Price assumption used for a transparent Elastic IP savings estimate."""

    reference_monthly_rate_usd: Decimal

    def __post_init__(self) -> None:
        if self.reference_monthly_rate_usd <= Decimal("0"):
            raise ValueError("reference_monthly_rate_usd must be positive")


class UnassociatedElasticIpRule:
    """Creates review findings for definitively unassociated Elastic IP addresses."""

    def __init__(self, config: UnassociatedElasticIpRuleConfig) -> None:
        self._config = config

    def evaluate(self, address: ElasticIpAddress) -> FindingCandidate | None:
        """Return a candidate only when the address has no current association fields."""
        if is_excluded_from_optimization(address.tags):
            return None
        if address.association_id or address.network_interface_id or address.instance_id:
            return None

        savings = Money(
            amount=self._config.reference_monthly_rate_usd.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            currency="USD",
        )
        return FindingCandidate(
            rule_id=RULE_ID,
            resource=address.resource,
            summary=f"Elastic IP {address.public_ip} is not associated with an AWS resource.",
            recommended_action=(
                "Review and release the Elastic IP if it is no longer reserved intentionally."
            ),
            severity=_severity_for(savings),
            estimated_monthly_savings=savings,
            evidence={
                "allocation_id": address.allocation_id,
                "public_ip": address.public_ip,
                "association_id": "",
                "network_interface_id": "",
                "instance_id": "",
                "reference_monthly_rate_usd": str(self._config.reference_monthly_rate_usd),
            },
        )


def _severity_for(savings: Money) -> FindingSeverity:
    if savings.amount >= Decimal("50"):
        return FindingSeverity.HIGH
    if savings.amount >= Decimal("10"):
        return FindingSeverity.MEDIUM
    return FindingSeverity.LOW
