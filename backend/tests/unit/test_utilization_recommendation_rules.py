from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from cost_optimization.domain.models import (
    ApplicationLoadBalancer,
    Ec2Instance,
    FindingSeverity,
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

_EVALUATED_AT = datetime(2026, 8, 12, 12, tzinfo=UTC)


def test_ec2_rule_requires_complete_low_cpu_and_low_network_evidence() -> None:
    candidate = _ec2_rule().evaluate(
        _ec2_instance(),
        evaluated_at=_EVALUATED_AT,
        cpu=_window("CPUUtilization", MetricStatistic.MAXIMUM, Decimal("2.5")),
        network_in=_window("NetworkIn", MetricStatistic.SUM, Decimal("200")),
        network_out=_window("NetworkOut", MetricStatistic.SUM, Decimal("300")),
    )

    assert candidate is not None
    assert candidate.severity is FindingSeverity.MEDIUM
    assert candidate.estimated_monthly_savings is None


def test_ec2_rule_rejects_incomplete_or_above_threshold_evidence() -> None:
    assert (
        _ec2_rule().evaluate(
            _ec2_instance(),
            evaluated_at=_EVALUATED_AT,
            cpu=_window("CPUUtilization", MetricStatistic.MAXIMUM, Decimal("2"), samples=13),
            network_in=_window("NetworkIn", MetricStatistic.SUM, Decimal("200")),
            network_out=_window("NetworkOut", MetricStatistic.SUM, Decimal("300")),
        )
        is None
    )
    assert (
        _ec2_rule().evaluate(
            _ec2_instance(),
            evaluated_at=_EVALUATED_AT,
            cpu=_window("CPUUtilization", MetricStatistic.MAXIMUM, Decimal("6")),
            network_in=_window("NetworkIn", MetricStatistic.SUM, Decimal("200")),
            network_out=_window("NetworkOut", MetricStatistic.SUM, Decimal("300")),
        )
        is None
    )


def test_rds_rule_skips_high_risk_topologies_and_requires_zero_client_connections() -> None:
    candidate = _rds_rule().evaluate(
        _rds_instance(),
        evaluated_at=_EVALUATED_AT,
        cpu=_window("CPUUtilization", MetricStatistic.MAXIMUM, Decimal("2")),
        database_connections=_window("DatabaseConnections", MetricStatistic.MAXIMUM, Decimal("0")),
    )

    assert candidate is not None
    assert candidate.severity is FindingSeverity.HIGH
    assert (
        _rds_rule().evaluate(
            _rds_instance(multi_az=True),
            evaluated_at=_EVALUATED_AT,
            cpu=_window("CPUUtilization", MetricStatistic.MAXIMUM, Decimal("2")),
            database_connections=_window(
                "DatabaseConnections", MetricStatistic.MAXIMUM, Decimal("0")
            ),
        )
        is None
    )
    assert (
        _rds_rule().evaluate(
            _rds_instance(),
            evaluated_at=_EVALUATED_AT,
            cpu=_window("CPUUtilization", MetricStatistic.MAXIMUM, Decimal("2")),
            database_connections=_window(
                "DatabaseConnections", MetricStatistic.MAXIMUM, Decimal("1")
            ),
        )
        is None
    )


def test_alb_rule_treats_no_request_metric_points_as_no_request_traffic() -> None:
    candidate = _alb_rule().evaluate(
        _load_balancer(),
        evaluated_at=_EVALUATED_AT,
        request_count=_window("RequestCount", MetricStatistic.SUM, None, samples=0),
    )

    assert candidate is not None
    assert candidate.evidence["request_count_total"] == "0"
    assert (
        _alb_rule().evaluate(
            _load_balancer(),
            evaluated_at=_EVALUATED_AT,
            request_count=_window("RequestCount", MetricStatistic.SUM, Decimal("1")),
        )
        is None
    )


def _ec2_rule() -> IdleEc2InstanceRule:
    return IdleEc2InstanceRule(
        IdleEc2InstanceRuleConfig(
            lookback_days=14,
            maximum_cpu_percent=Decimal("5"),
            maximum_total_network_bytes=Decimal("1000"),
        )
    )


def _rds_rule() -> IdleRdsInstanceRule:
    return IdleRdsInstanceRule(
        IdleRdsInstanceRuleConfig(lookback_days=14, maximum_cpu_percent=Decimal("5"))
    )


def _alb_rule() -> InactiveApplicationLoadBalancerRule:
    return InactiveApplicationLoadBalancerRule(
        InactiveApplicationLoadBalancerRuleConfig(lookback_days=14)
    )


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


def _ec2_instance() -> Ec2Instance:
    return Ec2Instance(
        resource=_resource(ResourceType.EC2_INSTANCE, "i-123"),
        instance_type="m7g.large",
        launched_at=datetime(2026, 7, 1, tzinfo=UTC),
    )


def _rds_instance(*, multi_az: bool = False) -> RdsInstance:
    return RdsInstance(
        resource=_resource(ResourceType.RDS_INSTANCE, "db-example"),
        instance_class="db.m7g.large",
        engine="postgres",
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
        multi_az=multi_az,
    )


def _load_balancer() -> ApplicationLoadBalancer:
    return ApplicationLoadBalancer(
        resource=_resource(ResourceType.APPLICATION_LOAD_BALANCER, "app/example/123"),
        name="example",
        cloudwatch_dimension_value="app/example/123",
        scheme="internet-facing",
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
    )


def _resource(resource_type: ResourceType, resource_id: str) -> ResourceReference:
    return ResourceReference(
        resource_type=resource_type,
        resource_id=resource_id,
        account_id="123456789012",
        region="ap-south-1",
    )
