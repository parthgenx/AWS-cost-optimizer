# Utilization recommendation rules

## Purpose

These rules identify workloads worth a human cost-optimization review. They do
not prove that a workload is unused, calculate a savings amount, stop a
resource, or create a cleanup request.

All rules honour `cost-optimizer:exclude=true`. They use complete UTC days and
exclude the current day, because its metrics are incomplete.

## EC2: sustained low utilization

Rule ID: `sustained-low-utilization-ec2-instance`

The scanner discovers running EC2 instances and queries daily `CPUUtilization`,
`NetworkIn`, and `NetworkOut` metrics from the `AWS/EC2` namespace. The
recommendation requires complete metric evidence for the whole window.

Default thresholds:

- 14 complete days of observation
- Maximum daily CPU at or below 5%
- Combined network traffic at or below 1 GiB across the full window

The recommended action is to verify ownership, schedules, and dependencies
before rightsizing, stopping, or terminating the instance.

## RDS: low utilization with no client connections

Rule ID: `sustained-low-utilization-rds-instance`

The scanner discovers available RDS instances and queries daily
`CPUUtilization` and `DatabaseConnections` metrics from `AWS/RDS`. It requires
complete evidence for the whole window.

Default thresholds:

- 14 complete days of observation
- Maximum daily CPU at or below 5%
- Maximum reported client connections equal to zero

The rule skips Multi-AZ, clustered, Aurora, and read-replica source instances.
Those topologies are more likely to serve resilience or dependency roles and
need a separate, more context-aware policy. `DatabaseConnections` excludes
internal database connections, so it is an investigation signal only. [AWS RDS metric definitions](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-metrics.html)

## Application Load Balancer: no request evidence

Rule ID: `no-request-application-load-balancer`

The scanner discovers active Application Load Balancers and queries the daily
`RequestCount` metric from `AWS/ApplicationELB`. It recommends review when the
load balancer has no metric points over the complete observation window, or
when its reported total is zero.

AWS publishes Application Load Balancer metrics only when requests flow, and
health checks are not included in `RequestCount`. An absent metric is therefore
a useful no-request signal, but DNS, failover, listener, target group, and
planned-use dependencies still need human confirmation. [AWS ALB metric definitions](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-cloudwatch-metrics.html)

## Metric batching and failure behaviour

The CloudWatch adapter uses boto3 `get_metric_data` and batches up to 500
metric queries in a request. Each query is aggregated into a typed metric
window before reaching the rule. Missing or incomplete required EC2 or RDS data
results in no finding. That fail-closed policy avoids a false recommendation
when monitoring evidence is insufficient.

ALB absence is intentionally treated differently because AWS documents that
the metric is not reported without requests.

## Why recommendations have no monthly savings estimate

This milestone does not use an AWS price catalog. EC2, RDS, and load-balancer
costs depend on region, usage model, instance type, storage, data transfer, and
other configuration. A later pricing integration can add an explicit, auditable
methodology. Until then, a blank estimate is more honest than a misleading
number.
