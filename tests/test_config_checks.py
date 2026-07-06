from managed_agent.config import config_summary


def test_config_summary_requires_deepline_key_and_chat_auth():
    summary = config_summary({})

    assert summary["status"] == "error"
    checks = {check["name"]: check for check in summary["checks"]}
    assert checks["deepline_api_key"]["status"] == "error"
    assert checks["chat_auth"]["status"] == "error"
    assert checks["cors"]["status"] == "ok"


def test_config_summary_accepts_explicit_auth_and_origins():
    summary = config_summary(
        {
            "DEEPLINE_API_KEY": "dlp_test",
            "API_KEY": "broker-secret",
            "CORS_ORIGINS": "https://app.example,https://admin.example",
        }
    )

    assert summary["status"] == "ok"
    checks = {check["name"]: check for check in summary["checks"]}
    assert checks["chat_auth"]["status"] == "ok"
    assert checks["cors"]["detail"] == "2 explicit origin(s) configured"


def test_config_summary_rejects_wildcard_cors():
    summary = config_summary(
        {
            "DEEPLINE_API_KEY": "dlp_test",
            "API_KEY": "broker-secret",
            "CORS_ORIGINS": "*",
        }
    )

    checks = {check["name"]: check for check in summary["checks"]}
    assert summary["status"] == "error"
    assert checks["cors"]["status"] == "error"
    assert "wildcard" in checks["cors"]["detail"]


def test_config_summary_blocks_local_runtime_with_production_live_writes():
    summary = config_summary(
        {
            "DEEPLINE_API_KEY": "dlp_test",
            "API_KEY": "broker-secret",
            "LOCAL_DEV": "true",
            "DEEPLINE_GTM_LIVE_WRITES": "true",
        }
    )

    checks = {check["name"]: check for check in summary["checks"]}
    assert summary["status"] == "error"
    assert checks["local_live_writes"]["status"] == "error"


def test_config_summary_allows_local_runtime_when_live_writes_are_disabled():
    summary = config_summary(
        {
            "DEEPLINE_API_KEY": "dlp_test",
            "API_KEY": "broker-secret",
            "LOCAL_DEV": "true",
        }
    )

    checks = {check["name"]: check for check in summary["checks"]}
    assert summary["status"] == "ok"
    assert checks["local_live_writes"]["status"] == "ok"
