from fastapi.testclient import TestClient


class FakeStreamingDeeplineClient:
    def __init__(self):
        self.stream_payloads = []
        self.execute_calls = []

    async def stream_agent(self, payload):
        self.stream_payloads.append(payload)
        yield 'data: {"type":"tool-call","toolName":"exa_search","input":{"query":"stripe"}}\n\n'
        yield 'data: {"type":"text-delta","textDelta":"Stripe is a payments company."}\n\n'
        yield "data: [DONE]\n\n"

    async def execute_tool(self, tool_id, payload):
        self.execute_calls.append((tool_id, payload))
        raise AssertionError("normal chat should stream through deeplineagent")


def test_e2e_chat_endpoint_authenticates_and_streams_through_deepline(monkeypatch):
    import managed_agent.server as server

    fake = FakeStreamingDeeplineClient()
    monkeypatch.setenv("DEEPLINE_API_KEY", "dlp_test_secret")
    monkeypatch.setenv("API_KEY", "broker-secret")
    monkeypatch.setattr(server, "get_deepline_client", lambda: fake)

    response = TestClient(server.app).post(
        "/chat",
        headers={"Authorization": "Bearer broker-secret"},
        json={"message": "Research stripe.com", "thread_id": "thread-123"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "Stripe is a payments company.",
        "thread_id": "thread-123",
    }
    assert fake.execute_calls == []
    assert len(fake.stream_payloads) == 1
    assert fake.stream_payloads[0]["response_mode"] == "stream"
    assert fake.stream_payloads[0]["messages"] == [
        {"role": "user", "content": "Research stripe.com"}
    ]
    assert "deeplineagent" in fake.stream_payloads[0]["enabledToolIds"]


def test_e2e_stream_endpoint_preserves_native_sse_and_tool_events(monkeypatch):
    import managed_agent.server as server

    fake = FakeStreamingDeeplineClient()
    monkeypatch.setenv("DEEPLINE_API_KEY", "dlp_test_secret")
    monkeypatch.setenv("API_KEY", "broker-secret")
    monkeypatch.setattr(server, "get_deepline_client", lambda: fake)

    with TestClient(server.app).stream(
        "POST",
        "/chat/stream",
        headers={"Authorization": "Bearer broker-secret"},
        json={"message": "Research stripe.com"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"type":"tool-call"' in body
    assert '"toolName":"exa_search"' in body
    assert "Stripe is a payments company." in body
    assert fake.stream_payloads[0]["prompt"] == "Research stripe.com"


def test_e2e_chat_rejects_missing_auth_before_deepline_call(monkeypatch):
    import managed_agent.server as server

    fake = FakeStreamingDeeplineClient()
    monkeypatch.setenv("DEEPLINE_API_KEY", "dlp_test_secret")
    monkeypatch.setenv("API_KEY", "broker-secret")
    monkeypatch.setattr(server, "get_deepline_client", lambda: fake)

    response = TestClient(server.app).post(
        "/chat",
        json={"message": "Research stripe.com"},
    )

    assert response.status_code == 401
    assert fake.stream_payloads == []
    assert fake.execute_calls == []


def test_e2e_chat_rejects_unallowed_tools_before_deepline_call(monkeypatch):
    import managed_agent.server as server

    fake = FakeStreamingDeeplineClient()
    monkeypatch.setenv("DEEPLINE_API_KEY", "dlp_test_secret")
    monkeypatch.setenv("API_KEY", "broker-secret")
    monkeypatch.setattr(server, "get_deepline_client", lambda: fake)

    response = TestClient(server.app).post(
        "/chat",
        headers={"Authorization": "Bearer broker-secret"},
        json={
            "message": "Research stripe.com",
            "enabledToolIds": ["hubspot_create_contact"],
        },
    )

    assert response.status_code == 400
    assert "hubspot_create_contact" in response.json()["detail"]
    assert fake.stream_payloads == []
    assert fake.execute_calls == []


def test_e2e_doctor_blocks_unsafe_local_live_write_setup(monkeypatch):
    import managed_agent.server as server

    monkeypatch.setenv("DEEPLINE_API_KEY", "dlp_test_secret")
    monkeypatch.setenv("API_KEY", "broker-secret")
    monkeypatch.setenv("LOCAL_DEV", "true")
    monkeypatch.setenv("DEEPLINE_GTM_LIVE_WRITES", "true")
    monkeypatch.delenv("DEEPLINE_HOST_URL", raising=False)
    monkeypatch.delenv("DEEPLINE_API_BASE_URL", raising=False)

    response = TestClient(server.app).get("/doctor")

    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert "dlp_test_secret" not in response.text
    checks = {check["name"]: check for check in response.json()["checks"]}
    assert checks["local_live_writes"]["status"] == "error"


def test_e2e_email_verification_falls_back_and_sanitizes_stream(monkeypatch):
    import managed_agent.server as server

    class FakeVerifierClient:
        def __init__(self):
            self.calls = []

        async def execute_tool(self, tool_id, payload):
            self.calls.append((tool_id, payload))
            if tool_id == "allegrow_validate":
                raise RuntimeError("provider unavailable")
            return {
                "status": "completed",
                "billing": {"cost": 999},
                "toolResponse": {
                    "raw": {
                        "email": payload["email"],
                        "status": "deliverable",
                        "provider": "UnitVerifier",
                        "request_id": "secret-request-id",
                    }
                },
            }

    fake = FakeVerifierClient()
    monkeypatch.setenv("DEEPLINE_API_KEY", "dlp_test_secret")
    monkeypatch.setenv("API_KEY", "broker-secret")
    monkeypatch.setattr(server, "get_deepline_client", lambda: fake)

    with TestClient(server.app).stream(
        "POST",
        "/chat/stream",
        headers={"Authorization": "Bearer broker-secret"},
        json={"message": "Verify jane@example.com and tell me if it is safe to send."},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert fake.calls == [
        ("allegrow_validate", {"email": "jane@example.com"}),
        ("leadmagic_email_validation", {"email": "jane@example.com"}),
    ]
    assert '"toolName":"allegrow_validate"' in body
    assert '"toolName":"leadmagic_email_validation"' in body
    assert "Status: deliverable" in body
    assert "secret-request-id" not in body
    assert '"billing"' not in body
