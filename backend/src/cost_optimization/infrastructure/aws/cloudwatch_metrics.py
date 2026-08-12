"""boto3-backed batched CloudWatch metric reads for utilization recommendations."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol, cast

import boto3
from botocore.config import Config

from cost_optimization.domain.models import MetricQuery, MetricWindow

_DAILY_PERIOD_SECONDS = 86_400
_MAX_QUERIES_PER_REQUEST = 500


class CloudWatchClient(Protocol):
    """Minimal CloudWatch client surface required by the metrics adapter."""

    def get_metric_data(self, **kwargs: object) -> Mapping[str, object]:
        """Return aggregate CloudWatch metric data for one batched request."""


class AwsCloudWatchResponseFormatError(ValueError):
    """Raised when CloudWatch returns incomplete or malformed metric data."""


def create_cloudwatch_client(region: str) -> CloudWatchClient:
    """Create a CloudWatch client with bounded retry behaviour for transient AWS failures."""
    return cast(
        CloudWatchClient,
        boto3.client(
            "cloudwatch",
            region_name=region,
            config=Config(retries={"mode": "standard", "max_attempts": 5}),
        ),
    )


class Boto3CloudWatchMetricReader:
    """Reads up to 500 metric queries at a time and maps them to domain windows."""

    def __init__(self, client: CloudWatchClient) -> None:
        self._client = client

    def get_daily_windows(self, queries: Mapping[str, MetricQuery]) -> Mapping[str, MetricWindow]:
        """Batch CloudWatch queries while preserving the caller's stable metric identifiers."""
        windows: dict[str, MetricWindow] = {}
        query_items = list(queries.items())
        for start_index in range(0, len(query_items), _MAX_QUERIES_PER_REQUEST):
            batch = query_items[start_index : start_index + _MAX_QUERIES_PER_REQUEST]
            windows.update(self._get_batch_windows(batch))
        return windows

    def _get_batch_windows(
        self, query_items: list[tuple[str, MetricQuery]]
    ) -> dict[str, MetricWindow]:
        query_ids = {f"m{index}": key for index, (key, _) in enumerate(query_items)}
        first_query = query_items[0][1]
        response = self._client.get_metric_data(
            MetricDataQueries=[
                _metric_data_query(query_id, query)
                for query_id, (_, query) in zip(query_ids, query_items, strict=True)
            ],
            StartTime=first_query.start_at,
            EndTime=first_query.end_at,
            ScanBy="TimestampAscending",
        )
        results = response.get("MetricDataResults")
        if not isinstance(results, list):
            raise AwsCloudWatchResponseFormatError("MetricDataResults must be a list")
        values_by_key = _values_by_key(results, query_ids)
        return {
            key: MetricWindow(
                metric_name=query.metric_name,
                statistic=query.statistic,
                sample_count=len(values_by_key[key]),
                expected_sample_count=query.expected_sample_count,
                value=_aggregate(values_by_key[key], query),
            )
            for key, query in query_items
        }


def _metric_data_query(query_id: str, query: MetricQuery) -> dict[str, object]:
    return {
        "Id": query_id,
        "MetricStat": {
            "Metric": {
                "Namespace": query.namespace,
                "MetricName": query.metric_name,
                "Dimensions": [
                    {"Name": name, "Value": value}
                    for name, value in sorted(query.dimensions.items())
                ],
            },
            "Period": _DAILY_PERIOD_SECONDS,
            "Stat": query.statistic.value,
        },
        "ReturnData": True,
    }


def _values_by_key(results: list[object], query_ids: Mapping[str, str]) -> dict[str, list[Decimal]]:
    values_by_key: dict[str, list[Decimal]] = {key: [] for key in query_ids.values()}
    result_ids: set[str] = set()
    for raw_result in results:
        if not isinstance(raw_result, Mapping):
            raise AwsCloudWatchResponseFormatError("MetricDataResults entries must be objects")
        result_id = raw_result.get("Id")
        if not isinstance(result_id, str) or result_id not in query_ids:
            raise AwsCloudWatchResponseFormatError(
                "CloudWatch returned an unknown metric result ID"
            )
        if result_id in result_ids:
            raise AwsCloudWatchResponseFormatError(
                "CloudWatch returned a duplicate metric result ID"
            )
        result_ids.add(result_id)
        if raw_result.get("StatusCode") != "Complete":
            raise AwsCloudWatchResponseFormatError("CloudWatch metric result was not complete")
        raw_values = raw_result.get("Values")
        if not isinstance(raw_values, list):
            raise AwsCloudWatchResponseFormatError("CloudWatch metric Values must be a list")
        values_by_key[query_ids[result_id]] = [_decimal_value(value) for value in raw_values]
    if result_ids != set(query_ids):
        raise AwsCloudWatchResponseFormatError(
            "CloudWatch omitted one or more requested metric results"
        )
    return values_by_key


def _decimal_value(value: object) -> Decimal:
    if not isinstance(value, (int, float, Decimal)) or isinstance(value, bool):
        raise AwsCloudWatchResponseFormatError("CloudWatch metric values must be numeric")
    return Decimal(str(value))


def _aggregate(values: list[Decimal], query: MetricQuery) -> Decimal | None:
    if not values:
        return None
    if query.statistic.value == "Maximum":
        return max(values)
    return sum(values, start=Decimal("0"))
