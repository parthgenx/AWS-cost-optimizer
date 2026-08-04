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

## Local validation

After AWS SAM CLI is installed, validate and build from the repository root:

```bash
sam validate --template infrastructure/template.yaml
sam build --template-file infrastructure/template.yaml
```

Deployment is deliberately deferred until the infrastructure is reviewed.
