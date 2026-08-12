from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime

from cost_optimization.infrastructure.aws.application_load_balancers import (
    Boto3ApplicationLoadBalancerDiscovery,
)
from cost_optimization.infrastructure.aws.ec2_instances import Boto3Ec2InstanceDiscovery
from cost_optimization.infrastructure.aws.rds_instances import Boto3RdsInstanceDiscovery


def test_ec2_discovery_requests_only_running_instances_and_maps_tags() -> None:
    paginator = FakePaginator(
        [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-123",
                                "InstanceType": "m7g.large",
                                "LaunchTime": datetime(2026, 1, 1, tzinfo=UTC),
                                "Tags": [{"Key": "Name", "Value": "worker"}],
                            }
                        ]
                    }
                ]
            }
        ]
    )

    instances = Boto3Ec2InstanceDiscovery(
        FakeEc2Client(paginator), account_id="123456789012", region="ap-south-1"
    ).list_running_instances()

    assert paginator.operation_name == "describe_instances"
    assert paginator.arguments == [
        {"Filters": [{"Name": "instance-state-name", "Values": ["running"]}]}
    ]
    assert instances[0].resource.resource_id == "i-123"
    assert instances[0].tags == {"Name": "worker"}


def test_rds_discovery_keeps_available_instances_and_fetches_tags() -> None:
    paginator = FakePaginator(
        [
            {
                "DBInstances": [
                    {
                        "DBInstanceIdentifier": "db-example",
                        "DBInstanceArn": "arn:aws:rds:ap-south-1:123456789012:db:db-example",
                        "DBInstanceClass": "db.m7g.large",
                        "Engine": "postgres",
                        "InstanceCreateTime": datetime(2026, 1, 1, tzinfo=UTC),
                        "MultiAZ": False,
                        "DBInstanceStatus": "available",
                    },
                    {"DBInstanceStatus": "stopped"},
                ]
            }
        ]
    )
    client = FakeRdsClient(paginator)

    instances = Boto3RdsInstanceDiscovery(
        client, account_id="123456789012", region="ap-south-1"
    ).list_available_instances()

    assert paginator.operation_name == "describe_db_instances"
    assert instances[0].resource.resource_id == "db-example"
    assert instances[0].tags == {"cost-optimizer:exclude": "true"}
    assert client.tag_requests == [
        {"ResourceName": "arn:aws:rds:ap-south-1:123456789012:db:db-example"}
    ]


def test_alb_discovery_keeps_active_application_load_balancers_and_maps_metric_dimension() -> None:
    arn = "arn:aws:elasticloadbalancing:ap-south-1:123456789012:loadbalancer/app/example/123"
    paginator = FakePaginator(
        [
            {
                "LoadBalancers": [
                    {
                        "LoadBalancerArn": arn,
                        "LoadBalancerName": "example",
                        "Type": "application",
                        "Scheme": "internet-facing",
                        "CreatedTime": datetime(2026, 1, 1, tzinfo=UTC),
                        "State": {"Code": "active"},
                    },
                    {"Type": "network", "State": {"Code": "active"}},
                ]
            }
        ]
    )
    client = FakeAlbClient(paginator)

    load_balancers = Boto3ApplicationLoadBalancerDiscovery(
        client, account_id="123456789012", region="ap-south-1"
    ).list_active_load_balancers()

    assert paginator.operation_name == "describe_load_balancers"
    assert load_balancers[0].cloudwatch_dimension_value == "app/example/123"
    assert load_balancers[0].tags == {"Name": "example"}
    assert client.tag_requests == [{"ResourceArns": [arn]}]


class FakePaginator:
    def __init__(self, pages: list[Mapping[str, object]]) -> None:
        self._pages = pages
        self.operation_name = ""
        self.arguments: list[dict[str, object]] = []

    def paginate(self, **kwargs: object) -> Iterator[Mapping[str, object]]:
        self.arguments.append(kwargs)
        return iter(self._pages)


class FakeEc2Client:
    def __init__(self, paginator: FakePaginator) -> None:
        self._paginator = paginator

    def get_paginator(self, operation_name: str) -> FakePaginator:
        self._paginator.operation_name = operation_name
        return self._paginator


class FakeRdsClient(FakeEc2Client):
    def __init__(self, paginator: FakePaginator) -> None:
        super().__init__(paginator)
        self.tag_requests: list[dict[str, object]] = []

    def list_tags_for_resource(self, **kwargs: object) -> dict[str, object]:
        self.tag_requests.append(kwargs)
        return {"TagList": [{"Key": "cost-optimizer:exclude", "Value": "true"}]}


class FakeAlbClient(FakeEc2Client):
    def __init__(self, paginator: FakePaginator) -> None:
        super().__init__(paginator)
        self.tag_requests: list[dict[str, object]] = []

    def describe_tags(self, **kwargs: object) -> dict[str, object]:
        self.tag_requests.append(kwargs)
        return {"TagDescriptions": [{"Tags": [{"Key": "Name", "Value": "example"}]}]}
