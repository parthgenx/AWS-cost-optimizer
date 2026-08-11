# Deployment foundation

## What this milestone deploys

The SAM template creates two on-demand DynamoDB tables and one manually
invokable EBS scanner Lambda function. It does not create a schedule, send a
notification, expose an API endpoint, or permit any delete operation.

## Why AWS SAM

AWS SAM is a CloudFormation extension for serverless applications. It keeps the
Lambda, IAM, DynamoDB, and CloudWatch configuration in one reviewable template
without adding an infrastructure framework that would obscure the project.

## Lambda flow

1. A caller manually invokes the EBS scanner Lambda.
2. The handler gets region and table names from environment variables.
3. It extracts the AWS account ID from Lambda's invocation ARN, avoiding an
   extra STS API permission.
4. It wires the existing boto3 EBS adapter, pure rule, and DynamoDB repositories.
5. It returns a small scan summary and writes structured logs to CloudWatch.

## IAM boundary

The scanner role may only call `ec2:DescribeVolumes`, update the Findings table,
and create/update ScanRuns records. EC2 `DescribeVolumes` cannot be scoped to a
specific resource ARN, so it necessarily uses `Resource: "*"`.

No permissions to delete EBS volumes, release IPs, alter RDS, or modify load
balancers are granted.

## Environment naming

The SAM stack uses concise deployment labels (`dev`, `staging`, and `prod`) in
resource names. The application configuration normalizes `dev` to
`development` and `prod` to `production` before validation, so Python code
always receives a canonical environment value.

## Local validation

After AWS SAM CLI is installed, validate and build from the repository root:

```bash
sam validate --template infrastructure/template.yaml
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
