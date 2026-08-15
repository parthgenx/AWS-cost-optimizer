# AWS Cost Optimizer dashboard

The dashboard is a React and TypeScript single-page application for one
self-hosted AWS Cost Optimization Automation System deployment. It is not a
multi-tenant SaaS application and never receives AWS credentials or DynamoDB
permissions.

## Current scope

Phase 3 adds server-paginated findings, supported lifecycle/resource/severity
filters, evidence and lifecycle detail, and confirmation-gated operator actions.
Only approved unattached EBS volume findings can request cleanup. Static-site
hosting remains a later phase.

## Local configuration

Copy the example file before starting the development server:

```bash
cp .env.example .env.local
npm run dev
```

The public `VITE_*` values identify your deployment and are safe to include in
the browser build. Do not put AWS access keys, Cognito user passwords, refresh
tokens, API keys, or a Cognito client secret in this file.

The Cognito Hosted Login callback is always:

```text
http://localhost:5173/auth/callback
```

The SAM stack registers both the deployed CloudFront callback URL and the local
development URL with the Cognito app client. GitHub Actions reads the deployed
stack outputs and supplies the hosted values at build time. Leaving values unset
locally intentionally shows a configuration-required screen rather than a
misleading mock dashboard.

## Authentication and API boundary

The app redirects users to Cognito Managed Login with OAuth 2.0 Authorization
Code + PKCE. Cognito returns the browser to `/auth/callback`; the OIDC client
exchanges the code for tokens and keeps the session in `sessionStorage`.

The API client sends only the Cognito access token as a Bearer token to API
Gateway. API Gateway validates the JWT before FastAPI runs. Browser code may
adjust its interface based on Cognito group claims, but FastAPI remains
authoritative for all authorization decisions. In particular, the
`cost-optimizer-operators` group is required by the backend for approval and
cleanup-request calls.

## Hosting

The frontend is published to a private S3 bucket through the deployment
workflow. CloudFront is the sole HTTPS viewer endpoint and uses Origin Access
Control to read the bucket; direct S3 public access is blocked. CloudFront
returns `index.html` for missing object paths so direct detail URLs work with
the React router.

The API Gateway CORS policy allows the exact CloudFront origin and
`http://localhost:5173` for local development. It allows `GET`, `POST`, and
`OPTIONS` with `authorization` and `content-type`; no wildcard origin or cookie
credentials are used.

## Findings workflow

The findings page uses the existing authenticated read APIs. Status is a
server-side lifecycle filter; resource and severity are optional additional
filters. Pagination uses API-provided opaque cursors and never exposes DynamoDB
keys to the browser.

On a finding detail page, an operator can approve an `open` finding. Approval
creates an audit record but does not delete anything. For an `approved`
unattached EBS volume, an operator can then submit a separate cleanup request.
That request travels through EventBridge to the isolated cleanup Lambda, which
revalidates the volume. The browser cannot override dry-run or cleanup-execution
settings, and non-EBS resource types have no cleanup action.

## Quality commands

```bash
npm run build
npm run test
npm run lint
```
