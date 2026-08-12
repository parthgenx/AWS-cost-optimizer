"""boto3-backed discovery of running EC2 instances for utilization recommendations."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import Protocol

from cost_optimization.domain.models import Ec2Instance, ResourceReference, ResourceType


class Ec2InstancePaginator(Protocol):
    """Small protocol matching the paginator surface used by this adapter."""

    def paginate(self, **kwargs: object) -> Iterator[Mapping[str, object]]:
        """Yield paginated EC2 API result pages."""


class Ec2InstanceClient(Protocol):
    """Minimal EC2 client surface required by the running-instance adapter."""

    def get_paginator(self, operation_name: str) -> Ec2InstancePaginator:
        """Return a paginator for the requested EC2 operation."""


class AwsEc2InstanceResponseFormatError(ValueError):
    """Raised when required EC2 instance fields are missing or malformed."""


class Boto3Ec2InstanceDiscovery:
    """Maps paginated running ``describe_instances`` results into domain models."""

    def __init__(self, client: Ec2InstanceClient, *, account_id: str, region: str) -> None:
        self._client = client
        self._account_id = account_id
        self._region = region

    def list_running_instances(self) -> list[Ec2Instance]:
        """Retrieve only current running instances through a server-side EC2 filter."""
        paginator = self._client.get_paginator("describe_instances")
        instances: list[Ec2Instance] = []
        for page in paginator.paginate(
            Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
        ):
            for reservation in _required_list(page, "Reservations"):
                for raw_instance in _required_list(
                    _required_mapping(reservation, "reservation"), "Instances"
                ):
                    instances.append(
                        self._to_domain_instance(_required_mapping(raw_instance, "instance"))
                    )
        return instances

    def _to_domain_instance(self, raw_instance: Mapping[str, object]) -> Ec2Instance:
        instance_id = _required_string(raw_instance, "InstanceId")
        return Ec2Instance(
            resource=ResourceReference(
                resource_type=ResourceType.EC2_INSTANCE,
                resource_id=instance_id,
                account_id=self._account_id,
                region=self._region,
            ),
            instance_type=_required_string(raw_instance, "InstanceType"),
            launched_at=_required_datetime(raw_instance, "LaunchTime"),
            tags=_to_tag_mapping(raw_instance.get("Tags", [])),
        )


def _required_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AwsEc2InstanceResponseFormatError(f"{field_name} must be an object")
    return value


def _required_list(values: Mapping[str, object], field_name: str) -> list[object]:
    value = values.get(field_name)
    if not isinstance(value, list):
        raise AwsEc2InstanceResponseFormatError(f"{field_name} must be a list")
    return value


def _required_string(values: Mapping[str, object], field_name: str) -> str:
    value = values.get(field_name)
    if not isinstance(value, str) or not value:
        raise AwsEc2InstanceResponseFormatError(f"{field_name} must be a non-empty string")
    return value


def _required_datetime(values: Mapping[str, object], field_name: str) -> datetime:
    value = values.get(field_name)
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise AwsEc2InstanceResponseFormatError(f"{field_name} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def _to_tag_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        raise AwsEc2InstanceResponseFormatError("Tags must be a list")
    tags: dict[str, str] = {}
    for raw_tag in value:
        tag = _required_mapping(raw_tag, "tag")
        tags[_required_string(tag, "Key")] = _required_string(tag, "Value")
    return tags
