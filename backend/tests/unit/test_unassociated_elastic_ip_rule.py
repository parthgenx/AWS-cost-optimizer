from __future__ import annotations

from decimal import Decimal

from cost_optimization.domain.models import ElasticIpAddress, ResourceReference, ResourceType
from cost_optimization.domain.rules.unassociated_elastic_ip import (
    UnassociatedElasticIpRule,
    UnassociatedElasticIpRuleConfig,
)


def test_unassociated_address_creates_a_finding_with_transparent_estimate() -> None:
    candidate = _rule().evaluate(_address())

    assert candidate is not None
    assert candidate.rule_id == "unassociated-elastic-ip"
    assert candidate.estimated_monthly_savings is not None
    assert candidate.estimated_monthly_savings.amount == Decimal("3.60")


def test_associated_or_excluded_addresses_are_not_flagged() -> None:
    assert _rule().evaluate(_address(association_id="eipassoc-123")) is None
    assert _rule().evaluate(_address(tags={"cost-optimizer:exclude": "true"})) is None


def _rule() -> UnassociatedElasticIpRule:
    return UnassociatedElasticIpRule(
        UnassociatedElasticIpRuleConfig(reference_monthly_rate_usd=Decimal("3.60"))
    )


def _address(
    *, association_id: str | None = None, tags: dict[str, str] | None = None
) -> ElasticIpAddress:
    return ElasticIpAddress(
        resource=ResourceReference(
            resource_type=ResourceType.ELASTIC_IP,
            resource_id="eipalloc-123",
            account_id="123456789012",
            region="ap-south-1",
        ),
        allocation_id="eipalloc-123",
        public_ip="203.0.113.10",
        association_id=association_id,
        tags=tags or {},
    )
