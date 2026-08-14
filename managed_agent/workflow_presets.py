"""Transcript-derived GTM agent workflow presets.

These presets are intentionally simple data structures so they can power docs,
API discovery, UI dropdowns, or future generated examples without creating a
second agent runtime.
"""

from __future__ import annotations

from typing import Any


WORKFLOW_PRESETS: dict[str, dict[str, Any]] = {
    "inbound_lead_approval": {
        "title": "Inbound lead research + rep approval",
        "speaker_pattern": "LangChain / Vishnu Suresh",
        "why": (
            "A lead should not go straight from CRM to outreach. The agent should "
            "research, check reasons not to act, draft with sources, and route to "
            "a rep for approval."
        ),
        "best_for": [
            "high-intent inbound",
            "contact-sales forms",
            "trust-center or compliance leads",
            "rep-approved outbound drafts",
        ],
        "prompt": (
            "Research this inbound lead, decide whether we should act, draft the "
            "next best outreach, and ask for rep approval before sending or CRM "
            "writeback. Show sources, reasons not to act, and missing context."
        ),
        "suggested_tool_bounds": {
            "maxToolCalls": 8,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "lead/account summary",
            "reasons to act",
            "reasons not to act",
            "source-backed draft",
            "approval question",
            "writeback fields after approval",
        ],
        "human_approval_required_for": [
            "sending outreach",
            "sequence enrollment",
            "CRM writeback",
        ],
    },
    "account_digest": {
        "title": "Weekly account intelligence digest",
        "speaker_pattern": "LangChain / Vishnu Suresh",
        "why": (
            "Reps with 80+ accounts need a ranked Monday digest, not another tab. "
            "The agent should combine CRM, product usage, web events, and meeting "
            "signals into the top actions for the week."
        ),
        "best_for": [
            "territory prioritization",
            "post-sales meeting prep",
            "renewal risk review",
            "account owner Q&A",
        ],
        "prompt": (
            "Create a weekly account digest for this territory. Rank accounts by "
            "what changed, source every signal, and return the top 3 actions. "
            "Do not write back without approval."
        ),
        "suggested_tool_bounds": {
            "maxToolCalls": 12,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "ranked accounts",
            "new signals",
            "product/customer context",
            "top 3 recommended actions",
            "missing data",
        ],
        "human_approval_required_for": [
            "task creation",
            "owner reassignment",
            "CRM field updates",
        ],
    },
    "self_serve_support_agent": {
        "title": "Self-serve support and onboarding agent",
        "speaker_pattern": "AssemblyAI / Matt Lawler",
        "why": (
            "Support/onboarding agents need current markdown docs, fast retrieval, "
            "visible progress, escalation rules, and a feedback loop into docs and "
            "product experience."
        ),
        "best_for": [
            "API signup onboarding",
            "docs Q&A",
            "pricing triage",
            "support deflection",
        ],
        "prompt": (
            "Answer this onboarding/support question using current docs and known "
            "policy context. Stream progress, cite the source, and escalate if the "
            "answer touches legal, pricing exceptions, or live pairing."
        ),
        "suggested_tool_bounds": {
            "maxToolCalls": 6,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "direct answer",
            "source docs",
            "code/config example when useful",
            "escalation decision",
            "self-serve gap to improve",
        ],
        "human_approval_required_for": [
            "pricing exceptions",
            "legal terms",
            "account-specific commitments",
        ],
    },
    "web_context_research": {
        "title": "Agent-native web context research",
        "speaker_pattern": "Exa / Scott Langille",
        "why": (
            "Search should return workflow-ready claims, not a pile of links. The "
            "agent needs extracted facts, source URLs, freshness, confidence, and "
            "a recommended next action."
        ),
        "best_for": [
            "account research",
            "market mapping",
            "entity verification",
            "web-native prospecting",
        ],
        "prompt": (
            "Research this account from web sources. Return source-backed claims, "
            "freshness, relevance to GTM, confidence, missing context, and the next "
            "safe workflow. Do not enrich contacts or write to CRM."
        ),
        "suggested_tool_bounds": {
            "enabledToolIds": ["deeplineagent", "firecrawl_search", "exa_search"],
            "maxToolCalls": 6,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "source-backed claims",
            "source URLs",
            "freshness",
            "GTM relevance",
            "confidence",
            "next workflow",
        ],
        "human_approval_required_for": [
            "enrichment",
            "CRM writeback",
            "outreach",
        ],
    },
    "account_brief": {
        "title": "Rep-ready account brief",
        "speaker_pattern": "Prove / account brief workflow",
        "why": (
            "Reps need a short account point of view before a call or outbound "
            "touch. The agent should gather company context, buyer context, "
            "current signals, likely pain, and a first-message angle without "
            "turning the brief into raw research notes."
        ),
        "best_for": [
            "pre-call prep",
            "target account research",
            "inbound follow-up",
            "rep-facing Slack brief",
        ],
        "prompt": (
            "Create a rep-ready account brief for this company and buyer. Include "
            "company snapshot, GTM motion, current signals, suspected pain, "
            "Deepline angle, first-message angle, open questions, sources, and "
            "proof status. Keep it concise and do not write back without approval."
        ),
        "suggested_tool_bounds": {
            "enabledToolIds": ["deeplineagent", "firecrawl_search", "exa_search"],
            "maxToolCalls": 8,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "company snapshot",
            "buyer or persona context",
            "current signals",
            "suspected pain",
            "first-message angle",
            "open questions",
            "sources and proof status",
        ],
        "human_approval_required_for": [
            "CRM writeback",
            "outreach send",
            "sequence enrollment",
        ],
    },
    "signal_stacking": {
        "title": "Signal stacking and ICP scoring",
        "speaker_pattern": "Prove / signal stacking workflow",
        "why": (
            "A single weak signal is noisy. The agent should combine public web, "
            "hiring, compliance, product, vendor, CRM, and warehouse signals into "
            "an explainable score with positive signals, anti-fit signals, and "
            "missing evidence."
        ),
        "best_for": [
            "ICP scoring",
            "territory prioritization",
            "trigger-based outbound",
            "account list ranking",
        ],
        "prompt": (
            "Score these accounts using signal stacking. Separate core fit, buying "
            "intent, and infrastructure readiness. Include source-backed positive "
            "signals, anti-fit signals, missing evidence, score rationale, and the "
            "next safe workflow. Do not enrich contacts or write to CRM without "
            "approval."
        ),
        "suggested_tool_bounds": {
            "enabledToolIds": [
                "deeplineagent",
                "firecrawl_search",
                "exa_search",
                "snowflake_query",
                "snowflake_execute_query",
            ],
            "maxToolCalls": 10,
            "read_only": True,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "account score",
            "core fit signals",
            "buying intent signals",
            "infrastructure readiness signals",
            "anti-fit signals",
            "source URLs or source tables",
            "recommended next workflow",
        ],
        "human_approval_required_for": [
            "contact enrichment",
            "CRM writeback",
            "outreach send",
            "sensitive row export",
        ],
    },
    "org_chart_building": {
        "title": "Org chart and buying committee builder",
        "speaker_pattern": "Prove / org chart workflow",
        "why": (
            "Enterprise reps need a stakeholder map, not a flat people list. The "
            "agent should discover likely buyers, influencers, blockers, and "
            "operators, mark inferred relationships, and preserve run IDs and "
            "source evidence."
        ),
        "best_for": [
            "account mapping",
            "buying committee discovery",
            "multi-threading plans",
            "Notion org chart output",
        ],
        "prompt": (
            "Build an org chart and buying committee map for this account. Choose "
            "company-wide or person-centric mode, run a small discovery pass first, "
            "classify likely buyer roles, mark inferred relationships, include "
            "source evidence and Deepline run IDs, and ask before email enrichment "
            "or Notion/CRM writes."
        ),
        "suggested_tool_bounds": {
            "enabledToolIds": ["deeplineagent"],
            "maxToolCalls": 8,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "target account and mode",
            "stakeholder table",
            "buyer role classification",
            "relationship confidence",
            "source evidence",
            "Deepline run IDs",
            "write or enrichment approval question",
        ],
        "human_approval_required_for": [
            "work-email enrichment",
            "Notion write",
            "CRM writeback",
            "outreach send",
        ],
    },
    "bounded_tool_action": {
        "title": "Scoped tool/action workflow",
        "speaker_pattern": "Composio / Sujay Choubey",
        "why": (
            "The useful part of tool access is not the number of integrations. It "
            "is discovery, auth, scopes, execution boundaries, audit trails, and "
            "revocation."
        ),
        "best_for": [
            "agent tool selection",
            "CRM/Gmail/Slack action flows",
            "permission-sensitive workflows",
            "MCP-style action surfaces",
        ],
        "prompt": (
            "Before using any tool, state the tool, why it is needed, whether it "
            "creates a side effect, and whether approval is required. Use the "
            "minimum tool set and return an audit trail."
        ),
        "suggested_tool_bounds": {
            "maxToolCalls": 5,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "selected tool",
            "reason for tool choice",
            "auth/scope assumption",
            "side-effect risk",
            "audit trail",
            "next safe step",
        ],
        "human_approval_required_for": [
            "external sends",
            "record creation",
            "record mutation",
            "sequence enrollment",
        ],
    },
    "closed_loop_gtm_workflow": {
        "title": "Closed-loop GTM workflow",
        "speaker_pattern": "Deepline / Jai Toor",
        "why": (
            "The useful loop is context, action, insight. Combine first-party and "
            "third-party context, take an approved action, then store what happened "
            "so the next run improves."
        ),
        "best_for": [
            "lead magnet personalization",
            "event follow-up",
            "provider waterfall testing",
            "Claude Code / Slack GTM workflows",
        ],
        "prompt": (
            "Combine first-party and third-party context, recommend the next GTM "
            "action, ask for approval, and after approval write back the result and "
            "the learning signal. Report provider misses and marginal cost signals."
        ),
        "suggested_tool_bounds": {
            "maxToolCalls": 10,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "first-party context",
            "third-party context",
            "recommended action",
            "approval question",
            "writeback result",
            "learning signal",
            "provider/cost notes",
        ],
        "human_approval_required_for": [
            "spend escalation",
            "CRM writeback",
            "outreach send",
        ],
    },
    "snowflake_query_agent": {
        "title": "Snowflake query agent",
        "speaker_pattern": "LangChain / Vishnu Suresh + Deepline / Jai Toor",
        "why": (
            "Transcript-derived GTM agents worked better when trusted business "
            "context landed in a warehouse and the agent could answer qualitative "
            "questions with SQL-like access. This preset keeps that power read-only, "
            "scoped, and explainable."
        ),
        "best_for": [
            "account intelligence from warehouse tables",
            "product usage and activation questions",
            "renewal or churn risk investigation",
            "territory and pipeline analysis",
            "meeting-transcript signal lookup",
        ],
        "prompt": (
            "Answer this GTM question using Snowflake/warehouse context. First "
            "identify the likely tables and fields, then propose the SQL before "
            "running it. Use read-only SELECT queries only. Limit exploratory "
            "queries, explain joins and filters, return the result with source "
            "tables, and ask for approval before any writeback or downstream action."
        ),
        "suggested_tool_bounds": {
            "enabledToolIds": [
                "deeplineagent",
                "snowflake_query",
                "snowflake_execute_query",
            ],
            "maxToolCalls": 8,
            "read_only": True,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "interpreted business question",
            "tables/fields used",
            "proposed SQL",
            "query result summary",
            "source table notes",
            "caveats or missing fields",
            "recommended next action",
            "approval question before CRM/outreach writeback",
        ],
        "human_approval_required_for": [
            "non-SELECT queries",
            "CRM writeback",
            "outreach or task creation",
            "exporting sensitive row-level data",
        ],
    },
}


def list_workflow_presets() -> list[dict[str, Any]]:
    """Return compact preset metadata for discovery UIs."""
    return [
        {
            "id": preset_id,
            "title": preset["title"],
            "speaker_pattern": preset["speaker_pattern"],
            "best_for": preset["best_for"],
        }
        for preset_id, preset in WORKFLOW_PRESETS.items()
    ]


def get_workflow_preset(preset_id: str) -> dict[str, Any] | None:
    """Return one workflow preset with its id included."""
    preset = WORKFLOW_PRESETS.get(preset_id)
    if not preset:
        return None
    return {"id": preset_id, **preset}
