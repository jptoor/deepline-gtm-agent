from pathlib import Path
import asyncio
import hmac
import hashlib
import json
import time

import pytest
from fastapi.testclient import TestClient


def test_managed_server_uses_native_deepline_stream():
    source = Path("managed_agent/server.py").read_text()

    assert "DeeplineV2Client" in source
    assert "/api/v2/integrations/deeplineagent/stream" not in source
    assert "BOOTSTRAP_MSG" not in source
    assert "create_session(" not in source
    assert "stream_events(" not in source


def test_root_server_delegates_to_v2_broker():
    source = Path("server.py").read_text()

    assert "from managed_agent.server import UVICORN_LOG_CONFIG, app" in source
    assert "create_gtm_agent" not in source
    assert "load_tool_catalog" not in source


def test_managed_agent_does_not_upload_cli_or_auth_files():
    combined = "\n".join(
        Path(path).read_text()
        for path in [
            "managed_agent/session.py",
            "managed_agent/setup.py",
            "managed_agent/Dockerfile",
            "railway.toml",
        ]
    )

    assert "deepline-auth.env" not in combined
    assert "/mnt/session/uploads/workspace/deepline" not in combined
    assert "zipapp" not in combined
    assert "NODE_TLS_REJECT_UNAUTHORIZED=0" not in combined


def test_server_logging_is_configured_for_stdout_on_railway():
    source = Path("managed_agent/server.py").read_text()
    root_source = Path("server.py").read_text()

    assert "stream=sys.stdout" in source
    assert "UVICORN_LOG_CONFIG" in source
    assert "log_config=UVICORN_LOG_CONFIG" in source
    assert "UVICORN_LOG_CONFIG" in root_source
    assert "log_config=UVICORN_LOG_CONFIG" in root_source


def test_dockerfile_preserves_managed_agent_package_for_workflow_presets():
    dockerfile = Path("managed_agent/Dockerfile").read_text()

    assert "COPY managed_agent/ ./managed_agent/" in dockerfile


def test_dockerfile_runs_as_non_root_user():
    dockerfile = Path("managed_agent/Dockerfile").read_text()

    assert "USER app" in dockerfile


def test_default_cors_does_not_use_wildcard():
    source = Path("managed_agent/server.py").read_text()

    assert 'os.environ.get("CORS_ORIGINS", "")' in source
    assert 'os.environ.get("CORS_ORIGINS", "*")' not in source
    assert 'o.strip() != "*"' in source


def test_broker_boundary_keeps_deepline_execution_in_deepline_api():
    managed_sources = "\n".join(
        path.read_text()
        for path in Path("managed_agent").glob("*.py")
        if path.name != "workflow_presets.py"
    )

    assert "startPlayRun" not in managed_sources
    assert "class ProviderAdapter" not in managed_sources
    assert "provider_adapter" not in managed_sources
    assert "execute_waterfall" not in managed_sources
    assert "waterfall_providers" not in managed_sources
    assert "run history" not in managed_sources.lower()
    assert "/api/v2/integrations/{tool_id}/execute" not in managed_sources


def test_health_fails_when_deepline_key_missing(monkeypatch):
    monkeypatch.delenv("DEEPLINE_API_KEY", raising=False)

    from managed_agent.server import app

    response = TestClient(app).get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "needs setup"
    assert response.json()["config_status"] == "error"


def test_doctor_reports_non_secret_setup_checks(monkeypatch):
    monkeypatch.setenv("DEEPLINE_API_KEY", "dlp_test_secret")
    monkeypatch.setenv("API_KEY", "broker-secret")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example")

    from managed_agent.server import app

    response = TestClient(app).get("/doctor")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["host"] == "https://code.deepline.com"
    assert "dlp_test_secret" not in response.text
    assert "broker-secret" not in response.text
    assert {check["name"] for check in body["checks"]} >= {
        "deepline_api_key",
        "chat_auth",
        "cors",
        "local_live_writes",
        "slack",
    }


def test_slack_signature_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)

    import managed_agent.server as server
    monkeypatch.setattr(server, "SLACK_SIGNING_SECRET", "")

    assert server._verify_slack_sig(b"{}", "1", "v0=fake") is False


def test_slack_url_verification_requires_valid_signature(monkeypatch):
    monkeypatch.delenv("DEEPLINE_API_KEY", raising=False)

    import managed_agent.server as server

    secret = "test-signing-secret"
    monkeypatch.setattr(server, "SLACK_SIGNING_SECRET", secret)

    app = server.app
    body = {"type": "url_verification", "challenge": "challenge-value"}

    unsigned = TestClient(app).post("/slack/events", json=body)
    assert unsigned.status_code == 403

    raw = json.dumps(body, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    base = b"v0:" + timestamp.encode() + b":" + raw
    signature = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()

    signed = TestClient(app).post(
        "/slack/events",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
    )

    assert signed.status_code == 200
    assert signed.json() == {"challenge": "challenge-value"}


def test_slack_signature_uses_raw_body_bytes(monkeypatch):
    import managed_agent.server as server

    secret = "test-signing-secret"
    body = b'{"payload":"\xff"}'
    timestamp = str(int(time.time()))
    signature = "v0=" + hmac.new(
        secret.encode(),
        b"v0:" + timestamp.encode() + b":" + body,
        hashlib.sha256,
    ).hexdigest()

    monkeypatch.setattr(server, "SLACK_SIGNING_SECRET", secret)

    assert server._verify_slack_sig(body, timestamp, signature) is True


def test_slack_request_body_size_is_limited():
    import managed_agent.server as server

    class FakeRequest:
        async def stream(self):
            yield b"123"
            yield b"45"

    with pytest.raises(Exception) as exc:
        asyncio.run(server._read_limited_body(FakeRequest(), max_bytes=4))

    assert getattr(exc.value, "status_code", None) == 413


def test_slack_post_raises_on_slack_api_error(monkeypatch):
    import managed_agent.server as server
    import httpx

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"ok": False, "error": "channel_not_found"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: FakeClient())

    try:
        asyncio.run(server._slack_post("C123", "hello", "xoxb-test"))
    except RuntimeError as exc:
        assert "channel_not_found" in str(exc)
    else:
        raise AssertionError("_slack_post should raise on Slack ok:false")


def test_bulk_prospect_requests_get_native_v2_list_guidance():
    from managed_agent.server import ChatRequest, _chat_payload

    payload = _chat_payload(
        ChatRequest(
            message="Build a CSV prospect list of 20 VP Engineering contacts at AI infrastructure companies."
        )
    )

    assert payload["prompt"].startswith("Bulk prospect/list requests")
    assert "native v2 list-building workflow" in payload["prompt"]
    assert "pilot/sample first" in payload["messages"][0]["content"]
    assert payload["messages"][0]["role"] == "user"


def test_one_off_prospect_requests_do_not_get_bulk_guidance():
    from managed_agent.server import ChatRequest, _chat_payload

    payload = _chat_payload(ChatRequest(message="Find the LinkedIn URL for Jensen Huang at NVIDIA."))

    assert payload["prompt"] == "Find the LinkedIn URL for Jensen Huang at NVIDIA."
    assert payload["messages"][0]["role"] == "user"
    assert "native v2 list-building workflow" not in payload["messages"][0]["content"]


def test_agent_workflow_requests_get_production_operating_loop():
    from managed_agent.server import ChatRequest, _chat_payload

    payload = _chat_payload(
        ChatRequest(
            message=(
                "Build a GTM agent that researches accounts, drafts outreach, "
                "asks for approval, and writes approved updates back to Salesforce."
            )
        )
    )

    content = payload["messages"][0]["content"]
    assert content.startswith("Production GTM agent requests must use this operating loop")
    assert "Approval gate" in content
    assert "Write back" in content
    assert "Approval loops and traceable reasoning" in content
    assert "Search should return workflow-ready context" in content
    assert "Tool use needs auth, scopes" in content
    assert "Voice and conversation agents" in content


def test_workflow_presets_are_discoverable(monkeypatch):
    monkeypatch.delenv("DEEPLINE_API_KEY", raising=False)

    from managed_agent.server import app

    response = TestClient(app).get("/workflow-presets")

    assert response.status_code == 200
    presets = response.json()["presets"]
    preset_ids = {preset["id"] for preset in presets}
    assert {
        "inbound_lead_approval",
        "account_digest",
        "self_serve_support_agent",
        "web_context_research",
        "account_brief",
        "signal_stacking",
        "org_chart_building",
        "bounded_tool_action",
        "closed_loop_gtm_workflow",
        "snowflake_query_agent",
    }.issubset(preset_ids)


def test_prove_workflow_presets_cover_rep_workflows(monkeypatch):
    monkeypatch.delenv("DEEPLINE_API_KEY", raising=False)

    from managed_agent.server import app

    account_brief = TestClient(app).get("/workflow-presets/account_brief").json()
    signal_stacking = TestClient(app).get("/workflow-presets/signal_stacking").json()
    org_chart = TestClient(app).get("/workflow-presets/org_chart_building").json()

    assert account_brief["title"] == "Rep-ready account brief"
    assert "first-message angle" in account_brief["expected_output"]
    assert signal_stacking["suggested_tool_bounds"]["read_only"] is True
    assert "anti-fit signals" in signal_stacking["expected_output"]
    assert "buying committee discovery" in org_chart["best_for"]
    assert "Notion write" in org_chart["human_approval_required_for"]


def test_workflow_preset_includes_prompt_tool_bounds_and_output_shape(monkeypatch):
    monkeypatch.delenv("DEEPLINE_API_KEY", raising=False)

    from managed_agent.server import app

    response = TestClient(app).get("/workflow-presets/web_context_research")

    assert response.status_code == 200
    preset = response.json()
    assert preset["speaker_pattern"] == "Exa / Scott Langille"
    assert "prompt" in preset
    assert "suggested_tool_bounds" in preset
    assert "expected_output" in preset
    assert "source-backed claims" in preset["expected_output"]
    assert preset["suggested_tool_bounds"]["maxToolCalls"] == 6


def test_snowflake_workflow_preset_is_read_only_and_bounded(monkeypatch):
    monkeypatch.delenv("DEEPLINE_API_KEY", raising=False)

    from managed_agent.server import app

    response = TestClient(app).get("/workflow-presets/snowflake_query_agent")

    assert response.status_code == 200
    preset = response.json()
    assert preset["title"] == "Snowflake query agent"
    assert preset["suggested_tool_bounds"]["read_only"] is True
    assert preset["suggested_tool_bounds"]["maxToolCalls"] == 8
    assert "snowflake_query" in preset["suggested_tool_bounds"]["enabledToolIds"]
    assert "proposed SQL" in preset["expected_output"]
    assert "non-SELECT queries" in preset["human_approval_required_for"]


def test_snowflake_requests_get_read_only_operating_loop():
    from managed_agent.server import ChatRequest, _chat_payload

    payload = _chat_payload(
        ChatRequest(
            message=(
                "Use Snowflake to query product usage for accounts at risk of churn."
            )
        )
    )

    content = payload["messages"][0]["content"]
    assert content.startswith(
        "Snowflake/warehouse query requests must use this read-only operating loop"
    )
    assert "Use read-only SELECT queries only" in content
    assert "Never run INSERT" in content
    assert "approval before CRM writeback" in content


def test_email_verification_requests_get_native_verifier_guidance():
    from managed_agent.server import ChatRequest, _chat_payload

    payload = _chat_payload(
        ChatRequest(message="Verify if john.smith@stripe.com is valid and safe to send to.")
    )

    content = payload["messages"][0]["content"]
    assert content.startswith("Email verification requests must execute a Deepline verifier")
    assert "deepline_call" in content
    assert "allegrow_validate" in content
    assert "leadmagic_email_validation" in content
    assert "ipqs_email_verify" not in content
    assert "john.smith@stripe.com" in content
    assert payload["enabledToolIds"] == [
        "deeplineagent",
        "serper_google_search",
        "exa_search",
        "firecrawl_scrape",
        "discolike_run_company_research",
        "exa_company_search",
        "limadata_find_person_profiles",
        "allegrow_validate",
        "leadmagic_email_validation",
    ]
    assert payload["maxToolCalls"] == 6


def test_chat_payload_rejects_unallowed_tool_ids():
    from fastapi import HTTPException
    from managed_agent.server import ChatRequest, _chat_payload

    with pytest.raises(HTTPException) as exc:
        _chat_payload(
            ChatRequest(
                message="research stripe.com",
                enabledToolIds=["hubspot_create_contact"],
            )
        )

    assert exc.value.status_code == 400
    assert "hubspot_create_contact" in exc.value.detail


def test_chat_payload_caps_max_tool_calls():
    from managed_agent.server import ChatRequest, MAX_TOOL_CALLS_LIMIT, _chat_payload

    payload = _chat_payload(ChatRequest(message="research stripe.com", maxToolCalls=999))

    assert payload["maxToolCalls"] == MAX_TOOL_CALLS_LIMIT


def test_chat_auth_fails_closed_when_api_key_missing(monkeypatch):
    import managed_agent.server as server

    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("ALLOW_UNAUTHENTICATED", raising=False)

    response = TestClient(server.app).post("/chat", json={"message": "research stripe.com"})

    assert response.status_code == 503
    assert response.json()["detail"] == "API authentication is not configured"


def test_chat_auth_can_be_explicitly_disabled_for_dev(monkeypatch):
    import managed_agent.server as server

    async def fake_collect(payload):
        return "ok"

    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("ALLOW_UNAUTHENTICATED", "true")
    monkeypatch.setattr(server, "_collect_native_reply", fake_collect)

    response = TestClient(server.app).post("/chat", json={"message": "research stripe.com"})

    assert response.status_code == 200
    assert response.json()["reply"] == "ok"


def test_email_verification_chat_endpoint_executes_direct_verifier(monkeypatch):
    import managed_agent.server as server

    class FakeVerifierClient:
        def __init__(self):
            self.calls = []

        async def execute_tool(self, tool_id, payload):
            self.calls.append((tool_id, payload))
            return {
                "status": "completed",
                "toolResponse": {
                    "raw": {
                        "email": payload["email"],
                        "verified": False,
                        "provider": "UnitVerifier",
                    }
                },
            }

    fake = FakeVerifierClient()
    monkeypatch.setattr(server, "get_deepline_client", lambda: fake)
    monkeypatch.setenv("API_KEY", "test-api-key")

    response = TestClient(server.app).post(
        "/chat",
        headers={"Authorization": "Bearer test-api-key"},
        json={"message": "Verify if john.smith@stripe.com is valid and safe to send to."},
    )

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert fake.calls == [("allegrow_validate", {"email": "john.smith@stripe.com"})]
    assert "Provider used: allegrow_validate (UnitVerifier)" in reply
    assert "Status: invalid" in reply
    assert "Do not send" in reply


def test_email_verification_stream_emits_tool_call_for_evals(monkeypatch):
    import managed_agent.server as server

    class FakeVerifierClient:
        async def execute_tool(self, tool_id, payload):
            return {
                "status": "completed",
                "toolResponse": {
                    "raw": {
                        "email": payload["email"],
                        "status": "deliverable",
                    }
                },
            }

    monkeypatch.setattr(server, "get_deepline_client", lambda: FakeVerifierClient())
    monkeypatch.setenv("API_KEY", "test-api-key")

    with TestClient(server.app).stream(
        "POST",
        "/chat/stream",
        headers={"Authorization": "Bearer test-api-key"},
        json={"message": "Verify if john.smith@stripe.com is valid and safe to send to."},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type":"tool-input-available"' in body
    assert '"toolName":"allegrow_validate"' in body
    assert '"email":"john.smith@stripe.com"' in body
    assert "Status: deliverable" in body


def test_email_verification_stream_sanitizes_tool_output(monkeypatch):
    import managed_agent.server as server

    class FakeVerifierClient:
        async def execute_tool(self, tool_id, payload):
            return {
                "status": "completed",
                "billing": {"cost": 999},
                "toolResponse": {
                    "raw": {
                        "email": payload["email"],
                        "status": "deliverable",
                        "provider": "UnitVerifier",
                        "company_name": "Sensitive Customer Inc.",
                        "request_id": "secret-request-id",
                    }
                },
            }

    monkeypatch.setattr(server, "get_deepline_client", lambda: FakeVerifierClient())
    monkeypatch.setenv("API_KEY", "test-api-key")

    with TestClient(server.app).stream(
        "POST",
        "/chat/stream",
        headers={"Authorization": "Bearer test-api-key"},
        json={"message": "Verify if john.smith@stripe.com is valid and safe to send to."},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "UnitVerifier" in body
    assert "Sensitive Customer Inc." not in body
    assert "secret-request-id" not in body
    assert '"billing"' not in body


def test_allegrow_email_status_and_catch_all_fields_are_formatted():
    from managed_agent.server import _format_email_verification_reply

    reply = _format_email_verification_reply(
        "john.smith@stripe.com",
        "allegrow_validate",
        {
            "status": "completed",
            "toolResponse": {
                "raw": {
                    "email": "john.smith@stripe.com",
                    "allegrowStatus": "dead_email",
                    "domain": {"isCatchAll": True},
                    "result": {"status": "dead_email"},
                }
            },
        },
    )

    assert "Provider used: allegrow_validate" in reply
    assert "Status: dead_email" in reply
    assert "Catch-all signal: True" in reply
    assert "Do not send" in reply


def test_slack_event_requires_allowlisted_channel_or_user(monkeypatch):
    import managed_agent.server as server

    monkeypatch.delenv("SLACK_ALLOWED_CHANNEL_IDS", raising=False)
    monkeypatch.delenv("SLACK_ALLOWED_USER_IDS", raising=False)

    assert server._slack_event_allowed({"channel": "C123", "user": "U123"}) is False


def test_slack_event_allows_configured_channel(monkeypatch):
    import managed_agent.server as server

    monkeypatch.setenv("SLACK_ALLOWED_CHANNEL_IDS", "C123")
    monkeypatch.delenv("SLACK_ALLOWED_USER_IDS", raising=False)

    assert server._slack_event_allowed({"channel": "C123", "user": "U999"}) is True
    assert server._slack_event_allowed({"channel": "C999", "user": "U999"}) is False


def test_slack_event_allows_explicit_channel_wildcard(monkeypatch):
    import managed_agent.server as server

    monkeypatch.setenv("SLACK_ALLOWED_CHANNEL_IDS", "*")
    monkeypatch.delenv("SLACK_ALLOWED_USER_IDS", raising=False)

    assert server._slack_event_allowed({"channel": "C123", "user": "U999"}) is True
    assert server._slack_event_allowed({"channel": "D123", "user": "U999"}) is True


def test_slack_event_allows_explicit_user_wildcard(monkeypatch):
    import managed_agent.server as server

    monkeypatch.delenv("SLACK_ALLOWED_CHANNEL_IDS", raising=False)
    monkeypatch.setenv("SLACK_ALLOWED_USER_IDS", "*")

    assert server._slack_event_allowed({"channel": "C123", "user": "U999"}) is True


def test_slack_agent_payload_is_read_only_and_bounded():
    import managed_agent.server as server

    payload = server._slack_agent_payload("Research stripe.com and add it to HubSpot")

    assert payload["enabledToolIds"][:4] == [
        "deeplineagent",
        "serper_google_search",
        "exa_search",
        "firecrawl_scrape",
    ]
    assert "hubspot_create_contact" not in payload["enabledToolIds"]
    assert "salesforce_create_lead" not in payload["enabledToolIds"]
    assert payload["maxToolCalls"] == 4
    assert "Do not send outreach" in payload["prompt"]
    assert "ask for approval" in payload["prompt"]


def test_slack_mobile_lookup_routes_to_deepline_contact_enrichment():
    import managed_agent.server as server

    payload = server._slack_agent_payload(
        (
            "use /deepline-gtm to get Luke Szendiuch's mobile please. "
            "He replied from ZeroClick and included linkedin.com/in/luke-szendiuch-62823084"
        )
    )

    assert "business mobile" in payload["prompt"]
    assert "licensed Deepline providers" in payload["prompt"]
    assert "do not refuse" in payload["prompt"].lower()
    assert "private individual" not in payload["prompt"].lower()
    assert "leadmagic_mobile_finder" in payload["enabledToolIds"]
    assert "dropleads_mobile_finder" in payload["enabledToolIds"]
    assert "ai_ark_mobile_phone_finder" in payload["enabledToolIds"]
    assert "ai_ark_mobile_finder" not in payload["enabledToolIds"]
    assert "forager_person_detail_lookup" in payload["enabledToolIds"]


def test_slack_mobile_lookup_payloads_use_live_deepline_contract():
    import managed_agent.server as server

    linkedin = "https://www.linkedin.com/in/luke-szendiuch-62823084"

    assert server._mobile_tool_payload("forager_person_detail_lookup", linkedin) == {
        "linkedin_public_identifier": "luke-szendiuch-62823084",
    }
    assert server._mobile_tool_payload("leadmagic_mobile_finder", linkedin) == {"profile_url": linkedin}
    assert server._mobile_tool_payload("dropleads_mobile_finder", linkedin) == {"linkedin_url": linkedin}
    assert server._mobile_tool_payload("ai_ark_mobile_phone_finder", linkedin) == {"linkedin": linkedin}
    assert (
        server._linkedin_profile_url(
            "<https://www.linkedin.com/in/luke-szendiuch-62823084|linkedin.com/in/luke-szendiuch-62823084>"
        )
        == linkedin
    )


def test_slack_mobile_lookup_extracts_nested_phone_candidate():
    import managed_agent.server as server

    result = {
        "toolResponse": {
            "raw": {
                "person": {
                    "phones": [{"type": "mobile", "number": "+1 555 010 9999"}],
                }
            }
        }
    }

    assert server._first_mobile_candidate(result) == "+1 555 010 9999"


def test_slack_mobile_lookup_falls_back_until_verified_result(monkeypatch):
    import asyncio
    import managed_agent.server as server

    class FakeMobileClient:
        def __init__(self):
            self.calls = []

        async def execute_tool(self, tool_id, payload):
            self.calls.append((tool_id, payload))
            if tool_id == "forager_person_detail_lookup":
                return {"toolResponse": {"raw": {"person": {"phones": []}}}}
            if tool_id == "leadmagic_mobile_finder":
                return {"toolResponse": {"raw": {"mobile_number": "+1 555 010 9999"}}}
            raise AssertionError(f"unexpected provider: {tool_id}")

    fake = FakeMobileClient()
    monkeypatch.setattr(server, "get_deepline_client", lambda: fake)

    linkedin, attempts, mobile = asyncio.run(
        server._execute_mobile_lookup(
            "get this person's business mobile: https://www.linkedin.com/in/luke-szendiuch-62823084"
        )
    )

    assert linkedin == "https://www.linkedin.com/in/luke-szendiuch-62823084"
    assert fake.calls == [
        (
            "forager_person_detail_lookup",
            {"linkedin_public_identifier": "luke-szendiuch-62823084"},
        ),
        ("leadmagic_mobile_finder", {"profile_url": linkedin}),
    ]
    assert attempts == [
        {"provider": "forager_person_detail_lookup", "status": "no verified business mobile returned"},
        {"provider": "leadmagic_mobile_finder", "status": "verified business mobile found"},
    ]
    assert mobile == "+1 555 010 9999"


def test_slack_handler_executes_mobile_lookup_without_native_chat(monkeypatch):
    import asyncio
    import managed_agent.server as server

    class FakeMobileClient:
        def __init__(self):
            self.execute_calls = []
            self.stream_payloads = []

        async def execute_tool(self, tool_id, payload):
            self.execute_calls.append((tool_id, payload))
            return {"toolResponse": {"raw": {"mobile_number": "+1 555 010 9999"}}}

        async def stream_agent(self, payload):
            self.stream_payloads.append(payload)
            raise AssertionError("Slack mobile lookup should execute providers directly")
            yield ""

    fake = FakeMobileClient()
    reactions = []
    posts = []

    async def fake_react(channel, ts, emoji, token, remove=False):
        reactions.append((channel, ts, emoji, token, remove))
        return True

    async def fake_post(channel, text, token, thread_ts=None):
        posts.append((channel, text, token, thread_ts))

    monkeypatch.setattr(server, "SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setattr(server, "get_deepline_client", lambda: fake)
    monkeypatch.setattr(server, "_slack_react", fake_react)
    monkeypatch.setattr(server, "_slack_post", fake_post)

    asyncio.run(
        server._handle_slack_event(
            {
                "channel": "C123",
                "user": "U123",
                "ts": "1784913061.798369",
                "text": (
                    "<@U0ANWHB4F71> get Luke's verified business mobile. "
                    "LinkedIn: <https://www.linkedin.com/in/luke-szendiuch-62823084|linkedin.com/in/luke-szendiuch-62823084>"
                ),
            },
            "T123",
        )
    )

    assert fake.stream_payloads == []
    assert fake.execute_calls == [
        (
            "forager_person_detail_lookup",
            {"linkedin_public_identifier": "luke-szendiuch-62823084"},
        )
    ]
    assert reactions[0] == ("C123", "1784913061.798369", "eyes", "xoxb-test", False)
    assert reactions[-1] == ("C123", "1784913061.798369", "eyes", "xoxb-test", True)
    assert len(posts) == 1
    assert posts[0][0] == "C123"
    assert posts[0][2] == "xoxb-test"
    assert posts[0][3] == "1784913061.798369"
    assert "forager_person_detail_lookup: verified business mobile found" in posts[0][1]
    assert "Business mobile: +1 555 010 9999" in posts[0][1]


def test_slack_oauth_requires_state_and_does_not_render_token(monkeypatch):
    import managed_agent.server as server
    import httpx

    monkeypatch.setenv("SLACK_CLIENT_ID", "client")
    monkeypatch.setenv("SLACK_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SLACK_OAUTH_STATE", "expected-state")

    class FakeResponse:
        def json(self):
            return {
                "ok": True,
                "access_token": "xoxb-secret-token",
                "team": {"id": "T123", "name": "Test Workspace"},
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: FakeClient())

    missing_state = TestClient(server.app).get("/slack/oauth_redirect?code=ok")
    assert missing_state.status_code == 403

    response = TestClient(server.app).get("/slack/oauth_redirect?code=ok&state=expected-state")

    assert response.status_code == 200
    assert "Connected to Test Workspace" in response.text
    assert "xoxb-secret-token" not in response.text


def test_plain_pipeline_questions_do_not_get_snowflake_guidance():
    from managed_agent.server import ChatRequest, _chat_payload

    payload = _chat_payload(ChatRequest(message="Summarize my pipeline risks this week."))

    assert "Snowflake/warehouse query requests" not in payload["messages"][0]["content"]


def test_unknown_workflow_preset_404s(monkeypatch):
    monkeypatch.delenv("DEEPLINE_API_KEY", raising=False)

    from managed_agent.server import app

    response = TestClient(app).get("/workflow-presets/nope")

    assert response.status_code == 404
