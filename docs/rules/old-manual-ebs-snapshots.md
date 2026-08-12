# Old manual EBS snapshot rule

## What it detects

The scanner retrieves only snapshots owned by the current AWS account and in
the `completed` state. It creates a review finding when a snapshot is at least
90 days old, is not excluded with `cost-optimizer:exclude=true`, and does not
have the standard AMI-created description prefix `Created by CreateImage(`.

## Why it is review-only

An old snapshot can still be essential for disaster recovery, compliance, or
forensic retention. AWS charges for incremental snapshot data rather than the
source volume size returned by `describe_snapshots`; using that source size as a
monthly cost estimate would overstate the saving. Therefore the finding has no
automatic cleanup path and no fabricated savings amount.

## What boto3 does here

The AWS adapter calls paginated EC2 `describe_snapshots` with `OwnerIds=["self"]`
and the `completed` status filter. Pagination avoids truncating large accounts,
and the owner filter prevents evaluating snapshots merely shared with the
account.
