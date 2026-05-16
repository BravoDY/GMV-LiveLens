from __future__ import annotations

import asyncio
import base64
import io
import json as _json
import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import HTTPException, WebSocket
from PIL import Image
from pydantic import BaseModel, Field, field_validator

from backend.collectors.remote_edge import EdgeActionTimeoutError, remote_edge_manager
from backend.models import CaptureTask
from backend.services import edge_binding, shop_config, store

ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "frontend"
_SHOPS_DEFAULT_PATH = ROOT_DIR / "data" / "shops_default.json"

clients: set[WebSocket] = set()


def screen_readonly_platform_unsupported_detail(task: CaptureTask) -> dict[str, Any]:
    platform_key = shop_config.platform_key(task.platform)
    return {
        "error": f"{platform_key} 平台的大屏只读规则尚未配置，请先使用 OCR，或为该平台补充独立只读规则。",
        "reason_code": "screen_readonly_platform_unsupported",
        "task_id": task.id,
        "platform": task.platform,
        "platform_key": platform_key,
        "supported_platforms": list(shop_config.SCREEN_READONLY_SUPPORTED_PLATFORM_KEYS),
    }


def image_from_data_url(value: str) -> Image.Image:
    if not value:
        raise ValueError("preview_image_required")
    _, _, payload = value.partition(",")
    if not payload:
        payload = value
    try:
        data = base64.b64decode(payload, validate=True)
        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise ValueError("invalid_preview_image") from exc


def safe_upsert_task(payload: dict[str, Any]) -> CaptureTask:
    try:
        return store.upsert_task(payload)
    except sqlite3.IntegrityError as exc:
        message = str(exc).lower()
        if "capture_tasks.platform, capture_tasks.shop_name" in message or "idx_capture_tasks_platform_shop_unique" in message:
            raise HTTPException(
                status_code=409,
                detail={
                    "reason_code": "duplicate_shop_task",
                    "message": "同一平台下的同名店铺任务必须唯一，系统已禁止创建重复任务。",
                },
            ) from exc
        raise


class PreviewRequest(BaseModel):
    hwnd: int


class SettingsPayload(BaseModel):
    ocr_engine: str
    interval_seconds: float = Field(default=1.0, ge=0.5)


class TestOcrRequest(BaseModel):
    task_id: int | None = None
    commit_result: bool = False
    hwnd: int | None = None
    page_id: str = ""
    edge_session_id: str = "default_real_edge"
    capture_mode: str = "window_capture"
    preview_image: str = ""
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float
    safety_margin: float = 0.05
    keyword_hint: str = ""
    last_value: int | None = None


class TaskPayload(BaseModel):
    id: int | None = None
    capture_mode: str = "remote_edge"
    value_source: str = "ocr"
    page_id: str = ""
    page_url: str = ""
    target_page_url: str = ""
    page_title: str = ""
    browser_profile: str = "default"
    edge_session_id: str = "default_real_edge"
    platform: str
    shop_name: str
    window_keyword: str
    keyword_hint: str = ""
    interval_seconds: float = Field(default=1, ge=0.5)
    enabled: bool = True
    base_width: int
    base_height: int
    x: int
    y: int
    width: int
    height: int
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float
    safety_margin: float = 0.05
    confirm_count: int = 2
    target: int = 0
    sort_order: int = 0


class EnablePayload(BaseModel):
    enabled: bool


class OpenManagedPagePayload(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("url_required")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url 必须以 http:// 或 https:// 开头")
        return v


class NetworkWatchPayload(BaseModel):
    max_events: int = Field(default=80, ge=10, le=200)
    url_keywords: list[str] = Field(default_factory=list)
    reset: bool = True


class PageClickTextPayload(BaseModel):
    text: str
    exact: bool = False
    timeout_ms: int = Field(default=8000, ge=500, le=20000)


class EdgeSessionPayload(BaseModel):
    session_id: str = ""
    name: str = ""
    platform: str = ""
    shop_name: str = ""
    debug_port: int | None = Field(default=None, ge=1024, le=65535)
    user_data_dir: str = ""
    session_mode: str = "isolated"
    enabled: bool = True


class RebindPagePayload(BaseModel):
    page_id: str
    page_url: str = ""
    page_title: str = ""
    capture_mode: str = "managed_browser"
    edge_session_id: str = "default_real_edge"


class ManualCorrectionPayload(BaseModel):
    value: int
    reason: str = "人工纠错"


class ShopsBindPayload(BaseModel):
    bindings: list[dict[str, Any]]


def build_snapshot() -> dict[str, Any]:
    tasks = [store.task_to_dict(task) for task in store.list_tasks(include_disabled=True)]
    tasks.sort(key=lambda t: (t.get("sort_order") or 0, str(t.get("shop_name") or "")))
    total = sum(task.get("last_trusted_value") or 0 for task in tasks if task.get("enabled"))
    active = sum(1 for task in tasks if task.get("enabled"))
    ok = sum(1 for task in tasks if task.get("status") == "ok")
    return {
        "type": "snapshot",
        "updated_at": store.now_sql(),
        "summary": {
            "total_gmv": total,
            "active_tasks": active,
            "ok_tasks": ok,
            "alert_tasks": max(0, active - ok),
        },
        "tasks": tasks,
    }


async def broadcast_snapshot() -> None:
    if not clients:
        return
    snapshot = build_snapshot()
    stale: list[WebSocket] = []
    for ws in list(clients):
        try:
            await ws.send_json(snapshot)
        except Exception:
            stale.append(ws)
    for ws in stale:
        clients.discard(ws)


def edge_session_for(session_id: str):
    resolved = (session_id or "").strip() or "default_real_edge"
    session = store.get_edge_session(resolved)
    if session is None:
        raise HTTPException(status_code=404, detail="edge_session_not_found")
    return session


def edge_client_for(session_id: str):
    session = edge_session_for(session_id)
    return remote_edge_manager.get_client(
        session.session_id,
        name=session.name,
        debug_port=session.debug_port,
        user_data_dir=session.user_data_dir,
        session_mode=session.session_mode,
    )


async def edge_health_payload(session_id: str) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(lambda: edge_client_for(session_id).health().__dict__)
    except EdgeActionTimeoutError as exc:
        remote_edge_manager.reset_client(session_id)
        return {
            "debug_available": False,
            "connected": False,
            "last_error": str(exc),
            "reason_code": getattr(exc, "reason_code", "edge_action_timeout"),
            "action": getattr(exc, "action", "health"),
            "stage": getattr(exc, "stage", ""),
            "is_window_op_running": False,
            "is_stale": True,
            "stale_reason": "edge_health_timeout",
        }
    except Exception as exc:
        return {
            "debug_available": False,
            "connected": False,
            "last_error": str(exc),
            "reason_code": getattr(exc, "reason_code", "edge_health_failed"),
            "action": "health",
            "stage": getattr(exc, "stage", ""),
            "is_window_op_running": False,
            "is_stale": True,
            "stale_reason": "edge_health_failed",
        }


async def build_edge_session_item(session: Any) -> dict[str, Any]:
    item = store.edge_session_to_dict(session)
    item["health"] = await edge_health_payload(session.session_id)
    return item


async def edge_timeout_detail(
    session_id: str,
    exc: EdgeActionTimeoutError,
    *,
    page_id: str = "",
    recovery_hint: str,
) -> dict[str, Any]:
    remote_edge_manager.reset_client(session_id)
    health = await edge_health_payload(session_id)
    return {
        "error": str(exc),
        "reason_code": getattr(exc, "reason_code", "edge_action_timeout"),
        "action": exc.action,
        "stage": exc.stage,
        "session_id": session_id,
        "page_id": page_id,
        "health": health,
        "recovery_hint": recovery_hint,
    }


async def edge_control_unavailable_detail(
    session_id: str,
    *,
    page_id: str = "",
    operation_label: str,
) -> dict[str, Any]:
    health = await edge_health_payload(session_id)
    reason_code = str(health.get("reason_code") or "")
    profile_initialized = bool(health.get("profile_initialized"))
    window_found = bool((health.get("window_diagnostics") or {}).get("window_found"))
    if reason_code == "edge_debug_disconnected":
        error = "当前店铺登录态/Profile 可能仍在，但 Edge 自动控制连接尚未恢复"
        recovery_hint = (
            f"请先点击“显示Edge”恢复当前店铺窗口，等待 1-2 秒后再重新{operation_label}；"
            "若仍失败，再关闭并重新启动当前店铺 Edge。"
        )
    else:
        reason_code = "edge_debug_unavailable"
        error = "当前店铺登录态/Profile 可能仍在，但 Edge 调试端口未接通"
        recovery_hint = (
            f"请先在任务管理点击“显示Edge”或“启动Edge”，确认当前店铺窗口与调试端口都恢复后，再重新{operation_label}。"
        )
        if window_found:
            recovery_hint = (
                f"已检测到当前店铺 Edge 窗口，但调试端口尚未接通。请先点击“显示Edge”确认窗口回到主屏，"
                f"再重新{operation_label}。"
            )
        elif not profile_initialized:
            error = "当前 Edge 调试端口未接通，且会话目录尚未完成初始化"
    return {
        "error": error,
        "reason_code": reason_code,
        "session_id": session_id,
        "page_id": page_id,
        "health": health,
        "recovery_hint": recovery_hint,
    }


async def task_screen_readonly_payload(task: CaptureTask) -> dict[str, Any]:
    if task.id is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    if task.capture_mode != "remote_edge":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "大屏只读正式链路仅支持真实 Edge 已绑定页面。",
                "reason_code": "screen_readonly_requires_remote_edge",
                "task_id": task.id,
            },
        )
    if not shop_config.screen_readonly_supported(task.platform):
        raise HTTPException(
            status_code=409,
            detail=screen_readonly_platform_unsupported_detail(task),
        )
    if not (task.edge_session_id or "").strip():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "当前任务没有绑定 Edge 会话。",
                "reason_code": "edge_session_not_found",
                "task_id": task.id,
            },
        )
    session_id = task.edge_session_id or "default_real_edge"
    if task.edge_session_id:
        try:
            pages = await asyncio.to_thread(edge_client_for(session_id).list_pages)
            task, _decision = await asyncio.to_thread(edge_binding.restore_task_binding_from_pages, task, session_id, pages)
        except Exception:
            pass
    if not (task.page_id or "").strip():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "当前任务还没有绑定真实页面，无法读取大屏只读值。",
                "reason_code": "screen_readonly_page_not_bound",
                "task_id": task.id,
                "session_id": session_id,
            },
        )
    try:
        result = await asyncio.to_thread(edge_client_for(session_id).read_screen_pay_amount, task.page_id)
    except EdgeActionTimeoutError as exc:
        detail = await edge_timeout_detail(
            session_id,
            exc,
            page_id=task.page_id,
            recovery_hint="当前大屏只读读取超时，系统已重建会话连接。请先确认真实大屏页是否仍在当前页签，再重新读取或执行一次正式采集。",
        )
        detail["task_id"] = task.id
        raise HTTPException(status_code=500, detail=detail) from exc
    except Exception as exc:
        code = str(exc)
        if code == "remote_page_not_found":
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "当前绑定页签已失效或不在当前会话中，无法读取大屏只读值。",
                    "reason_code": "remote_page_not_found",
                    "task_id": task.id,
                    "page_id": task.page_id,
                    "session_id": session_id,
                },
            ) from exc
        if "真实 Edge 调试端口未连接" in code or "连接真实 Edge 失败" in code:
            raise HTTPException(
                status_code=409,
                detail={
                    **(
                        await edge_control_unavailable_detail(
                            session_id,
                            page_id=task.page_id,
                            operation_label="读取大屏只读值",
                        )
                    ),
                    "task_id": task.id,
                },
            ) from exc
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "reason_code": "screen_readonly_failed",
                "task_id": task.id,
                "page_id": task.page_id,
                "session_id": session_id,
            },
        ) from exc
    latest_task = store.get_task(task.id) or task
    return {
        "task": store.task_to_dict(latest_task),
        "readonly": result,
        "value_source": latest_task.value_source,
        "last_value_source": latest_task.last_value_source,
        "last_reason_code": latest_task.last_reason_code,
    }


def edge_tasks_for_platform(platform: str) -> list[CaptureTask]:
    deduped: dict[str, CaptureTask] = {}
    for task in store.list_tasks(include_disabled=True):
        if task.platform != platform:
            continue
        if task.capture_mode != "remote_edge":
            continue
        session_id = (task.edge_session_id or "").strip()
        if not session_id:
            continue
        deduped.setdefault(session_id, task)
    tasks = list(deduped.values())
    if not tasks:
        raise HTTPException(status_code=404, detail=f"未找到平台可控 Edge 任务: {platform}")
    tasks.sort(key=lambda item: (int(item.id or 0), str(item.shop_name or "")))
    return tasks


EDGE_RUNTIME_STALE_STATUSES = {
    "edge_session_not_ready",
    "edge_debug_unavailable",
    "edge_debug_disconnected",
    "window_not_found",
    "remote_page_not_found",
    "edge_recovered",
    "edge_login_page_bound",
    "edge_page_bound",
    "edge_target_page_ready",
}


def edge_action_payload(raw: dict[str, Any]) -> dict[str, Any]:
    payload = dict(raw)
    diagnostics = payload.get("window_diagnostics") or {}
    payload.setdefault("action", "")
    payload.setdefault("stage", "")
    payload.setdefault("reason_code", "")
    payload.setdefault("window_action", "")
    payload.setdefault("recovery_attempted", [])
    payload.setdefault("debug_available", False)
    payload.setdefault("window_found", bool(diagnostics.get("window_found")))
    payload.setdefault("closed", False)
    payload.setdefault("page_count", int(payload.get("page_count") or payload.get("total_pages") or 0))
    payload.setdefault("primary_page_id", "")
    payload.setdefault("primary_page_url", "")
    payload.setdefault("closed_extra_pages_count", 0)
    payload.setdefault("closed_extra_pages", [])
    return payload


def reconcile_edge_session_task_runtime(session_id: str, pages: list[Any] | None = None) -> None:
    page_map = {
        str(getattr(page, "page_id", "") or ""): {
            "page_id": str(getattr(page, "page_id", "") or ""),
            "url": str(getattr(page, "url", "") or ""),
            "title": str(getattr(page, "title", "") or ""),
        }
        for page in (pages or [])
    }
    page_ids = set(page_map)
    for task in store.list_tasks(include_disabled=True):
        if task.capture_mode != "remote_edge" or (task.edge_session_id or "default_real_edge") != session_id or task.id is None:
            continue
        if task.page_id and page_ids and task.page_id not in page_ids:
            restored_task, decision = edge_binding.restore_task_binding_from_pages(task, session_id, pages or [])
            if decision.get("restored"):
                task = restored_task
                continue
            store.update_task_runtime(
                task.id,
                {
                    "status": "remote_page_not_found",
                    "last_reason": "当前 Edge 会话已恢复，但原绑定页签已失效，请重新扫描并重新绑定页面。",
                    "last_reason_code": "remote_page_not_found",
                },
            )
            continue
        bound_page = page_map.get(task.page_id or "")
        if bound_page and task.status in EDGE_RUNTIME_STALE_STATUSES:
            store.update_task_runtime(task.id, _task_runtime_for_bound_page(task, bound_page, automatic=False))


def _page_match_score(task: CaptureTask, page: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    return edge_binding.page_match_score(task, page)


def _task_runtime_for_bound_page(task: CaptureTask, page: dict[str, Any], *, automatic: bool) -> dict[str, str]:
    return edge_binding.task_runtime_for_bound_page(task, page, automatic=automatic)


def _build_task_page_candidates(task: CaptureTask, session: Any, pages: list[Any]) -> dict[str, Any]:
    task_dict = store.task_to_dict(task)
    session_dict = store.edge_session_to_dict(session)
    current_binding = {
        "page_id": task.page_id,
        "page_url": task.page_url,
        "page_title": task.page_title,
        "edge_session_id": task.edge_session_id,
    }
    page_items: list[dict[str, Any]] = []
    for item in pages:
        page = {"page_id": item.page_id, "url": item.url, "title": item.title}
        score, flags = _page_match_score(task, page)
        page_items.append({**page, **flags, "match_score": score})
    page_items.sort(
        key=lambda item: (
            item["match_score"],
            1 if item.get("is_current_bound") else 0,
            len(item.get("title") or ""),
            len(item.get("url") or ""),
        ),
        reverse=True,
    )

    bound_exists = any(item.get("is_current_bound") for item in page_items)
    if not page_items and task.page_id:
        flow_state = "rebind_required"
        next_action = "当前任务记录的原绑定页签已失效，当前会话里还没有可重新绑定的页签。请先去任务管理打开正确后台页，再回到采集配置重新扫描。"
        recovery_hint = "虽然当前任务保存过绑定页，但这次会话里已经找不到原绑定页签。"
    elif not page_items:
        flow_state = "waiting_page"
        next_action = "请先去任务管理打开当前店铺对应后台页，再回到采集配置点击“重新扫描”。"
        recovery_hint = "当前会话里还没有可供绑定的页签。"
    elif task.page_id and not bound_exists:
        flow_state = "rebind_required"
        next_action = "当前绑定页签已失效，请从下面页签列表重新选择一个页面并重新绑定。"
        recovery_hint = "原绑定页签不在当前会话中；系统会在启动/显示 Edge 成功后自动尝试恢复绑定，若仍未恢复，请手动重新绑定。"
    elif task.page_id and bound_exists:
        flow_state = "page_selected"
        next_action = "当前任务已绑定页签，可直接生成预览或继续采集。"
        recovery_hint = ""
    else:
        flow_state = "waiting_page"
        next_action = "请从下面页签列表手动选择一个用于 OCR 的页面，再点击“使用此页面”。"
        recovery_hint = ""

    return {
        "task": task_dict,
        "session": session_dict,
        "current_binding": current_binding,
        "pages": page_items,
        "flow_state": flow_state,
        "next_action": next_action,
        "recovery_hint": recovery_hint,
    }


AMBIGUOUS_BINDING_REASON_CODES = {
    "ambiguous_target_candidates",
    "ambiguous_task_url_candidates",
}


def _build_binding_resolution(
    task: CaptureTask,
    payload: dict[str, Any],
    recovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    recovery = recovery or {}
    flow_state = str(payload.get("flow_state") or "")
    reason_code = str(recovery.get("reason_code") or "")
    restored = bool(recovery.get("restored"))
    manual_required = bool(recovery.get("manual_required"))
    pages = payload.get("pages") or []
    bound_exists = any(bool(item.get("is_current_bound")) for item in pages if isinstance(item, dict))

    if restored:
        return {
            "state": "recovered",
            "reason_code": reason_code or "auto_rebind_restored",
            "manual_required": False,
            "restored": True,
            "summary": "系统已根据候选页自动恢复到最新绑定页签，可直接生成预览。",
            "detail": str(recovery.get("reason") or payload.get("next_action") or ""),
        }

    if flow_state == "page_selected" and (bound_exists or task.page_id):
        return {
            "state": "bound",
            "reason_code": reason_code or "bound_page_ready",
            "manual_required": False,
            "restored": False,
            "summary": "当前绑定页签已确认有效，可直接生成预览。",
            "detail": str(payload.get("next_action") or ""),
        }

    if flow_state == "rebind_required" and reason_code in AMBIGUOUS_BINDING_REASON_CODES:
        return {
            "state": "ambiguous",
            "reason_code": reason_code,
            "manual_required": True,
            "restored": False,
            "summary": "检测到多个相似候选页，系统不会自动改绑，请人工确认。",
            "detail": str(recovery.get("reason") or recovery.get("recovery_hint") or payload.get("recovery_hint") or ""),
        }

    if flow_state == "rebind_required":
        return {
            "state": "invalidated",
            "reason_code": reason_code or "binding_invalidated",
            "manual_required": manual_required,
            "restored": False,
            "summary": "当前会话里未找到可安全恢复的业务页，原绑定可视为真实失效。",
            "detail": str(recovery.get("reason") or payload.get("recovery_hint") or payload.get("next_action") or ""),
        }

    return {
        "state": "waiting_page",
        "reason_code": reason_code or ("no_candidate_pages" if not pages else "waiting_manual_bind"),
        "manual_required": True,
        "restored": False,
        "summary": "当前还没有完成页面绑定，请先扫描并选择页签。",
        "detail": str(payload.get("recovery_hint") or payload.get("next_action") or ""),
    }


def auto_restore_edge_session_task_bindings_with_report(
    session_id: str,
    pages: list[Any] | None = None,
    *,
    target_task_id: int | None = None,
) -> dict[str, Any]:
    page_items = list(pages or [])
    restored: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for task in store.list_tasks(include_disabled=True):
        if task.capture_mode != "remote_edge" or (task.edge_session_id or "default_real_edge") != session_id or task.id is None:
            continue
        _restored_task, decision = edge_binding.restore_task_binding_from_pages(task, session_id, page_items)
        task_decision = {
            "task_id": task.id,
            "shop_name": task.shop_name,
            "session_id": session_id,
            "reason_code": decision["reason_code"],
            "reason": decision["reason"],
            "manual_required": bool(decision["manual_required"]),
            "recovery_hint": decision["recovery_hint"],
            "restored": False,
        }
        restored_item = decision.get("restored_item")
        if decision.get("restored") and isinstance(restored_item, dict):
            restored.append(restored_item)
            task_decision.update(
                {
                    "restored": True,
                    "manual_required": False,
                    "reason_code": str(decision.get("reason_code") or "auto_rebind_restored"),
                    "reason": str(decision.get("reason") or restored_item.get("last_reason") or ""),
                    "recovery_hint": "",
                }
            )
        decisions.append(task_decision)
    target_task = None
    if target_task_id is not None:
        target_task = next((item for item in decisions if int(item.get("task_id") or 0) == int(target_task_id)), None)
    _log = logging.getLogger(__name__)
    restored_count = len(restored)
    if restored_count > 0 or decisions:
        skipped = [d for d in decisions if not d.get("restored")]
        _log.info(
            "edge_bind_restore_summary session=%s restored=%s skipped=%s total=%s",
            session_id, restored_count, len(skipped), len(decisions),
        )
    return {
        "session_id": session_id,
        "restored": restored,
        "restored_count": len(restored),
        "decisions": decisions,
        "target_task": target_task or {},
    }


def auto_restore_edge_session_task_bindings(session_id: str, pages: list[Any] | None = None) -> list[dict[str, Any]]:
    report = auto_restore_edge_session_task_bindings_with_report(session_id, pages)
    return list(report.get("restored") or [])


async def lightweight_reconcile_and_auto_restore() -> dict[str, Any]:
    session_ids = sorted(
        {
            (task.edge_session_id or "default_real_edge")
            for task in store.list_tasks(include_disabled=True)
            if task.capture_mode == "remote_edge" and task.id is not None
        }
    )
    reports: list[dict[str, Any]] = []
    restored_tasks: list[dict[str, Any]] = []
    for session_id in session_ids:
        session = store.get_edge_session(session_id)
        if session is None:
            reports.append(
                {
                    "session_id": session_id,
                    "ok": False,
                    "reason_code": "edge_session_not_found",
                    "reason": "会话不存在，无法执行绑定自愈。",
                    "manual_required": True,
                    "restored_count": 0,
                }
            )
            continue
        client = remote_edge_manager.get_client(
            session.session_id,
            name=session.name,
            debug_port=session.debug_port,
            user_data_dir=session.user_data_dir,
            session_mode=session.session_mode,
        )
        if not client.debug_available_quick():
            reports.append(
                {
                    "session_id": session_id,
                    "ok": False,
                    "reason_code": "edge_debug_unavailable",
                    "reason": "调试链路未就绪，暂不执行自动改绑。",
                    "manual_required": True,
                    "restored_count": 0,
                }
            )
            continue
        try:
            pages = await asyncio.to_thread(client.list_pages)
            await asyncio.to_thread(reconcile_edge_session_task_runtime, session_id, pages)
            report = await asyncio.to_thread(auto_restore_edge_session_task_bindings_with_report, session_id, pages)
            restored = list(report.get("restored") or [])
            restored_tasks.extend(restored)
            needs_manual = [
                {
                    "task_id": item.get("task_id"),
                    "shop_name": item.get("shop_name"),
                    "reason_code": item.get("reason_code"),
                    "reason": item.get("reason"),
                    "recovery_hint": item.get("recovery_hint"),
                }
                for item in (report.get("decisions") or [])
                if not item.get("restored") and item.get("manual_required")
            ]
            reports.append(
                {
                    "session_id": session_id,
                    "ok": True,
                    "reason_code": "self_heal_checked",
                    "reason": "已完成轻量自愈检查。",
                    "manual_required": bool(needs_manual),
                    "manual_review_tasks": needs_manual,
                    "restored_count": len(restored),
                }
            )
        except EdgeActionTimeoutError as exc:
            remote_edge_manager.reset_client(session_id)
            reports.append(
                {
                    "session_id": session_id,
                    "ok": False,
                    "reason_code": getattr(exc, "reason_code", "edge_action_timeout"),
                    "reason": str(exc),
                    "manual_required": True,
                    "restored_count": 0,
                }
            )
        except Exception as exc:
            reports.append(
                {
                    "session_id": session_id,
                    "ok": False,
                    "reason_code": getattr(exc, "reason_code", "self_heal_failed"),
                    "reason": str(exc),
                    "manual_required": True,
                    "restored_count": 0,
                }
            )
    return {
        "requested_sessions": len(session_ids),
        "restored_count": len(restored_tasks),
        "restored_tasks": restored_tasks,
        "session_reports": reports,
    }


def _resume_after_login_message(task: CaptureTask) -> tuple[bool, str, str]:
    if task.status == "edge_target_page_ready":
        return True, "", "目标业务页已打开并恢复绑定，可直接生成预览并继续标定。"
    if task.status == "edge_login_page_bound":
        return False, "login_still_required", "系统已尝试打开目标业务页，但当前会话仍停留在登录页。请确认是否已在 Edge 中真正完成登录。"
    if task.status == "edge_page_bound":
        return False, "target_page_not_ready", "系统已尝试自动继续，但当前绑定页仍不是目标业务页。请确认页面是否跳转到了正确业务页。"
    return False, "resume_after_login_incomplete", "系统已尝试自动继续，但当前任务还未进入目标业务页。请重新扫描或手动确认当前页签。"


async def run_platform_edge_action(
    platform: str,
    action: str,
    runner: Callable[[Any, CaptureTask], Any],
) -> dict[str, Any]:
    tasks = edge_tasks_for_platform(platform)

    async def run_one(task: CaptureTask) -> dict[str, Any]:
        session = store.get_edge_session(task.edge_session_id or "default_real_edge")
        if session is None:
            return {
                "shop_name": task.shop_name,
                "edge_session_id": task.edge_session_id,
                "debug_port": 0,
                "ok": False,
                "last_error": "edge_session_not_found",
            }
        client = remote_edge_manager.get_client(
            session.session_id,
            name=session.name,
            debug_port=session.debug_port,
            user_data_dir=session.user_data_dir,
            session_mode=session.session_mode,
        )
        try:
            result = await asyncio.to_thread(runner, client, task)
            auto_rebound_tasks: list[dict[str, Any]] = []
            if getattr(result, "debug_available", False):
                try:
                    pages = await asyncio.to_thread(client.list_pages)
                except Exception:
                    pages = []
                await asyncio.to_thread(reconcile_edge_session_task_runtime, session.session_id, pages)
                auto_rebound_tasks = await asyncio.to_thread(auto_restore_edge_session_task_bindings, session.session_id, pages)
            payload = edge_action_payload(result.__dict__)
            ok = bool(payload.get("closed")) if action == "close" else bool(payload.get("window_found", payload.get("debug_available")))
            return {
                "shop_name": task.shop_name,
                "task_id": task.id,
                "edge_session_id": session.session_id,
                "debug_port": session.debug_port,
                "ok": ok,
                "sequence_index": 0,
                "total_in_platform": len(tasks),
                "auto_rebound_tasks": auto_rebound_tasks,
                **payload,
            }
        except EdgeActionTimeoutError as exc:
            remote_edge_manager.reset_client(session.session_id)
            return {
                "shop_name": task.shop_name,
                "task_id": task.id,
                "edge_session_id": session.session_id,
                "debug_port": session.debug_port,
                "ok": False,
                "last_error": str(exc),
                "reason_code": getattr(exc, "reason_code", "edge_action_timeout"),
                "action": action,
                "stage": getattr(exc, "stage", ""),
                "sequence_index": 0,
                "total_in_platform": len(tasks),
                "reset_client": True,
            }
        except Exception as exc:
            reason_code = getattr(exc, "reason_code", "edge_action_failed")
            stage = getattr(exc, "stage", "")
            return {
                "shop_name": task.shop_name,
                "task_id": task.id,
                "edge_session_id": session.session_id,
                "debug_port": session.debug_port,
                "ok": False,
                "last_error": str(exc),
                "reason_code": reason_code,
                "action": action,
                "stage": stage,
                "sequence_index": 0,
                "total_in_platform": len(tasks),
            }

    results: list[dict[str, Any]] = []
    for index, task in enumerate(tasks, start=1):
        item = await run_one(task)
        item["sequence_index"] = index
        item["total_in_platform"] = len(tasks)
        results.append(item)
    succeeded = sum(1 for item in results if item["ok"])
    auto_rebound_tasks: list[dict[str, Any]] = []
    seen_task_ids: set[int] = set()
    for item in results:
        for rebound in item.get("auto_rebound_tasks") or []:
            task_id = int(rebound.get("task_id") or 0)
            if task_id and task_id not in seen_task_ids:
                seen_task_ids.add(task_id)
                auto_rebound_tasks.append(rebound)
    return {
        "platform": platform,
        "action": action,
        "requested": len(tasks),
        "controlled_edge_tasks": len(tasks),
        "succeeded": succeeded,
        "execution_mode": "sequential",
        "auto_rebound_tasks": auto_rebound_tasks,
        "auto_rebound_count": len(auto_rebound_tasks),
        "results": results,
    }


def start_and_show_edge_for_task(client: Any, task: CaptureTask) -> Any:
    launch_url = store.preferred_launch_url_for_task(task)
    return client.show_edge(launch_url)


def _load_shops_default() -> list[dict[str, Any]]:
    try:
        return shop_config.shop_configs_as_dicts()
    except Exception:
        if not _SHOPS_DEFAULT_PATH.exists():
            return []
        with open(_SHOPS_DEFAULT_PATH, encoding="utf-8") as f:
            return _json.load(f)
