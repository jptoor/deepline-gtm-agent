"""FastAPI broker for Deepline GTM native v2 chat.

The broker keeps transport concerns here: REST, web chat, Slack verification,
Slack formatting, and optional bearer auth. Deepline owns the agent runtime,
tool execution, provider credentials, billing, and streaming contract.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import logging
import os
import re
import sys
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent))
from deepline_gtm_agent.formatting import md_to_slack, truncate_for_slack
from deepline_gtm_agent.v2_client import DeeplineV2Client, extract_text_from_stream_chunk
from managed_agent.config import config_summary, deepline_host
from managed_agent.workflow_presets import get_workflow_preset, list_workflow_presets
from managed_agent.reply_copilot import router as reply_copilot_router

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

UVICORN_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(message)s",
            "use_colors": None,
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
    },
}

_bearer = HTTPBearer(auto_error=False)
MAX_SLACK_BODY_BYTES = int(os.environ.get("MAX_SLACK_BODY_BYTES", "1048576"))
DEFAULT_MAX_TOOL_CALLS = int(os.environ.get("DEFAULT_MAX_TOOL_CALLS", "6"))
MAX_TOOL_CALLS_LIMIT = int(os.environ.get("MAX_TOOL_CALLS_LIMIT", "12"))
DEFAULT_CHAT_TOOL_IDS = [
    tool_id.strip()
    for tool_id in os.environ.get(
        "DEFAULT_CHAT_TOOL_IDS",
        (
            "deeplineagent,serper_google_search,exa_search,firecrawl_scrape,"
            "discolike_run_company_research,exa_company_search,"
            "limadata_find_person_profiles,allegrow_validate,leadmagic_email_validation"
        ),
    ).split(",")
    if tool_id.strip()
]
ALLOWED_CLIENT_TOOL_IDS = {
    tool_id.strip()
    for tool_id in os.environ.get(
        "ALLOWED_CLIENT_TOOL_IDS",
        ",".join(DEFAULT_CHAT_TOOL_IDS + ["snowflake_query", "snowflake_execute_query"]),
    ).split(",")
    if tool_id.strip()
}
SLACK_SAFE_INSTRUCTIONS = """\
Slack requests run in read-only mode by default. Do not send outreach, modify CRM
records, enroll sequences, create external tasks, export sensitive row-level data,
or mutate any external system. If the user asks for a side effect, draft the plan
and ask for approval instead of taking the action.

Business contact enrichment is allowed in Slack when requested by an authenticated
workspace user. Work phones, business mobile numbers, work emails, LinkedIn URLs,
titles, and company context for named professionals are normal B2B GTM data. Use
licensed Deepline providers, report source/provider status, and do not refuse these
requests on privacy grounds. Never invent data; if providers return no result,
say no verified result was found.
"""
SLACK_DEFAULT_TOOL_IDS = [
    tool_id.strip()
    for tool_id in os.environ.get(
        "SLACK_ENABLED_TOOL_IDS",
        (
            "deeplineagent,serper_google_search,exa_search,firecrawl_scrape,"
            "limadata_find_person_profiles,forager_person_detail_lookup,"
            "leadmagic_mobile_finder,dropleads_mobile_finder,ai_ark_mobile_phone_finder"
        ),
    ).split(",")
    if tool_id.strip()
]
SLACK_MAX_TOOL_CALLS = min(
    int(os.environ.get("SLACK_MAX_TOOL_CALLS", "4")),
    MAX_TOOL_CALLS_LIMIT,
)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


async def require_api_key(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    api_key = os.environ.get("API_KEY", "")
    if not api_key:
        if _env_flag("ALLOW_UNAUTHENTICATED", default=False):
            return
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    if not credentials or credentials.credentials != api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def get_deepline_client() -> DeeplineV2Client:
    return DeeplineV2Client()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Deepline GTM native v2 broker starting")
    yield


app = FastAPI(title="Deepline GTM Native Agent", version="2.0.0", lifespan=lifespan)
app.include_router(reply_copilot_router)

_cors_raw = os.environ.get("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip() and o.strip() != "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    messages: list[ChatMessage] | None = None
    thread_id: str | None = None
    enabled_tool_ids: list[str] | None = Field(default=None, alias="enabledToolIds")
    max_tool_calls: int | None = Field(default=None, alias="maxToolCalls")
    model: str | None = None

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    reply: str
    thread_id: str | None = None


BULK_PROSPECT_LIST_INSTRUCTIONS = """\
Bulk prospect/list requests must use Deepline's native v2 list-building workflow.
Create an execution plan, produce or reference an auditable seed list, and run only
a pilot/sample first unless the user has explicitly approved the full run. Do not
invent prospects, companies, emails, LinkedIn URLs, or CSV rows. If a CSV/artifact
is requested, return the artifact/status details Deepline produced and the next
approval step before any full enrichment.
"""

PRODUCTION_GTM_AGENT_INSTRUCTIONS = """\
Production GTM agent requests must use this operating loop:

1. Source: gather account/contact/context from named systems or web sources.
2. Verify: state what is confirmed, what is inferred, and what is missing.
3. Bound tools: use only the minimum tools needed; respect auth/scopes and do not
   spray every provider when a focused workflow or Deepline play exists.
4. Draft/recommend: produce the next action with source-backed reasoning.
5. Approval gate: ask before sending outreach, changing CRM data, enrolling in a
   sequence, creating a task, or writing back to a system of record.
6. Write back: after approval, update the chosen system and include the record ID,
   source fields, and timestamp in the response.
7. Learn: summarize the outcome signal that should improve the next run.

Bias toward production GTM agent patterns:
- Approval loops and traceable reasoning before side effects.
- Search should return workflow-ready context, not generic link dumps.
- Tool use needs auth, scopes, execution boundaries, and audit trails.
- Voice and conversation agents need persistent context before action.
- The data layer and writeback loop are usually the bottleneck.
"""

SNOWFLAKE_QUERY_AGENT_INSTRUCTIONS = """\
Snowflake/warehouse query requests must use this read-only operating loop:

1. Interpret the business question and restate the metric/entity/time window.
2. Identify likely tables and fields before querying.
3. Propose the SQL before execution when the schema or metric definition is ambiguous.
4. Use read-only SELECT queries only. Never run INSERT, UPDATE, DELETE, MERGE,
   CREATE, DROP, ALTER, COPY, GRANT, or external stage operations.
5. Limit exploratory queries and avoid exporting unnecessary row-level data.
6. Explain joins, filters, and caveats in the result.
7. Ask for approval before CRM writeback, outreach, task creation, or sharing
   sensitive rows outside the system.

Bias toward warehouse-backed GTM questions from the talks:
- account owner, activation, product usage, renewal/churn risk
- customer cloud/provider signals extracted from calls
- weekly account intelligence digests
- pipeline or territory prioritization
"""

EMAIL_VERIFICATION_INSTRUCTIONS = """\
Email verification requests must execute a Deepline verifier before answering.
Use deepline_call with one of these tool IDs: allegrow_validate or
leadmagic_email_validation. Do not infer deliverability from search results or
public web pages alone. Prefer Allegrow first, then fall back to LeadMagic only
if needed. Report the provider used, the returned status, catch-all or risk
signals if available, and a plain safe-to-send recommendation. If no verifier
returns a result, say the email is unverified instead of guessing.
"""

EMAIL_VERIFICATION_TOOL_IDS = [
    "allegrow_validate",
    "leadmagic_email_validation",
]

_BULK_LIST_TERMS = ("csv", "list", "prospect", "prospects", "contacts", "accounts")
_BULK_ACTION_TERMS = ("build", "create", "find", "source", "generate")
_BULK_COUNT_TERMS = ("5", "10", "20", "25", "50", "100", "bulk", "batch")

_PRODUCTION_AGENT_TERMS = (
    "agent",
    "agents",
    "workflow",
    "writeback",
    "write back",
    "approval",
    "approve",
    "crm",
    "salesforce",
    "hubspot",
    "sequence",
    "outreach",
    "voice",
    "call",
    "lead magnet",
    "build kit",
)

_SNOWFLAKE_QUERY_SOURCE_TERMS = (
    "snowflake",
    "warehouse",
    "sql",
    "data warehouse",
)

_SNOWFLAKE_QUERY_ANALYTIC_TERMS = (
    "query",
    "table",
    "tables",
    "activation",
    "product usage",
    "churn",
    "renewal",
    "pipeline",
    "account owner",
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")
_LINKEDIN_PROFILE_RE = re.compile(r"https?://(?:[\w-]+\.)?linkedin\.com/in/[^\s<>)]+", re.IGNORECASE)
_EMAIL_VERIFY_TERMS = (
    "verify",
    "valid",
    "deliverable",
    "safe to send",
    "safe-to-send",
    "email status",
    "catch-all",
    "catch all",
)
_MOBILE_LOOKUP_TERMS = (
    "mobile",
    "mobile number",
    "phone",
    "phone number",
    "cell",
    "direct dial",
)
_MOBILE_LOOKUP_PROVIDER_IDS = [
    "forager_person_detail_lookup",
    "leadmagic_mobile_finder",
    "dropleads_mobile_finder",
    "ai_ark_mobile_phone_finder",
]

def _looks_like_bulk_prospect_list(message: str) -> bool:
    text = message.lower()
    return (
        any(term in text for term in _BULK_LIST_TERMS)
        and any(term in text for term in _BULK_ACTION_TERMS)
        and any(term in text for term in _BULK_COUNT_TERMS)
    )


def _with_bulk_prospecting_guidance(message: str) -> str:
    if not _looks_like_bulk_prospect_list(message):
        return message
    if "native v2 list-building workflow" in message:
        return message
    return f"{BULK_PROSPECT_LIST_INSTRUCTIONS}\n\nUser request:\n{message}"


def _looks_like_production_gtm_agent_request(message: str) -> bool:
    text = message.lower()
    return any(term in text for term in _PRODUCTION_AGENT_TERMS)


def _with_production_gtm_agent_guidance(message: str) -> str:
    if not _looks_like_production_gtm_agent_request(message):
        return message
    if "Production GTM agent requests must use this operating loop" in message:
        return message
    return f"{PRODUCTION_GTM_AGENT_INSTRUCTIONS}\n\nUser request:\n{message}"


def _looks_like_snowflake_query_request(message: str) -> bool:
    text = message.lower()
    return any(term in text for term in _SNOWFLAKE_QUERY_SOURCE_TERMS) and any(
        term in text for term in _SNOWFLAKE_QUERY_ANALYTIC_TERMS
    )


def _with_snowflake_query_guidance(message: str) -> str:
    if not _looks_like_snowflake_query_request(message):
        return message
    if "Snowflake/warehouse query requests must use this read-only operating loop" in message:
        return message
    return f"{SNOWFLAKE_QUERY_AGENT_INSTRUCTIONS}\n\nUser request:\n{message}"


def _looks_like_email_verification_request(message: str) -> bool:
    text = message.lower()
    return bool(_EMAIL_RE.search(message)) and any(term in text for term in _EMAIL_VERIFY_TERMS)


def _email_for_verification(message: str) -> str | None:
    if not _looks_like_email_verification_request(message):
        return None
    match = _EMAIL_RE.search(message)
    return match.group(0) if match else None


def _looks_like_business_mobile_request(message: str) -> bool:
    text = message.lower()
    return any(term in text for term in _MOBILE_LOOKUP_TERMS) and (
        "linkedin.com/in/" in text
        or "business" in text
        or "work" in text
        or "licensed-provider" in text
        or "licensed provider" in text
    )


def _linkedin_profile_url(message: str) -> str | None:
    match = _LINKEDIN_PROFILE_RE.search(message)
    if not match:
        return None
    return match.group(0).split("|", 1)[0].rstrip(".,;")


def _linkedin_public_identifier(linkedin_url: str) -> str | None:
    match = re.search(r"linkedin\.com/in/([^/?#\s]+)", linkedin_url, re.IGNORECASE)
    return match.group(1).strip("/") if match else None


def _with_email_verification_guidance(message: str) -> str:
    if not _looks_like_email_verification_request(message):
        return message
    if "Email verification requests must execute a Deepline verifier" in message:
        return message
    return f"{EMAIL_VERIFICATION_INSTRUCTIONS}\n\nUser request:\n{message}"


def _validate_enabled_tool_ids(tool_ids: list[str]) -> list[str]:
    disallowed = sorted(set(tool_ids) - ALLOWED_CLIENT_TOOL_IDS)
    if disallowed:
        raise HTTPException(
            status_code=400,
            detail=f"Tool IDs are not allowed: {', '.join(disallowed)}",
        )
    return tool_ids


def _bounded_max_tool_calls(value: int | None) -> int:
    if value is None:
        return DEFAULT_MAX_TOOL_CALLS
    if value < 0:
        raise HTTPException(status_code=400, detail="maxToolCalls must be non-negative")
    return min(value, MAX_TOOL_CALLS_LIMIT)


def _chat_payload(req: ChatRequest) -> dict[str, Any]:
    if _looks_like_bulk_prospect_list(req.message):
        prompt = (
            f"{BULK_PROSPECT_LIST_INSTRUCTIONS}\n\n"
            f"{PRODUCTION_GTM_AGENT_INSTRUCTIONS}\n\n"
            f"User request:\n{req.message}"
        )
    else:
        prompt = _with_email_verification_guidance(
            _with_snowflake_query_guidance(
                _with_production_gtm_agent_guidance(req.message)
            )
        )
    messages = (
        [{"role": m.role, "content": m.content} for m in req.messages]
        if req.messages and prompt == req.message
        else [{"role": "user", "content": prompt}]
    )
    payload: dict[str, Any] = {
        "prompt": prompt,
        "messages": messages,
        "response_mode": "stream",
        "enabledToolIds": (
            _validate_enabled_tool_ids(req.enabled_tool_ids)
            if req.enabled_tool_ids is not None
            else DEFAULT_CHAT_TOOL_IDS
        ),
        "maxToolCalls": _bounded_max_tool_calls(req.max_tool_calls),
    }
    if req.model:
        payload["model"] = req.model
    return payload


def _compact_tool_response(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _compact_tool_response(v) for k, v in value.items() if k not in {"billing"}}
    if isinstance(value, list):
        return [_compact_tool_response(v) for v in value[:5]]
    return value


def _email_verification_payload(result: dict[str, Any]) -> dict[str, Any]:
    tool_response = result.get("toolResponse")
    if isinstance(tool_response, dict):
        raw = tool_response.get("raw")
        if isinstance(raw, dict):
            return raw
        return tool_response
    return result


def _email_signal(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _nested_email_signal(payload: dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        value: Any = payload
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if value not in (None, ""):
            return value
    return None


def _status_from_email_payload(payload: dict[str, Any]) -> str:
    status = _email_signal(
        payload,
        "status",
        "email_status",
        "allegrowStatus",
        "deliverability",
        "state",
        "sub_status",
    ) or _nested_email_signal(
        payload,
        ("result", "status"),
        ("result", "subStatus"),
    )
    if isinstance(status, str):
        return status
    for key in ("valid", "verified", "deliverable", "is_valid"):
        value = payload.get(key)
        if isinstance(value, bool):
            return "valid" if value else "invalid"
    return "unknown"


def _safe_to_send_recommendation(status: str, payload: dict[str, Any]) -> str:
    normalized = status.lower()
    risky = any(
        bool(payload.get(key))
        for key in (
            "disposable",
            "honeypot",
            "spamtrap",
            "fraud",
            "risky",
            "catch_all",
            "catchAll",
        )
    ) or bool(_nested_email_signal(payload, ("domain", "isCatchAll")))
    if normalized in {"valid", "deliverable", "safe"} and not risky:
        return "Safe to send with normal outbound throttling."
    if normalized in {"invalid", "undeliverable", "do_not_send", "risky", "dead_email"} or risky:
        return "Do not send until you have another verified address."
    return "Treat as unverified; do not send at scale without another verification pass."


def _format_email_verification_reply(email: str, tool_id: str | None, result: dict[str, Any] | None) -> str:
    if not tool_id or not result:
        return (
            f"Email: {email}\n"
            "Provider used: none\n"
            "Status: unverified\n"
            "Safe-to-send recommendation: Do not send until a verifier returns a result."
        )

    payload = _email_verification_payload(result)
    status = _status_from_email_payload(payload)
    provider = _email_signal(payload, "provider", "source", "vendor") or tool_id
    catch_all = _email_signal(
        payload,
        "catch_all",
        "catchAll",
        "accept_all",
    )
    if catch_all is None:
        catch_all = _nested_email_signal(payload, ("domain", "isCatchAll"))
    risk = _email_signal(payload, "risk", "risk_level", "fraud_score", "disposable", "honeypot")
    recommendation = _safe_to_send_recommendation(status, payload)

    lines = [
        f"Email: {email}",
        f"Provider used: {tool_id}" + (f" ({provider})" if provider != tool_id else ""),
        f"Status: {status}",
    ]
    if catch_all is not None:
        lines.append(f"Catch-all signal: {catch_all}")
    if risk is not None:
        lines.append(f"Risk signal: {risk}")
    lines.append(f"Safe-to-send recommendation: {recommendation}")
    return "\n".join(lines)


def _safe_email_tool_output(tool_id: str, result: dict[str, Any]) -> dict[str, Any]:
    payload = _email_verification_payload(result)
    status = _status_from_email_payload(payload)
    provider = _email_signal(payload, "provider", "source", "vendor") or tool_id
    catch_all = _email_signal(payload, "catch_all", "catchAll", "accept_all")
    if catch_all is None:
        catch_all = _nested_email_signal(payload, ("domain", "isCatchAll"))
    risk = _email_signal(payload, "risk", "risk_level", "fraud_score", "disposable", "honeypot")
    safe_output: dict[str, Any] = {
        "provider": provider,
        "status": status,
        "safe_to_send": _safe_to_send_recommendation(status, payload),
    }
    if catch_all is not None:
        safe_output["catch_all"] = catch_all
    if risk is not None:
        safe_output["risk"] = risk
    return safe_output


async def _execute_email_verification(
    message: str,
    on_attempt: Any | None = None,
) -> tuple[str, str | None, dict[str, Any] | None]:
    email = _email_for_verification(message)
    if not email:
        raise ValueError("No email verification target found")

    client = get_deepline_client()
    for tool_id in EMAIL_VERIFICATION_TOOL_IDS:
        payload = {"email": email}
        if on_attempt:
            await on_attempt(tool_id, payload)
        try:
            result = await client.execute_tool(tool_id, payload)
            return email, tool_id, result
        except Exception as e:
            logger.warning("Email verifier %s failed: %s", tool_id, e)
    return email, None, None


async def _collect_email_verification_reply(message: str) -> str:
    email, tool_id, result = await _execute_email_verification(message)
    return _format_email_verification_reply(email, tool_id, result)


def _mobile_tool_payload(tool_id: str, linkedin_url: str) -> dict[str, Any]:
    if tool_id == "forager_person_detail_lookup":
        public_identifier = _linkedin_public_identifier(linkedin_url)
        if not public_identifier:
            raise ValueError("LinkedIn public identifier could not be parsed")
        return {"linkedin_public_identifier": public_identifier}
    if tool_id == "leadmagic_mobile_finder":
        return {"profile_url": linkedin_url}
    if tool_id == "dropleads_mobile_finder":
        return {"linkedin_url": linkedin_url}
    if tool_id == "ai_ark_mobile_phone_finder":
        return {"linkedin": linkedin_url}
    raise ValueError(f"Unsupported mobile provider: {tool_id}")


def _flatten_phone_candidates(value: Any, *, phone_context: bool = False) -> list[str]:
    candidates: list[str] = []
    phoneish_keys = {
        "phone",
        "phones",
        "phone_number",
        "phone_numbers",
        "mobile",
        "mobiles",
        "mobile_phone",
        "mobile_phone_number",
        "mobile_number",
        "direct_dial",
        "direct_phone",
        "work_phone",
        "business_phone",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower()
            next_phone_context = phone_context or key_text in phoneish_keys or "phone" in key_text or "mobile" in key_text
            if next_phone_context:
                candidates.extend(_flatten_phone_candidates(nested, phone_context=True))
            elif isinstance(nested, (dict, list)):
                candidates.extend(_flatten_phone_candidates(nested, phone_context=False))
    elif isinstance(value, list):
        for item in value:
            candidates.extend(_flatten_phone_candidates(item, phone_context=phone_context))
    elif phone_context and isinstance(value, str):
        text = value.strip()
        if re.search(r"\+?\d[\d\s().-]{6,}\d", text):
            candidates.append(text)
    return candidates


def _first_mobile_candidate(result: dict[str, Any]) -> str | None:
    payload = _email_verification_payload(result)
    for candidate in _flatten_phone_candidates(payload):
        normalized = re.sub(r"\s+", " ", candidate).strip()
        if normalized:
            return normalized
    return None


def _mobile_provider_status(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            data = exc.response.json()
        except ValueError:
            data = {}
        detail = (
            data.get("message")
            or data.get("error")
            or data.get("details")
            or f"HTTP {exc.response.status_code}"
        )
        return str(detail)
    return str(exc)


async def _execute_mobile_lookup(message: str) -> tuple[str, list[dict[str, str]], str | None]:
    linkedin_url = _linkedin_profile_url(message)
    if not linkedin_url:
        raise ValueError("A LinkedIn profile URL is required for Slack mobile lookup.")

    client = get_deepline_client()
    attempts: list[dict[str, str]] = []
    for tool_id in _MOBILE_LOOKUP_PROVIDER_IDS:
        payload = _mobile_tool_payload(tool_id, linkedin_url)
        try:
            result = await client.execute_tool(tool_id, payload)
        except Exception as e:
            logger.warning("Mobile provider %s failed: %s", tool_id, e)
            attempts.append({"provider": tool_id, "status": _mobile_provider_status(e)})
            continue

        mobile = _first_mobile_candidate(result)
        if mobile:
            attempts.append({"provider": tool_id, "status": "verified business mobile found"})
            return linkedin_url, attempts, mobile
        attempts.append({"provider": tool_id, "status": "no verified business mobile returned"})

    return linkedin_url, attempts, None


def _format_mobile_lookup_reply(linkedin_url: str, attempts: list[dict[str, str]], mobile: str | None) -> str:
    lines = [
        f"LinkedIn: {linkedin_url}",
        "Providers checked:",
    ]
    for attempt in attempts:
        lines.append(f"- {attempt['provider']}: {attempt['status']}")
    if mobile:
        lines.extend(
            [
                "Verified business mobile found: yes",
                f"Business mobile: {mobile}",
            ]
        )
    else:
        lines.append("Verified business mobile found: no")
    return "\n".join(lines)


async def _collect_mobile_lookup_reply(message: str) -> str:
    linkedin_url, attempts, mobile = await _execute_mobile_lookup(message)
    return _format_mobile_lookup_reply(linkedin_url, attempts, mobile)


def _sse(event: dict[str, Any] | str) -> str:
    if isinstance(event, str):
        return f"data: {event}\n\n"
    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n"


async def _stream_email_verification_reply(message: str) -> AsyncIterator[str]:
    attempts: list[tuple[str, dict[str, Any]]] = []

    async def on_attempt(tool_id: str, payload: dict[str, Any]) -> None:
        attempts.append((tool_id, payload))

    email, tool_id, result = await _execute_email_verification(message, on_attempt=on_attempt)
    for attempted_tool_id, payload in attempts:
        yield _sse(
            {
                "type": "tool-input-available",
                "toolName": attempted_tool_id,
                "input": payload,
            }
        )
        if attempted_tool_id == tool_id and result is not None:
            yield _sse(
                {
                    "type": "tool-output-available",
                    "toolName": attempted_tool_id,
                    "output": _safe_email_tool_output(attempted_tool_id, result),
                }
            )

    reply = _format_email_verification_reply(email, tool_id, result)
    yield _sse({"type": "text-start", "id": "email_verification_result"})
    yield _sse({"type": "text-delta", "id": "email_verification_result", "delta": reply})
    yield _sse({"type": "text-end", "id": "email_verification_result"})
    yield _sse({"type": "finish-step"})
    yield _sse({"type": "finish", "finishReason": "stop"})
    yield _sse("[DONE]")


async def _collect_native_reply(payload: dict[str, Any]) -> str:
    client = get_deepline_client()
    parts: list[str] = []
    async for chunk in client.stream_agent(payload):
        parts.append(extract_text_from_stream_chunk(chunk))
    return "".join(parts).strip()


@app.get("/health")
async def health():
    checks = config_summary()
    body = {
        "status": "ok" if os.environ.get("DEEPLINE_API_KEY") else "needs setup",
        "agent": "deepline-gtm-native-v2",
        "deepline": "configured" if os.environ.get("DEEPLINE_API_KEY") else "missing DEEPLINE_API_KEY",
        "host": deepline_host(),
        "slack": "configured" if os.environ.get("SLACK_BOT_TOKEN") else "not configured",
        "config_status": checks["status"],
    }
    return JSONResponse(body, status_code=200 if os.environ.get("DEEPLINE_API_KEY") else 503)


@app.get("/doctor")
async def doctor():
    """Return non-secret setup diagnostics for the broker boundary."""
    summary = config_summary()
    return JSONResponse(summary, status_code=200 if summary["status"] != "error" else 503)


@app.get("/workflow-presets")
async def workflow_presets():
    """List transcript-derived starter workflows for GTM agents."""
    return {"presets": list_workflow_presets()}


@app.get("/workflow-presets/{preset_id}")
async def workflow_preset(preset_id: str):
    """Return a full workflow preset with prompt, tool bounds, and output shape."""
    preset = get_workflow_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Unknown workflow preset")
    return preset


@app.get("/", response_class=HTMLResponse)
async def chat_ui():
    html_path = Path(__file__).parent / "chat.html"
    if html_path.exists():
        return html_path.read_text()
    return "<h2>Deepline GTM Agent</h2><p>POST to /chat or /chat/stream</p>"


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest):
    if _email_for_verification(req.message):
        reply = await _collect_email_verification_reply(req.message)
    else:
        reply = await _collect_native_reply(_chat_payload(req))
    return ChatResponse(reply=reply, thread_id=req.thread_id)


@app.post("/chat/stream", dependencies=[Depends(require_api_key)])
async def chat_stream(req: ChatRequest):
    if _email_for_verification(req.message):
        return StreamingResponse(
            _stream_email_verification_reply(req.message),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    payload = _chat_payload(req)

    async def generate() -> AsyncIterator[str]:
        async for chunk in get_deepline_client().stream_agent(payload):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
_workspace_tokens: dict[str, str] = {}


def _verify_slack_sig(body: bytes, timestamp: str, signature: str) -> bool:
    if not SLACK_SIGNING_SECRET:
        return False
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False
    if abs(time.time() - ts) > 300:
        return False
    base = b"v0:" + timestamp.encode() + b":" + body
    expected = "v0=" + hmac.new(SLACK_SIGNING_SECRET.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _read_limited_body(request: Request, max_bytes: int = MAX_SLACK_BODY_BYTES) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:
            raise HTTPException(status_code=413, detail="Request too large")
    return bytes(body)


def _csv_env_set(name: str) -> set[str]:
    return {value.strip() for value in os.environ.get(name, "").split(",") if value.strip()}


def _slack_event_allowed(event: dict[str, Any]) -> bool:
    allowed_channels = _csv_env_set("SLACK_ALLOWED_CHANNEL_IDS")
    allowed_users = _csv_env_set("SLACK_ALLOWED_USER_IDS")
    if not allowed_channels and not allowed_users:
        logger.warning("Ignoring Slack event because no channel or user allowlist is configured")
        return False
    channel = event.get("channel", "")
    user = event.get("user", "")
    if allowed_channels and "*" not in allowed_channels and channel not in allowed_channels:
        return False
    if allowed_users and "*" not in allowed_users and user not in allowed_users:
        return False
    return True


def _slack_agent_payload(user_text: str) -> dict[str, Any]:
    base = _chat_payload(ChatRequest(message=user_text))
    prompt = f"{SLACK_SAFE_INSTRUCTIONS}\n\n{base['prompt']}"
    return {
        "prompt": prompt,
        "messages": [{"role": "user", "content": prompt}],
        "response_mode": "stream",
        "enabledToolIds": SLACK_DEFAULT_TOOL_IDS,
        "maxToolCalls": SLACK_MAX_TOOL_CALLS,
    }


async def _slack_api_post(endpoint: str, payload: dict[str, Any], token: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            f"https://slack.com/api/{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=10,
        )
    try:
        data = resp.json()
    except ValueError:
        data = {}

    if resp.status_code >= 400 or not data.get("ok"):
        detail = data.get("error") or getattr(resp, "text", "") or f"HTTP {resp.status_code}"
        raise RuntimeError(f"Slack {endpoint} failed: {detail}")
    return data


async def _slack_post(channel: str, text: str, token: str, thread_ts: str | None = None):
    payload = {"channel": channel, "text": text, "mrkdwn": True}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    await _slack_api_post("chat.postMessage", payload, token)


async def _slack_react(channel: str, ts: str, emoji: str, token: str, remove: bool = False) -> bool:
    endpoint = "reactions.remove" if remove else "reactions.add"
    try:
        await _slack_api_post(
            endpoint,
            {"channel": channel, "timestamp": ts, "name": emoji},
            token,
        )
        return True
    except Exception as e:
        logger.warning("Slack %s failed: %s", endpoint, e)
        return False


async def _fetch_thread_history(channel: str, thread_ts: str, token: str, limit: int = 20) -> list[dict]:
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                "https://slack.com/api/conversations.replies",
                headers={"Authorization": f"Bearer {token}"},
                params={"channel": channel, "ts": thread_ts, "limit": limit},
                timeout=10,
            )
        if resp.status_code >= 400:
            logger.warning("Slack conversations.replies HTTP %s", resp.status_code)
            return []
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Slack conversations.replies failed: %s", data.get("error", "unknown_error"))
            return []
        messages = []
        for msg in data.get("messages", [])[:-1]:
            text = msg.get("text", "").strip()
            if text.startswith("<@"):
                text = text.split(">", 1)[-1].strip()
            if not text:
                continue
            messages.append({"role": "assistant" if msg.get("bot_id") else "user", "content": text})
        return messages
    except Exception as e:
        logger.warning("Failed to fetch Slack thread history: %s", e)
        return []


async def _handle_slack_event(event: dict, team_id: str):
    token = _workspace_tokens.get(team_id, SLACK_BOT_TOKEN)
    channel = event.get("channel", "")
    user_text = event.get("text", "").strip()
    if user_text.startswith("<@"):
        user_text = user_text.split(">", 1)[-1].strip()
    if not user_text:
        return

    message_ts = event.get("ts", "")
    thread_ts = event.get("thread_ts") or message_ts
    await _slack_react(channel, message_ts, "eyes", token)

    try:
        history = await _fetch_thread_history(channel, thread_ts, token) if event.get("thread_ts") else []
        if _email_for_verification(user_text):
            reply = await _collect_email_verification_reply(user_text)
        elif _looks_like_business_mobile_request(user_text) and _linkedin_profile_url(user_text):
            reply = await _collect_mobile_lookup_reply(user_text)
        else:
            payload = _slack_agent_payload(user_text)
            if history:
                payload["messages"] = history + [{"role": "user", "content": payload["prompt"]}]
            reply = await _collect_native_reply(payload)

        await _slack_react(channel, message_ts, "eyes", token, remove=True)
        slack_reply = md_to_slack(reply) if reply else "(no response)"
        for chunk in truncate_for_slack(slack_reply):
            await _slack_post(channel, chunk, token, thread_ts)
    except Exception as e:
        logger.exception("Slack handler error")
        try:
            await _slack_react(channel, message_ts, "eyes", token, remove=True)
            await _slack_post(
                channel,
                ":warning: Sorry, I hit an internal error while handling that request.",
                token,
                thread_ts,
            )
        except Exception:
            logger.exception("Failed to send Slack error message")


_seen_events: OrderedDict[str, None] = OrderedDict()
_MAX_SEEN = 5000


def _mark_seen(event_id: str) -> bool:
    if event_id in _seen_events:
        return True
    _seen_events[event_id] = None
    while len(_seen_events) > _MAX_SEEN:
        _seen_events.popitem(last=False)
    return False


@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await _read_limited_body(request)
    except HTTPException:
        return Response(status_code=413)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return Response(status_code=400)

    if not _verify_slack_sig(
        body,
        request.headers.get("X-Slack-Request-Timestamp", ""),
        request.headers.get("X-Slack-Signature", ""),
    ):
        return Response(status_code=403)

    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    if payload.get("type") == "event_callback":
        event = payload.get("event", {})
        event_id = payload.get("event_id", "")
        etype = event.get("type", "")
        ctype = event.get("channel_type", "")

        if event_id and _mark_seen(event_id):
            return Response(status_code=200)
        if event.get("bot_id") or event.get("subtype"):
            return Response(status_code=200)
        if etype == "app_mention" or (etype == "message" and ctype == "im"):
            if not _slack_event_allowed(event):
                return Response(status_code=200)
            background_tasks.add_task(_handle_slack_event, event, payload.get("team_id", ""))

    return Response(status_code=200)


@app.get("/slack/oauth_redirect")
async def slack_oauth_redirect(code: str = "", state: str = "", error: str = ""):
    import httpx

    if error:
        return HTMLResponse(f"<h2>OAuth error: {html.escape(error)}</h2>", status_code=400)
    if not code:
        return HTMLResponse("<h2>Missing code</h2>", status_code=400)
    expected_state = os.environ.get("SLACK_OAUTH_STATE", "")
    if not expected_state:
        return HTMLResponse("<h2>Slack OAuth is not configured</h2>", status_code=503)
    if not state or not hmac.compare_digest(state, expected_state):
        return HTMLResponse("<h2>Invalid OAuth state</h2>", status_code=403)

    client_id = os.environ.get("SLACK_CLIENT_ID", "")
    client_secret = os.environ.get("SLACK_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return HTMLResponse("<h2>Set SLACK_CLIENT_ID and SLACK_CLIENT_SECRET</h2>", status_code=500)

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            "https://slack.com/api/oauth.v2.access",
            data={"client_id": client_id, "client_secret": client_secret, "code": code},
            timeout=10,
        )
    data = resp.json()
    if not data.get("ok"):
        return HTMLResponse(f"<h2>OAuth failed: {html.escape(str(data.get('error')))}</h2>", status_code=400)

    bot_token = data.get("access_token", "")
    team_id = data.get("team", {}).get("id", "")
    team_name = html.escape(data.get("team", {}).get("name", "workspace"))
    if team_id and bot_token:
        _workspace_tokens[team_id] = bot_token

    return HTMLResponse(f"""<!DOCTYPE html>
<html><body style="font-family:system-ui;max-width:600px;margin:60px auto;padding:0 20px">
<h2>Connected to {team_name}</h2>
<p>The bot token was stored for this process. Persist it in your secret manager outside this page.</p>
</body></html>""")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        log_config=UVICORN_LOG_CONFIG,
    )
