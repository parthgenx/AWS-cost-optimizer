"""boto3-backed discovery of EBS volumes through the EC2 API."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import Protocol, cast

import boto3

from cost_optimization.domain.models import (
    EbsVolume,
    EbsVolumeState,
    ResourceReference,
    ResourceType,
)


class Ec2VolumesPaginator(Protocol):
    """Small protocol matching the paginator surface used by this adapter."""

    def paginate(self, **kwargs: object) -> Iterator[Mapping[str, object]]:
        """Yield paginated EC2 API result pages."""


class Ec2VolumesClient(Protocol):
    """Small protocol matching the EC2 client surface used by this adapter."""

    def get_paginator(self, operation_name: str) -> Ec2VolumesPaginator:
        """Return a paginator for the requested EC2 operation."""


class AwsResponseFormatError(ValueError):
    """Raised when a required EC2 volume field is missing or malformed."""


def create_ec2_client(region: str) -> Ec2VolumesClient:
    """Create an EC2 client; this is the only boto3 client construction point."""
    client = boto3.client("ec2", region_name=region)
    return cast(Ec2VolumesClient, client)


class Boto3EbsVolumeDiscovery:
    """Translates paginated ``describe_volumes`` responses into domain EBS models."""

    def __init__(self, client: Ec2VolumesClient, *, account_id: str, region: str) -> None:
        self._client = client
        self._account_id = account_id
        self._region = region

    def list_unattached_volumes(self) -> list[EbsVolume]:
        """Retrieve only AWS volumes whose current state is ``available``."""
        paginator = self._client.get_paginator("describe_volumes")
        volumes: list[EbsVolume] = []
        for page in paginator.paginate(Filters=[{"Name": "status", "Values": ["available"]}]):
            for raw_volume in _required_list(page, "Volumes"):
                volumes.append(self._to_domain_volume(_required_mapping(raw_volume, "volume")))
        return volumes

    def _to_domain_volume(self, raw_volume: Mapping[str, object]) -> EbsVolume:
        volume_id = _required_string(raw_volume, "VolumeId")
        created_at = _required_datetime(raw_volume, "CreateTime")
        return EbsVolume(
            resource=ResourceReference(
                resource_type=ResourceType.EBS_VOLUME,
                resource_id=volume_id,
                region=self._region,
                account_id=self._account_id,
            ),
            state=_required_ebs_state(raw_volume),
            size_gib=_required_positive_int(raw_volume, "Size"),
            created_at=created_at,
            volume_type=_required_string(raw_volume, "VolumeType"),
            tags=_to_tag_mapping(raw_volume.get("Tags", [])),
        )


def _required_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AwsResponseFormatError(f"{field_name} must be an object")
    return value


def _required_list(page: Mapping[str, object], field_name: str) -> list[object]:
    value = page.get(field_name)
    if not isinstance(value, list):
        raise AwsResponseFormatError(f"{field_name} must be a list")
    return value


def _required_string(values: Mapping[str, object], field_name: str) -> str:
    value = values.get(field_name)
    if not isinstance(value, str) or not value:
        raise AwsResponseFormatError(f"{field_name} must be a non-empty string")
    return value


def _required_positive_int(values: Mapping[str, object], field_name: str) -> int:
    value = values.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise AwsResponseFormatError(f"{field_name} must be a positive integer")
    return value


def _required_datetime(values: Mapping[str, object], field_name: str) -> datetime:
    value = values.get(field_name)
    if not isinstance(value, datetime):
        raise AwsResponseFormatError(f"{field_name} must be a datetime")
    if value.tzinfo is None:
        raise AwsResponseFormatError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _required_ebs_state(values: Mapping[str, object]) -> EbsVolumeState:
    state = _required_string(values, "State")
    try:
        return EbsVolumeState(state)
    except ValueError as error:
        raise AwsResponseFormatError(f"State is not a supported EBS state: {state}") from error


def _to_tag_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        raise AwsResponseFormatError("Tags must be a list")

    tags: dict[str, str] = {}
    for raw_tag in value:
        tag = _required_mapping(raw_tag, "tag")
        key = _required_string(tag, "Key")
        tags[key] = _required_string(tag, "Value")
    return tags
