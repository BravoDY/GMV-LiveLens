from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Header, HTTPException

from backend.core.config import get_settings

SENSITIVE_WRITE_PATH_PREFIXES = (
    "/api/settings",
    "/api/scheduler/start",
    "/api/scheduler/pause",
    "/api/tasks",
    "/api/shops/init",
    "/api/shops/bind",
    "/api/edge-sessions",
    "/api/platforms",
    "/api/window-preview",
    "/api/test-ocr",
    "/api/dashboard-cache/refresh",
)


def is_write_token_required() -> bool:
    settings = get_settings()
    return settings.require_api_token or settings.is_production


def verify_api_token_value(token: str | None) -> bool:
    settings = get_settings()
    if not is_write_token_required():
        return True
    if not settings.api_token:
        return False
    return secrets.compare_digest(str(token or ""), settings.api_token)


def require_api_token(x_api_token: Annotated[str | None, Header(alias="X-API-Token")] = None) -> None:
    if verify_api_token_value(x_api_token):
        return
    raise HTTPException(
        status_code=401,
        detail={
            "code": "UNAUTHORIZED",
            "message": "缺少或无效的 API Token。",
            "recovery_hint": "请在请求头 X-API-Token 中提供有效 token，或检查 GMV_API_TOKEN 配置。",
        },
    )


def public_security_status() -> dict[str, object]:
    settings = get_settings()
    return {
        "app_env": settings.app_env,
        "require_api_token": is_write_token_required(),
        "api_token_configured": bool(settings.api_token),
        "debug_api_enabled": settings.debug_api_enabled,
    }
