# Workflow Coverage

This repo is for teams that want a rep-facing GTM agent surface backed by
Deepline's execution layer. It should make proven workflows easy to trigger from
Slack, HTTP, Eve, Notion Custom Agents, Hermes, or an MCP-style wrapper without
copying provider logic into this repo.

Tested framework targets:

- `Eve`
- `LangChain Deep Agents`
- `Anthropic Managed Agents`

## Prove Workflow Coverage

| Workflow | Status | Agent entry point | Required behavior |
|---|---|---|---|
| Account briefs | Covered | `account_brief`, `web_context_research`, Hermes `deepline-account-research` | Return company snapshot, buyer context, current signals, suspected pain, Deepline angle, first-message angle, open questions, sources, and proof status. |
| Signal stacking | Covered | `signal_stacking`, `snowflake_query_agent`, niche-signal skill docs | Combine public web, hiring, compliance, product, CRM, and warehouse signals. Separate fit, intent, readiness, anti-fit, missing evidence, and recommended next workflow. |
| Org chart building | Covered | `org_chart_building`, Notion Worker org-chart tools, `deepline-gtm/recipes/account-orgchart.md` | Choose company-wide or person-centric mode, run a small discovery pass, classify buying-committee roles, mark inferred relationships, preserve run IDs, and ask before email enrichment or writes. |
| Company-to-contact waterfall | Covered | Notion Worker `deeplineWaterfallEnrichCompanyContacts`, shared Deepline recipes | Run company-to-contact first. Run work-email waterfall only when asked or approved. Return provider/run status instead of guessing. |
| HubSpot job-change workflow | Covered in Notion Worker | `deeplineRunHubSpotJobChangeSample`, `deeplineRenderHubSpotJobChanges` | Run small samples, return positives, write Notion output only when requested, and avoid rerunning paid checks for rendering. |
| Database cleanup | Covered in Notion Worker | `deeplinePreviewDatabaseCleanup`, `deeplineApplyDatabaseCleanup` | Preview duplicate/status/owner/date fixes first. Apply only after exact approval phrase. |
| Slack business-mobile enrichment | Covered | Slack broker direct Deepline provider path | Legal B2B mobile requests with LinkedIn URLs run licensed Deepline providers directly; no refusal, no invented numbers. |

## Public Repo Patterns To Borrow

| Pattern | Seen in public repos | What this repo should do |
|---|---|---|
| Clear surface choice | CLI/dashboard in [OneShot GTM](https://github.com/oneshot-agent/oneshot-gtm), Slackbot in [CRM Bot](https://github.com/TextQLLabs/crm-bot), skill packs in [GTMify](https://github.com/GTMify/aigtm) and [GTM Agents](https://github.com/gtmagents/gtm-agents) | Lead with deploy surfaces: Slackbot, REST/custom agent backend, Eve/Vercel, Notion Worker, Hermes, Azure Container Apps. |
| Named workflows | OneShot plays; GTMify skills; [AgentMail GTM examples](https://github.com/agentmail-to/agentmail-examples) | Keep workflow presets discoverable and test them in Python and Eve. |
| Approval and ledger/audit | OneShot receipts; CRM Bot Slack-to-CRM flow; [Relaticle](https://github.com/relaticle/relaticle) MCP/CRUD boundary | Keep side effects approval-gated and return provider/run IDs, source status, and writeback IDs. |
| Tool boundary | Relaticle MCP server; CRM Bot native tool calling | Deepline should own provider execution and CRM/writeback APIs. This repo should own transport, auth, prompt bounds, and deploy recipes. |
| Rep-facing ergonomics | Slackbot and inbox examples | Return concise briefs, status tables, and next actions. Avoid raw provider dumps. |

## Gaps To Keep Closing

- Add an MCP server wrapper only if a target host requires MCP. The wrapper should
  expose narrow workflow tools and call this broker or Deepline v2; it should not
  duplicate provider waterfalls locally.
- Add Azure Container Apps as a first-class deployment path and test it with a
  real Azure subscription.
- Add workflow evals for `account_brief`, `signal_stacking`, and
  `org_chart_building` so README claims stay executable.
- Keep syncing Eve skills from Deepline's well-known skills index so there is one
  shared skill source across Deepline API and this agent.
