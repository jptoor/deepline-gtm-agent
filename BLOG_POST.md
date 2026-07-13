# What We Learned Porting Our GTM Agent to Eve

We added an Eve implementation to [`getaero-io/deepline-gtm-agent`](https://github.com/getaero-io/deepline-gtm-agent/).

The goal was not to rebuild Deepline inside another agent framework.

The goal was smaller:

- keep Deepline as the GTM execution backend
- use Eve for sessions, channels, evals, and Vercel deployment
- make the agent easier to install and test
- keep Slack and the existing Python broker working

That constraint shaped the whole migration.

## The Old Shape

The first production version was a Python broker.

It handled REST, web chat, Slack, auth, Slack formatting, streaming, thread context, and prompt shaping. It sent GTM work to Deepline's v2 agent/chat and API layer.

That worked.

It was also easy to let the broker grow.

Every adapter bug looked like a reason to add more local logic. A Slack formatting bug became a rendering rule. A batch enrichment request became a prompt rule. A provider failure became a local fallback. That is how a broker turns into a second product.

We did not want that.

## What Eve Changed

Eve gave us a cleaner runtime shape.

The agent lives as files:

- `agent/instructions.md`
- `agent/tools`
- `agent/skills`
- `agent/channels`
- evals and smoke scripts

That made the agent easier to inspect. It also made deployment simpler. The Eve app can run locally, expose Eve session routes, and deploy to Vercel without maintaining another service shape.

The useful part was packaging.

Eve gave us a standard place to put the agent boundary.

## What Deepline Still Owns

The important decision was what not to port.

Deepline still owns:

- provider routing
- enrichment
- CRM and outreach actions
- plays and workflows
- credentials
- billing
- run state
- provider-specific failure handling

Eve should not know how to run a provider waterfall. It should not know how to write to HubSpot. It should not keep a second run history for Deepline work.

Eve should ask Deepline to do the work, then present the result.

## Skills Had To Come From The API

The first risk was skill drift.

It is tempting to copy GTM playbooks into an Eve repo and call it done. That works for a week. Then the Deepline API skill changes, the Eve copy does not, and two agents start teaching users different things.

So the Eve implementation now syncs skills from Deepline's published well-known skills API.

The generated snapshot keeps:

- `SKILL.md`
- references
- scripts
- metadata
- recipe wrappers
- file hashes

The repo can still deploy without a local `deepline-api` checkout. The source of truth stays in Deepline API.

## Recipes Had The Same Problem

Reusable GTM recipes also had to come from Deepline API.

The Eve app now vendors a generated recipe snapshot. The snapshot is committed so Vercel deploys work out of the box. But nobody should hand-edit those recipes in Eve.

If a recipe is wrong, fix it in Deepline API, publish it, sync it, and test it.

This is less convenient than editing one local prompt. It prevents two copies of the same GTM recipe from drifting apart.

## What We Gained

We gained a faster path to a working deployed agent.

The Eve path gives us:

- local session routes
- Vercel deployment
- AI Gateway configuration
- smoke tests
- eval hooks
- a filesystem contract for tools and skills
- a clear place for future channels

The Python broker is still useful. It already has Slack behavior, REST compatibility, and hardened production defaults.

Eve is the faster deploy path. The Python broker is the stable compatibility path.

Keeping both for now is not indecision. It is how we avoid breaking users while the Eve path proves parity.

## What We Gave Up

We gave up the illusion that one framework should own the whole agent.

Eve owns runtime shape.

Deepline owns GTM execution.

The broker owns transport safety.

That split creates more files and more tests. It also forces decisions that were previously hidden in prompts.

For example, the public broker now has a `/doctor` endpoint. It checks whether the Deepline key is present, whether chat auth is configured, whether CORS is explicit, whether Slack is configured, and whether local live-write mode is unsafe.

That does not make the model better. It makes the deployment less surprising.

## The Security Lesson

Most agent risk was not in the model call.

It was in the edges:

- public chat endpoints without auth
- wildcard CORS
- Slack events without signature checks
- local development pointing at production writes
- streamed tool output leaking more than the user needs

So we added tests at the boundary.

The new E2E tests hit the real FastAPI app in-process. They verify that `/chat` requires auth, disallowed tools fail before Deepline is called, `/chat/stream` preserves native SSE events, `/doctor` catches unsafe setup, and email verification fallback does not stream billing or request IDs.

Those tests match the repo's job. They test the adapter.

They do not pretend to test all of Deepline.

## The Eval Lesson

Mock evals are easy to misread.

Our `--no-live-api` eval mode returns a generic canned response. That is useful for making sure the runner does not crash. It is not useful for GTM content assertions.

If an eval asks for "Find 5 VP Sales contacts" and the mock reply says "Mock native Deepline v2 response," the eval should fail.

That failure is not a product failure. It means content evals need a real backend or a realistic fixture.

For this agent, the better local signal is endpoint-level E2E coverage plus targeted deterministic tests. Live GTM evals should run only with explicit Deepline credentials and the right internal workspace.

## What We Would Do Again

We would keep Eve additive.

Replacing the Python broker first would have been riskier. The existing broker already handled Slack, REST, web chat, and production safety. Eve gave us a better future path, not an excuse to delete working surfaces.

We would keep skills and recipes API-owned.

Copied playbooks rot. Synced snapshots are a better compromise. They deploy cleanly, but they still point back to one source of truth.

We would keep the agent thin.

The more local GTM logic we add, the less useful Deepline becomes as the system of record. The agent should route, ask for approval, render, and explain. Deepline should execute.

## The Current Shape

The repo now has three useful surfaces:

1. The Python broker for REST, web chat, and Slack.
2. The Eve app for faster Vercel deployment and durable sessions.
3. Deepline API as the execution layer for GTM tools, plays, skills, recipes, credentials, and run state.

Frameworks help when they remove runtime work.

They hurt when they tempt you to duplicate your product.

Eve made the runtime easier to ship.

Deepline still does the work.
