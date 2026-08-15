# Deployment foundation

## What this milestone deploys

The SAM template creates three on-demand DynamoDB tables, separate read-only
scanner Lambdas for EBS volumes, Elastic IPs, EBS snapshots, EC2 utilization,
RDS utilization, and Application Load Balancers, an isolated EBS cleanup
Lambda, and an API Lambda. The API is exposed through API Gateway HTTP API and
protected by a Cognito JWT authorizer. The stack also includes separate SNS
topics for findings and operational alerts, EventBridge rules, encrypted SQS
dead-letter queues, CloudWatch alarms, an operational dashboard, and the
self-hosted React dashboard delivery layer.

## Hosted dashboard

The frontend is built outside the Lambda package and deployed as static assets
to a private, application-owned S3 bucket. CloudFront is the only public
viewer endpoint. Its Origin Access Control signs requests to S3; the bucket
policy permits `s3:GetObject` only from that exact distribution. S3 public
access blocks remain enabled and the bucket has no static-website endpoint.

CloudFront uses its default HTTPS certificate and redirects HTTP to HTTPS. A
custom error mapping returns `index.html` for S3 403 and 404 responses, so
direct navigation and refreshes on routes such as `/findings/<finding-id>` are
handled by the React router. A response-headers policy adds a restrictive CSP,
HSTS, frame denial, MIME sniffing protection, and a referrer policy.

No custom domain, Route 53 zone, or multi-account access layer is created. The
CloudFront URL is the normal recruiter-facing dashboard URL for one deployment
in one AWS account.

### Cognito browser application

The existing Cognito app client is configured as a public browser client with
Authorization Code + PKCE, `openid` and `email` scopes, and no client secret.
A Cognito managed-login domain is created by the stack. Public user signup is
still disabled at the user-pool level: administrators create users, then add
operators to `cost-optimizer-operators`.

The app client allows these exact return locations:

- `https://<CloudFront-domain>/auth/callback` after sign-in.
- `https://<CloudFront-domain>/` after sign-out.
- The equivalent `http://localhost:5173` routes for deliberate local UI work.

The browser receives tokens through the existing frontend OIDC client and sends
the access token to API Gateway. Callback URLs do not grant any AWS permission;
API Gateway JWT validation and FastAPI operator-group checks remain the source
of access control.

### CORS boundary

API Gateway owns CORS, rather than FastAPI. It allows only these origins:

- The exact CloudFront distribution HTTPS origin created by this stack.
- `http://localhost:5173` for local development.

It allows only `GET`, `POST`, and `OPTIONS`, with `authorization` and
`content-type` request headers. It does not enable credentialed cookies or a
wildcard origin. API Gateway responds to browser preflight requests before the
FastAPI Lambda is invoked.

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

The GitHub deployment role receives write access only to the deterministic
development dashboard bucket and can create CloudFront resources through the
reviewed development stack. It does not grant the API Lambda any new IAM
permission. The S3 bucket policy grants runtime reads to CloudFront, not to
public S3 clients.

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

## Deployment outputs and frontend publishing

After deployment, the stack exposes the following public configuration values:

| Output | Purpose |
|---|---|
| `DashboardUrl` | HTTPS CloudFront URL for the dashboard. |
| `DashboardBucketName` | Private S3 origin used only by deployment and cleanup. |
| `DashboardDistributionId` | CloudFront distribution invalidated after publishing assets. |
| `ApiEndpoint` | API Gateway base URL compiled into the frontend. |
| `CognitoIssuer` | OIDC issuer URL compiled into the frontend. |
| `CognitoDomain` | Cognito managed-login URL compiled into the frontend. |
| `DashboardCognitoClientId` | Public browser client ID compiled into the frontend. |

The manually-dispatched GitHub workflow deploys infrastructure first, reads
those outputs, then runs `npm ci` and `npm run build` with the four `VITE_*`
configuration values. It uploads hashed assets with a long immutable cache
period, uploads `index.html` with `no-store`, and creates a CloudFront `/*`
invalidation. No environment file, AWS credential, Cognito password, or token
is committed to the repository.

## Cleaning up the development environment

The project includes a deliberately narrow cleanup command:

```bash
./scripts/cleanup-dev.sh --region ap-south-1
```

It only targets the `aws-cost-optimizer-dev` stack. After a `DELETE`
confirmation, it reads the private `DashboardBucketName` from that exact stack
and removes its non-versioned static assets. It then runs `sam delete`, which
removes the bucket, bucket policy, CloudFront distribution, Cognito managed-login
domain, API, Lambdas, tables, and other application resources. The script
leaves an empty shared SAM artifact bucket alone because it may be used by
another SAM project; an empty S3 bucket has no storage charge. It verifies that
the stack no longer exists before reporting success.

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
