# Setup Guide

This guide deploys the Deepline v2 native agent/chat broker. It uses environment variables and the Deepline SDK/API, with no dependency on local Deepline CLI state.

For the additive Eve reference implementation, use the "Eve on Vercel" section below. The Python broker remains the Railway/Slack path.
For Azure-native hosting, use [docs/azure-container-apps.md](docs/azure-container-apps.md).

## Eve on Vercel

The Eve app lives in `eve_agent/` and is the fastest deploy path for an out-of-the-box Deepline GTM agent session server.

### Local setup

```bash
cd eve_agent
npm install
cp .env.example .env
```

Set:

```bash
DEEPLINE_API_KEY="dlp_..."
```

Then configure model access through Vercel AI Gateway:

```bash
npm run link
```

For non-Vercel environments, set `AI_GATEWAY_API_KEY` instead.

Run locally:

```bash
npm run dev
```

Verify in another terminal:

```bash
npm run smoke -- --host http://127.0.0.1:3000
```

### Deploy

```bash
cd eve_agent
npm run deploy
```

Set Vercel project environment variables:

| Variable | Required | Description |
|---|---|---|
| `DEEPLINE_API_KEY` | Yes | Deepline v2 API key from [code.deepline.com](https://code.deepline.com) |
| `DEEPLINE_API_BASE_URL` | Optional | Defaults to `https://code.deepline.com` |
| `AI_GATEWAY_API_KEY` | Optional | Static fallback; Vercel OIDC is preferred |
| `EVE_MODEL` | Optional | Model override, for example `anthropic/claude-sonnet-4.6` |

After deployment:

```bash
cd eve_agent
npm run smoke -- --host https://<your-vercel-url>
```

### Eve verification

```bash
cd eve_agent
npm test
npm run info
npm run typecheck
npm run build
npm run eval -- smoke
```

The unit tests and build are local checks. Evals and smoke sessions require configured model credentials.

The Eve web channel includes Vercel's explicit `none()` auth helper for parity with the current Python web UI. For a private deployment, remove `none()` from `eve_agent/agent/channels/eve.ts` or replace it with your own auth provider before deploying.

## Railway

### CLI setup

```bash
npm install -g @railway/cli
railway login
railway init

railway variables set \
  DEEPLINE_API_KEY="dlp_..." \
  PORT="8000"

railway up --detach
railway domain
```

Optional production variables:

```bash
railway variables set \
  API_KEY="choose-a-server-api-key" \
  CORS_ORIGINS="https://your-app.example"
railway up --detach
```

### UI setup

1. Go to [railway.app](https://railway.app) and create a new project from your GitHub repo.
2. Railway builds with `managed_agent/Dockerfile`.
3. Add `DEEPLINE_API_KEY` and `PORT=8000` in the service variables.
4. Generate a public domain under **Settings** -> **Networking**.

## Redis

Redis is optional. Add it if you want Slack thread history to survive deploys and restarts.

1. Railway dashboard -> your project -> **New** -> **Database** -> **Add Redis**.
2. Railway sets `REDIS_URL` automatically.

## Slack

You need a bot token, signing secret, and events webhook pointed at your Railway domain.

### Manifest path

1. Replace `YOUR_RAILWAY_DOMAIN` in `slack-manifest.json` with your Railway hostname.
2. Go to [api.slack.com/apps](https://api.slack.com/apps) -> **Create New App** -> **From manifest**.
3. Install the app to your workspace.
4. In **OAuth & Permissions**, copy the bot token.
5. In **Basic Information**, copy the signing secret.
6. Set both in Railway:

```bash
railway variables set \
  SLACK_BOT_TOKEN="xoxb-..." \
  SLACK_SIGNING_SECRET="..."
railway up --detach
```

### Manual path

Create a Slack app from scratch and configure:

| Area | Value |
|---|---|
| Redirect URL | `https://<your-railway-domain>/slack/oauth_redirect` |
| Events URL | `https://<your-railway-domain>/slack/events` |
| Bot events | `app_mention`, `message.im` |
| Bot scopes | `chat:write`, `reactions:write`, `app_mentions:read`, `im:read`, `im:history`, `channels:read`, `channels:history`, `groups:history`, `mpim:history` |

## Verify

```bash
curl https://<your-railway-domain>/health
```

Expected status is `ok` once required configuration is present.

Check non-secret setup diagnostics:

```bash
curl https://<your-railway-domain>/doctor
```

`/doctor` should not return API keys or tokens. It reports missing Deepline auth, missing chat auth, wildcard CORS, Slack setup, and unsafe local/live-write combinations.

Test chat:

```bash
curl -X POST https://<your-railway-domain>/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find 3 VP Sales at B2B SaaS companies, 100-500 employees, US"}'
```

If `API_KEY` is set, include:

```bash
-H "Authorization: Bearer <API_KEY>"
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DEEPLINE_API_KEY` | Yes | Deepline v2 API key from [code.deepline.com](https://code.deepline.com) |
| `PORT` | Yes | Server port, usually `8000` |
| `API_KEY` | Optional | Protects `/chat` endpoints with bearer auth |
| `CORS_ORIGINS` | Optional | Comma-separated allowed origins; empty disables browser CORS |
| `REDIS_URL` | Optional | Enables persistent Slack conversation history |
| `SLACK_BOT_TOKEN` | For Slack | Bot token from Slack OAuth |
| `SLACK_SIGNING_SECRET` | For Slack | Slack signing secret |
| `SLACK_CLIENT_ID` | Optional | Used by Slack OAuth install flow |
| `SLACK_CLIENT_SECRET` | Optional | Used by Slack OAuth install flow |
| `DEEPLINE_GTM_LIVE_WRITES` | Optional | Enables live-write mode for approved workflows; leave unset by default |

`ANTHROPIC_API_KEY`, `MANAGED_AGENT_ID`, and `MANAGED_ENVIRONMENT_ID` are optional and only needed for manual Anthropic Managed Agent experiments.
