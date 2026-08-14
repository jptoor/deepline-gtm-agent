# Deepline GTM Agent

FastAPI broker for Deepline v2 native agent/chat. It exposes REST, streaming, web chat, and Slack endpoints while Deepline handles GTM tool routing through the v2 SDK/API.

## How It Works

```
Slack / REST / Web UI
  |
  v
FastAPI broker
  |
  v
Deepline v2 agent/chat + SDK/API
  |
  v
Deepline integrations and provider workflows
```

Configure the broker with environment variables. Managed sessions should not depend on local Deepline CLI state.

## Setup

```bash
pip install -r requirements.txt

export DEEPLINE_API_KEY=dlp_...
export API_KEY=change-me

python server.py
```

Open `http://localhost:8000` for web chat.

## API

### POST /chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"message": "find emails for 5 VP Sales at fintech companies"}'
```

### POST /chat/stream

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"message": "research stripe.com"}'
```

Set `API_KEY` to require `Authorization: Bearer <API_KEY>` on chat endpoints.
If `API_KEY` is missing, chat endpoints fail closed unless `ALLOW_UNAUTHENTICATED=true`
is explicitly set for local development.

## Docker

```bash
docker build -f managed_agent/Dockerfile -t deepline-gtm-agent .
docker run -p 8000:8000 \
  -e DEEPLINE_API_KEY=dlp_... \
  -e API_KEY=change-me \
  deepline-gtm-agent
```

## Railway

```bash
railway init
railway variables set \
  DEEPLINE_API_KEY=dlp_... \
  API_KEY=change-me \
  PORT=8000
railway up --detach
```

For Slack, also set `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, and at least one
of `SLACK_ALLOWED_CHANNEL_IDS` or `SLACK_ALLOWED_USER_IDS`. Slack agent calls run
with a read-only prompt, bounded tool list, and capped tool-call count. If you use
the OAuth redirect flow, set `SLACK_OAUTH_STATE`; the redirect page never renders
the bot token.

Explicit Slack business-mobile requests with a LinkedIn profile URL execute a
bounded Deepline provider waterfall directly. The broker reports providers
checked and only returns a mobile number when a licensed provider returns one.

Set `CORS_ORIGINS` to the exact browser origins that should call the broker. The
default is empty, which avoids accidentally exposing authenticated chat endpoints
to every origin.

`ANTHROPIC_API_KEY`, `MANAGED_AGENT_ID`, and `MANAGED_ENVIRONMENT_ID` are optional and only used by `setup.py` / `session.py` for manual Anthropic Managed Agent experiments. The default broker path does not require them.

## Environment

See [env.example](env.example) for all supported variables.
