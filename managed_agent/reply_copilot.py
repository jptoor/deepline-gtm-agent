"""Lemlist reply copilot: Deepline context, Slack approval, and writeback.

The durable source of truth is Deepline Customer DB. This module only owns the
rep-facing Slack gate and the thin frontend orchestration around Deepline APIs.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from pydantic import BaseModel, Field

from deepline_gtm_agent.v2_client import DeeplineV2Client, extract_text_from_stream_chunk
from managed_agent.config import live_writes_enabled


router = APIRouter(prefix="/reply-copilot", tags=["reply-copilot"])

BOOKING_URL_DEFAULT = "https://calendly.com/d/csdb-85z-t6z/deepline-meeting"
CLASSIFICATIONS = {"positive", "question", "objection", "not_interested", "out_of_office"}


class ReplyEvent(BaseModel):
    delivery_id: str
    event_type: str = "emailsReplied"
    activity_id: str | None = None
    created_at: str | None = None
    campaign_id: str | None = None
    campaign_name: str | None = None
    lead_id: str | None = None
    contact_id: str | None = None
    lead_email: str | None = None
    lead_first_name: str | None = None
    lead_last_name: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    send_user_id: str | None = None
    send_user_email: str | None = None
    send_user_mailbox_id: str | None = None
    subject: str | None = None
    reply_subject: str | None = None
    reply_text: str | None = None
    raw_event: dict[str, Any]


class DraftResult(BaseModel):
    classification: Literal[
        "positive", "question", "objection", "not_interested", "out_of_office"
    ]
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"
    contextual_analysis: str
    missing_context: list[str] = Field(default_factory=list)
    company_headcount: int | None = None
    recommended_route: Literal["meeting", "plg", "manual"] = "manual"
    draft: str


MIGRATION_SQL = (
    "CREATE SCHEMA IF NOT EXISTS jai_reply_copilot",
    """CREATE TABLE IF NOT EXISTS jai_reply_copilot.reply_events (
        delivery_id text PRIMARY KEY,
        contact_id text,
        lead_id text,
        lead_email text,
        company_name text,
        company_domain text,
        inbound_text text,
        received_at timestamptz,
        raw_event jsonb NOT NULL,
        status text NOT NULL DEFAULT 'received',
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS jai_reply_copilot.drafts (
        delivery_id text PRIMARY KEY REFERENCES jai_reply_copilot.reply_events(delivery_id),
        classification text NOT NULL,
        confidence text NOT NULL,
        contextual_analysis text NOT NULL,
        missing_context jsonb NOT NULL DEFAULT '[]'::jsonb,
        company_headcount integer,
        recommended_route text NOT NULL,
        draft_text text NOT NULL,
        booking_url text,
        promo_url text,
        slack_channel_id text,
        slack_message_ts text,
        status text NOT NULL DEFAULT 'pending_approval',
        model text,
        provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS jai_reply_copilot.draft_revisions (
        delivery_id text NOT NULL REFERENCES jai_reply_copilot.drafts(delivery_id),
        revision_number integer NOT NULL,
        previous_text text,
        revised_text text NOT NULL,
        edited_by text,
        edit_source text NOT NULL DEFAULT 'slack_modal',
        edited_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (delivery_id, revision_number)
    )""",
    """CREATE TABLE IF NOT EXISTS jai_reply_copilot.send_log (
        delivery_id text PRIMARY KEY REFERENCES jai_reply_copilot.drafts(delivery_id),
        final_text text NOT NULL,
        approved_by text,
        lemlist_result jsonb,
        hubspot_result jsonb,
        sent_at timestamptz,
        crm_logged_at timestamptz,
        status text NOT NULL,
        error_text text
    )""",
)


def normalize_monitor_row(row: dict[str, Any]) -> ReplyEvent:
    """Normalize the declared lemlist.campaign_events stream row."""
    delivery_id = str(row.get("delivery_id") or "").strip()
    if not delivery_id:
        raise ValueError("delivery_id is required")
    event_type = str(row.get("event_type") or "emailsReplied")
    if event_type != "emailsReplied":
        raise ValueError(f"unsupported event_type: {event_type}")
    reply_text = row.get("reply_text") or row.get("message_text") or row.get("message_preview")
    return ReplyEvent(
        delivery_id=delivery_id,
        event_type=event_type,
        activity_id=_string(row.get("activity_id")),
        created_at=_string(row.get("created_at")),
        campaign_id=_string(row.get("campaign_id")),
        campaign_name=_string(row.get("campaign_name")),
        lead_id=_string(row.get("lead_id")),
        contact_id=_string(row.get("contact_id")),
        lead_email=_string(row.get("lead_email")),
        lead_first_name=_string(row.get("lead_first_name") or row.get("lead_custom_first_name")),
        lead_last_name=_string(row.get("lead_last_name") or row.get("lead_custom_last_name")),
        company_name=_string(row.get("company_name") or row.get("lead_company_name")),
        company_domain=_string(row.get("company_domain")),
        send_user_id=_string(row.get("send_user_id")),
        send_user_email=_string(row.get("send_user_email")),
        send_user_mailbox_id=_string(row.get("send_user_mailbox_id")),
        subject=_string(row.get("subject")),
        reply_subject=_string(row.get("reply_subject")),
        reply_text=_string(reply_text),
        raw_event=row,
    )


def choose_route(headcount: int | None) -> Literal["meeting", "plg", "manual"]:
    """User rule: over 50 gets a meeting; 50 or fewer gets PLG."""
    if headcount is None or headcount < 0:
        return "manual"
    return "meeting" if headcount > 50 else "plg"


def extract_headcount(value: Any) -> int | None:
    """Find a mechanical headcount field without treating ranges as exact."""
    preferred = {
        "employee_count",
        "employees_count",
        "number_of_employees",
        "headcount",
        "company_headcount",
        "staff_count",
    }
    pending = [value]
    seen: set[int] = set()
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if id(item) in seen:
                continue
            seen.add(id(item))
            for key, nested in item.items():
                if key.lower() in preferred:
                    parsed = _positive_int(nested)
                    if parsed is not None:
                        return parsed
                pending.append(nested)
        elif isinstance(item, list):
            pending.extend(item)
    return None


def build_draft_prompt(
    event: ReplyEvent,
    thread: Any,
    customer_history: list[dict[str, Any]],
    company_context: Any,
    headcount: int | None,
) -> str:
    route = choose_route(headcount)
    booking_url = os.environ.get("REPLY_COPILOT_BOOKING_URL", BOOKING_URL_DEFAULT)
    promo_url = os.environ.get("REPLY_COPILOT_PROMO_URL", "")
    return f"""You draft replies for Jai, founder of Deepline.

Classify before drafting. Allowed classifications: positive, question, objection,
not_interested, out_of_office. Analyze the complete interaction history and name
what is missing. Never invent a fact.

Routing is deterministic and must not be changed:
- Verified company headcount: {headcount!r}
- Route: {route}
- If route=meeting, the only allowed CTA link is {booking_url}
- If route=plg, the only allowed promo link is {promo_url or '[NOT CONFIGURED: omit link and flag missing context]'}
- If route=manual, do not add a link.

Voice:
- practitioner sharing field notes with a smart colleague
- short sentences, one idea per paragraph, lowercase energy is fine
- specific, helpful, humble; one CTA at most; usually under 75 words
- useful phrases include "curious if...", "quick question", "if not, no stress"
- no em dashes, fake personalization, generic SaaS gloss, or unsupported claims
- avoid: landscape, vibrant, pivotal, crucial, moreover, additionally,
  game-changer, revolutionary, unlock, transform, data platform,
  orchestration layer, semantic layer

Return strict JSON with exactly these keys:
classification, confidence (HIGH|MEDIUM|LOW), contextual_analysis,
missing_context (string array), company_headcount (integer or null),
recommended_route (meeting|plg|manual), draft.

Inbound event:
{json.dumps(event.model_dump(exclude={"raw_event"}), ensure_ascii=False)}

Full Lemlist thread:
{json.dumps(thread, ensure_ascii=False, default=str)}

Prior Customer DB interactions and rep edits:
{json.dumps(customer_history, ensure_ascii=False, default=str)}

Firmographic context:
{json.dumps(company_context, ensure_ascii=False, default=str)}
"""


def slack_gate_blocks(event: ReplyEvent, draft: DraftResult) -> list[dict[str, Any]]:
    route_label = {"meeting": "Book a meeting", "plg": "Send to PLG", "manual": "Manual review"}[
        draft.recommended_route
    ]
    name = " ".join(filter(None, [event.lead_first_name, event.lead_last_name])) or event.lead_email or "Unknown contact"
    context = draft.contextual_analysis[:1200]
    missing = ", ".join(draft.missing_context) if draft.missing_context else "none"
    return [
        {"type": "header", "text": {"type": "plain_text", "text": f"Reply draft: {name}"[:150]}},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Class*\n{draft.classification}"},
                {"type": "mrkdwn", "text": f"*Route*\n{route_label}"},
                {"type": "mrkdwn", "text": f"*Headcount*\n{draft.company_headcount if draft.company_headcount is not None else 'unknown'}"},
                {"type": "mrkdwn", "text": f"*Missing*\n{missing[:250]}"},
            ],
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Why*\n{context}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Draft*\n{draft.draft[:2800]}"}},
        {
            "type": "actions",
            "block_id": f"reply_gate:{event.delivery_id}",
            "elements": [
                {"type": "button", "action_id": "reply_approve", "text": {"type": "plain_text", "text": "Approve"}, "style": "primary", "value": event.delivery_id},
                {"type": "button", "action_id": "reply_edit", "text": {"type": "plain_text", "text": "Edit"}, "value": event.delivery_id},
                {"type": "button", "action_id": "reply_reject", "text": {"type": "plain_text", "text": "Reject"}, "style": "danger", "value": event.delivery_id},
            ],
        },
    ]


class ReplyCopilotService:
    def __init__(self, client: DeeplineV2Client | None = None):
        self.client = client or DeeplineV2Client()
        self.slack_token = os.environ.get("SLACK_BOT_TOKEN", "")
        self.slack_channel = os.environ.get("REPLY_COPILOT_SLACK_CHANNEL_ID", "")

    async def migrate(self) -> None:
        for statement in MIGRATION_SQL:
            await self._query(statement)

    async def process(self, event: ReplyEvent) -> None:
        await self.migrate()
        await self._store_event(event)
        if await self._draft_row(event.delivery_id):
            return
        thread = await self._read_or_missing("lemlist_thread", lambda: self._thread(event))
        history_value = await self._read_or_missing("customer_history", lambda: self._history(event))
        history = history_value if isinstance(history_value, list) else [history_value]
        company = await self._read_or_missing("company_context", lambda: self._company(event))
        headcount = extract_headcount(company)
        prompt = build_draft_prompt(event, thread, history, company, headcount)
        draft = await self._draft(prompt)
        draft.company_headcount = headcount
        draft.recommended_route = choose_route(headcount)
        if draft.recommended_route == "plg" and not os.environ.get("REPLY_COPILOT_PROMO_URL"):
            if "promo URL is not configured" not in draft.missing_context:
                draft.missing_context.append("promo URL is not configured")
            draft.draft = _strip_unapproved_links(draft.draft)
        await self._store_draft(event, draft, company)
        await self._post_gate(event, draft)

    async def approve(self, delivery_id: str, user_id: str) -> None:
        row = await self._draft_row(delivery_id)
        if not row:
            raise ValueError("draft not found")
        if not live_writes_enabled():
            await self._query(
                f"UPDATE jai_reply_copilot.drafts SET status='approved_pending_live_writes', updated_at=now() WHERE delivery_id={_sql(delivery_id)}"
            )
            await self._update_gate(row, "Approved. Live writes are disabled, so nothing was sent.")
            return

        required = ("send_user_id", "send_user_email", "send_user_mailbox_id", "contact_id", "lead_id")
        missing = [key for key in required if not row.get(key)]
        if missing:
            raise ValueError(f"cannot send; missing {', '.join(missing)}")
        claimed = await self._query(
            "UPDATE jai_reply_copilot.drafts SET status='sending', updated_at=now() "
            f"WHERE delivery_id={_sql(delivery_id)} AND status IN ('pending_approval','edited','approved_pending_live_writes') "
            "RETURNING delivery_id"
        )
        if not claimed:
            return
        subject = row.get("reply_subject") or row.get("subject") or "Re: your note"
        try:
            send_result = await self.client.execute_tool(
                "lemlist_send_email",
                {
                    "send_user_id": row["send_user_id"],
                    "send_user_email": row["send_user_email"],
                    "send_user_mailbox_id": row["send_user_mailbox_id"],
                    "contact_id": row["contact_id"],
                    "lead_id": row["lead_id"],
                    "subject": subject,
                    "message": _text_to_html(row["draft_text"]),
                },
            )
            hubspot_result = await self._log_hubspot(row, subject)
        except Exception as exc:
            await self._query(
                f"UPDATE jai_reply_copilot.drafts SET status='send_failed', updated_at=now() WHERE delivery_id={_sql(delivery_id)}"
            )
            raise RuntimeError(f"reply send failed: {type(exc).__name__}") from exc
        crm_logged = not (isinstance(hubspot_result, dict) and hubspot_result.get("skipped"))
        await self._query(
            "INSERT INTO jai_reply_copilot.send_log "
            "(delivery_id,final_text,approved_by,lemlist_result,hubspot_result,sent_at,crm_logged_at,status) VALUES "
            f"({_sql(delivery_id)},{_sql(row['draft_text'])},{_sql(user_id)},{_json_sql(send_result)},{_json_sql(hubspot_result)},now(),"
            f"{'now()' if crm_logged else 'NULL'},'sent') ON CONFLICT (delivery_id) DO NOTHING"
        )
        await self._query(
            f"UPDATE jai_reply_copilot.drafts SET status='sent', updated_at=now() WHERE delivery_id={_sql(delivery_id)}"
        )
        note = "Sent through Lemlist and logged to HubSpot." if crm_logged else "Sent through Lemlist. HubSpot logging needs follow-up."
        await self._update_gate(row, note)

    async def reject(self, delivery_id: str, user_id: str) -> None:
        row = await self._draft_row(delivery_id)
        await self._query(
            f"UPDATE jai_reply_copilot.drafts SET status='rejected', updated_at=now(), provenance=provenance || {_json_sql({'rejected_by': user_id})} WHERE delivery_id={_sql(delivery_id)}"
        )
        if row:
            await self._update_gate(row, "Rejected. Nothing was sent.")

    async def open_edit_modal(self, trigger_id: str, delivery_id: str) -> None:
        row = await self._draft_row(delivery_id)
        if not row:
            raise ValueError("draft not found")
        await self._slack(
            "views.open",
            {
                "trigger_id": trigger_id,
                "view": {
                    "type": "modal",
                    "callback_id": "reply_edit_submit",
                    "private_metadata": delivery_id,
                    "title": {"type": "plain_text", "text": "Edit reply"},
                    "submit": {"type": "plain_text", "text": "Save draft"},
                    "close": {"type": "plain_text", "text": "Cancel"},
                    "blocks": [
                        {
                            "type": "input",
                            "block_id": "draft_text",
                            "label": {"type": "plain_text", "text": "Reply"},
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "value",
                                "multiline": True,
                                "initial_value": row["draft_text"][:3000],
                            },
                        }
                    ],
                },
            },
        )

    async def save_edit(self, delivery_id: str, text: str, user_id: str) -> None:
        text = text.strip()
        if not text:
            raise ValueError("draft cannot be empty")
        row = await self._draft_row(delivery_id)
        if not row:
            raise ValueError("draft not found")
        await self._query(
            "WITH next_revision AS (SELECT COALESCE(MAX(revision_number),0)+1 AS n "
            f"FROM jai_reply_copilot.draft_revisions WHERE delivery_id={_sql(delivery_id)}) "
            "INSERT INTO jai_reply_copilot.draft_revisions "
            "(delivery_id,revision_number,previous_text,revised_text,edited_by) SELECT "
            f"{_sql(delivery_id)},n,{_sql(row['draft_text'])},{_sql(text)},{_sql(user_id)} FROM next_revision"
        )
        await self._query(
            f"UPDATE jai_reply_copilot.drafts SET draft_text={_sql(text)}, status='edited', updated_at=now() WHERE delivery_id={_sql(delivery_id)}"
        )
        row["draft_text"] = text
        await self._update_gate(row, "Draft updated in Slack and saved to Customer DB.", keep_actions=True)

    async def _query(self, sql: str) -> list[dict[str, Any]]:
        result = await self.client.execute_tool("query_customer_db", {"sql": sql, "max_rows": 100})
        raw = _raw(result)
        rows = raw.get("rows", []) if isinstance(raw, dict) else []
        return rows if isinstance(rows, list) else []

    async def _read_or_missing(
        self,
        label: str,
        read: Callable[[], Awaitable[Any]],
    ) -> Any:
        try:
            return await read()
        except Exception as exc:
            return {"missing": label, "error_type": type(exc).__name__}

    async def _store_event(self, event: ReplyEvent) -> None:
        await self._query(
            "INSERT INTO jai_reply_copilot.reply_events "
            "(delivery_id,contact_id,lead_id,lead_email,company_name,company_domain,inbound_text,received_at,raw_event) VALUES "
            f"({_sql(event.delivery_id)},{_sql(event.contact_id)},{_sql(event.lead_id)},{_sql(event.lead_email)},"
            f"{_sql(event.company_name)},{_sql(event.company_domain)},{_sql(event.reply_text)},"
            f"COALESCE({_sql(event.created_at)}::timestamptz,now()),{_json_sql(event.raw_event)}) "
            "ON CONFLICT (delivery_id) DO UPDATE SET raw_event=EXCLUDED.raw_event, inbound_text=EXCLUDED.inbound_text, updated_at=now()"
        )

    async def _thread(self, event: ReplyEvent) -> Any:
        if not event.contact_id:
            return {"missing": "contact_id"}
        result = await self.client.execute_tool(
            "lemlist_get_inbox_thread",
            {"contact_id": event.contact_id, "user_id": event.send_user_id, "limit": 100},
        )
        return _raw(result)

    async def _history(self, event: ReplyEvent) -> list[dict[str, Any]]:
        predicates = [f"contact_id={_sql(event.contact_id)}"] if event.contact_id else []
        if event.lead_email:
            predicates.append(f"lead_email={_sql(event.lead_email)}")
        where = " OR ".join(predicates) or "false"
        return await self._query(
            "SELECT source,occurred_at,event_type,body,actor FROM ("
            "SELECT 'lemlist'::text AS source,created_at AS occurred_at,event_type,"
            "COALESCE(reply_text,message_text,message_preview) AS body,send_user_email AS actor "
            f"FROM lemlist.lemlist_campaign_events WHERE {where} "
            "UNION ALL SELECT 'rep_edit',edited_at,'draft_edited',revised_text,edited_by "
            "FROM jai_reply_copilot.draft_revisions WHERE delivery_id IN "
            f"(SELECT delivery_id FROM jai_reply_copilot.reply_events WHERE {where}) "
            "UNION ALL SELECT 'copilot_send',sent_at,'sent',final_text,approved_by "
            "FROM jai_reply_copilot.send_log WHERE delivery_id IN "
            f"(SELECT delivery_id FROM jai_reply_copilot.reply_events WHERE {where})"
            ") history ORDER BY occurred_at DESC NULLS LAST LIMIT 100"
        )

    async def _company(self, event: ReplyEvent) -> Any:
        if not event.company_domain and not event.company_name:
            return {"missing": "company domain and name"}
        payload: dict[str, Any] = {}
        if event.company_domain:
            payload["company_website"] = event.company_domain
        if event.company_name:
            payload["company_name"] = event.company_name
        result = await self.client.execute_tool("prospeo_enrich_company", payload)
        return _raw(result)

    async def _draft(self, prompt: str) -> DraftResult:
        payload = {
            "prompt": prompt,
            "messages": [{"role": "user", "content": prompt}],
            "response_mode": "stream",
            "enabledToolIds": ["serper_google_search", "exa_search", "firecrawl_scrape"],
            "maxToolCalls": 4,
            "model": os.environ.get("REPLY_COPILOT_MODEL", "openai/gpt-5.4-mini"),
        }
        parts: list[str] = []
        async for chunk in self.client.stream_agent(payload):
            parts.append(extract_text_from_stream_chunk(chunk))
        data = _extract_json("".join(parts))
        if data.get("classification") not in CLASSIFICATIONS:
            raise ValueError("agent returned an unsupported classification")
        return DraftResult.model_validate(data)

    async def _store_draft(self, event: ReplyEvent, draft: DraftResult, company: Any) -> None:
        model = os.environ.get("REPLY_COPILOT_MODEL", "openai/gpt-5.4-mini")
        await self._query(
            "INSERT INTO jai_reply_copilot.drafts "
            "(delivery_id,classification,confidence,contextual_analysis,missing_context,company_headcount,recommended_route,draft_text,booking_url,promo_url,model,provenance) VALUES "
            f"({_sql(event.delivery_id)},{_sql(draft.classification)},{_sql(draft.confidence)},{_sql(draft.contextual_analysis)},"
            f"{_json_sql(draft.missing_context)},{draft.company_headcount if draft.company_headcount is not None else 'NULL'},"
            f"{_sql(draft.recommended_route)},{_sql(draft.draft)},{_sql(os.environ.get('REPLY_COPILOT_BOOKING_URL', BOOKING_URL_DEFAULT))},"
            f"{_sql(os.environ.get('REPLY_COPILOT_PROMO_URL'))},{_sql(model)},{_json_sql({'company_tool': 'prospeo_enrich_company', 'company_context': company})}) "
            "ON CONFLICT (delivery_id) DO NOTHING"
        )

    async def _post_gate(self, event: ReplyEvent, draft: DraftResult) -> None:
        if not self.slack_channel:
            raise RuntimeError("REPLY_COPILOT_SLACK_CHANNEL_ID is required")
        result = await self._slack(
            "chat.postMessage",
            {
                "channel": self.slack_channel,
                "text": f"Reply draft for {event.lead_email or event.delivery_id}",
                "blocks": slack_gate_blocks(event, draft),
            },
        )
        await self._query(
            f"UPDATE jai_reply_copilot.drafts SET slack_channel_id={_sql(result.get('channel'))}, slack_message_ts={_sql(result.get('ts'))}, updated_at=now() WHERE delivery_id={_sql(event.delivery_id)}"
        )

    async def _draft_row(self, delivery_id: str) -> dict[str, Any] | None:
        rows = await self._query(
            "SELECT d.*,e.contact_id,e.lead_id,e.lead_email,e.company_name,e.company_domain,e.raw_event->>'send_user_id' AS send_user_id,"
            "e.raw_event->>'send_user_email' AS send_user_email,e.raw_event->>'send_user_mailbox_id' AS send_user_mailbox_id,"
            "e.raw_event->>'subject' AS subject,e.raw_event->>'reply_subject' AS reply_subject "
            "FROM jai_reply_copilot.drafts d JOIN jai_reply_copilot.reply_events e USING (delivery_id) "
            f"WHERE d.delivery_id={_sql(delivery_id)} LIMIT 1"
        )
        return rows[0] if rows else None

    async def _update_gate(self, row: dict[str, Any], note: str, keep_actions: bool = False) -> None:
        blocks: list[dict[str, Any]] = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{note}*"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Final draft*\n{row['draft_text'][:2800]}"}},
        ]
        if keep_actions:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {"type": "button", "action_id": "reply_approve", "text": {"type": "plain_text", "text": "Approve"}, "style": "primary", "value": row["delivery_id"]},
                        {"type": "button", "action_id": "reply_edit", "text": {"type": "plain_text", "text": "Edit again"}, "value": row["delivery_id"]},
                        {"type": "button", "action_id": "reply_reject", "text": {"type": "plain_text", "text": "Reject"}, "style": "danger", "value": row["delivery_id"]},
                    ],
                }
            )
        await self._slack(
            "chat.update",
            {"channel": row["slack_channel_id"], "ts": row["slack_message_ts"], "text": note, "blocks": blocks},
        )

    async def _log_hubspot(self, row: dict[str, Any], subject: str) -> Any:
        if not row.get("lead_email"):
            return {"skipped": "missing lead_email"}
        search = await self.client.execute_tool(
            "hubspot_search_objects",
            {
                "object_type": "contacts",
                "properties": ["email", "firstname", "lastname"],
                "limit": 1,
                "filter_groups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": row["lead_email"]}]}],
            },
        )
        raw = _raw(search)
        results = raw.get("results", []) if isinstance(raw, dict) else []
        contact_id = str(results[0].get("id")) if results else ""
        if not contact_id:
            return {"skipped": "HubSpot contact not found"}
        return await self.client.execute_tool(
            "hubspot_log_email",
            {
                "id": contact_id,
                "time_stamp": datetime.now(timezone.utc).isoformat(),
                "subject": subject,
                "text": row["draft_text"],
                "html": _text_to_html(row["draft_text"]),
                "direction": "EMAIL",
                "status": "SENT",
            },
        )

    async def _slack(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.slack_token:
            raise RuntimeError("SLACK_BOT_TOKEN is required")
        import httpx

        async with httpx.AsyncClient(timeout=10) as http:
            response = await http.post(
                f"https://slack.com/api/{endpoint}",
                headers={"Authorization": f"Bearer {self.slack_token}"},
                json=payload,
            )
        data = response.json()
        if response.status_code >= 400 or not data.get("ok"):
            raise RuntimeError(f"Slack {endpoint} failed: {data.get('error', response.status_code)}")
        return data


def _webhook_authorized(request: Request) -> bool:
    secret = os.environ.get("REPLY_COPILOT_WEBHOOK_SECRET", "")
    provided = request.headers.get("Authorization", "").removeprefix("Bearer ")
    return bool(secret and provided and hmac.compare_digest(secret, provided))


def _slack_authorized(body: bytes, request: Request) -> bool:
    secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not secret or not timestamp or not signature:
        return False
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except ValueError:
        return False
    expected = "v0=" + hmac.new(secret.encode(), b"v0:" + timestamp.encode() + b":" + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/events", status_code=202)
async def receive_reply_event(request: Request, background_tasks: BackgroundTasks):
    if not _webhook_authorized(request):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    payload = await request.json()
    try:
        event = normalize_monitor_row(payload.get("row", payload))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(ReplyCopilotService().process, event)
    return {"accepted": True, "delivery_id": event.delivery_id}


@router.post("/slack/interactions")
async def slack_interactions(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    if not _slack_authorized(body, request):
        return Response(status_code=403)
    from urllib.parse import parse_qs

    raw_payload = parse_qs(body.decode()).get("payload", ["{}"])[0]
    payload = json.loads(raw_payload)
    service = ReplyCopilotService()
    if payload.get("type") == "view_submission" and payload.get("view", {}).get("callback_id") == "reply_edit_submit":
        delivery_id = payload["view"].get("private_metadata", "")
        text = payload["view"]["state"]["values"]["draft_text"]["value"].get("value", "")
        background_tasks.add_task(service.save_edit, delivery_id, text, payload.get("user", {}).get("id", ""))
        return Response(status_code=200)
    actions = payload.get("actions") or []
    if not actions:
        return Response(status_code=200)
    action = actions[0]
    delivery_id = action.get("value", "")
    user_id = payload.get("user", {}).get("id", "")
    if action.get("action_id") == "reply_edit":
        await service.open_edit_modal(payload.get("trigger_id", ""), delivery_id)
    elif action.get("action_id") == "reply_approve":
        background_tasks.add_task(service.approve, delivery_id, user_id)
    elif action.get("action_id") == "reply_reject":
        background_tasks.add_task(service.reject, delivery_id, user_id)
    return Response(status_code=200)


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and value >= 0 and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"[\d,]+", value.strip()):
        return int(value.replace(",", ""))
    return None


def _raw(result: Any) -> Any:
    if isinstance(result, dict):
        response = result.get("toolResponse")
        if isinstance(response, dict) and "raw" in response:
            return response["raw"]
    return result


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("agent returned no JSON object")
    value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("agent JSON must be an object")
    return value


def _sql(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def _json_sql(value: Any) -> str:
    return _sql(json.dumps(value, ensure_ascii=False, default=str)) + "::jsonb"


def _text_to_html(text: str) -> str:
    return "".join(f"<p>{html.escape(part)}</p>" for part in re.split(r"\n\s*\n", text.strip()) if part)


def _strip_unapproved_links(text: str) -> str:
    return re.sub(r"\s*https?://\S+", "", text).strip()
