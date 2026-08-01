# Delivery milestones

1. **Foundation:** package structure, FastAPI health endpoint, configuration,
   structured logs, tests, Docker, and CI.
2. **Unattached EBS volume detection:** one complete read-only vertical slice.
3. **Scheduling and notification:** EventBridge, SNS, scan records, metrics,
   retries, and DLQ.
4. **Approval and safe cleanup:** state transitions, audit trail, revalidation,
   EventBridge cleanup event, and dry-run mode.
5. **Additional resources:** Elastic IPs, EBS snapshots, then carefully scoped
   EC2 detection.
6. **Production hardening:** Cognito authorization, alarms, OIDC deployment,
   runbooks, and sandbox end-to-end testing.

Each milestone is reviewed before the next starts.
