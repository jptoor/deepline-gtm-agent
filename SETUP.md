# Setup

The agent runs on Vercel. Slack credentials are held by Vercel Connect, so this
repo never stores a Slack token or signing secret.

## Prerequisites

- Node.js 24
- A Deepline API key from [code.deepline.com](https://code.deepline.com)
- A Vercel account with Connect enabled

## 1. Install

```bash
cd eve_agent
npm install
```

## 2. Link the Vercel project

```bash
npx vercel link
npm run link       # pulls AI Gateway OIDC credentials
```

Set `DEEPLINE_API_KEY` in the Vercel project environment variables, or in a
local ignored `.env.local` for development:

```bash
DEEPLINE_API_KEY=dlp_...
```

For non-Vercel environments, use a static AI Gateway key instead:

```bash
AI_GATEWAY_API_KEY=...
EVE_MODEL=anthropic/claude-sonnet-4.6
```

## 3. Create the Slack connector

Vercel Connect registers the Slack app for you. You do not create a Slack app,
manage a manifest, or copy a bot token.

The connector name sets its UID, and `agent/channels/slack.ts` hard-codes that
UID. Use `--name deepline-gtm-eve-agent` to get `slack/deepline-gtm-eve-agent`,
or pick your own name and update the channel file to match.

```bash
npx vercel connect create slack --name deepline-gtm-eve-agent --triggers --yes
npx vercel connect detach slack/deepline-gtm-eve-agent --yes
npx vercel connect attach slack/deepline-gtm-eve-agent \
  --triggers --trigger-path /eve/v1/slack --yes
```

`create` provisions the connector at Connect's default path. `detach` then
`attach --trigger-path /eve/v1/slack` re-points the trigger at eve's Slack
route, because eve does not serve Connect's default path. `--triggers` turns on
Slack Event Subscriptions; without it, Slack never delivers `app_mention` or
`message.im`.

The channel reads its credentials from that connector:

```ts
// eve_agent/agent/channels/slack.ts
import { connectSlackCredentials } from "@vercel/connect/eve";
import { slackChannel } from "eve/channels/slack";

export default slackChannel({
  credentials: connectSlackCredentials("slack/deepline-gtm-eve-agent"),
});
```

## 4. Deploy

```bash
VERCEL_USE_EXPERIMENTAL_FRAMEWORKS=1 npx vercel deploy --prod
```

The flag lets the Vercel CLI recognize eve as a framework during the build.

## 5. Install to a Slack workspace

Open the connector in the Vercel dashboard and authorize it against your
workspace:

```bash
npx vercel connect open slack/<uid>
```

Until a workspace authorizes the connector, token requests fail with
`Token subject is not accessible to this requester`.

## Verify

```bash
# Unsigned requests must be rejected by Connect
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  https://<your-deployment>/eve/v1/slack \
  -H "Content-Type: application/json" -d '{}'
# expect 401

# The channel should be registered
curl -s https://<your-deployment>/eve/v1/info | grep slack
```

Then `@mention` the bot in a channel, or DM it.

## Environment variables

| Variable             | Required | What it is                                       |
| -------------------- | -------- | ------------------------------------------------ |
| `DEEPLINE_API_KEY`   | yes      | Deepline v2 API key                              |
| `AI_GATEWAY_API_KEY` | no       | Static AI Gateway key for non-Vercel environments |
| `EVE_MODEL`          | no       | Model override; defaults to Claude Sonnet 4.6     |

Slack credentials are intentionally absent. Connect holds them.
