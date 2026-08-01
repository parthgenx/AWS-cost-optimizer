from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime

import pytest

from cost_optimization.domain.models import EbsVolumeState
from cost_optimization.infrastructure.aws.ec2_volumes import (
    AwsResponseFormatError,
    Boto3EbsVolumeDiscovery,
)


def test_discovery_paginates_and_maps_aws_response_to_domain_model() -> None:
    paginator = FakePaginator(
        [
            {"Volumes": [_aws_volume("vol-first", 20, {"Name": "first"})]},
            {"Volumes": [_aws_volume("vol-second", 50, {"cost-optimizer:exclude": "true"})]},
        ]
    )
    discovery = Boto3EbsVolumeDiscovery(
        FakeEc2Client(paginator), account_id="123456789012", region="ap-south-1"
    )

    volumes = discovery.list_unattached_volumes()

    assert paginator.arguments == [{"Filters": [{"Name": "status", "Values": ["available"]}]}]
    assert [volume.resource.resource_id for volume in volumes] == ["vol-first", "vol-second"]
    assert volumes[0].state is EbsVolumeState.AVAILABLE
    assert volumes[1].tags["cost-optimizer:exclude"] == "true"


def test_discovery_rejects_malformed_aws_response() -> None:
    discovery = Boto3EbsVolumeDiscovery(
        FakeEc2Client(FakePaginator([{"Volumes": [{"VolumeId": "vol-missing-fields"}]}])),
        account_id="123456789012",
        region="ap-south-1",
    )

    with pytest.raises(AwsResponseFormatError, match="CreateTime"):
        discovery.list_unattached_volumes()


class FakePaginator:
    def __init__(self, pages: list[Mapping[str, object]]) -> None:
        self._pages = pages
        self.arguments: list[dict[str, object]] = []

    def paginate(self, **kwargs: object) -> Iterator[Mapping[str, object]]:
        self.arguments.append(kwargs)
        return iter(self._pages)


class FakeEc2Client:
    def __init__(self, paginator: FakePaginator) -> None:
        self._paginator = paginator

    def get_paginator(self, operation_name: str) -> FakePaginator:
        assert operation_name == "describe_volumes"
        return self._paginator


def _aws_volume(volume_id: str, size_gib: int, tags: dict[str, str]) -> dict[str, object]:
    return {
        "VolumeId": volume_id,
        "CreateTime": datetime(2026, 7, 1, tzinfo=UTC),
        "State": "available",
        "Size": size_gib,
        "VolumeType": "gp3",
        "Tags": [{"Key": key, "Value": value} for key, value in tags.items()],
    }
