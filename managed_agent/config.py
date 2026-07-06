"""Configuration diagnostics for the Deepline GTM broker.

The broker should stay thin: it validates transport/setup concerns and delegates
GTM execution, provider routing, plays, run state, billing, and workflow logic to
Deepline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


DEEPLINE_PRODUCTION_HOST = "https://code.deepline.com"
_LOCAL_HOST_MARKERS = ("localhost", "127.0.0.1", "0.0.0.0", "::1")


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def _env_flag(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    value = env.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def deepline_host(env: Mapping[str, str] | None = None) -> str:
    resolved_env = env or os.environ
    return (
        resolved_env.get("DEEPLINE_HOST_URL")
        or resolved_env.get("DEEPLINE_API_BASE_URL")
        or DEEPLINE_PRODUCTION_HOST
    ).rstrip("/")


def is_local_host(value: str | None) -> bool:
    if not value:
        return False
    return any(marker in value.lower() for marker in _LOCAL_HOST_MARKERS)


def live_writes_enabled(env: Mapping[str, str] | None = None) -> bool:
    return _env_flag(env or os.environ, "DEEPLINE_GTM_LIVE_WRITES", default=False)


def config_checks(env: Mapping[str, str] | None = None) -> list[Check]:
    resolved_env = env or os.environ
    checks: list[Check] = []

    checks.append(
        Check(
            "deepline_api_key",
            "ok" if resolved_env.get("DEEPLINE_API_KEY") else "error",
            "configured" if resolved_env.get("DEEPLINE_API_KEY") else "missing DEEPLINE_API_KEY",
        )
    )

    if resolved_env.get("API_KEY"):
        auth_status = "ok"
        auth_detail = "chat endpoints require bearer auth"
    elif _env_flag(resolved_env, "ALLOW_UNAUTHENTICATED", default=False):
        auth_status = "warning"
        auth_detail = "ALLOW_UNAUTHENTICATED is enabled; use only for local development"
    else:
        auth_status = "error"
        auth_detail = "chat endpoints fail closed until API_KEY is set"
    checks.append(Check("chat_auth", auth_status, auth_detail))

    cors_origins = [o.strip() for o in resolved_env.get("CORS_ORIGINS", "").split(",") if o.strip()]
    if not cors_origins:
        cors_status = "ok"
        cors_detail = "browser CORS disabled by default"
    elif "*" in cors_origins:
        cors_status = "error"
        cors_detail = "wildcard CORS is not allowed for this broker"
    else:
        cors_status = "ok"
        cors_detail = f"{len(cors_origins)} explicit origin(s) configured"
    checks.append(Check("cors", cors_status, cors_detail))

    host = deepline_host(resolved_env)
    local_runtime = is_local_host(resolved_env.get("RAILWAY_PUBLIC_DOMAIN")) is False and (
        _env_flag(resolved_env, "LOCAL_DEV", default=False)
        or is_local_host(resolved_env.get("HOST"))
        or is_local_host(resolved_env.get("VERCEL_URL"))
    )
    if local_runtime and host == DEEPLINE_PRODUCTION_HOST and live_writes_enabled(resolved_env):
        checks.append(
            Check(
                "local_live_writes",
                "error",
                "local runtime points at production Deepline with live writes enabled",
            )
        )
    else:
        checks.append(
            Check(
                "local_live_writes",
                "ok" if not live_writes_enabled(resolved_env) else "warning",
                "live write mode disabled"
                if not live_writes_enabled(resolved_env)
                else "live write mode enabled; require explicit approvals",
            )
        )

    if resolved_env.get("SLACK_BOT_TOKEN") and resolved_env.get("SLACK_SIGNING_SECRET"):
        slack_status = "ok"
        slack_detail = "Slack bot token and signing secret configured"
    elif resolved_env.get("SLACK_BOT_TOKEN") or resolved_env.get("SLACK_SIGNING_SECRET"):
        slack_status = "warning"
        slack_detail = "Slack is partially configured"
    else:
        slack_status = "ok"
        slack_detail = "Slack not configured"
    checks.append(Check("slack", slack_status, slack_detail))

    return checks


def config_summary(env: Mapping[str, str] | None = None) -> dict[str, object]:
    checks = config_checks(env)
    if any(check.status == "error" for check in checks):
        status = "error"
    elif any(check.status == "warning" for check in checks):
        status = "warning"
    else:
        status = "ok"
    return {
        "status": status,
        "host": deepline_host(env),
        "live_writes": live_writes_enabled(env),
        "checks": [check.as_dict() for check in checks],
    }
