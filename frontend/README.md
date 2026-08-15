# AWS Cost Optimizer dashboard

The dashboard is a React and TypeScript single-page application for one
self-hosted AWS Cost Optimization Automation System deployment. It is not a
multi-tenant SaaS application and never receives AWS credentials or DynamoDB
permissions.

## Current scope

Phase 2 implements the protected application shell, Cognito login/logout,
authenticated FastAPI client, and read-only Overview page. Approval, cleanup
requests, findings navigation, and static-site hosting are intentionally later
phases.

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

The future hosting phase will add the deployed CloudFront callback URL to the
Cognito app client. Until then, leaving the values unset intentionally shows a
configuration-required screen rather than a misleading mock dashboard.

## Authentication and API boundary

The app redirects users to Cognito Managed Login with OAuth 2.0 Authorization
Code + PKCE. Cognito returns the browser to `/auth/callback`; the OIDC client
exchanges the code for tokens and keeps the session in `sessionStorage`.

The API client sends only the Cognito access token as a Bearer token to API
Gateway. API Gateway validates the JWT before FastAPI runs. Browser code may
adjust its interface based on session state, but FastAPI remains authoritative
for all authorization decisions.

## Quality commands

```bash
npm run build
npm run test
npm run lint
```
