# Inbound Buying Committee Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trigger one published Deepline Play from a HubSpot contact-created event so the play qualifies the account, builds and stores a buying committee, drafts outreach, prepares a Lemlist placeholder, and DMs Jai in Slack.

**Architecture:** The Python broker validates and normalizes the inbound event, then calls `POST /api/v2/plays/run` with the live play name and returns the Deepline run ID. All business logic and side effects live in a TypeScript Deepline Play packaged with a local Eve skill. Pure qualification, stakeholder ranking, inferred-edge, and Slack-rendering helpers are separated from runtime calls so they can be tested deterministically.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, httpx, pytest; TypeScript, Node test runner, Deepline Plays SDK/CLI; HubSpot, Deepline Customer DB datasets, Slack, Lemlist.

## Global Constraints

- The agent performs trigger validation and exactly one published-play dispatch; it contains no qualification, enrichment, drafting, Slack, persistence, or Lemlist workflow logic.
- Qualification requires all three gates: `employee_count >= 50`, explicit B2B evidence, and an identifiable GTM or RevOps function.
- Unknown qualification evidence yields `manual_review`, not automatic qualification.
- The signup contact can appear in the committee but cannot be selected as the primary outbound target.
- All reporting relationships are labeled `inferred` and include evidence, confidence, and the reporting-line disclaimer.
- Lemlist defaults to a stored `ready_to_create` placeholder. No lead enrollment, send, CRM writeback, or campaign activation is allowed.
- Play runtime I/O uses replay-safe `ctx.*` APIs with stable call and dataset keys.
- Provider-backed execution is limited to one controlled pilot until the required credit-and-scope approval gate is satisfied.

## File Structure

- `deepline_gtm_agent/v2_client.py`: add the reusable named-play dispatch method.
- `managed_agent/inbound_buying_committee.py`: own webhook authentication, event normalization, and thin dispatch service.
- `managed_agent/server.py`: register the new router only.
- `managed_agent/env.example`: document the play reference and webhook secret.
- `tests/test_v2_client.py`: verify the exact V2 play-run request contract.
- `tests/test_inbound_buying_committee.py`: verify webhook normalization, auth, idempotency keys, and thin dispatch behavior.
- `eve_agent/agent/skills/inbound-buying-committee/SKILL.md`: teach the agent when and how to trigger the published play.
- `eve_agent/agent/skills/inbound-buying-committee/skill-metadata.json`: register the skill entrypoint.
- `eve_agent/agent/skills/inbound-buying-committee/shared/committee-logic.ts`: deterministic qualification, role classification, ranking, edge inference, and Slack rendering.
- `eve_agent/agent/skills/inbound-buying-committee/plays/inbound-buying-committee.play.ts`: own all Deepline runtime orchestration and durable datasets.
- `eve_agent/tests/inbound-buying-committee.test.ts`: verify pure workflow rules and skill packaging.
- `README.md` and `SETUP.md`: document the HubSpot workflow-to-agent-to-play deployment path.

---

### Task 1: Named Deepline Play Dispatch

**Files:**
- Modify: `deepline_gtm_agent/v2_client.py`
- Test: `tests/test_v2_client.py`

**Interfaces:**
- Consumes: existing `DeeplineV2Client._headers()`, base URL, transport, and timeout.
- Produces: `async def start_play(self, name: str, input: dict[str, Any]) -> dict[str, Any]`.

- [ ] **Step 1: Write the failing request-contract test**

```python
def test_start_play_uses_named_play_route():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2/plays/run"
        assert json.loads(request.read()) == {
            "name": "jai-inbound-buying-committee",
            "input": {"hubspotContactId": "123", "idempotencyKey": "hubspot:123:created"},
        }
        return httpx.Response(202, json={"workflowId": "play_run_1", "status": "running"})
```

- [ ] **Step 2: Run the focused test and verify it fails because `start_play` is missing**

Run: `pytest tests/test_v2_client.py::test_start_play_uses_named_play_route -q`

- [ ] **Step 3: Implement the minimal named-play request**

```python
async def start_play(self, name: str, input: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(...) as http:
        response = await http.post(
            "/api/v2/plays/run",
            headers=self._headers(),
            json={"name": name, "input": input},
        )
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 4: Run the focused test, then all V2 client tests**

Run: `pytest tests/test_v2_client.py -q`

- [ ] **Step 5: Commit the isolated client change**

```bash
git add deepline_gtm_agent/v2_client.py tests/test_v2_client.py
git commit -m "feat: dispatch named Deepline plays"
```

### Task 2: Thin HubSpot Contact-Created Trigger

**Files:**
- Create: `managed_agent/inbound_buying_committee.py`
- Modify: `managed_agent/server.py`
- Modify: `managed_agent/env.example`
- Create: `tests/test_inbound_buying_committee.py`

**Interfaces:**
- Consumes: `DeeplineV2Client.start_play(name, input)` from Task 1.
- Produces: `InboundBuyingCommitteeEvent`, `normalize_hubspot_contact_created(payload)`, `build_idempotency_key(event)`, `InboundBuyingCommitteeService.dispatch(event)`, and `POST /inbound-buying-committee/events`.

- [ ] **Step 1: Write failing event and dispatch tests**

```python
def test_normalizes_hubspot_contact_created_event():
    event = normalize_hubspot_contact_created({"objectId": 123, "eventId": "evt_1"})
    assert event.hubspot_contact_id == "123"
    assert build_idempotency_key(event) == "hubspot:123:evt_1"

def test_service_only_dispatches_the_published_play():
    result = asyncio.run(InboundBuyingCommitteeService(client=fake).dispatch(event))
    assert fake.calls == [("jai-inbound-buying-committee", expected_input)]
    assert result.run_id == "play_run_1"
```

- [ ] **Step 2: Run the focused tests and verify missing-module failures**

Run: `pytest tests/test_inbound_buying_committee.py -q`

- [ ] **Step 3: Implement strict normalization and stable idempotency**

Accept HubSpot workflow payloads containing `objectId` or `hubspotContactId`.
Reject missing/blank contact IDs. Normalize `eventId` when present and otherwise
use the literal `created`, producing `hubspot:<contact-id>:<event-id-or-created>`.

- [ ] **Step 4: Implement bearer authentication and the thin 202 endpoint**

Require `INBOUND_BUYING_COMMITTEE_WEBHOOK_SECRET`, dispatch the play in a FastAPI
background task, and return `{accepted, hubspot_contact_id, idempotency_key}`.
The service response exposes `workflowId`, initial status, and dashboard URL in
logs without waiting for enrichment.

- [ ] **Step 5: Register the router and document environment variables**

Add only the router import and `app.include_router(...)` to `server.py`. Document:

```dotenv
INBOUND_BUYING_COMMITTEE_WEBHOOK_SECRET=
INBOUND_BUYING_COMMITTEE_PLAY_NAME=jai-inbound-buying-committee
```

- [ ] **Step 6: Run endpoint, broker, and client tests**

Run: `pytest tests/test_inbound_buying_committee.py tests/test_v2_client.py tests/test_managed_v2_broker.py -q`

- [ ] **Step 7: Commit the thin trigger**

```bash
git add managed_agent/inbound_buying_committee.py managed_agent/server.py managed_agent/env.example tests/test_inbound_buying_committee.py
git commit -m "feat: trigger buying committee play from HubSpot"
```

### Task 3: Deterministic Buying-Committee Rules and Skill Package

**Files:**
- Create: `eve_agent/agent/skills/inbound-buying-committee/SKILL.md`
- Create: `eve_agent/agent/skills/inbound-buying-committee/skill-metadata.json`
- Create: `eve_agent/agent/skills/inbound-buying-committee/shared/committee-logic.ts`
- Create: `eve_agent/tests/inbound-buying-committee.test.ts`

**Interfaces:**
- Produces: `qualifyAccount`, `classifyStakeholder`, `rankStakeholders`, `inferOrgEdges`, `renderSlackBrief`, `REPORTING_DISCLAIMER`, and their TypeScript input/output types.
- Consumed by: the play in Task 4.

- [ ] **Step 1: Write failing qualification boundary tests**

Cover headcounts 49, 50, 51, and unknown; B2B `no`/`unknown`; and GTM-function
`no`/`unknown`. Assert only three explicit `yes` gates produce `qualified`.

- [ ] **Step 2: Write failing stakeholder and org-edge tests**

Assert the signup contact is never primary, RevOps/GTM/economic-buyer roles rank
above generic ICs, deterministic ties remain stable, and every inferred edge
contains `relationship: "inferred"`, evidence, confidence, and the disclaimer.

- [ ] **Step 3: Write the failing Slack brief and skill-discovery tests**

Assert the brief starts with “You signed up a larger org (Enterprise for now).”,
contains the primary draft and disclaimer, and that the skill entrypoint and
metadata are present with the published play name and safety boundary.

- [ ] **Step 4: Run the focused Node test and verify failures**

Run: `cd eve_agent && npx tsx --test tests/inbound-buying-committee.test.ts`

- [ ] **Step 5: Implement the pure workflow rules**

Use explicit input types and stable score weights. Keep provider payload parsing,
runtime handles, secrets, and side effects out of this helper module.

- [ ] **Step 6: Write the skill entrypoint and metadata**

The skill instructs the agent to normalize a HubSpot contact-created event and
invoke `jai-inbound-buying-committee` once. It states that all qualification,
committee discovery, org inference, drafting, persistence, Slack, and Lemlist
logic belongs to the play and that Lemlist is draft-only.

- [ ] **Step 7: Run focused and full Eve tests**

Run: `cd eve_agent && npm test && npm run typecheck`

- [ ] **Step 8: Commit the skill and deterministic rules**

```bash
git add eve_agent/agent/skills/inbound-buying-committee eve_agent/tests/inbound-buying-committee.test.ts
git commit -m "feat: add inbound buying committee skill"
```

### Task 4: Deepline Play Orchestration

**Files:**
- Create: `eve_agent/agent/skills/inbound-buying-committee/plays/inbound-buying-committee.play.ts`
- Modify: `eve_agent/tests/inbound-buying-committee.test.ts`

**Interfaces:**
- Consumes: Task 3 pure rules; live tool contracts for `hubspot_get_object`, `hubspot_search_objects`, `company_titles`, `search_contact`, `deeplineagent`, `slack_post_message`, and optionally `lemlist_create_campaign` only when an explicit play input enables the paused live placeholder.
- Produces: published play `jai-inbound-buying-committee` and durable datasets `inbound_runs`, `account_qualification`, `committee_members`, `org_edges`, `outreach_drafts`, `campaign_placeholders`, and `slack_notifications`.

- [ ] **Step 1: Add failing play-source contract assertions**

Read the play source and assert it contains the exact play name, all seven
dataset keys, `maxCreditsPerRun`, stable tool IDs, `ready_to_create`, the Slack
destination secret, and no `process.env`, `Date.now`, `Math.random`, local `fs`,
raw `fetch`, lead enrollment, send, or CRM writeback tool IDs.

- [ ] **Step 2: Run the focused test and verify it fails because the play is absent**

Run: `cd eve_agent && npx tsx --test tests/inbound-buying-committee.test.ts`

- [ ] **Step 3: Implement intake, CRM context, and qualification datasets**

Fetch the HubSpot contact with associated companies, fetch the company record,
get its real title roster, and use a bounded structured `deeplineagent` call for
B2B and GTM/RevOps evidence. Persist the three gates and stop with
`manual_review` or `disqualified` before paid people search when appropriate.

- [ ] **Step 4: Implement committee discovery and org inference**

Use the title roster to select exact relevant titles, pass them to
`search_contact` with `page_size: 12`, exclude the signup contact from primary
selection, and persist flat committee and inferred-edge datasets with evidence.

- [ ] **Step 5: Implement bounded role-specific drafting**

Call `deeplineagent` with tools disabled (`maxToolCalls: 0`) and a strict JSON
schema to draft subject/body/value proposition for the bounded committee using
only already-persisted evidence. Persist each result as `draft_only`.

- [ ] **Step 6: Implement safe Lemlist placeholder and Slack delivery**

Always persist a stable `ready_to_create` campaign spec. Only call
`lemlist_create_campaign` when the input explicitly sets
`createPausedLemlistCampaign: true`; never add leads, sequences, schedules, or
send actions. Post the rendered brief to `JAI_SLACK_USER_ID` with a stable tool
receipt and persist delivery metadata.

- [ ] **Step 7: Run source tests and cloud compiler validation**

Run:

```bash
cd eve_agent && npx tsx --test tests/inbound-buying-committee.test.ts
cd .. && deepline plays check eve_agent/agent/skills/inbound-buying-committee/plays/inbound-buying-committee.play.ts
```

- [ ] **Step 8: Run the full local verification suite**

Run: `pytest tests/test_inbound_buying_committee.py tests/test_v2_client.py tests/test_managed_v2_broker.py -q && cd eve_agent && npm test && npm run typecheck`

- [ ] **Step 9: Commit the checked play**

```bash
git add eve_agent/agent/skills/inbound-buying-committee/plays/inbound-buying-committee.play.ts eve_agent/tests/inbound-buying-committee.test.ts
git commit -m "feat: build inbound buying committee play"
```

### Task 5: Documentation, Publication, and Deployment Verification

**Files:**
- Modify: `README.md`
- Modify: `SETUP.md`

**Interfaces:**
- Consumes: checked play and agent endpoint from Tasks 2–4.
- Produces: published live play reference and deployable HubSpot workflow setup instructions.

- [ ] **Step 1: Add failing documentation assertions**

Extend the existing broker/skill tests to require the HubSpot workflow endpoint,
play name, required environment variables, draft-only Lemlist boundary, and
one-account pilot instructions in README/SETUP.

- [ ] **Step 2: Run the documentation assertions and verify failure**

Run: `pytest tests/test_inbound_buying_committee.py -q`

- [ ] **Step 3: Document the exact deployment path**

Document HubSpot contact-created workflow webhook → agent endpoint → published
play, required bearer header, secrets, run observability, and how to leave
Lemlist live creation disabled.

- [ ] **Step 4: Publish the checked play without running paid enrichment**

Run the current CLI publication flow discovered from `deepline plays --help`,
publish the live named play `jai-inbound-buying-committee`, and verify it with
`deepline plays describe jai-inbound-buying-committee --json`. Do not trigger a
provider-backed run yet.

- [ ] **Step 5: Verify repository tests and deployment configuration**

Run the full relevant Python and Eve suites, `deepline plays check`, and the
repository’s non-mutating deployment/configuration checks. Record the play
reference and dashboard URL.

- [ ] **Step 6: Stop at the paid pilot approval gate**

Before the first real HubSpot contact run, present the exact four required
sections: `Assumptions`, `CSV Preview (ASCII)`, `Credits + Scope + Cap`, and
`Approval Question`. The full continuous trigger remains disabled until that
pilot succeeds and the user explicitly approves scale.

- [ ] **Step 7: Commit documentation changes**

```bash
git add README.md SETUP.md tests/test_inbound_buying_committee.py
git commit -m "docs: deploy inbound buying committee workflow"
```

## Final Verification

- [ ] `pytest tests/test_inbound_buying_committee.py tests/test_v2_client.py tests/test_managed_v2_broker.py -q`
- [ ] `cd eve_agent && npm test && npm run typecheck`
- [ ] `deepline plays check eve_agent/agent/skills/inbound-buying-committee/plays/inbound-buying-committee.play.ts`
- [ ] `deepline plays describe jai-inbound-buying-committee --json`
- [ ] Confirm no paid pilot, Slack DM, HubSpot writeback, Lemlist lead enrollment, or outbound send occurred during publication.
