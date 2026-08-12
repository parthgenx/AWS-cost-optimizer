"""Conservative CloudWatch-backed recommendation rule for running EC2 instances."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from cost_optimization.domain.models import (
    Ec2Instance,
    FindingCandidate,
    FindingSeverity,
    MetricWindow,
)
from cost_optimization.domain.policies.resource_exclusion import is_excluded_from_optimization

RULE_ID = "sustained-low-utilization-ec2-instance"


@dataclass(frozen=True)
class IdleEc2InstanceRuleConfig:
    """Thresholds used to make a conservative EC2 review recommendation."""

    lookback_days: int
    maximum_cpu_percent: Decimal
    maximum_total_network_bytes: Decimal

    def __post_init__(self) -> None:
        if self.lookback_days < 1:
            raise ValueError("lookback_days must be at least 1")
        if not Decimal("0") <= self.maximum_cpu_percent <= Decimal("100"):
            raise ValueError("maximum_cpu_percent must be between 0 and 100")
        if self.maximum_total_network_bytes < Decimal("0"):
            raise ValueError("maximum_total_network_bytes must be non-negative")


class IdleEc2InstanceRule:
    """Flags only old-enough running instances with complete, consistently low evidence."""

    def __init__(self, config: IdleEc2InstanceRuleConfig) -> None:
        self._config = config

    def evaluate(
        self,
        instance: Ec2Instance,
        *,
        evaluated_at: datetime,
        cpu: MetricWindow,
        network_in: MetricWindow,
        network_out: MetricWindow,
    ) -> FindingCandidate | None:
        """Return a recommendation only if all CPU and network evidence is complete and low."""
        if evaluated_at.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        if is_excluded_from_optimization(instance.tags):
            return None
        if instance.launched_at.astimezone(UTC) > evaluated_at.astimezone(UTC) - timedelta(
            days=self._config.lookback_days
        ):
            return None
        if not all(
            window.is_complete and window.has_values for window in (cpu, network_in, network_out)
        ):
            return None
        assert cpu.value is not None
        assert network_in.value is not None
        assert network_out.value is not None
        total_network_bytes = network_in.value + network_out.value
        if cpu.value > self._config.maximum_cpu_percent:
            return None
        if total_network_bytes > self._config.maximum_total_network_bytes:
            return None

        return FindingCandidate(
            rule_id=RULE_ID,
            resource=instance.resource,
            summary=(
                f"EC2 instance {instance.resource.resource_id} had sustained low CPU and network "
                f"activity across {self._config.lookback_days} complete days."
            ),
            recommended_action=(
                "Review workload ownership, schedules, and dependencies before rightsizing, "
                "stopping, or terminating this instance."
            ),
            severity=FindingSeverity.MEDIUM,
            estimated_monthly_savings=None,
            evidence={
                "instance_type": instance.instance_type,
                "lookback_days": str(self._config.lookback_days),
                "cpu_maximum_percent": str(cpu.value),
                "maximum_cpu_percent": str(self._config.maximum_cpu_percent),
                "network_in_total_bytes": str(network_in.value),
                "network_out_total_bytes": str(network_out.value),
                "total_network_bytes": str(total_network_bytes),
                "maximum_total_network_bytes": str(self._config.maximum_total_network_bytes),
            },
        )
