from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.collectors.remote_edge import EdgeActionTimeoutError, remote_edge_manager
from backend.routers.common import (
    EnablePayload,
    ManualCorrectionPayload,
    RebindPagePayload,
    TaskPayload,
    _build_binding_resolution,
    _build_task_page_candidates,
    _resume_after_login_message,
    _task_runtime_for_bound_page,
    auto_restore_edge_session_task_bindings,
    auto_restore_edge_session_task_bindings_with_report,
    broadcast_snapshot,
    build_snapshot,
    edge_client_for,
    edge_control_unavailable_detail,
    edge_session_for,
    edge_timeout_detail,
    lightweight_reconcile_and_auto_restore,
    reconcile_edge_session_task_runtime,
    safe_upsert_task,
    task_screen_readonly_payload,
)
from backend.services import store
from backend.services.scheduler import scheduler

router = APIRouter()


@router.get("/api/tasks")
async def tasks() -> dict[str, Any]:
    return build_snapshot()


@router.post("/api/tasks/self-heal")
async def tasks_self_heal() -> dict[str, Any]:
    recovery_report = await lightweight_reconcile_and_auto_restore()
    await broadcast_snapshot()
    return recovery_report


@router.post("/api/tasks")
async def save_task(payload: TaskPayload) -> dict[str, Any]:
    task = safe_upsert_task(payload.model_dump(exclude_unset=True))
    await broadcast_snapshot()
    return store.task_to_dict(task)


@router.post("/api/tasks/{task_id}/enabled")
async def enable_task(task_id: int, payload: EnablePayload) -> dict[str, Any]:
    if store.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    store.set_task_enabled(task_id, payload.enabled)
    await broadcast_snapshot()
    return {"ok": True}


@router.post("/api/tasks/{task_id}/rebind-page")
async def rebind_page(task_id: int, payload: RebindPagePayload) -> dict[str, Any]:
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    data = store.task_to_dict(task)
    data.update(
        {
            "capture_mode": payload.capture_mode,
            "page_id": payload.page_id,
            "page_url": payload.page_url,
            "page_title": payload.page_title,
            "edge_session_id": payload.edge_session_id,
        }
    )
    saved = safe_upsert_task(data)
    if payload.capture_mode == "remote_edge" and saved.id is not None:
        runtime = _task_runtime_for_bound_page(
            saved,
            {"page_id": payload.page_id, "url": payload.page_url, "title": payload.page_title},
            automatic=False,
        )
        store.update_task_runtime(saved.id, runtime)
        saved = store.get_task(saved.id) or saved
    await broadcast_snapshot()
    return store.task_to_dict(saved)


@router.post("/api/tasks/{task_id}/resume-after-login")
async def resume_after_login(task_id: int) -> dict[str, Any]:
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    if task.capture_mode != "remote_edge":
        raise HTTPException(status_code=409, detail="task_not_remote_edge")
    if not (task.edge_session_id or "").strip():
        raise HTTPException(status_code=409, detail="edge_session_not_found")
    target_page_url = (task.target_page_url or "").strip()
    if not target_page_url:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "当前任务缺少目标业务页 URL，无法自动继续。",
                "reason_code": "target_page_url_required",
                "task_id": task_id,
                "recovery_hint": "请先为当前任务配置目标业务页 URL，或手动打开目标业务页后重新扫描绑定。",
            },
        )
    if task.status not in {"edge_login_page_bound", "edge_page_bound", "edge_target_page_ready"}:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "当前任务不处于可自动继续的状态。",
                "reason_code": "resume_after_login_invalid_state",
                "task_id": task_id,
                "task_status": task.status,
                "recovery_hint": "只有待登录、待切业务页或已恢复到业务页的任务，才可执行“登录后自动继续”。",
            },
        )

    session = edge_session_for(task.edge_session_id or "default_real_edge")
    client = edge_client_for(session.session_id)
    if getattr(client, "is_window_op_running", False):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "当前店铺 Edge 仍在执行启动或显示动作，请稍候再试。",
                "reason_code": "edge_window_op_in_progress",
                "task_id": task_id,
                "recovery_hint": "请等待 1-2 秒，确认 Edge 窗口稳定后，再点击“已登录，打开业务页并自动继续”。",
            },
        )
    try:
        health = await asyncio.to_thread(client.health)
    except EdgeActionTimeoutError as exc:
        detail = await edge_timeout_detail(
            session.session_id,
            exc,
            recovery_hint="当前店铺 Edge 会话仍在处理上一轮动作，请稍候再试；若连续超时，请先重新显示该店铺 Edge。",
        )
        detail["task_id"] = task_id
        raise HTTPException(status_code=409, detail=detail) from exc
    if not health.debug_available:
        raise HTTPException(
            status_code=409,
            detail={
                **(await edge_control_unavailable_detail(session.session_id, operation_label="登录后自动继续")),
                "task_id": task_id,
            },
        )
    try:
        navigation = await asyncio.to_thread(client.ensure_launch_page, target_page_url)
        pages = await asyncio.to_thread(client.list_pages)
    except EdgeActionTimeoutError as exc:
        detail = await edge_timeout_detail(
            session.session_id,
            exc,
            recovery_hint="登录后自动继续超时，系统已重建会话连接。请先确认当前业务页是否已打开；若仍未恢复，再点击“已登录，打开业务页并自动继续”。",
        )
        detail["task_id"] = task_id
        raise HTTPException(status_code=500, detail=detail) from exc
    except Exception as exc:
        if "真实 Edge 调试端口未连接" in str(exc) or "连接真实 Edge 失败" in str(exc):
            raise HTTPException(
                status_code=409,
                detail={
                    **(await edge_control_unavailable_detail(session.session_id, operation_label="登录后自动继续")),
                    "task_id": task_id,
                },
            ) from exc
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "reason_code": getattr(exc, "reason_code", "resume_after_login_failed"),
                "task_id": task_id,
                "session_id": session.session_id,
                "recovery_hint": "系统已尝试自动继续，但处理过程中出现异常。请先重新扫描；若仍失败，再去任务管理重新显示该店铺 Edge。",
            },
        ) from exc

    await asyncio.to_thread(reconcile_edge_session_task_runtime, session.session_id, pages)
    auto_rebound_tasks = await asyncio.to_thread(auto_restore_edge_session_task_bindings, session.session_id, pages)
    latest_task = store.get_task(task_id) or task
    latest_task_dict = store.task_to_dict(latest_task)
    page_candidates_payload = _build_task_page_candidates(latest_task, session, pages)
    ok, reason_code, message = _resume_after_login_message(latest_task)
    if not ok and navigation.reason_code and navigation.reason_code != "target_page_not_found":
        reason_code = navigation.reason_code
    refreshed_health = await asyncio.to_thread(client.health)
    await broadcast_snapshot()
    return {
        "ok": ok,
        "task_id": task_id,
        "edge_session_id": session.session_id,
        "target_page_url": target_page_url,
        "task_status": latest_task.status,
        "message": message,
        "reason_code": reason_code,
        "navigation": navigation.__dict__,
        "target_page_found": bool(navigation.target_found),
        "auto_rebound_tasks": auto_rebound_tasks,
        "auto_rebound_count": len(auto_rebound_tasks),
        "rebound_current_task": any(int(item.get("task_id") or 0) == task_id for item in auto_rebound_tasks),
        "task": latest_task_dict,
        "page_candidates": page_candidates_payload,
        "health": refreshed_health.__dict__,
    }


@router.get("/api/tasks/{task_id}/page-candidates")
async def task_page_candidates(task_id: int, session_id: str = Query(default="")) -> dict[str, Any]:
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    if task.capture_mode != "remote_edge":
        raise HTTPException(status_code=409, detail="task_not_remote_edge")

    requested_session_id = (session_id or "").strip()
    session = edge_session_for(requested_session_id or task.edge_session_id or "default_real_edge")

    client = remote_edge_manager.get_client(
        session.session_id,
        name=session.name,
        debug_port=session.debug_port,
        user_data_dir=session.user_data_dir,
        session_mode=session.session_mode,
    )
    if not client.debug_available_quick():
        raise HTTPException(
            status_code=409,
            detail={
                **(await edge_control_unavailable_detail(session.session_id, operation_label="扫描页签")),
                "task_id": task_id,
            },
        )

    try:
        pages = await asyncio.to_thread(client.list_pages)
    except EdgeActionTimeoutError as exc:
        detail = await edge_timeout_detail(
            session.session_id,
            exc,
            recovery_hint="当前会话页签扫描超时，系统已重建会话连接。请重新扫描；若仍失败，请先关闭并重新显示该店铺 Edge。",
        )
        try:
            pages = await asyncio.to_thread(edge_client_for(session.session_id).list_pages)
        except Exception:
            raise HTTPException(status_code=500, detail=detail) from exc
    except Exception as exc:
        if "真实 Edge 调试端口未连接" in str(exc) or "连接真实 Edge 失败" in str(exc):
            raise HTTPException(
                status_code=409,
                detail={
                    **(await edge_control_unavailable_detail(session.session_id, operation_label="扫描页签")),
                    "task_id": task_id,
                },
            ) from exc
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "reason_code": "list_pages_failed",
                "task_id": task_id,
                "session_id": session.session_id,
            },
        ) from exc

    await asyncio.to_thread(reconcile_edge_session_task_runtime, session.session_id, pages)
    recovery_report = await asyncio.to_thread(
        auto_restore_edge_session_task_bindings_with_report,
        session.session_id,
        pages,
        target_task_id=task_id,
    )
    latest_task = store.get_task(task_id) or task
    payload = _build_task_page_candidates(latest_task, session, pages)
    payload["auto_rebound_tasks"] = recovery_report.get("restored", [])
    payload["auto_rebound_count"] = int(recovery_report.get("restored_count") or 0)
    payload["binding_recovery"] = recovery_report.get("target_task", {})
    payload["binding_resolution"] = _build_binding_resolution(
        latest_task,
        payload,
        recovery_report.get("target_task", {}),
    )
    payload["health"] = client.health_quick()
    payload["task"] = store.task_to_dict(latest_task)
    return payload


@router.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int) -> dict[str, Any]:
    if store.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    store.delete_task(task_id)
    await broadcast_snapshot()
    return {"ok": True}


@router.post("/api/tasks/{task_id}/delete")
async def delete_task_fallback(task_id: int) -> dict[str, Any]:
    return await delete_task(task_id)


@router.post("/api/tasks/{task_id}/capture-once")
async def capture_once(task_id: int) -> dict[str, Any]:
    result = await asyncio.to_thread(scheduler.capture_once, task_id)
    await broadcast_snapshot()
    return result


@router.post("/api/tasks/{task_id}/manual-correction")
async def manual_correction(task_id: int, payload: ManualCorrectionPayload) -> dict[str, Any]:
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    now = store.now_sql()
    reason = payload.reason or "人工纠错"
    store.update_task_runtime(
        task_id,
        {
            "last_trusted_value": payload.value,
            "pending_value": None,
            "pending_count": 0,
            "status": "ok",
            "last_success_at": now,
            "last_sample_at": now,
            "last_reason": reason,
            "last_reason_code": "",
            "last_value_source": "manual",
        },
    )
    store.add_sample(
        task_id,
        task.last_ocr_text,
        [],
        payload.value,
        payload.value,
        "ok",
        reason,
        task.last_screenshot_path,
        sample_meta={
            "selected_candidate_source_kind": "manual_correction",
            "required_confirms": 1,
            "accepted_after_confirms": 1,
        },
    )
    await broadcast_snapshot()
    return {"ok": True, "trusted_value": payload.value}


@router.get("/api/tasks/{task_id}/samples")
async def samples(task_id: int, limit: int = Query(default=20, ge=1, le=500)) -> list[dict[str, Any]]:
    if store.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    return store.recent_samples(task_id, limit)


@router.get("/api/tasks/{task_id}/screen-readonly")
async def get_task_screen_readonly(task_id: int) -> dict[str, Any]:
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    return await task_screen_readonly_payload(task)
