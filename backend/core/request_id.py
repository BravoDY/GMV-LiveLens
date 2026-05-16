from __future__ import annotations

import contextvars
import time
import uuid

_REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def new_request_id() -> str:
    """Create a compact request id for API responses and logs."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"req_{timestamp}_{suffix}"


def set_request_id(request_id: str) -> contextvars.Token[str]:
    return _REQUEST_ID.set(request_id or "-")


def reset_request_id(token: contextvars.Token[str]) -> None:
    _REQUEST_ID.reset(token)


def get_request_id() -> str:
    return _REQUEST_ID.get()
