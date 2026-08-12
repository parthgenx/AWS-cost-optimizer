"""Application service for conservative EC2 utilization recommendations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from cost_optimization.application.services.run_detection_scan import DetectionScanResult
from cost_optimization.application.services.utilization_window import daily_metric_query
from cost_optimization.domain.models import MetricQuery, MetricStatistic, MetricWindow
from cost_optimization.domain.ports import CloudWatchMetricReader, Ec2InstanceDiscovery
from cost_optimization.domain.rules.idle_ec2_instance import IdleEc2InstanceRule

_NAMESPACE = "AWS/EC2"


class DetectIdleEc2Instances:
    """Batch EC2 utilization evidence and keep evaluation independent of boto3."""

    def __init__(
        self,
        discovery: Ec2InstanceDiscovery,
        metrics: CloudWatchMetricReader,
        rule: IdleEc2InstanceRule,
        *,
        lookback_days: int,
    ) -> None:
        self._discovery = discovery
        self._metrics = metrics
        self._rule = rule
        self._lookback_days = lookback_days

    def execute(self, evaluated_at: datetime) -> DetectionScanResult:
        """Return candidates only where the full CPU and network evidence supports review."""
        instances = self._discovery.list_running_instances()
        queries: dict[str, MetricQuery] = {}
        for index, instance in enumerate(instances):
            dimensions = {"InstanceId": instance.resource.resource_id}
            queries[f"{index}_cpu"] = daily_metric_query(
                namespace=_NAMESPACE,
                metric_name="CPUUtilization",
                statistic=MetricStatistic.MAXIMUM,
                dimensions=dimensions,
                evaluated_at=evaluated_at,
                lookback_days=self._lookback_days,
            )
            queries[f"{index}_network_in"] = daily_metric_query(
                namespace=_NAMESPACE,
                metric_name="NetworkIn",
                statistic=MetricStatistic.SUM,
                dimensions=dimensions,
                evaluated_at=evaluated_at,
                lookback_days=self._lookback_days,
            )
            queries[f"{index}_network_out"] = daily_metric_query(
                namespace=_NAMESPACE,
                metric_name="NetworkOut",
                statistic=MetricStatistic.SUM,
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
                    network_in=_window(windows, f"{index}_network_in"),
                    network_out=_window(windows, f"{index}_network_out"),
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
