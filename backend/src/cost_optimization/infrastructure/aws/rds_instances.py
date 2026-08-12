"""boto3-backed discovery of available RDS instances for utilization recommendations."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import Protocol, cast

import boto3
from botocore.config import Config

from cost_optimization.domain.models import RdsInstance, ResourceReference, ResourceType


class RdsPaginator(Protocol):
    """Small protocol matching the paginator surface used by this adapter."""

    def paginate(self, **kwargs: object) -> Iterator[Mapping[str, object]]:
        """Yield paginated RDS API result pages."""


class RdsClient(Protocol):
    """Minimal RDS client surface required by the instance discovery adapter."""

    def get_paginator(self, operation_name: str) -> RdsPaginator:
        """Return a paginator for the requested RDS operation."""

    def list_tags_for_resource(self, **kwargs: object) -> Mapping[str, object]:
        """Return resource tags used by the shared exclusion policy."""


class AwsRdsResponseFormatError(ValueError):
    """Raised when required RDS response fields are missing or malformed."""


def create_rds_client(region: str) -> RdsClient:
    """Create an RDS client with bounded retries for throttling and transient failures."""
    return cast(
        RdsClient,
        boto3.client(
            "rds",
            region_name=region,
            config=Config(retries={"mode": "standard", "max_attempts": 5}),
        ),
    )


class Boto3RdsInstanceDiscovery:
    """Maps available provisioned RDS instances and their tags into domain models."""

    def __init__(self, client: RdsClient, *, account_id: str, region: str) -> None:
        self._client = client
        self._account_id = account_id
        self._region = region

    def list_available_instances(self) -> list[RdsInstance]:
        """Retrieve available DB instances and fetch tags needed for policy exclusions."""
        paginator = self._client.get_paginator("describe_db_instances")
        instances: list[RdsInstance] = []
        for page in paginator.paginate():
            for raw_instance in _required_list(page, "DBInstances"):
                instance = _required_mapping(raw_instance, "DB instance")
                if instance.get("DBInstanceStatus") != "available":
                    continue
                instances.append(self._to_domain_instance(instance))
        return instances

    def _to_domain_instance(self, raw_instance: Mapping[str, object]) -> RdsInstance:
        identifier = _required_string(raw_instance, "DBInstanceIdentifier")
        arn = _required_string(raw_instance, "DBInstanceArn")
        return RdsInstance(
            resource=ResourceReference(
                resource_type=ResourceType.RDS_INSTANCE,
                resource_id=identifier,
                account_id=self._account_id,
                region=self._region,
            ),
            instance_class=_required_string(raw_instance, "DBInstanceClass"),
            engine=_required_string(raw_instance, "Engine"),
            created_at=_required_datetime(raw_instance, "InstanceCreateTime"),
            multi_az=_required_bool(raw_instance, "MultiAZ"),
            db_cluster_identifier=_optional_string(raw_instance, "DBClusterIdentifier"),
            read_replica_source_identifier=_optional_string(
                raw_instance, "ReadReplicaSourceDBInstanceIdentifier"
            ),
            tags=self._tags_for_arn(arn),
        )

    def _tags_for_arn(self, arn: str) -> dict[str, str]:
        response = self._client.list_tags_for_resource(ResourceName=arn)
        return _to_tag_mapping(response.get("TagList", []))


def _required_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AwsRdsResponseFormatError(f"{field_name} must be an object")
    return value


def _required_list(values: Mapping[str, object], field_name: str) -> list[object]:
    value = values.get(field_name)
    if not isinstance(value, list):
        raise AwsRdsResponseFormatError(f"{field_name} must be a list")
    return value


def _required_string(values: Mapping[str, object], field_name: str) -> str:
    value = values.get(field_name)
    if not isinstance(value, str) or not value:
        raise AwsRdsResponseFormatError(f"{field_name} must be a non-empty string")
    return value


def _optional_string(values: Mapping[str, object], field_name: str) -> str | None:
    value = values.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise AwsRdsResponseFormatError(f"{field_name} must be a non-empty string when present")
    return value


def _required_bool(values: Mapping[str, object], field_name: str) -> bool:
    value = values.get(field_name)
    if not isinstance(value, bool):
        raise AwsRdsResponseFormatError(f"{field_name} must be a boolean")
    return value


def _required_datetime(values: Mapping[str, object], field_name: str) -> datetime:
    value = values.get(field_name)
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise AwsRdsResponseFormatError(f"{field_name} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def _to_tag_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        raise AwsRdsResponseFormatError("TagList must be a list")
    tags: dict[str, str] = {}
    for raw_tag in value:
        tag = _required_mapping(raw_tag, "tag")
        tags[_required_string(tag, "Key")] = _required_string(tag, "Value")
    return tags
