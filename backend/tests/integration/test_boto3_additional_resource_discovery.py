from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime

from cost_optimization.infrastructure.aws.ec2_elastic_ips import Boto3ElasticIpDiscovery
from cost_optimization.infrastructure.aws.ec2_snapshots import Boto3EbsSnapshotDiscovery


def test_elastic_ip_discovery_maps_an_unassociated_address() -> None:
    paginator = FakePaginator(
        [{"Addresses": [{"AllocationId": "eipalloc-123", "PublicIp": "203.0.113.10", "Tags": []}]}]
    )

    addresses = Boto3ElasticIpDiscovery(
        FakeClient(paginator), account_id="123456789012", region="ap-south-1"
    ).list_addresses()

    assert paginator.operation_name == "describe_addresses"
    assert paginator.arguments == [{}]
    assert addresses[0].association_id is None
    assert addresses[0].resource.resource_id == "eipalloc-123"


def test_snapshot_discovery_scopes_to_self_owned_completed_snapshots() -> None:
    paginator = FakePaginator(
        [
            {
                "Snapshots": [
                    {
                        "SnapshotId": "snap-123",
                        "State": "completed",
                        "StartTime": datetime(2026, 1, 1, tzinfo=UTC),
                        "VolumeId": "vol-123",
                        "VolumeSize": 100,
                        "Tags": [],
                    }
                ]
            }
        ]
    )

    snapshots = Boto3EbsSnapshotDiscovery(
        FakeClient(paginator), account_id="123456789012", region="ap-south-1"
    ).list_owned_snapshots()

    assert paginator.operation_name == "describe_snapshots"
    assert paginator.arguments == [
        {"OwnerIds": ["self"], "Filters": [{"Name": "status", "Values": ["completed"]}]}
    ]
    assert snapshots[0].resource.resource_id == "snap-123"


class FakePaginator:
    def __init__(self, pages: list[Mapping[str, object]]) -> None:
        self._pages = pages
        self.operation_name = ""
        self.arguments: list[dict[str, object]] = []

    def paginate(self, **kwargs: object) -> Iterator[Mapping[str, object]]:
        self.arguments.append(kwargs)
        return iter(self._pages)


class FakeClient:
    def __init__(self, paginator: FakePaginator) -> None:
        self._paginator = paginator

    def get_paginator(self, operation_name: str) -> FakePaginator:
        self._paginator.operation_name = operation_name
        return self._paginator
