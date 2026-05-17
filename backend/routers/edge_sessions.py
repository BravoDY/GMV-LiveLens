from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.collectors.remote_edge import EdgeActionTimeoutError, remote_edge_manager
from backend.collectors.window_capture import image_to_data_url
from backend.routers.common import (
    EdgeSessionPayload,
    OpenManagedPagePayload,
    PageClickTextPayload,
    auto_restore_edge_session_task_bindings,
    broadcast_snapshot,
    build_edge_session_item,
    edge_action_payload,
    edge_client_for,
    edge_control_unavailable_detail,
    edge_health_payload,
    edge_timeout_detail,
    reconcile_edge_session_task_runtime,
)
from backend.services import store

router = APIRouter()


@router.get("/api/edge-sessions")
async def edge_sessions() -> list[dict[str, Any]]:
    return await asyncio.gather(*(build_edge_session_item(session) for session in store.list_edge_sessions()))


@router.post("/api/edge-sessions")
async def save_edge_session(payload: EdgeSessionPayload) -> dict[str, Any]:
    try:
        session = store.upsert_edge_session(payload.model_dump())
        return await build_edge_session_item(session)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/edge-sessions/{session_id}")
async def delete_edge_session(session_id: str) -> dict[str, Any]:
    try:
        store.delete_edge_session(session_id)
        await broadcast_snapshot()
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/edge-sessions/{session_id}/health")
async def edge_session_health(session_id: str) -> dict[str, Any]:
    client = edge_client_for(session_id)
    try:
        return await asyncio.to_thread(lambda: client.health().__dict__)
    except EdgeActionTimeoutError:
        remote_edge_manager.reset_client(session_id)
        return await edge_health_payload(session_id)


@router.post("/api/edge-sessions/{session_id}/start")
async def start_edge_session(session_id: str, launch_url: str = Query(default="")) -> dict[str, Any]:
    client = edge_client_for(session_id)
    resolved_launch_url = (launch_url or "").strip() or store.preferred_launch_url_for_session(session_id)
    try:
        health = await asyncio.to_thread(client.start_edge, resolved_launch_url)
        if health.debug_available:
            try:
                pages = await asyncio.to_thread(client.list_pages)
            except Exception:
                pages = []
            await asyncio.to_thread(reconcile_edge_session_task_runtime, session_id, pages)
            auto_rebound_tasks = await asyncio.to_thread(auto_restore_edge_session_task_bindings, session_id, pages)
        else:
            auto_rebound_tasks = []
        await broadcast_snapshot()
        payload = edge_action_payload(health.__dict__)
        payload["auto_rebound_tasks"] = auto_rebound_tasks
        payload["auto_rebound_count"] = len(auto_rebound_tasks)
        return payload
    except EdgeActionTimeoutError as exc:
        detail = await edge_timeout_detail(
            session_id,
            exc,
            recovery_hint="当前店铺 Edge 启动或重连超时，系统已重建会话连接。请先点击“显示Edge”确认窗口是否已恢复；若仍无法采集，再重试“启动Edge”。",
        )
        await broadcast_snapshot()
        raise HTTPException(status_code=500, detail=detail) from exc
    except Exception as exc:
        await broadcast_snapshot()
        health = await edge_health_payload(session_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "reason_code": getattr(exc, "reason_code", "start_edge_failed"),
                "action": "start_edge",
                "stage": getattr(exc, "stage", health.get("stage", "")),
                "health": health,
            },
        ) from exc


@router.post("/api/edge-sessions/{session_id}/show")
async def show_edge_session(session_id: str, launch_url: str = Query(default="")) -> dict[str, Any]:
    client = edge_client_for(session_id)
    if client.is_window_op_running:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "当前店铺 Edge 窗口操作正在进行中，请稍后再试。",
                "reason_code": "window_op_in_progress",
                "action": "show_edge",
                "session_id": session_id,
            },
        )
    resolved_launch_url = (launch_url or "").strip() or store.preferred_launch_url_for_session(session_id)
    try:
        result = await asyncio.to_thread(client.show_edge, resolved_launch_url)
    except EdgeActionTimeoutError as exc:
        detail = await edge_timeout_detail(
            session_id,
            exc,
            recovery_hint="当前店铺 Edge 显示超时，系统已重建会话连接。请先观察窗口是否已经恢复；若仍未回到主屏，再重试“显示Edge”，必要时再执行“启动Edge”。",
        )
        await broadcast_snapshot()
        raise HTTPException(status_code=500, detail=detail) from exc
    except Exception as exc:
        await broadcast_snapshot()
        health = await edge_health_payload(session_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "reason_code": getattr(exc, "reason_code", "show_edge_failed"),
                "action": "show_edge",
                "stage": getattr(exc, "stage", health.get("stage", "")),
                "health": health,
            },
        ) from exc
    if result.debug_available:
        try:
            pages = await asyncio.to_thread(client.list_pages)
        except Exception:
            pages = []
        await asyncio.to_thread(reconcile_edge_session_task_runtime, session_id, pages)
        auto_rebound_tasks = await asyncio.to_thread(auto_restore_edge_session_task_bindings, session_id, pages)
    else:
        auto_rebound_tasks = []
    await broadcast_snapshot()
    payload = edge_action_payload(result.__dict__)
    payload["auto_rebound_tasks"] = auto_rebound_tasks
    payload["auto_rebound_count"] = len(auto_rebound_tasks)
    if not result.window_found:
        raise HTTPException(
            status_code=409,
            detail={
                **payload,
                "error": result.last_error or "当前店铺 Edge 窗口未能显示到主屏前台",
                "reason_code": result.reason_code or "show_window_failed",
                "health": await edge_health_payload(session_id),
            },
        )
    return payload


@router.post("/api/edge-sessions/{session_id}/hide")
async def hide_edge_session(session_id: str) -> dict[str, Any]:
    client = edge_client_for(session_id)
    if client.is_window_op_running:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "当前店铺 Edge 窗口操作正在进行中，请稍后再试。",
                "reason_code": "window_op_in_progress",
                "action": "hide_edge",
                "session_id": session_id,
            },
        )
    try:
        result = await asyncio.to_thread(client.hide_edge)
    except EdgeActionTimeoutError as exc:
        detail = await edge_timeout_detail(
            session_id,
            exc,
            recovery_hint="当前店铺 Edge 隐藏超时。请先观察窗口是否仍在主屏可见区域；若仍可见，请重试“隐藏Edge”，必要时先关闭再启动该店铺 Edge。",
        )
        await broadcast_snapshot()
        raise HTTPException(status_code=500, detail=detail) from exc
    except Exception as exc:
        await broadcast_snapshot()
        health = await edge_health_payload(session_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "reason_code": getattr(exc, "reason_code", "hide_edge_failed"),
                "action": "hide_edge",
                "stage": getattr(exc, "stage", health.get("stage", "")),
                "health": health,
            },
        ) from exc
    await broadcast_snapshot()
    payload = edge_action_payload(result.__dict__)
    if not result.window_found:
        raise HTTPException(
            status_code=409,
            detail={
                **payload,
                "error": result.last_error or "当前店铺 Edge 窗口未能成功隐藏",
                "reason_code": result.reason_code or "hide_window_failed",
                "health": await edge_health_payload(session_id),
            },
        )
    return payload


@router.post("/api/edge-sessions/{session_id}/close")
async def close_edge_session(session_id: str) -> dict[str, Any]:
    client = edge_client_for(session_id)
    if client.is_window_op_running:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "当前店铺 Edge 窗口操作正在进行中，请稍后再试。",
                "reason_code": "window_op_in_progress",
                "action": "close_edge",
                "session_id": session_id,
            },
        )
    try:
        result = await asyncio.to_thread(client.close_edge)
    except EdgeActionTimeoutError as exc:
        detail = await edge_timeout_detail(
            session_id,
            exc,
            recovery_hint="当前店铺 Edge 关闭超时。系统可能仍在等待优雅退出；请稍后刷新任务状态，若窗口或进程仍存在，再重试“关闭Edge”。",
        )
        await broadcast_snapshot()
        raise HTTPException(status_code=500, detail=detail) from exc
    except Exception as exc:
        await broadcast_snapshot()
        health = await edge_health_payload(session_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "reason_code": getattr(exc, "reason_code", "close_edge_failed"),
                "action": "close_edge",
                "stage": getattr(exc, "stage", health.get("stage", "")),
                "health": health,
            },
        ) from exc
    await broadcast_snapshot()
    payload = edge_action_payload(result.__dict__)
    if not result.closed:
        raise HTTPException(
            status_code=409,
            detail={
                **payload,
                "error": result.last_error or "当前店铺 Edge 未能完全关闭",
                "reason_code": result.reason_code or "close_failed",
                "health": await edge_health_payload(session_id),
            },
        )
    return payload


@router.get("/api/edge-sessions/{session_id}/pages")
async def edge_session_pages(session_id: str) -> list[dict[str, Any]]:
    client = edge_client_for(session_id)
    if not client.debug_available_quick():
        return []
    try:
        pages = await asyncio.to_thread(client.list_pages)
        return [page.__dict__ for page in pages]
    except EdgeActionTimeoutError as exc:
        await edge_timeout_detail(
            session_id,
            exc,
            recovery_hint="当前 Edge 页签扫描超时，系统已重建会话连接。请重新扫描；若仍失败，请先关闭并重新显示该店铺 Edge。",
        )
        try:
            pages = await asyncio.to_thread(edge_client_for(session_id).list_pages)
            return [page.__dict__ for page in pages]
        except EdgeActionTimeoutError as retry_exc:
            retry_detail = await edge_timeout_detail(
                session_id,
                retry_exc,
                recovery_hint="页签扫描连续超时，请先关闭并重新显示该店铺 Edge 后再重新扫描。",
            )
            raise HTTPException(status_code=500, detail=retry_detail) from retry_exc
        except Exception as retry_exc:
            retry_health = await edge_health_payload(session_id)
            raise HTTPException(
                status_code=500,
                detail={"error": str(retry_exc), "health": retry_health},
            ) from retry_exc
    except Exception as exc:
        health = await edge_health_payload(session_id)
        raise HTTPException(status_code=500, detail={"error": str(exc), "health": health}) from exc


@router.post("/api/edge-sessions/{session_id}/open")
async def open_edge_session_page(session_id: str, payload: OpenManagedPagePayload) -> dict[str, Any]:
    client = edge_client_for(session_id)
    try:
        health = await asyncio.to_thread(client.health)
        if not health.debug_available:
            health = await asyncio.to_thread(client.start_edge, payload.url)
            if not health.debug_available:
                raise HTTPException(status_code=409, detail={"error": health.last_error, "health": health.__dict__})
        pages = await asyncio.to_thread(client.list_pages)
        for page in pages:
            current = (page.url or "").strip().rstrip("/")
            target = payload.url.strip().rstrip("/")
            if current == target or current.startswith(f"{target}/"):
                return page.__dict__
        page = await asyncio.to_thread(client.open_page, payload.url)
        return page.__dict__
    except HTTPException:
        raise
    except Exception as exc:
        health = await edge_health_payload(session_id)
        raise HTTPException(status_code=500, detail={"error": "打开 Edge 页面失败", "health": health}) from exc


@router.post("/api/edge-sessions/{session_id}/pages/{page_id}/preview")
async def edge_session_preview(session_id: str, page_id: str) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            image, info = await asyncio.to_thread(edge_client_for(session_id).screenshot_page, page_id)
            return {
                "page": info.__dict__,
                "width": image.width,
                "height": image.height,
                "image": image_to_data_url(image, max_width=1400),
            }
        except EdgeActionTimeoutError as exc:
            detail = await edge_timeout_detail(
                session_id,
                exc,
                page_id=page_id,
                recovery_hint="当前页签截图超时，系统已重建会话连接。请重新生成预览；若仍失败，请先关闭并重新显示该店铺 Edge，再重新扫描绑定。",
            )
            try:
                image, info = await asyncio.to_thread(edge_client_for(session_id).screenshot_page, page_id)
                return {
                    "page": info.__dict__,
                    "width": image.width,
                    "height": image.height,
                    "image": image_to_data_url(image, max_width=1400),
                }
            except Exception:
                raise HTTPException(status_code=500, detail=detail) from exc
        except Exception as exc:
            reason_code = str(exc)
            if reason_code == "remote_page_not_found":
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "当前绑定页签已失效或不在当前会话中",
                        "reason_code": reason_code,
                        "page_id": page_id,
                        "session_id": session_id,
                        "recovery_hint": "当前记录的是旧 page_id。请先重新获取候选页，系统会优先尝试自动恢复绑定，再决定是否需要手动重选。",
                        "requires_page_candidates": True,
                    },
                ) from exc
            if "真实 Edge 调试端口未连接" in reason_code or "连接真实 Edge 失败" in reason_code:
                raise HTTPException(
                    status_code=409,
                    detail=await edge_control_unavailable_detail(
                        session_id,
                        page_id=page_id,
                        operation_label="生成预览",
                    ),
                ) from exc
            last_exc = exc
            if attempt < 2:
                await asyncio.sleep(0.4)
    raise HTTPException(
        status_code=500,
        detail={
            "error": str(last_exc),
            "reason_code": "edge_preview_failed",
            "page_id": page_id,
            "session_id": session_id,
        },
    ) from last_exc


@router.post("/api/edge-sessions/{session_id}/pages/{page_id}/reload")
async def reload_edge_session_page(session_id: str, page_id: str) -> dict[str, Any]:
    try:
        page = await asyncio.to_thread(edge_client_for(session_id).reload_page, page_id)
        return page.__dict__
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/edge-sessions/{session_id}/pages/{page_id}/screen-readonly")
async def get_edge_session_page_screen_readonly(session_id: str, page_id: str) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(edge_client_for(session_id).read_screen_pay_amount, page_id)
    except EdgeActionTimeoutError as exc:
        detail = await edge_timeout_detail(
            session_id,
            exc,
            page_id=page_id,
            recovery_hint="当前大屏只读读取超时，系统已重建会话连接。请重新读取；若仍失败，请先显示当前店铺 Edge 并确认大屏页仍在。",
        )
        raise HTTPException(status_code=500, detail=detail) from exc
    except Exception as exc:
        code = str(exc)
        if code == "remote_page_not_found":
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "当前页签不存在或已失效，无法读取大屏只读值。",
                    "reason_code": code,
                    "page_id": page_id,
                    "session_id": session_id,
                },
            ) from exc
        if "真实 Edge 调试端口未连接" in code or "连接真实 Edge 失败" in code:
            raise HTTPException(
                status_code=409,
                detail=await edge_control_unavailable_detail(
                    session_id,
                    page_id=page_id,
                    operation_label="读取大屏只读值",
                ),
            ) from exc
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "reason_code": "screen_readonly_failed",
                "page_id": page_id,
                "session_id": session_id,
            },
        ) from exc


@router.post("/api/edge-sessions/{session_id}/pages/{page_id}/click-text")
async def click_edge_session_page_text(
    session_id: str,
    page_id: str,
    payload: PageClickTextPayload,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            edge_client_for(session_id).click_page_text,
            page_id,
            payload.text,
            exact=payload.exact,
            timeout_ms=payload.timeout_ms,
        )
    except Exception as exc:
        code = str(exc)
        if code in {"remote_page_not_found", "click_text_required", "click_target_not_found"}:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "当前页签上没有找到目标按钮，或页签已失效。",
                    "reason_code": code,
                    "page_id": page_id,
                    "session_id": session_id,
                    "text": payload.text,
                },
            ) from exc
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "reason_code": "click_page_text_failed",
                "page_id": page_id,
                "session_id": session_id,
                "text": payload.text,
            },
        ) from exc

