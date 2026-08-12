"""boto3-backed discovery of active Application Load Balancers for utilization review."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import Protocol, cast

import boto3
from botocore.config import Config

from cost_optimization.domain.models import (
    ApplicationLoadBalancer,
    ResourceReference,
    ResourceType,
)


class LoadBalancerPaginator(Protocol):
    """Small protocol matching the paginator surface used by this adapter."""

    def paginate(self, **kwargs: object) -> Iterator[Mapping[str, object]]:
        """Yield paginated Elastic Load Balancing API result pages."""


class ApplicationLoadBalancerClient(Protocol):
    """Minimal ELBv2 client surface required by the ALB discovery adapter."""

    def get_paginator(self, operation_name: str) -> LoadBalancerPaginator:
        """Return a paginator for the requested ELBv2 operation."""

    def describe_tags(self, **kwargs: object) -> Mapping[str, object]:
        """Return tags used by the shared exclusion policy."""


class AwsApplicationLoadBalancerResponseFormatError(ValueError):
    """Raised when required Application Load Balancer fields are malformed."""


def create_elbv2_client(region: str) -> ApplicationLoadBalancerClient:
    """Create an ELBv2 client with bounded retries for throttling and transient failures."""
    return cast(
        ApplicationLoadBalancerClient,
        boto3.client(
            "elbv2",
            region_name=region,
            config=Config(retries={"mode": "standard", "max_attempts": 5}),
        ),
    )


class Boto3ApplicationLoadBalancerDiscovery:
    """Maps active application load balancers and their tags into domain models."""

    def __init__(
        self, client: ApplicationLoadBalancerClient, *, account_id: str, region: str
    ) -> None:
        self._client = client
        self._account_id = account_id
        self._region = region

    def list_active_load_balancers(self) -> list[ApplicationLoadBalancer]:
        """Retrieve only active application load balancers and their exclusion tags."""
        paginator = self._client.get_paginator("describe_load_balancers")
        load_balancers: list[ApplicationLoadBalancer] = []
        for page in paginator.paginate():
            for raw_load_balancer in _required_list(page, "LoadBalancers"):
                load_balancer = _required_mapping(raw_load_balancer, "load balancer")
                if (
                    load_balancer.get("Type") != "application"
                    or _state_code(load_balancer) != "active"
                ):
                    continue
                load_balancers.append(self._to_domain_load_balancer(load_balancer))
        return load_balancers

    def _to_domain_load_balancer(
        self, raw_load_balancer: Mapping[str, object]
    ) -> ApplicationLoadBalancer:
        arn = _required_string(raw_load_balancer, "LoadBalancerArn")
        return ApplicationLoadBalancer(
            resource=ResourceReference(
                resource_type=ResourceType.APPLICATION_LOAD_BALANCER,
                resource_id=arn,
                account_id=self._account_id,
                region=self._region,
            ),
            name=_required_string(raw_load_balancer, "LoadBalancerName"),
            cloudwatch_dimension_value=_cloudwatch_dimension_value(arn),
            scheme=_required_string(raw_load_balancer, "Scheme"),
            created_at=_required_datetime(raw_load_balancer, "CreatedTime"),
            tags=self._tags_for_arn(arn),
        )

    def _tags_for_arn(self, arn: str) -> dict[str, str]:
        response = self._client.describe_tags(ResourceArns=[arn])
        tag_descriptions = _required_list(response, "TagDescriptions")
        if len(tag_descriptions) != 1:
            raise AwsApplicationLoadBalancerResponseFormatError(
                "TagDescriptions must contain one requested load balancer"
            )
        description = _required_mapping(tag_descriptions[0], "tag description")
        return _to_tag_mapping(description.get("Tags", []))


def _state_code(values: Mapping[str, object]) -> str:
    state = _required_mapping(values.get("State"), "State")
    return _required_string(state, "Code")


def _cloudwatch_dimension_value(load_balancer_arn: str) -> str:
    marker = "loadbalancer/"
    if marker not in load_balancer_arn:
        raise AwsApplicationLoadBalancerResponseFormatError(
            "LoadBalancerArn must contain a loadbalancer resource component"
        )
    dimension_value = load_balancer_arn.split(marker, maxsplit=1)[1]
    if not dimension_value:
        raise AwsApplicationLoadBalancerResponseFormatError(
            "LoadBalancerArn resource component is empty"
        )
    return dimension_value


def _required_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AwsApplicationLoadBalancerResponseFormatError(f"{field_name} must be an object")
    return value


def _required_list(values: Mapping[str, object], field_name: str) -> list[object]:
    value = values.get(field_name)
    if not isinstance(value, list):
        raise AwsApplicationLoadBalancerResponseFormatError(f"{field_name} must be a list")
    return value


def _required_string(values: Mapping[str, object], field_name: str) -> str:
    value = values.get(field_name)
    if not isinstance(value, str) or not value:
        raise AwsApplicationLoadBalancerResponseFormatError(
            f"{field_name} must be a non-empty string"
        )
    return value


def _required_datetime(values: Mapping[str, object], field_name: str) -> datetime:
    value = values.get(field_name)
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise AwsApplicationLoadBalancerResponseFormatError(
            f"{field_name} must be a timezone-aware datetime"
        )
    return value.astimezone(UTC)


def _to_tag_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        raise AwsApplicationLoadBalancerResponseFormatError("Tags must be a list")
    tags: dict[str, str] = {}
    for raw_tag in value:
        tag = _required_mapping(raw_tag, "tag")
        tags[_required_string(tag, "Key")] = _required_string(tag, "Value")
    return tags
