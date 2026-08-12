from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from cost_optimization.domain.models import MetricQuery, MetricStatistic
from cost_optimization.infrastructure.aws.cloudwatch_metrics import Boto3CloudWatchMetricReader


def test_metric_reader_batches_queries_and_aggregates_selected_statistics() -> None:
    client = FakeCloudWatchClient(
        [
            {"Id": "m0", "StatusCode": "Complete", "Values": [1.0, 3.0]},
            {"Id": "m1", "StatusCode": "Complete", "Values": [100.0, 200.0]},
        ]
    )
    query_time = datetime(2026, 8, 12, tzinfo=UTC)
    windows = Boto3CloudWatchMetricReader(client).get_daily_windows(
        {
            "cpu": _query("CPUUtilization", MetricStatistic.MAXIMUM, query_time),
            "network": _query("NetworkIn", MetricStatistic.SUM, query_time),
        }
    )

    request = client.requests[0]
    assert len(request["MetricDataQueries"]) == 2
    assert request["MetricDataQueries"][0]["MetricStat"]["Stat"] == "Maximum"
    assert windows["cpu"].value == Decimal("3.0")
    assert windows["network"].value == Decimal("300.0")
    assert windows["network"].sample_count == 2


def test_metric_reader_preserves_an_empty_complete_metric_as_no_data() -> None:
    client = FakeCloudWatchClient([{"Id": "m0", "StatusCode": "Complete", "Values": []}])

    window = Boto3CloudWatchMetricReader(client).get_daily_windows(
        {"requests": _query("RequestCount", MetricStatistic.SUM, datetime(2026, 8, 12, tzinfo=UTC))}
    )["requests"]

    assert window.sample_count == 0
    assert window.value is None


class FakeCloudWatchClient:
    def __init__(self, results: list[dict[str, object]]) -> None:
        self._results = results
        self.requests: list[dict[str, object]] = []

    def get_metric_data(self, **kwargs: object) -> dict[str, object]:
        self.requests.append(kwargs)
        return {"MetricDataResults": self._results}


def _query(metric_name: str, statistic: MetricStatistic, end_at: datetime) -> MetricQuery:
    return MetricQuery(
        namespace="AWS/EC2",
        metric_name=metric_name,
        statistic=statistic,
        dimensions={"InstanceId": "i-123"},
        start_at=datetime(2026, 7, 29, tzinfo=UTC),
        end_at=end_at,
        expected_sample_count=14,
    )
