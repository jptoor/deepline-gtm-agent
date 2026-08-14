# deepline-gtm-agent

Open-source GTM agent powered by [Deepline](https://deepline.com), built on
[eve](https://eve.dev) and deployed to Vercel.

Use this repo when you want to ship a rep-facing GTM agent surface without
rebuilding data providers, enrichment waterfalls, workflow state, billing,
credentials, or writebacks yourself. The agent brokers Slack and HTTP while
Deepline handles tool routing, enrichment, research, CRM actions,
provider-specific workflows, and run observability through the v2 API.

**API portal:** [code.deepline.com](https://code.deepline.com) - create your `DEEPLINE_API_KEY` there.

## When to use this

Use this repo if you are building:

- a Slackbot that lets reps ask for account briefs, enrichment, routing, or next
  actions
- a custom agent backend for rep workflows
- a reference implementation for approval-gated CRM/outreach actions where
  Deepline remains the system that owns execution and logging

Do not use this repo to recreate Deepline inside another app. Keep provider
waterfalls, CRM writes, play execution, credentials, billing, and run history in
Deepline. Keep this repo focused on transport, auth, prompt/tool bounds, and
workflow packaging.

## Architecture

Everything runs on Vercel. There is no separate broker service.

```
Slack workspace
  |
  v
Vercel Connect          verifies the inbound webhook, mints the bot token
  |
  v
eve agent on Vercel     agent/channels/slack.ts -> /eve/v1/slack
  |
  v
Deepline v2 API         tools, enrichment, plays, CRM writes, billing
```

Slack credentials live in Vercel Connect, not in this repo and not in
environment variables. Connect owns both directions: it verifies inbound Slack
events before forwarding them, and it issues short-lived bot tokens for outbound
calls. There is no `SLACK_BOT_TOKEN` or `SLACK_SIGNING_SECRET` to manage.

## Quickstart

```bash
cd eve_agent
npm install
npm run dev
```

Set `DEEPLINE_API_KEY` in the Vercel project environment, or in a local ignored
`.env.local` for development.

See [SETUP.md](SETUP.md) for Slack setup and deployment.

## Layout

| Path                        | What it is                                        |
| --------------------------- | ------------------------------------------------- |
| `eve_agent/`                | The agent: channels, tools, skills, evals         |
| `eve_agent/agent/channels/` | Slack and HTTP entry points                       |
| `eve_agent/agent/tools/`    | Deepline-backed tools exposed to the model        |
| `eve_agent/agent/skills/`   | Skills synced from deepline-api                   |
| `docs/`                     | Design notes and plans                            |

## Tests

```bash
cd eve_agent
npm run typecheck
npm test
npm run check:skills   # skills snapshot drift against deepline-api
```

## Skills

`eve_agent/agent/skills/` is a snapshot copied from deepline-api. Refresh it
with `npm run sync:skills`, and check it for drift with `npm run check:skills`.
