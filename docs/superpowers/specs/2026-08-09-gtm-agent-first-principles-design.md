# GTM Agent From First Principles

## Goal

Extend `Deepline-GTM-Agent-Teardown.html` with a first-principles framework and a concrete architecture for the first GTM agent Deepline should ship. The section must connect the teardown's shared lessons to one narrow implementation: a Lemlist Reply Copilot.

The result should answer two questions for an internal Deepline audience:

1. What does every useful GTM-agent build need?
2. How do Deepline, Slack, Notion, HubSpot, Lemlist, and the agent runtime fit together for the first workflow?

## Story Placement

The new material sits between the existing teardown pattern and MVP slides:

1. Teardown takeaway
2. First-principles framework
3. Concrete system architecture and workflow
4. Existing Deepline MVP slide

This preserves the narrative progression from observed pattern, to design framework, to system, to build order.

## Slide 07: First-Principles Framework

Change the heading from “Everyone built the same six things.” to:

> Every build needs the same six things.

Replace the generic numbered checklist with six questions. “What” and “How” remain separate questions even though both are enabled by tools.

| Question | Capability | Meaning in the first build |
| --- | --- | --- |
| Who | Enrichment | Identify the sender, account, role, ownership, and conversation history behind the reply. |
| When | Trigger | Start when a new Lemlist reply arrives. Monitors may become an additional trigger later. |
| What | Tools for context | Let the agent retrieve the reply thread, company and person data, CRM state, and supporting sources. |
| How | Tools for action | Let the agent classify the reply, draft a response, request approval, send, and update downstream systems. |
| Why | Filters and qualification | Decide whether the reply is positive, a question, an objection, not interested, or out of office before drafting. |
| Where | Rep surface | Put decisions and approvals where the team works: Slack first, HubSpot as CRM, with a custom app only if later needed. |

The slide should read as a conceptual framework, not as six implementation steps.

## New Slide 08: Architecture

### Visual concept

Create a native HTML/CSS/SVG architecture diagram that matches the existing restrained editorial deck. It must remain legible in light and dark themes and adapt to narrow screens.

The diagram uses a strong central spine rather than a generic grid of cards:

- **Slack** at the top is the human interface: review the classification and evidence, then approve, edit, or reject the draft.
- **Vercel Eve agent** is the orchestrator and runtime.
- **Deepline** is the tools-and-compute substrate, connecting the agent to enrichment and source data rather than acting as a passive database.
- **HubSpot** provides ownership, lifecycle, suppression, and prior-activity context and receives the disposition and activity after approval.
- **Notion** stores durable reply-handling guidance, account research, and workflow learnings.
- **Lemlist** supplies the inbound reply and sends the approved response.

Connections must show direction and meaning:

- New Lemlist reply / HubSpot state → agent
- Agent ↔ Deepline tools and data
- Agent ↔ Slack approval loop
- Approved response → Lemlist; disposition and context → HubSpot and Notion

### Supporting copy

The architecture slide should explicitly describe the single workflow:

1. A new reply arrives from Lemlist.
2. The agent classifies it as positive, question, objection, not interested, or out of office.
3. Deepline gathers person and company context while HubSpot supplies ownership, lifecycle, prior activity, and suppression state.
4. The agent drafts a grounded response and recommends the next action.
5. Slack presents the reply, evidence, classification, and draft for approval, editing, or rejection.
6. On approval, Lemlist sends the response, HubSpot records the disposition and activity, and Notion retains durable research or workflow learnings when useful.

The MVP auto-drafts but does not auto-send. Human approval in Slack is required before Lemlist sends. Low-risk reply categories may graduate to auto-send only after observed edits demonstrate reliable behavior. Monitors are not required for the MVP and may later supply additional trigger types through the same boundary.

## Runtime Decision

Use **Vercel Eve today, with Claude as the model**.

Reasons:

- Eve already has a minimal Slack-agent starter with tools and skills.
- Vercel Connect handles Slack authentication, while AI Gateway handles model access.
- The repository already contains an `eve_agent` implementation path, reducing time to a working build.
- The architecture remains model-provider-flexible while allowing Claude to power reasoning.

Claude Managed Agents is a future option when the workflow needs long-running durable sessions, platform-managed credential vaults, per-tool permissions, or centralized audit traces. It is currently a public-beta platform surface and is not necessary for the narrow first workflow.

The slide should present this as a decisive sequence: “Ship on Eve now; reassess Managed Agents after the workflow proves it needs a heavier managed runtime.”

## Visual and Interaction Requirements

- Preserve the current deck's typography, palette, borders, slide proportions, theme behavior, keyboard navigation, and editorial tone.
- Add only the CSS needed for the new framework and architecture components.
- Avoid embedded raster art for the new diagram; use semantic HTML and inline SVG so text remains crisp.
- Use meaningful labels on connector lines rather than decorative arrows.
- Ensure all diagram text meets readable contrast in both themes.
- On screens below 820px, convert the diagram into a clear vertical flow without hiding any system.
- Respect the existing `prefers-color-scheme` behavior.

## Acceptance Criteria

- The “Every build needs the same six things.” wording is present.
- The six questions map correctly to enrichment, triggers, tools, qualification, and rep surfaces.
- The architecture visibly includes Deepline, Slack, Notion, HubSpot, Lemlist, and Vercel Eve.
- The diagram makes Deepline the data/tool integration layer and Slack the human interface.
- The workflow is specifically a Lemlist Reply Copilot.
- Classification and qualification happen before drafting or sending.
- Human approval in Slack happens before Lemlist execution.
- Notion and HubSpot receive durable outputs/state.
- Auto-drafting is clearly distinguished from future autonomous auto-send.
- Monitors are described only as a later trigger option.
- The page remains self-contained, responsive, theme-compatible, and keyboard navigable.
- The runtime recommendation clearly favors Vercel Eve for the first build while naming the conditions that would justify Claude Managed Agents later.

## Verification

- Parse the finished HTML and confirm the expected slide count and required system labels.
- Open the page in a browser at desktop and mobile widths.
- Inspect light and dark themes.
- Verify arrow-key navigation across the inserted slide.
- Confirm no existing embedded images or teardown content were damaged.
