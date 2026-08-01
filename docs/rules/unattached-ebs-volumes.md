# Unattached EBS volume rule

## Purpose

Identify EBS volumes that are in the AWS `available` state and are older than a
configurable minimum resource age. These volumes can continue to incur storage
charges despite not being attached to an EC2 instance.

## AWS interaction

The AWS adapter creates a boto3 EC2 client and calls the paginated
`describe_volumes` operation with the server-side filter `status=available`.
Pagination is mandatory: a single AWS response is not guaranteed to include all
volumes.

The adapter translates AWS response fields into an `EbsVolume` domain model.
No detection rule imports boto3 or receives a raw AWS response.

## Rule conditions

All conditions must be true:

1. The volume state is `available`.
2. Its creation time is at least `minimum_volume_age_days` old (default: 14).
3. It does not have the case-insensitive tag
   `cost-optimizer:exclude=true`.

## Savings estimate

`size_gib × configured reference monthly USD/GiB rate`

The estimate includes the configured rate, size, and creation time as finding
evidence. It is deliberately labeled a reference estimate because EBS pricing
depends on region and volume type.

## Safety posture

This milestone is read-only. A finding recommends human review; it does not
persist a finding, send a notification, or call a delete API.

AWS does not provide a detachment timestamp in `describe_volumes`. Therefore,
the first rule must not claim a volume has been unattached for the full age
threshold. After DynamoDB persistence is introduced, the system will record a
`first_seen_unattached_at` value and can apply a true detached-duration rule.
