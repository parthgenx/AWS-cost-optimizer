from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

from cost_optimization.application.services.detect_idle_ec2_instances import DetectIdleEc2Instances
from cost_optimization.application.services.detect_idle_rds_instances import DetectIdleRdsInstances
from cost_optimization.application.services.detect_inactive_application_load_balancers import (
    DetectInactiveApplicationLoadBalancers,
)
from cost_optimization.domain.models import (
    ApplicationLoadBalancer,
    Ec2Instance,
    MetricStatistic,
    MetricWindow,
    RdsInstance,
    ResourceReference,
    ResourceType,
)
from cost_optimization.domain.rules.idle_ec2_instance import (
    IdleEc2InstanceRule,
    IdleEc2InstanceRuleConfig,
)
from cost_optimization.domain.rules.idle_rds_instance import (
    IdleRdsInstanceRule,
    IdleRdsInstanceRuleConfig,
)
from cost_optimization.domain.rules.inactive_application_load_balancer import (
    InactiveApplicationLoadBalancerRule,
    InactiveApplicationLoadBalancerRuleConfig,
)

_NOW = datetime(2026, 8, 12, 12, tzinfo=UTC)


def test_ec2_detection_batches_three_queries_per_running_instance() -> None:
    metrics = FakeMetricReader(
        {
            "0_cpu": _window("CPUUtilization", MetricStatistic.MAXIMUM, Decimal("2")),
            "0_network_in": _window("NetworkIn", MetricStatistic.SUM, Decimal("100")),
            "0_network_out": _window("NetworkOut", MetricStatistic.SUM, Decimal("200")),
        }
    )
    result = DetectIdleEc2Instances(
        FakeEc2Discovery([_ec2()]),
        metrics,
        IdleEc2InstanceRule(IdleEc2InstanceRuleConfig(14, Decimal("5"), Decimal("1000"))),
        lookback_days=14,
    ).execute(_NOW)

    assert result.evaluated_resource_count == 1
    assert len(result.findings) == 1
    assert set(metrics.queries) == {"0_cpu", "0_network_in", "0_network_out"}
    assert metrics.queries["0_cpu"].end_at == datetime(2026, 8, 12, tzinfo=UTC)


def test_rds_detection_batches_cpu_and_connection_queries_per_instance() -> None:
    metrics = FakeMetricReader(
        {
            "0_cpu": _window("CPUUtilization", MetricStatistic.MAXIMUM, Decimal("2")),
            "0_connections": _window("DatabaseConnections", MetricStatistic.MAXIMUM, Decimal("0")),
        }
    )
    result = DetectIdleRdsInstances(
        FakeRdsDiscovery([_rds()]),
        metrics,
        IdleRdsInstanceRule(IdleRdsInstanceRuleConfig(14, Decimal("5"))),
        lookback_days=14,
    ).execute(_NOW)

    assert result.evaluated_resource_count == 1
    assert len(result.findings) == 1
    assert metrics.queries["0_connections"].dimensions == {"DBInstanceIdentifier": "db-example"}


def test_alb_detection_batches_request_count_queries_and_handles_no_metric_data() -> None:
    metrics = FakeMetricReader({"0": _window("RequestCount", MetricStatistic.SUM, None, samples=0)})
    result = DetectInactiveApplicationLoadBalancers(
        FakeAlbDiscovery([_alb()]),
        metrics,
        InactiveApplicationLoadBalancerRule(InactiveApplicationLoadBalancerRuleConfig(14)),
        lookback_days=14,
    ).execute(_NOW)

    assert result.evaluated_resource_count == 1
    assert len(result.findings) == 1
    assert metrics.queries["0"].dimensions == {"LoadBalancer": "app/example/123"}


class FakeMetricReader:
    def __init__(self, windows: Mapping[str, MetricWindow]) -> None:
        self._windows = windows
        self.queries: Mapping[str, object] = {}

    def get_daily_windows(self, queries: Mapping[str, object]) -> Mapping[str, MetricWindow]:
        self.queries = queries
        return self._windows


class FakeEc2Discovery:
    def __init__(self, instances: list[Ec2Instance]) -> None:
        self._instances = instances

    def list_running_instances(self) -> list[Ec2Instance]:
        return self._instances


class FakeRdsDiscovery:
    def __init__(self, instances: list[RdsInstance]) -> None:
        self._instances = instances

    def list_available_instances(self) -> list[RdsInstance]:
        return self._instances


class FakeAlbDiscovery:
    def __init__(self, load_balancers: list[ApplicationLoadBalancer]) -> None:
        self._load_balancers = load_balancers

    def list_active_load_balancers(self) -> list[ApplicationLoadBalancer]:
        return self._load_balancers


def _window(
    metric_name: str, statistic: MetricStatistic, value: Decimal | None, *, samples: int = 14
) -> MetricWindow:
    return MetricWindow(
        metric_name=metric_name,
        statistic=statistic,
        sample_count=samples,
        expected_sample_count=14,
        value=value,
    )


def _ec2() -> Ec2Instance:
    return Ec2Instance(
        resource=_resource(ResourceType.EC2_INSTANCE, "i-123"),
        instance_type="m7g.large",
        launched_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _rds() -> RdsInstance:
    return RdsInstance(
        resource=_resource(ResourceType.RDS_INSTANCE, "db-example"),
        instance_class="db.m7g.large",
        engine="postgres",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        multi_az=False,
    )


def _alb() -> ApplicationLoadBalancer:
    return ApplicationLoadBalancer(
        resource=_resource(ResourceType.APPLICATION_LOAD_BALANCER, "app/example/123"),
        name="example",
        cloudwatch_dimension_value="app/example/123",
        scheme="internet-facing",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _resource(resource_type: ResourceType, resource_id: str) -> ResourceReference:
    return ResourceReference(
        resource_type=resource_type,
        resource_id=resource_id,
        account_id="123456789012",
        region="ap-south-1",
    )
