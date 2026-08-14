# Deepline GTM Agent v2 Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate `deepline-gtm-agent` from custom LangGraph/CLI-wrapper execution to Deepline v2 SDK and native Deepline agent/chat surfaces, then redeploy it as an Anthropic Managed Agent broker.

**Architecture:** Keep the public FastAPI broker for REST, web chat, and Slack, but make Deepline v2 the source of truth for tool discovery, execution, plays, run state, and chat streaming. Remove the in-process LangGraph tool wrapper and stop uploading/patching the Deepline CLI into every Anthropic session; the managed agent should call Deepline through configured v2 SDK/API surfaces using workspace-scoped credentials and Deepline-managed plays.

**Tech Stack:** Python 3.12, FastAPI, Anthropic Managed Agents SDK, Deepline v2 REST/SDK contract, Deepline native `deeplineagent` streaming endpoint, Deepline plays, pytest, httpx.

---

## Current Implementation Review

`deepline-gtm-agent` currently has two competing implementations:

- Root LangGraph app: `server.py`, `deepline_gtm_agent/agent.py`, `deepline_gtm_agent/tools.py`, `deepline_gtm_agent/deepline.py`.
- Managed agent broker: `managed_agent/server.py`, `managed_agent/session.py`, `managed_agent/setup.py`.

The root app builds a Deep Agents/LangGraph agent with Python tool functions and a dynamic `deepline_call` tool. The Deepline client is a hand-written wrapper in `deepline_gtm_agent/deepline.py` that posts to `/api/v2/integrations/{operation}/execute`, unwraps response envelopes itself, and falls back to CLI subprocess execution.

The managed app is closer to the desired deployment model, but still bootstraps by uploading the Deepline binary, uploading local auth files, patching the CLI zipapp for proxy behavior, and embedding a large CLI runbook into the agent prompt. That makes every session depend on local filesystem auth and session bootstrap scripts instead of Deepline-owned setup.

`deepline-api` already has the v2 surfaces this repo should use:

- SDK client: `../deepline-api/sdk/src/client.ts` exposes `DeeplineClient.executeTool`, `searchTools`, `getTool`, `startPlayRun`, `runPlay`, and run status/tail helpers.
- High-level SDK: `../deepline-api/sdk/src/play.ts` exposes `Deepline.connect()`, `deepline.tools.execute`, and named play handles.
- Native tool execution route: `../deepline-api/src/app/api/v2/integrations/[toolId]/execute/route.ts`.
- Legacy route warning: `../deepline-api/src/app/api/v2/integrations/execute/route.ts` explicitly says to use `/api/v2/integrations/{toolId}/execute`.
- Native AI/chat stream: `../deepline-api/src/app/api/v2/integrations/[toolId]/stream/route.ts` streams only `deeplineagent` through `streamDeeplineAgent`.
- Native chat implementation: `../deepline-api/src/lib/deeplineagent/runtime.ts` uses Vercel AI SDK `streamText()` and `toUIMessageStreamResponse()`, with Deepline-managed tool execution and billing.
- Plays API: `../deepline-api/src/app/api/v2/plays/run/route.ts` and SDK methods in `../deepline-api/sdk/src/client.ts`.

## Migration Principles

- Deepline owns GTM workflow setup: provider routing, plays, tool metadata, billing, and run state should live in Deepline v2, not in Python prompt strings.
- The agent broker should not invent a second SDK: remove `deepline_gtm_agent/deepline.py` and replace it with a small typed v2 client or generated SDK bridge.
- Native chat first: web chat and Slack should stream from Deepline’s `deeplineagent` stream endpoint rather than reimplementing streaming, tool events, and markdown assembly.
- Plays over loops: batch/list workflows should call Deepline plays or `deepline plays` equivalents through the v2 API, not Python loops over `tools execute`.
- Keep the managed agent deployment, but shrink it: Anthropic Managed Agents can remain the hosted operator runtime, while Deepline provides all GTM execution surfaces.

---

### Task 1: Pin the v2 Contract and Add a Python Deepline v2 Client

**Files:**
- Create: `deepline_gtm_agent/v2_client.py`
- Create: `tests/test_v2_client.py`
- Modify: `pyproject.toml`

**Step 1: Write the failing tests**

Create `tests/test_v2_client.py`:

```python
import httpx
import pytest

from deepline_gtm_agent.v2_client import DeeplineV2Client


@pytest.mark.asyncio
async def test_execute_tool_uses_v2_tool_route():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["headers"] = dict(request.headers)
        seen["json"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "toolResponse": {"raw": {"email": "jane@acme.com"}},
            },
        )

    transport = httpx.MockTransport(handler)
    client = DeeplineV2Client(
        api_key="dl_test",
        base_url="https://code.deepline.com",
        transport=transport,
    )

    result = await client.execute_tool("hunter_email_finder", {"domain": "acme.com"})

    assert seen["path"] == "/api/v2/integrations/hunter_email_finder/execute"
    assert seen["headers"]["authorization"] == "Bearer dl_test"
    assert seen["headers"]["x-deepline-execute-response-contract"] == "v2-tool-response"
    assert result["toolResponse"]["raw"]["email"] == "jane@acme.com"


@pytest.mark.asyncio
async def test_stream_agent_uses_native_deeplineagent_stream_route():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2/integrations/deeplineagent/stream"
        assert request.headers["authorization"] == "Bearer dl_test"
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b'data: {"type":"text-delta","textDelta":"hello"}\n\n',
        )

    client = DeeplineV2Client(
        api_key="dl_test",
        base_url="https://code.deepline.com",
        transport=httpx.MockTransport(handler),
    )

    chunks = [chunk async for chunk in client.stream_agent({"prompt": "hi"})]

    assert chunks == ['data: {"type":"text-delta","textDelta":"hello"}\n\n']
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_v2_client.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'deepline_gtm_agent.v2_client'`.

**Step 3: Write minimal implementation**

Create `deepline_gtm_agent/v2_client.py`:

```python
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

V2_EXECUTE_RESPONSE_CONTRACT = "v2-tool-response"


class DeeplineV2Client:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key or os.environ["DEEPLINE_API_KEY"]
        self.base_url = (base_url or os.environ.get("DEEPLINE_HOST_URL") or "https://code.deepline.com").rstrip("/")
        self._transport = transport
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "x-deepline-execute-response-contract": V2_EXECUTE_RESPONSE_CONTRACT,
        }

    async def execute_tool(self, tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as http:
            response = await http.post(
                f"/api/v2/integrations/{tool_id}/execute",
                headers=self._headers(),
                json={"payload": payload},
            )
            response.raise_for_status()
            return response.json()

    async def stream_agent(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=None,
            transport=self._transport,
        ) as http:
            async with http.stream(
                "POST",
                "/api/v2/integrations/deeplineagent/stream",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_text():
                    if chunk:
                        yield chunk
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_v2_client.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml deepline_gtm_agent/v2_client.py tests/test_v2_client.py
git commit -m "feat: add deepline v2 client"
```

---

### Task 2: Replace the Custom Deepline Wrapper in Root Tooling

**Files:**
- Modify: `deepline_gtm_agent/deepline.py`
- Modify: `deepline_gtm_agent/dynamic_tools.py`
- Test: `tests/test_v2_client.py`

**Step 1: Write the failing test**

Extend `tests/test_v2_client.py`:

```python
def test_legacy_deepline_execute_is_removed_from_public_path():
    import inspect
    import deepline_gtm_agent.deepline as deepline

    source = inspect.getsource(deepline)
    assert "subprocess" not in source
    assert "/api/v2/integrations/{operation}/execute" not in source
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_v2_client.py::test_legacy_deepline_execute_is_removed_from_public_path -v`

Expected: FAIL because `deepline_gtm_agent/deepline.py` imports `subprocess`.

**Step 3: Write minimal implementation**

Change `deepline_gtm_agent/deepline.py` into a compatibility shim:

```python
import asyncio
from typing import Any

from deepline_gtm_agent.v2_client import DeeplineV2Client


def deepline_execute(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Compatibility shim for old LangGraph tools; new code should use DeeplineV2Client."""
    async def _run() -> dict[str, Any]:
        return await DeeplineV2Client().execute_tool(operation, payload)

    return asyncio.run(_run())
```

Update `deepline_gtm_agent/dynamic_tools.py` so catalog loading prefers v2 SDK routes:

```python
# replace /api/v2/integrations/list usage with /api/v2/tools/search?q=
# or /api/v2/tools depending on whether the caller needs ranked search.
```

Do not add new fallback CLI code.

**Step 4: Run tests**

Run: `pytest tests/test_v2_client.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add deepline_gtm_agent/deepline.py deepline_gtm_agent/dynamic_tools.py tests/test_v2_client.py
git commit -m "refactor: route deepline execution through v2 client"
```

---

### Task 3: Make Managed Web Chat Use Native Deepline Agent Streaming

**Files:**
- Modify: `managed_agent/server.py`
- Modify: `managed_agent/chat.html`
- Test: `tests/test_managed_chat_v2.py`

**Step 1: Write the failing test**

Create `tests/test_managed_chat_v2.py`:

```python
import inspect


def test_managed_server_uses_deeplineagent_stream_not_anthropic_session_loop():
    import managed_agent.server as server

    source = inspect.getsource(server)
    assert "/api/v2/integrations/deeplineagent/stream" in source
    assert "stream_events(" not in source
    assert "BOOTSTRAP_MSG" not in source
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_managed_chat_v2.py -v`

Expected: FAIL because `managed_agent/server.py` imports `stream_events` and `BOOTSTRAP_MSG`.

**Step 3: Write minimal implementation**

In `managed_agent/server.py`:

- Remove `create_session`, `send_message`, `stream_events`, and `BOOTSTRAP_MSG` from the web chat path.
- Import `DeeplineV2Client` from `deepline_gtm_agent.v2_client`.
- Change `ChatRequest` to include `message`, optional `messages`, optional `thread_id`, and optional `enabled_tool_ids`.
- Implement `/chat/stream` as a direct proxy to `DeeplineV2Client.stream_agent()`.
- Preserve bearer auth and CORS behavior.

Payload shape:

```python
payload = {
    "prompt": req.message,
    "messages": req.messages or [{"role": "user", "content": req.message}],
    "enabledToolIds": req.enabled_tool_ids,
    "response_mode": "stream",
}
```

Keep `/chat` by collecting the native stream into text for non-streaming callers.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_managed_chat_v2.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add managed_agent/server.py managed_agent/chat.html tests/test_managed_chat_v2.py
git commit -m "feat: stream managed chat through deeplineagent"
```

---

### Task 4: Remove Per-Session CLI Upload and Bootstrap From Managed Sessions

**Files:**
- Modify: `managed_agent/session.py`
- Modify: `managed_agent/setup.py`
- Modify: `managed_agent/Dockerfile`
- Modify: `managed_agent/env.example`
- Test: `tests/test_managed_no_cli_bootstrap.py`

**Step 1: Write the failing test**

Create `tests/test_managed_no_cli_bootstrap.py`:

```python
from pathlib import Path


def test_managed_agent_does_not_upload_cli_or_auth_files():
    session_source = Path("managed_agent/session.py").read_text()
    setup_source = Path("managed_agent/setup.py").read_text()
    dockerfile = Path("managed_agent/Dockerfile").read_text()

    combined = session_source + setup_source + dockerfile

    assert "deepline-auth.env" not in combined
    assert "/mnt/session/uploads/workspace/deepline" not in combined
    assert "zipapp" not in combined
    assert "NODE_TLS_REJECT_UNAUTHORIZED=0" not in combined
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_managed_no_cli_bootstrap.py -v`

Expected: FAIL because current managed setup uploads auth, copies CLI, and patches zipapp.

**Step 3: Write minimal implementation**

- Delete `_upload_resources()` usage for Deepline binary/auth from `managed_agent/session.py`.
- Keep Anthropic session creation only if still needed for Anthropic Managed Agent redeploy tests.
- Replace `BOOTSTRAP_MSG` with a short user task wrapper that says Deepline is configured through the v2 API and no CLI bootstrap is required.
- Remove CLI install from `managed_agent/Dockerfile`.
- Change `managed_agent/env.example` to use `DEEPLINE_API_KEY`, `DEEPLINE_HOST_URL`, `ANTHROPIC_API_KEY`, `MANAGED_AGENT_ID`, and `MANAGED_ENVIRONMENT_ID`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_managed_no_cli_bootstrap.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add managed_agent/session.py managed_agent/setup.py managed_agent/Dockerfile managed_agent/env.example tests/test_managed_no_cli_bootstrap.py
git commit -m "refactor: remove managed agent cli bootstrap"
```

---

### Task 5: Move GTM Workflows to Deepline Plays

**Files:**
- Create: `plays/gtm-person-email.play.ts`
- Create: `plays/gtm-company-research.play.ts`
- Create: `plays/gtm-prospect-search.play.ts`
- Modify: `README.md`
- Test: `tests/test_play_contracts.py`

**Step 1: Write the failing test**

Create `tests/test_play_contracts.py`:

```python
from pathlib import Path


def test_gtm_plays_exist_and_use_deepline_sdk():
    for path in [
        "plays/gtm-person-email.play.ts",
        "plays/gtm-company-research.play.ts",
        "plays/gtm-prospect-search.play.ts",
    ]:
        source = Path(path).read_text()
        assert "definePlay" in source
        assert "ctx.tools.execute" in source or "ctx.runPlay" in source
        assert "deepline_gtm_agent" not in source
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_play_contracts.py -v`

Expected: FAIL because `plays/` does not exist.

**Step 3: Write minimal implementation**

Create the three play files as Deepline SDK plays. Keep them small:

```ts
import { definePlay } from 'deepline';

export default definePlay('gtm-person-email', async (ctx, input) => {
  const linkedin = typeof input.linkedin_url === 'string' ? input.linkedin_url : undefined;
  const domain = typeof input.domain === 'string' ? input.domain : undefined;
  return await ctx.runPlay('prebuilt/person-linkedin-to-email', {
    ...input,
    linkedin_url: linkedin,
    domain,
  });
});
```

Use existing prebuilt plays when possible:

- Person email: `prebuilt/person-linkedin-to-email` or `prebuilt/person-to-email`.
- Company research: call `deeplineagent` with constrained research tools or use an existing research play if present in `deepline-api`.
- Prospect search: call provider tools through `ctx.tools.execute` or reference an existing prebuilt prospecting play once available.

Run Deepline validation from `../deepline-api` if the local SDK is linked:

```bash
cd /Users/jaitoor/dev/deepline-api
bun run deepline -- plays check /Users/jaitoor/dev/deepline-gtm-agent/plays/gtm-person-email.play.ts
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_play_contracts.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add plays README.md tests/test_play_contracts.py
git commit -m "feat: move gtm workflows to deepline plays"
```

---

### Task 6: Simplify Slack to a Thin Native Chat Adapter

**Files:**
- Modify: `managed_agent/server.py`
- Modify: `deepline_gtm_agent/formatting.py`
- Test: `tests/test_slack_native_chat_adapter.py`

**Step 1: Write the failing test**

Create `tests/test_slack_native_chat_adapter.py`:

```python
import inspect


def test_slack_handler_uses_native_chat_stream():
    import managed_agent.server as server

    source = inspect.getsource(server)
    assert "DeeplineV2Client" in source
    assert "create_session(" not in source
    assert "stream_events(" not in source
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_slack_native_chat_adapter.py -v`

Expected: FAIL because Slack currently creates Anthropic sessions directly.

**Step 3: Write minimal implementation**

In `_handle_slack_event`:

- Keep Slack signature verification, dedupe, reactions, thread history fetch, and `chat.postMessage`.
- Replace Anthropic session creation with `DeeplineV2Client.stream_agent()`.
- Send prior Slack thread context as `messages`, not as prompt text glued to bootstrap instructions.
- Convert final text to Slack markdown with `md_to_slack`.
- Do not stream every token to Slack; collect text and post one or chunked final response.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_slack_native_chat_adapter.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add managed_agent/server.py deepline_gtm_agent/formatting.py tests/test_slack_native_chat_adapter.py
git commit -m "refactor: make slack a native chat adapter"
```

---

### Task 7: Deprecate the LangGraph App and Remove Duplicate Tool Logic

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`
- Modify: `server.py`
- Modify: `deepline_gtm_agent/agent.py`
- Modify: `deepline_gtm_agent/tools.py`
- Modify: `tests/run_evals.py`

**Step 1: Write the failing test**

Create or update `tests/test_no_langgraph_default.py`:

```python
from pathlib import Path


def test_langgraph_is_not_default_runtime():
    readme = Path("README.md").read_text().lower()
    pyproject = Path("pyproject.toml").read_text()

    assert "managed agent" in readme
    assert "langgraph" not in readme.split("quickstart", 1)[0]
    assert '"deepagents>=0.4"' not in pyproject
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_no_langgraph_default.py -v`

Expected: FAIL because `deepagents` is a dependency and README presents LangGraph as a deployment option.

**Step 3: Write minimal implementation**

- Move LangGraph files under `legacy_langgraph/` or mark them explicitly deprecated.
- Remove `deepagents`, `langchain-anthropic`, and `langchain-openai` from default dependencies.
- Keep only FastAPI/httpx/anthropic requirements required by the managed broker.
- Update `tests/run_evals.py` to evaluate deployed `/chat` and `/chat/stream` responses through native chat and Deepline run IDs, not LangGraph tool calls.

**Step 4: Run tests**

Run:

```bash
pytest tests/test_no_langgraph_default.py tests/test_v2_client.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md pyproject.toml server.py deepline_gtm_agent/agent.py deepline_gtm_agent/tools.py tests/run_evals.py tests/test_no_langgraph_default.py
git commit -m "chore: deprecate langgraph runtime"
```

---

### Task 8: Add End-to-End v2 Smoke Tests

**Files:**
- Create: `tests/test_v2_smoke.py`
- Modify: `tests/evals.yml`
- Modify: `tests/run_evals.py`

**Step 1: Write the smoke tests**

Create `tests/test_v2_smoke.py`:

```python
import os

import pytest

from deepline_gtm_agent.v2_client import DeeplineV2Client


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_tool_search_and_execute_contract():
    if not os.environ.get("DEEPLINE_API_KEY"):
        pytest.skip("DEEPLINE_API_KEY required")

    client = DeeplineV2Client()
    result = await client.execute_tool("test_company_search", {"domain": "stripe.com"})

    assert result["status"] in {"completed", "success"}
    assert "toolResponse" in result


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_deeplineagent_stream_contract():
    if not os.environ.get("DEEPLINE_API_KEY"):
        pytest.skip("DEEPLINE_API_KEY required")

    client = DeeplineV2Client()
    chunks = []
    async for chunk in client.stream_agent({"prompt": "Say ok in one word.", "maxToolCalls": 0}):
        chunks.append(chunk)
        if len(chunks) > 3:
            break

    assert chunks
```

**Step 2: Run non-live tests**

Run: `pytest tests/test_v2_smoke.py -v`

Expected: SKIPPED if `DEEPLINE_API_KEY` is not set.

**Step 3: Run live tests before redeploy**

Run:

```bash
DEEPLINE_API_KEY=... pytest tests/test_v2_smoke.py -v -m live
```

Expected: PASS.

**Step 4: Commit**

```bash
git add tests/test_v2_smoke.py tests/evals.yml tests/run_evals.py
git commit -m "test: add deepline v2 smoke coverage"
```

---

### Task 9: Update Deployment for Anthropic Managed Agents

**Files:**
- Modify: `managed_agent/setup.py`
- Modify: `managed_agent/README.md`
- Modify: `railway.toml`
- Modify: `managed_agent/railway.toml`
- Modify: `managed_agent/Dockerfile`

**Step 1: Write deployment checklist into README**

Update `managed_agent/README.md` with:

```md
## v2 Deployment

Required environment variables:

- `ANTHROPIC_API_KEY`
- `DEEPLINE_API_KEY`
- `DEEPLINE_HOST_URL=https://code.deepline.com`
- `MANAGED_AGENT_ID`
- `MANAGED_ENVIRONMENT_ID`
- `API_KEY` for broker auth
- `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET` for Slack

The broker does not upload Deepline CLI binaries or local auth files. Deepline tools,
plays, billing, and provider credentials are configured in Deepline.
```

**Step 2: Update setup**

In `managed_agent/setup.py`, make the Anthropic managed agent prompt say:

```text
You are a concise GTM operator. Use Deepline v2 through the broker-provided native chat/tool endpoints. Do not run or bootstrap a local Deepline CLI. Do not ask users for provider API keys; provider credentials and billing are configured in Deepline.
```

**Step 3: Verify Docker and Railway**

Run:

```bash
docker build -f managed_agent/Dockerfile -t deepline-gtm-agent-v2 .
```

Expected: image builds without installing or copying the Deepline CLI.

**Step 4: Commit**

```bash
git add managed_agent/setup.py managed_agent/README.md railway.toml managed_agent/railway.toml managed_agent/Dockerfile
git commit -m "chore: update managed agent v2 deployment"
```

---

### Task 10: Final Verification and Cutover

**Files:**
- Modify: `README.md`
- Modify: `BLOG_POST.md` if it remains published from this repo
- Modify: `SETUP.md`

**Step 1: Run unit tests**

Run:

```bash
pytest tests -v
```

Expected: PASS, with live tests skipped unless `DEEPLINE_API_KEY` is set.

**Step 2: Run live v2 smoke tests**

Run:

```bash
DEEPLINE_API_KEY=... pytest tests/test_v2_smoke.py -v -m live
```

Expected: PASS.

**Step 3: Start the broker locally**

Run:

```bash
cd managed_agent
DEEPLINE_API_KEY=... ANTHROPIC_API_KEY=... python server.py
```

Expected: server starts on `http://localhost:8000`.

**Step 4: Test chat stream**

Run:

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"Research stripe.com in 3 bullets."}'
```

Expected: SSE stream from native Deepline chat with text chunks and a terminal event.

**Step 5: Test Slack in staging**

Send a Slack DM:

```text
Research stripe.com and summarize ICP fit for a sales intelligence tool.
```

Expected: one concise threaded response, no bootstrap text, no CLI/DNS/proxy narration.

**Step 6: Redeploy**

Deploy the managed broker with v2 environment variables. Do not deploy the root LangGraph server as the default runtime.

**Step 7: Commit final docs**

```bash
git add README.md SETUP.md BLOG_POST.md
git commit -m "docs: document deepline v2 migration"
```

---

## Open Decisions Before Execution

- Whether to keep Anthropic Managed Agents as an outer operator runtime once native `deeplineagent` streaming handles chat. If the managed agent is only brokering native Deepline chat, it may no longer need Anthropic sessions for normal `/chat` and Slack requests.
- Whether `deepline-api` should expose a first-class Python SDK package. If yes, replace the local `DeeplineV2Client` with the official SDK instead of maintaining even a small client.
- Which GTM workflows should become first-class prebuilt Deepline plays in `deepline-api` versus repo-local `.play.ts` files in `deepline-gtm-agent`.
- Whether old LangGraph evals that assert Python tool names should be deleted or rewritten to assert Deepline v2 run/tool events.

## Done Criteria

- No default runtime path imports `deepagents`, `langchain`, or the old `deepline_execute` HTTP wrapper.
- No managed runtime uploads `deepline-auth.env`, copies a local CLI binary, patches zipapps, or sets `NODE_TLS_REJECT_UNAUTHORIZED=0`.
- `/chat/stream` uses `/api/v2/integrations/deeplineagent/stream`.
- Tool execution uses `/api/v2/integrations/{toolId}/execute` with `x-deepline-execute-response-contract: v2-tool-response`.
- Batch/list workflows are Deepline plays or prebuilt plays.
- Slack is a thin adapter around native chat.
- Tests cover native stream proxying, v2 tool execution, no CLI bootstrap, and live v2 smoke behavior.
