# Deployment foundation

## What this milestone deploys

The SAM template creates three on-demand DynamoDB tables, separate read-only
scanner Lambdas for EBS volumes, Elastic IPs, EBS snapshots, EC2 utilization,
RDS utilization, and Application Load Balancers, an isolated EBS cleanup
Lambda, and an API Lambda. The API is exposed through API Gateway HTTP API and
protected by a Cognito JWT authorizer. The stack also includes separate SNS
topics for findings and operational alerts, EventBridge rules, encrypted SQS
dead-letter queues, CloudWatch alarms, and an operational dashboard.

## Why AWS SAM

AWS SAM is a CloudFormation extension for serverless applications. It keeps the
Lambda, IAM, DynamoDB, and CloudWatch configuration in one reviewable template
without adding an infrastructure framework that would obscure the project.

## Lambda flow

1. A caller manually invokes one resource-specific scanner Lambda, or
   EventBridge invokes every scanner when scheduled scans are enabled.
2. The handler gets region and table names from environment variables.
3. It extracts the AWS account ID from Lambda's invocation ARN, avoiding an
   extra STS API permission.
4. It wires a boto3 resource adapter, pure rule, and DynamoDB repositories.
   The EC2, RDS, and Application Load Balancer scanners also use a batched
   CloudWatch metrics adapter for their utilization evidence.
5. It emits scan metrics through structured CloudWatch logs.
6. If findings exist, it publishes a compact summary to SNS.
7. It returns a small scan summary and writes structured logs to CloudWatch.

The API Lambda is a separate path. API Gateway validates a Cognito JWT before
the request reaches FastAPI. FastAPI verifies the required Cognito operator
group in the API Gateway-provided claims, then records the JWT subject in the
approval audit event or cleanup request.

## Scheduled scans and notifications

Scheduled scans are disabled by default. This prevents unexpected background
activity in a newly deployed development environment. Enable them deliberately
when deploying:

```bash
sam deploy ... \
  --parameter-overrides \
  'Environment=dev ScheduledScansEnabled=true NotificationEmail=operator@example.com'
```

`ScanScheduleExpression` defaults to 03:00 UTC every Sunday and can be
overridden with a valid EventBridge schedule expression. Keep the full
parameter-override string quoted when the expression contains spaces, for
example: `'Environment=dev ScheduledScansEnabled=true
ScanScheduleExpression="rate(1 hour)"'`. EventBridge retries a failed Lambda
invocation up to three times for one hour. After that, it writes the original
event to the encrypted SQS dead-letter queue for investigation.

SNS notifications are sent only when a completed scan has one or more findings.
This avoids routine “nothing found” email noise. Email recipients must confirm
the SNS subscription before receiving messages. A failure to publish a
notification is logged and metered but does not rerun a scan that already
completed successfully.

## IAM boundary

Each scanner receives only the read permissions it needs. The EBS, Elastic IP,
snapshot, and EC2 scanners use the matching EC2 `Describe` action. The RDS
scanner receives `rds:DescribeDBInstances` and `rds:ListTagsForResource`; the
Application Load Balancer scanner receives `elasticloadbalancing:DescribeLoadBalancers`
and `elasticloadbalancing:DescribeTags`; utilization scanners receive
`cloudwatch:GetMetricData`. Each may update the Findings table, create/update
ScanRuns records, and publish summary notifications. These discovery and metric
read actions cannot be restricted to a specific resource ARN, so they use
`Resource: "*"`.

Only the isolated EBS cleanup Lambda has `ec2:DeleteVolume`, scoped to EBS
volume ARNs in the deployed account and region. It is dry-run by default and
requires explicit deployment configuration before it can delete. No Lambda has
permission to release IPs, alter RDS, or modify load balancers.

The API Lambda can read one finding, atomically write an approval and audit
event, and publish a cleanup request to the default EventBridge bus. It has no
permission to delete an EBS volume or modify the resources being evaluated.

## Environment naming

The SAM stack uses concise deployment labels (`dev`, `staging`, and `prod`) in
resource names. The application configuration normalizes `dev` to
`development` and `prod` to `production` before validation, so Python code
always receives a canonical environment value.

## Local validation

After AWS SAM CLI is installed, validate and build from the repository root:

```bash
sam validate --template infrastructure/template.yaml
sam validate --lint --template infrastructure/template.yaml
sam build --template-file infrastructure/template.yaml
```

Deployment is deliberately deferred until the infrastructure is reviewed.

## Cleaning up the development environment

The project includes a deliberately narrow cleanup command:

```bash
./scripts/cleanup-dev.sh --region ap-south-1
```

It only targets the `aws-cost-optimizer-dev` stack. After a `DELETE`
confirmation, `sam delete` removes the CloudFormation resources and the
deployment artifacts associated with that application. The script leaves an
empty shared SAM artifact bucket alone because it may be used by another SAM
project; an empty S3 bucket has no storage charge. It verifies that the stack
no longer exists before reporting success.

For automation, such as a temporary sandbox environment, use:

```bash
./scripts/cleanup-dev.sh --region ap-south-1 --yes
```

Do not use this script as a production teardown mechanism. A production
environment needs a separately reviewed retention and recovery decision.

AWS can report charges after resources are removed because billing data is
delayed. Once the script succeeds, however, this project's deployed resources
no longer generate ongoing charges in the selected region.

The separate GitHub OIDC bootstrap stack is intentionally outside this cleanup
script because it contains account-level CI identity and artifact-bucket
resources. See [CI/CD and GitHub OIDC deployment](ci-cd.md) for its independent
retention and removal decision.
