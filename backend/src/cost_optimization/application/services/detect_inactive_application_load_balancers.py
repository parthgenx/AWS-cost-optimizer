"""Application service for Application Load Balancer no-request recommendations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from cost_optimization.application.services.run_detection_scan import DetectionScanResult
from cost_optimization.application.services.utilization_window import daily_metric_query
from cost_optimization.domain.models import MetricQuery, MetricStatistic, MetricWindow
from cost_optimization.domain.ports import (
    ApplicationLoadBalancerDiscovery,
    CloudWatchMetricReader,
)
from cost_optimization.domain.rules.inactive_application_load_balancer import (
    InactiveApplicationLoadBalancerRule,
)

_NAMESPACE = "AWS/ApplicationELB"


class DetectInactiveApplicationLoadBalancers:
    """Batch ALB request-count evidence and keep evaluation independent of boto3."""

    def __init__(
        self,
        discovery: ApplicationLoadBalancerDiscovery,
        metrics: CloudWatchMetricReader,
        rule: InactiveApplicationLoadBalancerRule,
        *,
        lookback_days: int,
    ) -> None:
        self._discovery = discovery
        self._metrics = metrics
        self._rule = rule
        self._lookback_days = lookback_days

    def execute(self, evaluated_at: datetime) -> DetectionScanResult:
        """Return candidates when no application-request traffic is observed for the full window."""
        load_balancers = self._discovery.list_active_load_balancers()
        queries: dict[str, MetricQuery] = {
            str(index): daily_metric_query(
                namespace=_NAMESPACE,
                metric_name="RequestCount",
                statistic=MetricStatistic.SUM,
                dimensions={"LoadBalancer": load_balancer.cloudwatch_dimension_value},
                evaluated_at=evaluated_at,
                lookback_days=self._lookback_days,
            )
            for index, load_balancer in enumerate(load_balancers)
        }
        windows = self._metrics.get_daily_windows(queries)
        findings = tuple(
            candidate
            for index, load_balancer in enumerate(load_balancers)
            if (
                candidate := self._rule.evaluate(
                    load_balancer,
                    evaluated_at=evaluated_at,
                    request_count=_window(windows, str(index)),
                )
            )
            is not None
        )
        return DetectionScanResult(evaluated_resource_count=len(load_balancers), findings=findings)


def _window(windows: Mapping[str, MetricWindow], key: str) -> MetricWindow:
    try:
        return windows[key]
    except KeyError as error:
        raise ValueError(f"CloudWatch did not return metric window {key}") from error
