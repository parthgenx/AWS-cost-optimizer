# Operations runbook

## Scope

This runbook covers the deployed development environment. It is intentionally
operational rather than a product-user guide: a finding is not an incident, but
an alarm, dead-letter message, or unexpected cleanup transition is.

The CloudWatch dashboard named `aws-cost-optimizer-<environment>` shows Lambda
errors, scanner outcomes, dead-letter queue depth, and API Gateway responses.
Operational alarms publish to the optional operational-alert SNS topic; finding
notifications continue to use their separate topic.

## Alarm response

### Scanner function errors

1. Open the dashboard's **Lambda errors** widget and identify the function.
2. Read the matching structured CloudWatch log stream around the alarm time.
3. Record the correlation ID, function name, error type, and affected AWS
   service in the incident note. Do not copy tokens or resource data that is
   not necessary for diagnosis.
4. Fix the underlying permission, AWS response, configuration, or code issue.
5. Run the affected scanner manually once. Confirm `FailedScans` stops rising
   and no unexpected findings were created.

Do not disable the alarm to silence a genuine scanner failure.

### API or cleanup workflow errors

An API/cleanup alarm is higher severity because it may affect approval audit
events or an approved cleanup workflow.

1. Confirm whether the cleanup Lambda was in dry-run mode.
2. Inspect the finding's DynamoDB status and append-only audit events.
3. If the failure occurred after a cleanup request, do not reissue the request
   until the resource and finding are revalidated.
4. Keep `CleanupDryRun=true` and `CleanupExecutionEnabled=false` while
   investigating. Those independent controls prevent an accidental real delete.
5. After remediation, use a deliberately created non-production test resource
   to validate the exact path.

### Dead-letter queue messages

DLQ messages mean EventBridge exhausted its retries. They are evidence, not an
automatic replay queue.

1. Inspect the original event and the target function's error first.
2. Resolve the cause before replaying anything.
3. For a scan event, manually invoke the matching scanner after the fix.
4. For a cleanup event, re-check approval state and live EBS eligibility before
   sending a new cleanup request. Never replay an old cleanup event blindly.
5. Delete the investigated DLQ message only after recording the outcome.

### API Gateway 5xx responses

1. Compare the API Gateway response time with API Lambda errors.
2. Check API Gateway access logs using the request ID and the Lambda structured
   log using the correlation ID.
3. Verify Cognito configuration only after confirming a 5xx; invalid or missing
   tokens should be a client-side 401 response, not a server error.

## Safe sandbox demonstration

Use a separate development account or clearly labelled non-production
resources. Never create a demonstration finding from a production workload.

1. Deploy with scheduled scans disabled and both cleanup safety parameters at
   their defaults.
2. Create one small, intentionally unattached EBS test volume with a tag such
   as `purpose=cost-optimizer-demo`.
3. Invoke the EBS scanner manually and confirm a finding, scan-run record,
   metric, and optional SNS notification.
4. Create a Cognito operator user, add it to `cost-optimizer-operators`, and
   use an access token to make the approval API request.
5. Request cleanup and confirm the cleanup Lambda records a dry-run audit event.
6. Capture only sanitized dashboard, API, and architecture screenshots.
7. Run `./scripts/cleanup-dev.sh --region ap-south-1` immediately after the
   demo, then manually remove the temporary EBS test volume if it was created
   outside the project stack.

## What to collect for a portfolio demonstration

- One dashboard screenshot after a successful scan.
- A redacted CloudWatch log with correlation ID and scanner result.
- The API's Cognito-protected approval response, with no token visible.
- DynamoDB finding and audit-event screenshots with non-sensitive test IDs.
- CI check and manually approved deployment workflow screenshots.

Use exact observations in your résumé, such as number of supported resource
rules or test coverage. Do not claim savings, uptime, or production traffic
that the demonstration did not measure.
