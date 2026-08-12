# Unassociated Elastic IP rule

## What it detects

This read-only rule creates a finding for a VPC Elastic IP when its AWS
`describe_addresses` response has no `AssociationId`, `NetworkInterfaceId`, or
`InstanceId`.

The scanner respects `cost-optimizer:exclude=true` and does not change or
release an address.

## Cost estimate

The default `$3.60/month` reference estimate is configurable through
`COST_OPTIMIZER_ELASTIC_IP_REFERENCE_MONTHLY_RATE_USD`. It is a visible
planning assumption, not a billing-grade price. The rule evidence retains the
assumption used for the finding.

## Why this definition

The association fields are direct AWS evidence that an EIP is attached to a
resource. This is far more reliable than inferring usage from traffic data.
The finding still requires a human review because an address may be deliberately
reserved for a planned migration or allow-listed integration.
