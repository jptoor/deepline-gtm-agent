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

This repo is an eve agent deployed to Vercel. It owns transport concerns: the
Slack and HTTP channels, prompt and tool bounds, and auth on its own routes.

Deepline owns GTM execution concerns: provider routing, workflows, plays, enrichment, billing, credentials, run state, and writebacks. Do not add local provider waterfalls, CRM write engines, or workflow run stores to this repo unless Deepline API explicitly delegates that responsibility.

### Slack credentials

Slack credentials live in Vercel Connect, not in this repo and not in
environment variables. Connect owns both directions: it verifies the inbound
Slack request signature before forwarding an event, and it issues short-lived
bot tokens for outbound calls, driving the refresh flow itself.

There is no `SLACK_BOT_TOKEN` or `SLACK_SIGNING_SECRET` to set, rotate, or leak.
Revoke access through Connect (`vercel connect revoke-tokens`) rather than by
rotating a secret here.

Connect signs the requests it forwards, so a handler must verify that signature
before acting on a payload. The eve Slack channel does this; a hand-written
receiver on the Connect trigger path would need to as well.

## Deployment Requirements

- Set `DEEPLINE_API_KEY` through the Vercel project environment, never in the repo.
- Prefer Vercel OIDC over static tokens where a choice exists. OIDC tokens are short-lived and project-bound.
- Scope every Connect token request. Do not request workspace-wide scopes for a single-channel operation.
- Use a separate connector per environment when environments need provider-level isolation. A project link controls which deployments can request tokens; it does not isolate one environment's provider installation from another's.
