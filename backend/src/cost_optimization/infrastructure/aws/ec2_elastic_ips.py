"""boto3-backed Elastic IP discovery through the EC2 API."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Protocol

from cost_optimization.domain.models import ElasticIpAddress, ResourceReference, ResourceType


class ElasticIpPaginator(Protocol):
    """Small protocol matching the paginator surface used by this adapter."""

    def paginate(self, **kwargs: object) -> Iterator[Mapping[str, object]]:
        """Yield paginated EC2 API result pages."""


class ElasticIpClient(Protocol):
    """Small EC2 client surface required by the Elastic IP adapter."""

    def get_paginator(self, operation_name: str) -> ElasticIpPaginator:
        """Return a paginator for the requested EC2 operation."""


class AwsElasticIpResponseFormatError(ValueError):
    """Raised when required Elastic IP response fields are missing or malformed."""


class Boto3ElasticIpDiscovery:
    """Maps paginated ``describe_addresses`` responses into domain address models."""

    def __init__(self, client: ElasticIpClient, *, account_id: str, region: str) -> None:
        self._client = client
        self._account_id = account_id
        self._region = region

    def list_addresses(self) -> list[ElasticIpAddress]:
        """Retrieve VPC Elastic IP addresses visible to the configured account and region."""
        paginator = self._client.get_paginator("describe_addresses")
        addresses: list[ElasticIpAddress] = []
        for page in paginator.paginate():
            for raw_address in _required_list(page, "Addresses"):
                addresses.append(self._to_domain_address(_required_mapping(raw_address, "address")))
        return addresses

    def _to_domain_address(self, raw_address: Mapping[str, object]) -> ElasticIpAddress:
        allocation_id = _required_string(raw_address, "AllocationId")
        return ElasticIpAddress(
            resource=ResourceReference(
                resource_type=ResourceType.ELASTIC_IP,
                resource_id=allocation_id,
                region=self._region,
                account_id=self._account_id,
            ),
            public_ip=_required_string(raw_address, "PublicIp"),
            allocation_id=allocation_id,
            association_id=_optional_string(raw_address, "AssociationId"),
            network_interface_id=_optional_string(raw_address, "NetworkInterfaceId"),
            instance_id=_optional_string(raw_address, "InstanceId"),
            tags=_to_tag_mapping(raw_address.get("Tags", [])),
        )


def _required_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AwsElasticIpResponseFormatError(f"{field_name} must be an object")
    return value


def _required_list(page: Mapping[str, object], field_name: str) -> list[object]:
    value = page.get(field_name)
    if not isinstance(value, list):
        raise AwsElasticIpResponseFormatError(f"{field_name} must be a list")
    return value


def _required_string(values: Mapping[str, object], field_name: str) -> str:
    value = values.get(field_name)
    if not isinstance(value, str) or not value:
        raise AwsElasticIpResponseFormatError(f"{field_name} must be a non-empty string")
    return value


def _optional_string(values: Mapping[str, object], field_name: str) -> str | None:
    value = values.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise AwsElasticIpResponseFormatError(
            f"{field_name} must be a non-empty string when present"
        )
    return value


def _to_tag_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        raise AwsElasticIpResponseFormatError("Tags must be a list")
    tags: dict[str, str] = {}
    for raw_tag in value:
        tag = _required_mapping(raw_tag, "tag")
        tags[_required_string(tag, "Key")] = _required_string(tag, "Value")
    return tags
