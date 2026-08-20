# Deployment foundation

## What this milestone deploys

The SAM template creates three on-demand DynamoDB tables, separate read-only
scanner Lambdas for EBS volumes, Elastic IPs, EBS snapshots, EC2 utilization,
RDS utilization, and Application Load Balancers, an isolated EBS cleanup
Lambda, and an API Lambda. The API is exposed through API Gateway HTTP API and
protected by a Cognito JWT authorizer. The stack also includes separate SNS
topics for findings and operational alerts, EventBridge rules, encrypted SQS
dead-letter queues, CloudWatch alarms, an operational dashboard, and the
Cognito-authenticated React dashboard integration.

## Hosted dashboard

The frontend is built outside the Lambda package and served as a static Vite
application by Vercel. Vercel has no AWS credentials, backend execution role,
or DynamoDB access. It only delivers the browser bundle; API Gateway remains
the sole backend entry point.

Before deploying AWS, create a Vercel project with `frontend` as its root
directory and record its stable production `https://<project>.vercel.app`
origin. Supply that exact origin as `DashboardOrigin` to SAM or as the
`DASHBOARD_ORIGIN` GitHub Actions environment variable. The stack validates an
HTTPS Vercel origin without a trailing slash; operators must deliberately use
the stable production URL, not a Vercel preview URL.

No custom domain, Route 53 zone, multi-account access layer, CloudFront
distribution, or dashboard S3 bucket is created. The Vercel production URL is
the normal operator-dashboard URL for one AWS-account deployment.

### Provider setup order

1. Import this repository into Vercel, select `frontend` as the project root,
   and keep `main` as the production branch. The initial deployment is safe but
   shows the dashboard's configuration-required screen because no API settings
   exist yet.
2. Copy Vercel's stable production URL, add it as the GitHub `development`
   environment variable `DASHBOARD_ORIGIN`, and deploy the AWS stack.
3. Read the public API and Cognito CloudFormation outputs, add the four
   `VITE_*` values to Vercel's Production environment, and redeploy Vercel.
4. Verify sign-in only at the production URL. Do not add preview deployment URLs
   to Cognito callbacks, API Gateway CORS, or Vercel Production variables.

### Cognito browser application

The existing Cognito app client is configured as a public browser client with
Authorization Code + PKCE, `openid` and `email` scopes, and no client secret.
A Cognito managed-login domain is created by the stack. Public user signup is
still disabled at the user-pool level: administrators create users, then add
operators to `cost-optimizer-operators`.

The app client allows these exact return locations:

- `https://<project>.vercel.app/auth/callback` after sign-in.
- `https://<project>.vercel.app/` after sign-out.
- The equivalent `http://localhost:5173` routes for deliberate local UI work.

The browser receives tokens through the existing frontend OIDC client and sends
the access token to API Gateway. Callback URLs do not grant any AWS permission;
API Gateway JWT validation and FastAPI operator-group checks remain the source
of access control.

### CORS boundary

API Gateway owns CORS, rather than FastAPI. It allows only these origins:

- The exact Vercel production HTTPS origin supplied as `DashboardOrigin`.
- `http://localhost:5173` for local development.

It allows only `GET`, `POST`, and `OPTIONS`, with `authorization` and
`content-type` request headers. It does not enable credentialed cookies or a
wildcard origin. API Gateway responds to browser preflight requests before the
FastAPI Lambda is invoked.

### Vercel routing and browser headers

`frontend/vercel.json` builds the existing Vite application, serves `dist`, and
rewrites all non-static routes to `index.html`. This preserves direct navigation
and refreshes for `/findings/<finding-id>` without proxying backend requests
through Vercel.

The manifest also sets CSP, HSTS, frame denial, MIME sniffing protection,
referrer policy, and permissions policy headers. Its CSP allows browser
connections only to the configured AWS region's API Gateway hostname pattern
(`https://*.execute-api.ap-south-1.amazonaws.com`) and Cognito managed-login
hostname pattern (`https://*.auth.ap-south-1.amazoncognito.com`). If the
project region changes, update these two CSP patterns in the same reviewed
change as the region change. Vercel preview deployments deliberately receive no
production `VITE_*` configuration and are not Cognito callback or CORS origins.

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

The GitHub deployment role packages Lambda artifacts into its dedicated private
SAM artifact bucket and deploys the reviewed AWS stack. It has no CloudFront or
dashboard-asset publishing permissions and does not grant the API Lambda any
new IAM permission. Vercel's separate GitHub integration publishes only the
frontend source and has no AWS identity.

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

## Deployment outputs and frontend configuration

After deployment, the stack exposes the following public configuration values:

| Output | Purpose |
|---|---|
| `DashboardUrl` | Configured Vercel production URL. |
| `ApiEndpoint` | API Gateway base URL configured in Vercel. |
| `CognitoIssuer` | OIDC issuer URL configured in Vercel. |
| `CognitoDomain` | Cognito managed-login URL configured in Vercel. |
| `DashboardCognitoClientId` | Public browser client ID configured in Vercel. |

The manually-dispatched GitHub workflow deploys only AWS infrastructure. It
requires the protected `development` environment's non-secret
`DASHBOARD_ORIGIN` variable and passes it to `DashboardOrigin`.

After AWS deployment, configure these **Production-only** Vercel environment
variables from the corresponding stack outputs, then redeploy the Vercel
project:

| Vercel variable | Stack output |
|---|---|
| `VITE_API_BASE_URL` | `ApiEndpoint` |
| `VITE_COGNITO_ISSUER` | `CognitoIssuer` |
| `VITE_COGNITO_DOMAIN` | `CognitoDomain` |
| `VITE_COGNITO_CLIENT_ID` | `DashboardCognitoClientId` |

These values identify public browser endpoints; they are not secrets. Do not
configure AWS credentials, Cognito passwords, tokens, or a Cognito client
secret in Vercel. Do not configure the production variables for preview
deployments.

## Cleaning up the development environment

The project includes a deliberately narrow cleanup command:

```bash
./scripts/cleanup-dev.sh --region ap-south-1
```

It only targets the `aws-cost-optimizer-dev` stack. After a `DELETE`
confirmation, it runs `sam delete`, which removes Cognito managed-login,
API Gateway, Lambdas, tables, and other application resources. It leaves an
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

The Vercel dashboard project is intentionally outside this AWS-only cleanup
script. Delete it manually in Vercel Project Settings and disconnect its GitHub
repository integration when retiring the environment. The separate GitHub OIDC
bootstrap stack is also outside this script because it contains account-level CI
identity and artifact-bucket resources. See [CI/CD and GitHub OIDC deployment](ci-cd.md)
for its independent retention and removal decision.
