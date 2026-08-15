# Threat model

## Assets

- AWS resources evaluated by scanners.
- Findings, approvals, cleanup requests, and append-only audit records.
- Cognito operator identities and JWTs.
- GitHub OIDC deployment permissions.
- Deployment artifacts and CloudWatch operational evidence.

## Primary threats and controls

| Threat | Control | Residual risk |
|---|---|---|
| Caller impersonates an approver with a header | API Gateway validates Cognito JWTs; FastAPI uses verified `sub` and requires the operator group | A valid operator token remains powerful until it expires or is revoked |
| Low utilization causes destructive action | EC2/RDS/ALB are recommendation-only; EBS cleanup requires approval, separate request, live revalidation, and two deployment safety controls | A human can still make an incorrect approval decision |
| Scanner compromise deletes resources | Scanner roles are read-only; only the isolated EBS cleanup role has `DeleteVolume` | Cleanup-role compromise remains a high-impact event |
| Failed EventBridge invocation disappears | Retries plus encrypted SQS DLQs and alarms | Operators must investigate and safely replay; the system does not automatically replay destructive events |
| GitHub repository compromise obtains AWS keys | GitHub OIDC uses short-lived credentials and an exact deployment-environment subject | A compromise of protected `main` plus the GitHub environment could still deploy within the role's permissions |
| AWS credentials or tokens leak through logs | Tokens are not logged; documentation prohibits tokens in source control, shared history, CI logs, and screenshots | Application code must continue to avoid logging request authorization headers |
| Cost grows after a demo | Scheduled scans are disabled by default; cleanup script deletes the development stack; CI deploys safe defaults | AWS billing data can lag, and resources created outside the stack require separate cleanup |

## Explicit non-goals

- This is not a multi-tenant SaaS isolation model.
- The system does not use an unrestricted public signup flow.
- It does not automatically terminate EC2, RDS, or load-balancer resources.
- It does not claim billing-grade savings estimates for utilization findings.

## Future review triggers

Revisit this threat model before enabling real EBS deletion in a shared account,
adding cross-account scans, exposing a browser frontend, or introducing a
production deployment environment.
