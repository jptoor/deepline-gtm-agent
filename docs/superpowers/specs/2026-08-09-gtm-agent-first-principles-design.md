# GTM Agent From First Principles

## Goal

Extend `Deepline-GTM-Agent-Teardown.html` with a first-principles framework and a concrete architecture for the first GTM agent Deepline should ship. The section must connect the teardown's shared lessons to one narrow implementation: a hiring-signal warm-outbound workflow.

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
| Who | Enrichment | Identify the account, relevant buyer, role, and evidence behind the match. |
| When | Trigger | Start when Deepline finds a qualified hiring signal. Monitors may become an additional trigger later. |
| What | Tools for context | Let the agent retrieve company, person, hiring, CRM, and source data. |
| How | Tools for action | Let the agent write outputs and prepare or launch downstream actions. |
| Why | Filters and qualification | Decide whether the signal is relevant and whether outreach is appropriate before drafting. |
| Where | Rep surface | Put decisions and approvals where the team works: Slack first, HubSpot as CRM, with a custom app only if later needed. |

The slide should read as a conceptual framework, not as six implementation steps.

## New Slide 08: Architecture

### Visual concept

Create a native HTML/CSS/SVG architecture diagram that matches the existing restrained editorial deck. It must remain legible in light and dark themes and adapt to narrow screens.

The diagram uses a strong central spine rather than a generic grid of cards:

- **Slack** at the top is the human interface: request, review, approve, edit, or reject.
- **Vercel Eve agent** is the orchestrator and runtime.
- **Deepline** is the tools-and-compute substrate, connecting the agent to enrichment and source data rather than acting as a passive database.
- **HubSpot** has two roles: inbound/CRM context into the workflow and approved activity/state written back to the CRM.
- **Notion** stores durable research and campaign outputs.
- **Lemlist** receives approved outbound drafts or campaigns for execution.

Connections must show direction and meaning:

- Hiring signal / HubSpot state → agent
- Agent ↔ Deepline tools and data
- Agent ↔ Slack approval loop
- Approved output → Notion, HubSpot, and Lemlist

### Supporting copy

The architecture slide should explicitly describe the single workflow:

1. Deepline detects a relevant hiring signal and enriches the company and likely buyer.
2. The agent checks HubSpot for ownership, lifecycle, prior activity, suppression, and duplicates.
3. The agent qualifies the signal and drafts grounded outreach with sources.
4. Slack presents the evidence, reasoning, and draft for approval or editing.
5. On approval, the agent stores research in Notion, updates HubSpot, and sends the draft to Lemlist.

Monitors are not required for the MVP. They may later supply recurring or event-driven hiring signals through the same trigger boundary.

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
- The workflow is specifically a hiring-signal warm-outbound play.
- Qualification happens before drafting or sending.
- Human approval in Slack happens before Lemlist execution.
- Notion and HubSpot receive durable outputs/state.
- Monitors are described only as a later trigger option.
- The page remains self-contained, responsive, theme-compatible, and keyboard navigable.
- The runtime recommendation clearly favors Vercel Eve for the first build while naming the conditions that would justify Claude Managed Agents later.

## Verification

- Parse the finished HTML and confirm the expected slide count and required system labels.
- Open the page in a browser at desktop and mobile widths.
- Inspect light and dark themes.
- Verify arrow-key navigation across the inserted slide.
- Confirm no existing embedded images or teardown content were damaged.
