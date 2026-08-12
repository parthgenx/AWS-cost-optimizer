"""Small Lambda runtime helpers shared by resource-specific workers."""

from __future__ import annotations


def account_id_from_lambda_arn(invoked_function_arn: str) -> str:
    """Extract an account ID without granting a worker an extra STS permission."""
    arn_parts = invoked_function_arn.split(":")
    if len(arn_parts) < 7 or arn_parts[2] != "lambda" or not arn_parts[4].isdigit():
        raise ValueError("invoked_function_arn must be a valid Lambda ARN")
    account_id = arn_parts[4]
    if len(account_id) != 12:
        raise ValueError("Lambda ARN must contain a 12-digit AWS account ID")
    return account_id
