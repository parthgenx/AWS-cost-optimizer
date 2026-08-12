"""CloudWatch-backed review rule for Application Load Balancers with no requests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cost_optimization.domain.models import (
    ApplicationLoadBalancer,
    FindingCandidate,
    FindingSeverity,
    MetricWindow,
)
from cost_optimization.domain.policies.resource_exclusion import is_excluded_from_optimization

RULE_ID = "no-request-application-load-balancer"


@dataclass(frozen=True)
class InactiveApplicationLoadBalancerRuleConfig:
    """The age of a complete request-observation window required for review."""

    lookback_days: int

    def __post_init__(self) -> None:
        if self.lookback_days < 1:
            raise ValueError("lookback_days must be at least 1")


class InactiveApplicationLoadBalancerRule:
    """Flags old-enough ALBs only when CloudWatch has no request evidence in the full window."""

    def __init__(self, config: InactiveApplicationLoadBalancerRuleConfig) -> None:
        self._config = config

    def evaluate(
        self,
        load_balancer: ApplicationLoadBalancer,
        *,
        evaluated_at: datetime,
        request_count: MetricWindow,
    ) -> FindingCandidate | None:
        """Return a review candidate when the ALB has no request metric points or a zero sum."""
        if evaluated_at.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        if is_excluded_from_optimization(load_balancer.tags):
            return None
        if load_balancer.created_at.astimezone(UTC) > evaluated_at.astimezone(UTC) - timedelta(
            days=self._config.lookback_days
        ):
            return None
        if request_count.sample_count != 0 and (
            request_count.value is None or request_count.value > 0
        ):
            return None

        return FindingCandidate(
            rule_id=RULE_ID,
            resource=load_balancer.resource,
            summary=(
                f"Application Load Balancer {load_balancer.name} had no CloudWatch request "
                "evidence "
                f"across {self._config.lookback_days} complete days."
            ),
            recommended_action=(
                "Review DNS, listener, target-group, failover, and planned-use dependencies before "
                "deleting this load balancer."
            ),
            severity=FindingSeverity.MEDIUM,
            estimated_monthly_savings=None,
            evidence={
                "scheme": load_balancer.scheme,
                "lookback_days": str(self._config.lookback_days),
                "request_count_samples": str(request_count.sample_count),
                "request_count_total": str(request_count.value or 0),
                "metric_interpretation": (
                    "Application Load Balancer RequestCount is emitted only when requests flow; "
                    "health checks are excluded."
                ),
            },
        )
