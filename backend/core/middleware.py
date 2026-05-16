from __future__ import annotations

import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from backend.core.request_id import new_request_id, reset_request_id, set_request_id
from backend.core.response import error_response
from backend.core.security import SENSITIVE_WRITE_PATH_PREFIXES, verify_api_token_value

logger = logging.getLogger("backend.access")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a request id to every HTTP request, response, and log line."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        token = set_request_id(request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception(
                "request_failed request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request_id=%s method=%s path=%s status=%s duration_ms=%s client=%s",
                request_id,
                request.method,
                request.url.path,
                status_code,
                duration_ms,
                request.client.host if request.client else "-",
            )
            reset_request_id(token)


class WriteTokenMiddleware(BaseHTTPMiddleware):
    """Protect sensitive write APIs when token protection is enabled."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        method = request.method.upper()
        should_check = method in {"POST", "PUT", "PATCH", "DELETE"} and any(
            path == prefix or path.startswith(f"{prefix}/") for prefix in SENSITIVE_WRITE_PATH_PREFIXES
        )
        if should_check and not verify_api_token_value(request.headers.get("X-API-Token")):
            return JSONResponse(
                status_code=401,
                content=error_response(
                    code="UNAUTHORIZED",
                    message="缺少或无效的 API Token。",
                    details={
                        "path": path,
                        "method": method,
                        "recovery_hint": "公网/生产环境写操作需要请求头 X-API-Token。",
                    },
                ),
            )
        return await call_next(request)
