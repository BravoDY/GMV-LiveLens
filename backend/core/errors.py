from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.core.response import error_response

HTTP_STATUS_CODE_MAP = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
}


def _detail_to_code_message_details(detail: Any, fallback_code: str) -> tuple[str, str, Any]:
    if isinstance(detail, dict):
        code = str(detail.get("reason_code") or detail.get("code") or fallback_code).upper()
        message = str(detail.get("error") or detail.get("message") or code)
        return code, message, detail
    if isinstance(detail, str):
        normalized = detail.strip()
        code = normalized.upper() if normalized and normalized.isascii() else fallback_code
        return code, normalized or fallback_code, {"detail": detail}
    return fallback_code, fallback_code, {"detail": detail}


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    fallback_code = HTTP_STATUS_CODE_MAP.get(exc.status_code, "HTTP_ERROR")
    code, message, details = _detail_to_code_message_details(exc.detail, fallback_code)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(code=code, message=message, details=details),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_response(
            code="VALIDATION_ERROR",
            message="请求参数校验失败",
            details={"errors": exc.errors()},
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_response(
            code="INTERNAL_ERROR",
            message="服务内部异常，请根据 request_id 查看后端日志。",
            details={},
        ),
    )
