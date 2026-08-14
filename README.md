# deepline-gtm-agent

Open-source GTM agent adapter powered by [Deepline](https://deepline.com).

**Tested framework targets:** `Eve` · `LangChain Deep Agents` · `Anthropic Managed Agents`

Use this repo when you want to ship a rep-facing GTM agent surface without
rebuilding data providers, enrichment waterfalls, workflow state, billing,
credentials, or writebacks yourself. The app brokers Slack, REST, web chat, Eve,
Notion Worker, Hermes, and Azure-hosted deployments while Deepline handles tool
routing, enrichment, research, CRM actions, provider-specific workflows, and run
observability through the v2 API.

**API portal:** [code.deepline.com](https://code.deepline.com) - create your `DEEPLINE_API_KEY` there.

## When to use this

Use this repo if you are building:

- a Slackbot that lets reps ask for account briefs, enrichment, routing, or next
  actions
- a custom agent backend for rep workflows in Claude, ChatGPT, Eve, Hermes,
  Notion Custom Agents, or an MCP-style host
- a deployable HTTP surface for GTM workflows on Railway, Vercel, Azure
  Container Apps, or your own container platform
- a reference implementation for approval-gated CRM/outreach actions where
  Deepline remains the system that owns execution and logging

Do not use this repo to recreate Deepline inside another app. Keep provider
waterfalls, CRM writes, play execution, credentials, billing, and run history in
Deepline. Keep this repo focused on transport, auth, prompt/tool bounds,
deployment, and workflow packaging.

## Quickstart

```bash
cd managed_agent
pip install -r requirements.txt

export DEEPLINE_API_KEY=dlp_...

python server.py     # starts REST, web chat, and Slack endpoints on :8000
```

Open `http://localhost:8000` for web chat, or call the REST API:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "find emails for 5 VP Sales at fintech companies"}'
```

## What it does

The agent handles common GTM workflows with Deepline's v2 tool catalog and API:

| Workflow | Example prompt |
|---|---|
| Account brief | "Create a rep-ready account brief for Prove before my call with their RevOps lead" |
| Signal stacking | "Score these accounts using fit, intent, readiness, anti-fit, and missing-evidence signals" |
| Org chart building | "Build a buying committee map for Stripe across Sales, RevOps, Partnerships, and Security" |
| Contact enrichment | "Find the verified work email for Jane Smith at Acme" |
| Prospect search | "Find 10 VP Sales at B2B SaaS companies, 200-500 employees, US" |
| Email verification | "Is jsmith@acme.com safe to send?" |
| LinkedIn resolution | "Find the LinkedIn URL for Tom Nguyen at Notion" |
| Slack business mobile lookup | "Use /deepline-gtm to find this person's verified business mobile from their LinkedIn URL" |
| CRM and outreach drafts | "Draft the HubSpot update and ask before writing it" |

Responses should include sources, provider outcomes, and a clear next step. The agent should state data gaps instead of inventing missing emails, titles, or company facts.

See [`docs/workflow-coverage.md`](docs/workflow-coverage.md) for the Prove
workflow coverage matrix and the public GTM-agent repo patterns this adapter is
designed around.

## Eve reference implementation

This repo now includes an additive Eve reference implementation in [`eve_agent/`](eve_agent/). It preserves the Deepline v2 execution backend while using Eve for durable sessions, local HTTP, evals, and fast Vercel deployment.

Use it when you want an out-of-the-box deployable agent path:

```bash
cd eve_agent
npm install
npm run link
# set DEEPLINE_API_KEY in Vercel env or local .env.local
npm run dev
npm run smoke -- --host http://127.0.0.1:3000
```

See [`eve_agent/README.md`](eve_agent/README.md) for the full local, eval, and Vercel flow.

## Tested Frameworks

| Framework | Repo surface | Use it when |
|---|---|---|
| Eve | [`eve_agent/`](eve_agent/) | You want durable sessions, evals, and fast Vercel deployment for a Deepline-backed GTM agent. |
| LangChain Deep Agents | legacy/self-hosted Python agent path and migration tests | You want to compare the older DIY agent loop against the current thin Deepline v2 broker. |
| Anthropic Managed Agents | [`managed_agent/setup.py`](managed_agent/setup.py), [`managed_agent/session.py`](managed_agent/session.py) | You want Anthropic's hosted operator runtime while Deepline remains the GTM execution backend. |

The current default runtime is still the thin FastAPI broker over Deepline v2.
The tested framework targets are adapter surfaces, not separate GTM execution
layers.

## Architecture

```
Slack / REST / Web UI / Eve / Notion Worker / Hermes / MCP-style host
      |
      v
Thin agent adapter
      |
      v
Deepline v2 agent/chat + SDK/API
      |
      v
Deepline integrations, enrichment providers, CRM, outreach, and research tools
```

Configure access with environment variables and call the Deepline v2 SDK/API directly. Managed sessions should not depend on local Deepline CLI state.

## Boundary

This repo should stay thin. It owns:

- REST, web chat, and Slack transport
- Slack request verification and formatting
- optional bearer auth for public chat endpoints
- CORS and deployment setup checks
- prompt/tool bounds that steer requests into Deepline

Deepline API owns provider routing, plays, workflows, enrichment, CRM/outreach actions, credentials, billing, run state, and workflow observability. Do not copy those systems into this agent.

## Hermes Compatibility

This repo also includes `hermes-agent-pack/`, the compatibility layer for running the Deepline GTM agent inside Hermes on a persistent Sprite/Fly-style workspace.

Use it when Hermes is the operator interface and Deepline is the GTM execution, logging, workflow, and observability layer. The pack makes the Hermes setup explicit:

- pruned Deepline context, claims, exclusions, and Jai voice rules
- Hermes prompts and skills for one primary `deepline-gtm-agent`
- bounded subagent workflows for sales, account research, CRM hygiene, AgentMail, proof review, and workflow specs
- split marketing specialists for content, campaign planning, and proof/claims review
- Telegram, AgentMail, connector, and `spawn-k2qb` setup docs
- the HTML deck for the Hermes AI marketing team call recording

Start with [`hermes-agent-pack/README.md`](hermes-agent-pack/README.md), then run [`hermes-agent-pack/prompts/00_seed_hermes.md`](hermes-agent-pack/prompts/00_seed_hermes.md) in Hermes.

Run the shared eval suite against a Hermes profile with:

```bash
python tests/run_evals.py \
  --hermes-command "deeplinegtm -z" \
  --output tmp/hermes-eval-results.json
```

For the Sprite-hosted profile:

```bash
python tests/run_evals.py \
  --hermes-command "sprite exec -s spawn-k2qb -- deeplinegtm -z" \
  --output tmp/hermes-sprite-eval-results.json
```

## Notion Worker GTM Waterfall

The Notion Worker demo is a standalone GTM workflow surface for Notion Custom Agents. It embeds the Deepline TypeScript SDK in a Notion Worker and exposes typed tools for company-to-contact discovery, work-email waterfall enrichment, play discovery, play execution, and run polling.

Use [`docs/notion-worker-gtm-waterfall.md`](docs/notion-worker-gtm-waterfall.md) for the deployed Worker details, Custom Agent instructions, waterfall input shape, and the current end-to-end test evidence.

## Azure Container Apps

Use Azure Container Apps when the buyer wants Azure-native hosting for the
FastAPI broker or Slackbot. The root `Dockerfile` is production-safe and the
repo includes a GitHub Actions workflow for Container Apps.

Start with [`docs/azure-container-apps.md`](docs/azure-container-apps.md).

## Interfaces

### Web chat

Run `python managed_agent/server.py` and open `http://localhost:8000`.

### Setup checks

Use `/doctor` to verify non-secret deployment configuration:

```bash
curl http://localhost:8000/doctor
```

The response reports missing auth, wildcard CORS, Slack setup, and unsafe local/live-write combinations without returning API keys or tokens.

### REST

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Research rippling.com"}'
```

With endpoint protection enabled:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"message": "Find 3 VP Sales in the US"}'
```

### Slack

Set `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET`, then DM the bot or mention it in a channel. See [SETUP.md](SETUP.md).

Slack runs read-only by default. For explicit B2B mobile lookups that include a
LinkedIn profile URL, the broker calls Deepline's licensed providers directly
and reports the provider status instead of refusing or inventing a number.

### SDK/API

Use `DEEPLINE_API_KEY` for Deepline v2 API calls. Keep API keys in environment variables or your deployment secret store.

```python
import os
import httpx

resp = httpx.post(
    "https://code.deepline.com/api/v2/integrations/apollo_search_people/execute",
    headers={"Authorization": f"Bearer {os.environ['DEEPLINE_API_KEY']}"},
    json={"payload": {"job_title": "VP Sales", "limit": 5}},
    timeout=60,
)
resp.raise_for_status()
print(resp.json())
```

For full chat behavior, use the v2 agent/chat SDK or API from the broker layer instead of shelling out to local CLI state.

## Deploy

See [SETUP.md](SETUP.md) for Railway and Slack setup, or
[`docs/azure-container-apps.md`](docs/azure-container-apps.md) for Azure
Container Apps. Required production variables:

| Variable | Required | Description |
|---|---|---|
| `DEEPLINE_API_KEY` | Yes | Deepline v2 API key |
| `PORT` | Yes | Usually `8000` |
| `API_KEY` | Optional | Protects `/chat` endpoints with bearer auth |
| `CORS_ORIGINS` | Optional | Comma-separated allowed origins; empty disables browser CORS |
| `SLACK_BOT_TOKEN` | For Slack | Slack bot token |
| `SLACK_SIGNING_SECRET` | For Slack | Slack request signing secret |
| `REDIS_URL` | Optional | Persistent Slack thread history |

`ANTHROPIC_API_KEY`, `MANAGED_AGENT_ID`, and `MANAGED_ENVIRONMENT_ID` are only needed for the optional Anthropic Managed Agent shell in `managed_agent/setup.py`; they are not required for the default native Deepline v2 broker.

For the Eve on Vercel path, see [`eve_agent/README.md`](eve_agent/README.md) and the Vercel section in [SETUP.md](SETUP.md).

## Legacy self-hosted agent

The root Python package contains a legacy self-hosted agent path for local experimentation. It is not the recommended deployment path. New deployments should use the v2 native agent/chat flow above.

## License

MIT
