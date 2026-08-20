# AWS Cost Optimizer dashboard

The dashboard is a React and TypeScript single-page application for one
self-hosted AWS Cost Optimization Automation System deployment. It is not a
multi-tenant SaaS application and never receives AWS credentials or DynamoDB
permissions.

## Current scope

The dashboard provides server-paginated findings, supported
lifecycle/resource/severity filters, evidence and lifecycle detail, and
confirmation-gated operator actions. Only approved unattached EBS volume
findings can request cleanup.

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

The SAM stack registers both the exact Vercel production callback URL and the
local development URL with the Cognito app client. Leaving values unset locally
intentionally shows a configuration-required screen rather than a misleading
mock dashboard.

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

Vercel hosts the static application with `frontend` configured as the Vercel
project root. `vercel.json` uses `npm ci`, builds `dist`, rewrites direct routes
to `index.html`, and applies browser security headers. Vercel has no AWS
credentials, DynamoDB access, or backend execution role.

Before deploying AWS, choose the Vercel project's stable production
`https://<project>.vercel.app` URL. Supply it as `DashboardOrigin`; API Gateway
CORS then allows only that exact origin and `http://localhost:5173`. It allows
`GET`, `POST`, and `OPTIONS` with `authorization` and `content-type`; no
wildcard origin or cookie credentials are used.

Set these **Production-only** Vercel environment variables from CloudFormation
outputs before deploying the live dashboard:

| Variable | Stack output |
|---|---|
| `VITE_API_BASE_URL` | `ApiEndpoint` |
| `VITE_COGNITO_ISSUER` | `CognitoIssuer` |
| `VITE_COGNITO_DOMAIN` | `CognitoDomain` |
| `VITE_COGNITO_CLIENT_ID` | `DashboardCognitoClientId` |

Do not configure production values for preview deployments. Preview URLs are
not Cognito callback or API CORS origins.

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
