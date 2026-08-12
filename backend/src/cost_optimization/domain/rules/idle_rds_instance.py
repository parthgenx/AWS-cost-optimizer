"""Conservative CloudWatch-backed recommendation rule for provisioned RDS instances."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from cost_optimization.domain.models import (
    FindingCandidate,
    FindingSeverity,
    MetricWindow,
    RdsInstance,
)
from cost_optimization.domain.policies.resource_exclusion import is_excluded_from_optimization

RULE_ID = "sustained-low-utilization-rds-instance"


@dataclass(frozen=True)
class IdleRdsInstanceRuleConfig:
    """Thresholds used to create a conservative RDS review recommendation."""

    lookback_days: int
    maximum_cpu_percent: Decimal

    def __post_init__(self) -> None:
        if self.lookback_days < 1:
            raise ValueError("lookback_days must be at least 1")
        if not Decimal("0") <= self.maximum_cpu_percent <= Decimal("100"):
            raise ValueError("maximum_cpu_percent must be between 0 and 100")


class IdleRdsInstanceRule:
    """Flags standalone RDS databases only after complete, zero-client evidence."""

    def __init__(self, config: IdleRdsInstanceRuleConfig) -> None:
        self._config = config

    def evaluate(
        self,
        instance: RdsInstance,
        *,
        evaluated_at: datetime,
        cpu: MetricWindow,
        database_connections: MetricWindow,
    ) -> FindingCandidate | None:
        """Return a review finding only for a low-risk, fully observed standalone RDS instance."""
        if evaluated_at.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        if is_excluded_from_optimization(instance.tags) or _is_higher_risk(instance):
            return None
        if instance.created_at.astimezone(UTC) > evaluated_at.astimezone(UTC) - timedelta(
            days=self._config.lookback_days
        ):
            return None
        if not all(
            window.is_complete and window.has_values for window in (cpu, database_connections)
        ):
            return None
        assert cpu.value is not None
        assert database_connections.value is not None
        if cpu.value > self._config.maximum_cpu_percent or database_connections.value > Decimal(
            "0"
        ):
            return None

        return FindingCandidate(
            rule_id=RULE_ID,
            resource=instance.resource,
            summary=(
                f"RDS instance {instance.resource.resource_id} had no reported client connections "
                f"and low CPU across {self._config.lookback_days} complete days."
            ),
            recommended_action=(
                "Review backups, disaster-recovery requirements, and application dependencies "
                "before "
                "rightsizing, stopping, or deleting this database."
            ),
            severity=FindingSeverity.HIGH,
            estimated_monthly_savings=None,
            evidence={
                "instance_class": instance.instance_class,
                "engine": instance.engine,
                "lookback_days": str(self._config.lookback_days),
                "cpu_maximum_percent": str(cpu.value),
                "maximum_cpu_percent": str(self._config.maximum_cpu_percent),
                "database_connections_maximum": str(database_connections.value),
            },
        )


def _is_higher_risk(instance: RdsInstance) -> bool:
    """Exclude HA, clustered, Aurora, and replica topologies from this first recommendation rule."""
    return (
        instance.multi_az
        or instance.db_cluster_identifier is not None
        or instance.read_replica_source_identifier is not None
        or instance.engine.startswith("aurora")
    )
