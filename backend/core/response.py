from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.core.request_id import get_request_id


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def success_response(
    data: Any = None,
    *,
    code: str = "OK",
    message: str = "success",
) -> dict[str, Any]:
    return {
        "success": True,
        "code": code,
        "message": message,
        "data": data,
        "request_id": get_request_id(),
        "timestamp": now_iso(),
    }


def error_response(
    *,
    code: str,
    message: str,
    details: Any = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "code": code,
        "message": message,
        "details": details or {},
        "request_id": get_request_id(),
        "timestamp": now_iso(),
    }
