import pytest

from managed_agent.reply_copilot import (
    DraftResult,
    ReplyCopilotService,
    build_draft_prompt,
    choose_route,
    extract_headcount,
    normalize_monitor_row,
    slack_gate_blocks,
)


class FakeClient:
    def __init__(self):
        self.calls = []

    async def execute_tool(self, tool_id, payload):
        self.calls.append((tool_id, payload))
        raise AssertionError("no external tool should run")


def sample_event():
    return normalize_monitor_row(
        {
            "delivery_id": "del_1",
            "event_type": "emailsReplied",
            "contact_id": "ctc_1",
            "lead_id": "lea_1",
            "lead_email": "ada@example.com",
            "lead_first_name": "Ada",
            "lead_last_name": "Lovelace",
            "company_domain": "example.com",
            "reply_text": "Can you send more details?",
        }
    )


def test_headcount_routing_boundary():
    assert choose_route(51) == "meeting"
    assert choose_route(50) == "plg"
    assert choose_route(1) == "plg"
    assert choose_route(None) == "manual"


def test_headcount_extraction_uses_exact_numeric_fields_only():
    assert extract_headcount({"company": {"employee_count": "1,250"}}) == 1250
    assert extract_headcount({"company": {"employee_range": "51-200"}}) is None


def test_monitor_normalization_rejects_non_reply_events():
    row = sample_event()
    assert row.reply_text == "Can you send more details?"
    try:
        normalize_monitor_row({"delivery_id": "x", "event_type": "emailsOpened"})
    except ValueError as exc:
        assert "unsupported event_type" in str(exc)
    else:
        raise AssertionError("expected non-reply event to fail")


def test_prompt_preserves_route_and_missing_promo_url(monkeypatch):
    monkeypatch.delenv("REPLY_COPILOT_PROMO_URL", raising=False)
    prompt = build_draft_prompt(sample_event(), [], [], {"employee_count": 25}, 25)
    assert "Route: plg" in prompt
    assert "NOT CONFIGURED" in prompt
    assert "must not be changed" in prompt


def test_slack_gate_has_approve_edit_reject_actions():
    draft = DraftResult(
        classification="question",
        confidence="HIGH",
        contextual_analysis="They asked a direct product question.",
        missing_context=[],
        company_headcount=75,
        recommended_route="meeting",
        draft="happy to show you. grab time here.",
    )
    blocks = slack_gate_blocks(sample_event(), draft)
    actions = [element["action_id"] for block in blocks if block["type"] == "actions" for element in block["elements"]]
    assert actions == ["reply_approve", "reply_edit", "reply_reject"]


@pytest.mark.asyncio
async def test_approval_never_sends_when_live_writes_are_disabled(monkeypatch):
    monkeypatch.delenv("DEEPLINE_GTM_LIVE_WRITES", raising=False)
    client = FakeClient()
    service = ReplyCopilotService(client=client)
    queries = []
    notes = []

    async def draft_row(_delivery_id):
        return {"delivery_id": "del_1", "draft_text": "hello"}

    async def query(sql):
        queries.append(sql)
        return []

    async def update_gate(_row, note, keep_actions=False):
        notes.append(note)

    service._draft_row = draft_row
    service._query = query
    service._update_gate = update_gate

    await service.approve("del_1", "U123")

    assert client.calls == []
    assert any("approved_pending_live_writes" in sql for sql in queries)
    assert notes == ["Approved. Live writes are disabled, so nothing was sent."]
