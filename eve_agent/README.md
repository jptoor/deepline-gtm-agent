# Deepline GTM Eve Agent

Eve reference implementation for the Deepline GTM agent. This app keeps Deepline as the GTM execution backend and uses Eve for durable agent sessions, local development, evals, and Vercel deployment.

This package is the runtime. The Python/FastAPI broker that used to serve Slack and REST is deleted.

## Requirements

- Node.js 24
- A Deepline API key from https://code.deepline.com
- One model path:
  - Vercel AI Gateway through `npm run link` and Vercel OIDC
  - `AI_GATEWAY_API_KEY` for non-Vercel/static-key environments

## Configure

```bash
cd eve_agent
npm install
npm run info
```

Set `DEEPLINE_API_KEY` in Vercel project environment variables, or in a local ignored `.env.local` for development:

```bash
DEEPLINE_API_KEY=dlp_...
```

Link Eve to a Vercel project and pull AI Gateway OIDC credentials:

```bash
npm run link
```

For non-Vercel environments, use a static AI Gateway key instead:

```bash
AI_GATEWAY_API_KEY=...
EVE_MODEL=anthropic/claude-sonnet-4.6
```

## Run Locally

```bash
npm run dev
```

Eve serves the local agent over HTTP. In another terminal, run:

```bash
npm run smoke -- --host http://127.0.0.1:3000
```

The smoke script checks Eve health, creates a session, opens the session stream, and waits for a completed or waiting event.

## Test

```bash
npm test
npm run info
npm run typecheck
npm run build
```

Run deterministic evals with:

```bash
npm run eval -- smoke
npm run eval -- workflow-presets
```

Eval execution requires model credentials. Without AI Gateway or a provider key, Eve will compile but model-backed evals will fail at runtime.

## Shared Deepline Recipes And Skills

Reusable GTM recipes should come from `deepline-api`, not from hand-written Eve-only copies. The Eve package vendors a committed generated snapshot of `deepline-api/src/lib/onboard/recipes.json` at `agent/lib/deepline-recipes.ts` so local installs and Vercel deploys work without a second repo checkout.

Reusable agent skills should also come from Deepline's published well-known skills API. The Eve package copies the built well-known skill packages from `https://code.deepline.com/.well-known/skills/index.json` into `agent/skills/<skill-name>/`, preserving `SKILL.md`, `references/`, `scripts`, metadata, and recipe wrappers. The sync strips only frontmatter fields Eve does not accept, such as `disable-model-invocation`.

The generated skill snapshot is locked in `agent/lib/deepline-skills-lock.ts`. The lock records the source index URL, published index version, generated timestamp, skill file list, and SHA-256 hash for every copied file.

To refresh copied skills from the published API:

```bash
cd eve_agent
npm run sync:deepline
```

To verify the committed snapshot is still current without mutating files:

```bash
npm run check:deepline
```

To sync from a staging API instead, point the script at a different well-known index:

```bash
DEEPLINE_SKILLS_INDEX_URL=https://staging.example.com/.well-known/skills/index.json npm run sync:deepline
```

The workflow preset tools expose shared recipes with `source: deepline-api-recipe`. Legacy transcript-derived presets remain available with `source: legacy-transcript-preset` for agent patterns that are not onboarding recipes yet.

Do not edit copied skill packages directly in Eve. Update and publish the Deepline API well-known skill artifacts, run `npm run sync:deepline`, then run the Eve tests. Recipe prompts are currently committed as a generated snapshot; refresh them only with an explicit `DEEPLINE_RECIPES_JSON_URL` or `DEEPLINE_RECIPES_JSON_PATH`.

## Deploy To Vercel

```bash
cd eve_agent
npm install
npm run link
npm run deploy
```

Set production environment variables in Vercel:

| Variable | Required | Description |
|---|---|---|
| `DEEPLINE_API_KEY` | Yes | Deepline v2 API key |
| `DEEPLINE_API_BASE_URL` | Optional | Defaults to `https://code.deepline.com` |
| `AI_GATEWAY_API_KEY` | Optional | Static fallback; Vercel OIDC is preferred |
| `EVE_MODEL` | Optional | Overrides Eve's default model |

After deployment, verify the live URL:

```bash
npm run smoke -- --host https://<your-vercel-url>
```

## Access Control

The Eve web channel includes `none()` explicitly so the reference app behaves like the current Python web chat and works immediately after deployment. This is the Vercel-supported anonymous route-auth helper, and it should stay as the final auth entry only when public chat is intended. For a private deployment, edit `agent/channels/eve.ts` and remove `none()` from the auth chain, or replace it with your application auth provider ahead of `localDev()` and `vercelOidc()`.

## Parity Surface

The Eve port preserves the important Deepline GTM behavior:

- full Deepline v2 agent/chat streaming through the `deepline_chat` tool
- direct Deepline v2 tool execution through `deepline_execute_tool`
- GTM guidance around evidence, uncertainty, CRM safety, and bounded action
- workflow presets for enrichment, account digests, support, web research, bounded tool action, closed-loop GTM, and Snowflake query agents
- deterministic eval coverage for smoke behavior, workflow presets, enrichment guidance, account research, and approval rules

Slack runs through `agent/channels/slack.ts`, with credentials supplied by Vercel Connect. The Python broker that previously served Slack is deleted.
