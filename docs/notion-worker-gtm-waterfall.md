# Notion Worker GTM Waterfall

This is the Notion-hosted version of the Deepline GTM agent workflow. It lets a Notion Custom Agent call Deepline plays directly through a Notion Worker, without shelling out to the Deepline CLI.

## Deployment

- Worker source: `/Users/jaitoor/dev/deepline-api/examples/notion-worker-deepline`
- Notion workspace ID: `c93aa292-eda9-4177-aca1-e822826fb9f3`
- Worker ID: `019f27e3-1ac4-718c-9013-397545f0cc1d`
- Demo page: [Deepline Notion Worker Demo](https://app.notion.com/p/aero-ai/Deepline-Notion-Worker-Demo-392da8d1d8eb8184b3f1c04714de724b)
- Deepline host: `https://code.deepline.com`

Secrets live in the Notion Worker environment:

- `DEEPLINE_API_KEY`
- `DEEPLINE_HOST_URL`

Do not put Deepline credentials in the agent prompt, Notion page body, or this repo.

## Exposed Worker Tools

Use the narrow typed tools first. Use generic discovery and execution only when the typed workflow does not fit.

| Tool | Purpose |
|---|---|
| `deeplineWorkflowGuide` | Returns operating guidance and recommended workflows for the agent. |
| `deeplineContactAgentJobChangeGuide` | Returns the Contact Agent job-change workflow: chunking, HubSpot query shape, Notion output contract, and safety rules. |
| `deeplineCreateDatabaseCleanupDemoData` | Creates a dirty inline Notion database for the database cleanup demo. |
| `deeplinePreviewDatabaseCleanup` | Audits a Notion data source or JSON rows for duplicates, invalid statuses, missing owners, missing/bad dates, and stale dates without writing. |
| `deeplineApplyDatabaseCleanup` | Applies previewed cleanup fixes only after exact approval phrase `APPLY_DATABASE_CLEANUP`. |
| `deeplineRunHubSpotJobChangeSample` | Checks a small HubSpot contact sample with Deepline `job_change` and writes positive moved contacts into Notion when explicitly requested. |
| `deeplineRenderHubSpotJobChanges` | Creates the Notion positive-results database from `positivesJson` without rerunning Deepline job-change checks. |
| `deeplineOrgChartSkillGuide` | Returns the Deepline `/orgchart` skill guidance: mode choice, source order, buying committee mapping, scoring, caveats, and Notion output contract. |
| `deeplinePreviewNotionOrgChartWrite` | Previews the Notion database title, stable output key, columns, and write requirements before creating org chart output. |
| `deeplineRunOrgChartDiscovery` | Runs Deepline org chart discovery and returns normalized rows without writing to Notion. |
| `deeplineRenderNotionOrgChart` | Creates the Notion org chart database from already-discovered rows and skips duplicate output by default. |
| `deeplineWaterfallEnrichCompanyContacts` | Runs the company-to-contact play, then optionally runs work-email waterfall for each matched contact. |
| `deeplineFindCompanyContact` | Finds role-matched contacts at a company using `prebuilt/company-to-contact`. |
| `deeplineFindWorkEmail` | Finds a verified work email for a known person using `prebuilt/name-and-domain-to-email-waterfall`. |
| `deeplineCreateNotionOrgChart` | Runs Deepline roster discovery, classifies an org chart / buying committee, and creates an inline Notion database under the requested parent page. |
| `deeplineSearchPlays` | Discovers available Deepline plays. |
| `deeplineDescribePlay` | Reads a play contract before running it. |
| `deeplineRunPlay` | Runs a known play with explicit input. |
| `deeplineGetRun` | Fetches status/output for an existing run ID. |
| `deeplineSearchTools` | Discovers atomic Deepline tools. |
| `deeplineDescribeTool` | Reads an atomic tool contract before calling it. |
| `deeplineExecuteTool` | Executes an atomic Deepline tool. |

## Agent Instructions

Use this prompt in the Notion Custom Agent instructions.

```text
You are a GTM research and enrichment agent powered by Deepline.

Goal:
- Help the user turn sparse company, contact, or account inputs into concise, sourced GTM outputs.
- Prefer repeatable Deepline workflows over one-off guessing.

Operating rules:
- Start from the identifiers the user provides: company name, domain, LinkedIn URL, role, seniority, person name, title, or location.
- Use workspace context first when it exists.
- Call deeplineWorkflowGuide when you need the recommended workflow or tool order.
- Prefer typed tools over generic tools:
  - For database cleanup, use deeplineCreateDatabaseCleanupDemoData only when the user wants a demo table. For a real table, call deeplinePreviewDatabaseCleanup with dataSourceId first. Show duplicate rows, invalid statuses, missing owners, bad/missing dates, stale dates, and fixesJson. Do not call deeplineApplyDatabaseCleanup unless the user explicitly approves with APPLY_DATABASE_CLEANUP.
  - For HubSpot job-change checks, call deeplineContactAgentJobChangeGuide first. Then call deeplineRunHubSpotJobChangeSample with a small contactsJson export or hubspot_search_objects input. Use chunks of 10-20 contacts. If positives are found and the user wants Notion output, pass positivesJson to deeplineRenderHubSpotJobChanges. Do not rerun paid job-change checks just to render a table.
  - For org chart, stakeholder map, account map, buying committee, or multi-threading tasks, call deeplineOrgChartSkillGuide first. Preferred flow: call deeplinePreviewNotionOrgChartWrite if you need to explain the write, call deeplineRunOrgChartDiscovery to get rows, then call deeplineRenderNotionOrgChart with rowsJson to create the database. Use deeplineCreateNotionOrgChart only for one-shot compatibility.
  - Use deeplineWaterfallEnrichCompanyContacts for company -> role-matched contacts -> optional work emails.
  - Use deeplineFindCompanyContact for company -> role-matched contacts only.
  - Use deeplineFindWorkEmail for known person + domain -> work email.
- If a typed tool does not fit, use deeplineSearchPlays or deeplineSearchTools, then describe the play/tool before running it.
- Never invent input fields. Read the contract first.
- Use small limits by default. Increase limits only when the user asks.
- Always include the Deepline run ID for executed workflows.
- If a run is queued, running, or waiting, call deeplineGetRun with the returned run ID.
- Keep outputs concise and scannable.

Quality bar:
- Do not invent facts.
- Do not merge two people or companies into one profile.
- Include source links when the tool returns them.
- Call out ambiguity and ask for a tie-breaker instead of guessing.
- Use only public or user-provided business information.
- Do not return sensitive personal data such as home addresses, personal phone numbers, family details, or non-public emails.

Default output:
- Summary of what was found.
- Contacts or records in a compact table or bullets.
- Evidence and source links.
- Deepline run IDs.
- Gaps, caveats, and next recommended action.
```

## Database Cleanup Workflow

Primary tools:

- `deeplineCreateDatabaseCleanupDemoData`
- `deeplinePreviewDatabaseCleanup`
- `deeplineApplyDatabaseCleanup`

Demo flow:

1. Call `deeplineCreateDatabaseCleanupDemoData` with the current page ID.
2. Call `deeplinePreviewDatabaseCleanup` with the returned `dataSourceId`:

```json
{
  "dataSourceId": "returned data source id",
  "rowsJson": null,
  "duplicateKeyProperties": ["Email", "LinkedIn"],
  "statusProperty": "Status",
  "validStatuses": ["New", "Active", "Closed"],
  "defaultStatus": "New",
  "ownerProperty": "Owner",
  "dateProperty": "Last Contact",
  "defaultDate": null,
  "staleDays": 180,
  "cleanupNotesProperty": "Cleanup Notes",
  "sampleLimit": 100
}
```

3. Present the preview. Do not write yet.
4. If the user approves with `APPLY_DATABASE_CLEANUP`, call `deeplineApplyDatabaseCleanup` with `fixesJson`.

The apply tool can annotate pages, set an explicit default select/status, or set an explicit default date. It does not guess owners.

## HubSpot Job-Change Workflow

Primary tools:

- `deeplineRunHubSpotJobChangeSample`
- `deeplineRenderHubSpotJobChanges`

Read first: `deeplineContactAgentJobChangeGuide`

Use a small sample first. Preferred input is a HubSpot contact JSON export:

```json
{
  "contactsJson": "[{\"id\":\"123\",\"properties\":{\"email\":\"person@example.com\",\"firstname\":\"Ada\",\"lastname\":\"Lovelace\",\"company\":\"Example\",\"website\":\"example.com\",\"jobtitle\":\"VP Sales\",\"linkedin_url\":\"https://www.linkedin.com/in/example\"}}]",
  "hubspotToolId": null,
  "hubspotInputJson": null,
  "sampleLimit": 5,
  "parentPageId": "current page id",
  "outputTitle": "HubSpot Job Changes - Deepline",
  "writeToNotion": true,
  "dryRun": false,
  "jobChangeToolId": null,
  "useSampleContacts": null
}
```

The run tool runs Deepline `job_change` with the correct native fields: `company_domain`, `professional_email`, `personal_email`, `contact_linkedin`, `contact_full_name`, and `company_linkedin`. It returns `positivesJson`. The render tool creates the Notion table from `positivesJson` and writes only `moved` contacts.

For Notion Agent reliability, do not run a single 50-contact batch. Run 10-20 contacts per call and aggregate positives. If the user wants a demo with a likely positive, prioritize old leads with `hs_linkedin_url HAS_PROPERTY` before broad newest/oldest slices.

## Waterfall Workflow

Primary tool: `deeplineWaterfallEnrichCompanyContacts`

Input shape:

```json
{
  "companyName": "Stripe",
  "domain": "stripe.com",
  "linkedinCompanyUrl": null,
  "roles": ["Partnerships"],
  "seniority": null,
  "limit": 1,
  "includeWorkEmail": false,
  "waitForSeconds": 45
}
```

Execution:

1. Runs `prebuilt/company-to-contact`.
2. Extracts compact contacts from the completed run output.
3. If `includeWorkEmail` is true and a contact has first name, last name, and domain, runs `prebuilt/name-and-domain-to-email-waterfall`.
4. Returns contact identity, title, LinkedIn URL, match evidence, waterfall status, run IDs, and caveats.

Use `includeWorkEmail=false` for demos and low-cost smoke tests. Use `includeWorkEmail=true` only when the user explicitly wants email enrichment and the Deepline workspace is allowed to spend on provider-backed lookups.

## End-to-End Tests

These checks were run against the deployed Notion Worker on July 3, 2026.

| Test | Command | Result |
|---|---|---|
| Local typecheck | `npm run typecheck` from the Worker source directory | Passed |
| Local build | `npm run build` from the Worker source directory | Passed |
| Local smoke import | `npm run smoke` from the Worker source directory | Passed |
| Remote guide tool | `npx ntn workers exec deeplineWorkflowGuide -d '{"topic":"waterfall enrichment"}'` | Passed; returned operating rules and recommended workflows |
| Remote play discovery | `npx ntn workers exec deeplineSearchPlays -d '{"query":"company contact","scope":"prebuilt"}'` | Passed; returned relevant prebuilt plays, including work email waterfall plays |
| Remote composite workflow | `npx ntn workers exec deeplineWaterfallEnrichCompanyContacts -d '{"companyName":"Stripe","domain":"stripe.com","linkedinCompanyUrl":null,"roles":["Partnerships"],"seniority":null,"limit":1,"includeWorkEmail":false,"waitForSeconds":45}'` | Passed; completed run `play/prebuilt/company-to-contact/run/20260703t122951-809-b41ace6a` |
| Remote org chart skill guide | `npx ntn workers exec deeplineOrgChartSkillGuide -d '{"mode":"company-wide"}'` | Passed on July 5, 2026; returned mode selection, source order, buying committee fields, quality bar, and required call order |
| Remote org chart routing guide | `npx ntn workers exec deeplineWorkflowGuide -d '{"topic":"org chart"}'` | Passed on July 5, 2026; tells the agent to call `deeplineOrgChartSkillGuide` before `deeplineCreateNotionOrgChart` |
| Remote org chart dry run | `npx ntn workers exec deeplineCreateNotionOrgChart -d '{"parentPageId":"392da8d1d8eb8184b3f1c04714de724b","companyName":"Stripe","domain":"stripe.com","linkedinCompanyUrl":null,"targetFunctions":["Sales"],"roles":null,"mode":"company-wide","maxRows":1,"limitPerRole":1,"includeWorkEmail":false,"waitForSeconds":45,"dryRun":true}'` | Passed on July 5, 2026; returned one Sales row and Deepline Native job `tool:search_contact:iad1::jhgmt-1783285704386-f9f3d58053f9` |
| Remote org chart write preview | `npx ntn workers exec deeplinePreviewNotionOrgChartWrite -d '{"parentPageId":"392da8d1d8eb8184b3f1c04714de724b","companyName":"Stripe","domain":"stripe.com","targetFunctions":["Sales","RevOps"],"roles":null,"mode":"company-wide","outputKey":null}'` | Passed on July 6, 2026; returned title `Stripe Org Chart - stripe-stripe-com-company-wide-sales-revops`, stable output key, and expected columns |
| Remote org chart discovery-only | `npx ntn workers exec deeplineRunOrgChartDiscovery -d '{"companyName":"Stripe","domain":"stripe.com","linkedinCompanyUrl":null,"targetFunctions":["Sales"],"roles":null,"mode":"company-wide","maxRows":1,"limitPerRole":1,"includeWorkEmail":false,"waitForSeconds":45}'` | Passed on July 6, 2026; returned one normalized row, rowsJson, render-next hint, and Deepline Native job `tool:search_contact:iad1::dxrrh-1783340163766-14b3e0dbfcd3` |
| Remote org chart compatibility dry run | `npx ntn workers exec deeplineCreateNotionOrgChart -d '{"parentPageId":"392da8d1d8eb8184b3f1c04714de724b","companyName":"Stripe","domain":"stripe.com","linkedinCompanyUrl":null,"targetFunctions":["Sales"],"roles":null,"mode":"company-wide","maxRows":1,"limitPerRole":1,"includeWorkEmail":false,"waitForSeconds":45,"dryRun":true,"outputKey":null,"skipIfExists":true}'` | Passed on July 6, 2026; legacy tool now returns stable output key, rowsJson, and render-next hint |
| Remote database cleanup preview | `npx ntn workers exec deeplinePreviewDatabaseCleanup -d '{"dataSourceId":null,"rowsJson":"[...]","duplicateKeyProperties":["Email"],"statusProperty":"Status","validStatuses":["New","Active","Closed"],"defaultStatus":"New","ownerProperty":"Owner","dateProperty":"Last Contact","defaultDate":null,"staleDays":180,"cleanupNotesProperty":"Cleanup Notes","sampleLimit":null}'` | Passed on July 6, 2026; returned duplicate, invalid status, missing owner, stale date, six planned fixes, and approval instructions |
| Remote cleanup approval gate | `npx ntn workers exec deeplineApplyDatabaseCleanup -d '{"fixesJson":"[]","approvalPhrase":"NO","maxFixes":null}'` | Passed on July 6, 2026; failed loudly before writing with `approvalPhrase must be APPLY_DATABASE_CLEANUP` |
| Remote HubSpot job-change planning guard | `npx ntn workers exec deeplineRunHubSpotJobChangeSample -d '{"contactsJson":null,"hubspotToolId":null,"hubspotInputJson":null,"sampleLimit":3,"parentPageId":null,"outputTitle":null,"writeToNotion":null,"dryRun":null,"jobChangeToolId":null,"useSampleContacts":null}'` | Passed on July 6, 2026; returned `needs_contacts` without spending credits or writing |

Observed composite workflow output:

- Status: `completed`
- Contact found: yes
- Contact: Dravya Nataraj
- Title: Partner Engineering Platform Partnerships
- Company: Stripe
- LinkedIn: `https://www.linkedin.com/in/dravyanataraj/`
- Confidence: high
- Email waterfall: skipped because `includeWorkEmail=false`

## How To Call It In Notion

1. In Notion, create or edit a Custom Agent.
2. Attach the deployed Deepline Notion Worker as a tool source.
3. Paste the instructions from this doc into the agent instructions.
4. Ask the agent:

```text
Use Deepline to find one Partnerships contact at Stripe. Use a low-cost demo run and include the run ID.
```

Expected behavior:

- The agent calls `deeplineWaterfallEnrichCompanyContacts`.
- It uses `includeWorkEmail=false` unless the user asks for email enrichment.
- It returns a concise result with the Deepline run ID.

For a Notion output task, ask:

```text
Use Deepline to create a Notion org chart table for Stripe under this page. Focus on Sales, Marketing, RevOps, and Partnerships. Do not run work-email enrichment unless I ask for emails. Include Deepline run IDs and clearly mark inferred relationships.
```

Expected behavior:

- The agent calls `deeplineOrgChartSkillGuide` first.
- The agent calls `deeplineRunOrgChartDiscovery` after choosing company-wide or person-centric handling.
- The agent calls `deeplineRenderNotionOrgChart` with `rowsJson` to create the database.
- It passes the current page ID as `parentPageId`.
- The Worker creates an inline Notion database containing the org chart table.
- Reporting relationships are marked as inferred unless explicitly confirmed by evidence.
