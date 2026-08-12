"""Application service for conservative RDS utilization recommendations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from cost_optimization.application.services.run_detection_scan import DetectionScanResult
from cost_optimization.application.services.utilization_window import daily_metric_query
from cost_optimization.domain.models import MetricQuery, MetricStatistic, MetricWindow
from cost_optimization.domain.ports import CloudWatchMetricReader, RdsInstanceDiscovery
from cost_optimization.domain.rules.idle_rds_instance import IdleRdsInstanceRule

_NAMESPACE = "AWS/RDS"


class DetectIdleRdsInstances:
    """Batch RDS utilization evidence and keep evaluation independent of boto3."""

    def __init__(
        self,
        discovery: RdsInstanceDiscovery,
        metrics: CloudWatchMetricReader,
        rule: IdleRdsInstanceRule,
        *,
        lookback_days: int,
    ) -> None:
        self._discovery = discovery
        self._metrics = metrics
        self._rule = rule
        self._lookback_days = lookback_days

    def execute(self, evaluated_at: datetime) -> DetectionScanResult:
        """Return candidates only where complete CPU and connection evidence supports review."""
        instances = self._discovery.list_available_instances()
        queries: dict[str, MetricQuery] = {}
        for index, instance in enumerate(instances):
            dimensions = {"DBInstanceIdentifier": instance.resource.resource_id}
            queries[f"{index}_cpu"] = daily_metric_query(
                namespace=_NAMESPACE,
                metric_name="CPUUtilization",
                statistic=MetricStatistic.MAXIMUM,
                dimensions=dimensions,
                evaluated_at=evaluated_at,
                lookback_days=self._lookback_days,
            )
            queries[f"{index}_connections"] = daily_metric_query(
                namespace=_NAMESPACE,
                metric_name="DatabaseConnections",
                statistic=MetricStatistic.MAXIMUM,
                dimensions=dimensions,
                evaluated_at=evaluated_at,
                lookback_days=self._lookback_days,
            )
        windows = self._metrics.get_daily_windows(queries)
        findings = tuple(
            candidate
            for index, instance in enumerate(instances)
            if (
                candidate := self._rule.evaluate(
                    instance,
                    evaluated_at=evaluated_at,
                    cpu=_window(windows, f"{index}_cpu"),
                    database_connections=_window(windows, f"{index}_connections"),
                )
            )
            is not None
        )
        return DetectionScanResult(evaluated_resource_count=len(instances), findings=findings)


def _window(windows: Mapping[str, MetricWindow], key: str) -> MetricWindow:
    try:
        return windows[key]
    except KeyError as error:
        raise ValueError(f"CloudWatch did not return metric window {key}") from error
