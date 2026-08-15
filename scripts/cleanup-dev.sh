#!/usr/bin/env bash
# Deletes the development deployment, hosted dashboard assets, and SAM-managed artifacts.
#
# This script intentionally targets only the development stack. Production
# teardown should remain an explicit, separately reviewed operation.

set -euo pipefail

readonly STACK_NAME="aws-cost-optimizer-dev"
readonly DEFAULT_REGION="ap-south-1"

region="${AWS_REGION:-${AWS_DEFAULT_REGION:-$DEFAULT_REGION}}"
skip_confirmation=false

usage() {
  cat <<'EOF'
Usage: ./scripts/cleanup-dev.sh [--region REGION] [--yes]

Deletes the aws-cost-optimizer-dev SAM application, its private hosted-dashboard
assets, and the deployment artifacts created for it. The script never targets
staging or production.

Options:
  --region REGION  AWS region containing the development stack.
  --yes            Skip the interactive confirmation.
  --help           Show this message.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --region." >&2
        exit 2
      fi
      region="$2"
      shift 2
      ;;
    --yes)
      skip_confirmation=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

for command in aws sam; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Required command not found: $command" >&2
    exit 1
  fi
done

account_id="$(aws sts get-caller-identity --query Account --output text)"

if ! aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$region" >/dev/null 2>&1; then
  echo "No deployment stack named '$STACK_NAME' exists in '$region'."
  echo "Nothing to clean up."
  exit 0
fi

echo "AWS account: $account_id"
echo "Region: $region"
echo "This permanently deletes the '$STACK_NAME' development stack, hosted dashboard assets, and SAM artifacts."

if [[ "$skip_confirmation" != true ]]; then
  read -r -p "Type DELETE to continue: " confirmation
  if [[ "$confirmation" != "DELETE" ]]; then
    echo "Cleanup cancelled."
    exit 0
  fi
fi

# CloudFormation cannot delete a non-empty S3 bucket. The dashboard bucket is
# an application-owned, non-versioned bucket whose exact name is read from this
# development stack, never guessed or supplied by the caller.
dashboard_bucket_name="$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$region" \
  --query "Stacks[0].Outputs[?OutputKey=='DashboardBucketName'].OutputValue | [0]" \
  --output text)"

if [[ -n "$dashboard_bucket_name" && "$dashboard_bucket_name" != "None" ]]; then
  echo "Deleting hosted dashboard assets from '$dashboard_bucket_name'."
  aws s3 rm "s3://$dashboard_bucket_name" --recursive --region "$region"
fi

# sam delete removes the CloudFormation stack and the deployment artifacts
# associated with this application. It does not delete a shared SAM bucket.
SAM_CLI_TELEMETRY=0 sam delete \
  --stack-name "$STACK_NAME" \
  --region "$region" \
  --no-prompts

if aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$region" >/dev/null 2>&1; then
  echo "Cleanup did not complete: stack '$STACK_NAME' still exists in '$region'." >&2
  exit 1
fi

echo "Verified: the development deployment is deleted."
echo "No deployed dashboard or other AWS resources managed by this project remain in '$region'."
