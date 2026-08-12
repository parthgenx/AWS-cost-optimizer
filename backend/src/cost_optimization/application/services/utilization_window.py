"""Shared observation-window construction for CloudWatch-backed recommendation scans."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from cost_optimization.domain.models import MetricQuery, MetricStatistic


def daily_metric_query(
    *,
    namespace: str,
    metric_name: str,
    statistic: MetricStatistic,
    dimensions: dict[str, str],
    evaluated_at: datetime,
    lookback_days: int,
) -> MetricQuery:
    """Create a query over full UTC days, excluding today's incomplete observation period."""
    if evaluated_at.tzinfo is None:
        raise ValueError("evaluated_at must be timezone-aware")
    if lookback_days < 1:
        raise ValueError("lookback_days must be at least 1")
    end_at = evaluated_at.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return MetricQuery(
        namespace=namespace,
        metric_name=metric_name,
        statistic=statistic,
        dimensions=dimensions,
        start_at=end_at - timedelta(days=lookback_days),
        end_at=end_at,
        expected_sample_count=lookback_days,
    )
