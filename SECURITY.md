# Security Policy

## Supported Version

Security fixes target the current `main` branch.

## Reporting a Vulnerability

Email security issues to the maintainers instead of opening a public issue. Include:

- affected endpoint or deployment surface
- reproduction steps
- expected impact
- relevant logs with secrets removed

Do not include Deepline API keys, Slack tokens, CRM credentials, customer data, or production URLs in reports.

## Security Model

This repo is a thin agent broker. It owns transport concerns such as REST, web chat, Slack verification, request limits, CORS, and optional bearer auth.

Deepline owns GTM execution concerns: provider routing, workflows, plays, enrichment, billing, credentials, run state, and writebacks. Do not add local provider waterfalls, CRM write engines, or workflow run stores to this repo unless Deepline API explicitly delegates that responsibility.

## Deployment Requirements

- Set `DEEPLINE_API_KEY` through the deployment secret store.
- Set `API_KEY` for any public `/chat` or `/chat/stream` endpoint.
- Leave `ALLOW_UNAUTHENTICATED` unset outside local development.
- Set `CORS_ORIGINS` to explicit origins. Wildcard CORS is rejected.
- Set `SLACK_SIGNING_SECRET` when Slack events are enabled.
- Keep `DEEPLINE_GTM_LIVE_WRITES` unset unless the deployment has explicit approval gates.

Run `/doctor` after deployment to verify non-secret setup checks.
