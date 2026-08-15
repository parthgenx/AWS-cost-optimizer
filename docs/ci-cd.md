# CI/CD and GitHub OIDC deployment

## Design

Pull requests run formatting, linting, static typing, tests, and SAM template
linting. Deployment is deliberately separate and manual through GitHub Actions
`workflow_dispatch`; a code push never creates AWS resources automatically.

The deployment workflow requests a short-lived GitHub OIDC token, then assumes
an AWS IAM role. It does not use `AWS_ACCESS_KEY_ID` or any other long-lived
AWS credential stored in GitHub. The workflow is attached to GitHub's protected
`development` environment, and the bootstrap trust policy accepts only that
environment's exact OIDC subject.

GitHub and AWS recommend restricting the OIDC trust policy to the expected
repository and deployment context. [GitHub OIDC on AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws) · [AWS IAM OIDC role guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html)

## One-time bootstrap

`infrastructure/github-oidc-bootstrap.yaml` is intentionally separate from the
application stack. It creates the GitHub OIDC provider, a narrowly purposed
deployment role, and a private encrypted artifact bucket. The bucket is
retained if the bootstrap stack is deleted, because deployment artifacts are an
account-level concern and may need an independent retention decision.

Before running it, create a GitHub environment named `development` in the
repository settings and configure protection rules that allow deployments only
from `main`. The IAM trust policy uses this exact OIDC subject:

```text
repo:parthgenx/AWS-cost-optimizer:environment:development
```

Deploy the bootstrap stack only after reviewing it. This requires an AWS
administrator once; it is not performed by the application workflow.

```bash
aws cloudformation deploy \
  --template-file infrastructure/github-oidc-bootstrap.yaml \
  --stack-name aws-cost-optimizer-github-oidc \
  --region ap-south-1 \
  --capabilities CAPABILITY_NAMED_IAM
```

If the account already has an IAM OIDC provider for
`token.actions.githubusercontent.com`, do not deploy a duplicate provider.
Create the deployment role through your account's reviewed identity-management
process using the same exact-subject trust policy instead.

Read the bootstrap-stack outputs, then create these **GitHub Actions variables**
for the `development` environment:

| Variable | Value |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | `DeploymentRoleArn` output |
| `AWS_SAM_ARTIFACT_BUCKET` | `DeploymentArtifactsBucketName` output |
| `AWS_ACCOUNT_ID` | Target AWS account ID |

These identifiers are configuration values, not secrets. Do not create static
AWS access-key secrets for this repository.

## Deploying

After the variables and environment protection are configured, open **Actions**
in GitHub, select **Deploy development environment**, and run it deliberately.
The workflow always deploys with:

```text
ScheduledScansEnabled=false
CleanupDryRun=true
CleanupExecutionEnabled=false
```

This means the CI/CD path cannot accidentally enable recurring scans or real
EBS deletion. Any future production deployment should use a separately reviewed
workflow, role, environment, and stack—not a modified development command.

## Trade-offs

The deployment role allows only this application's deployment operations and a
prefix in its dedicated artifact bucket. Some AWS control-plane actions still
require `Resource: "*"` because AWS does not support resource-level IAM
permissions for them. The role is therefore limited by its exact GitHub OIDC
subject, short one-hour sessions, protected GitHub environment, fixed stack
name, and service/action set.

The workflow is manually dispatched rather than deploying on every merge. This
is slower, but appropriate while the project is an educational, cost-sensitive
development environment. It creates a clear review point before an AWS change.
