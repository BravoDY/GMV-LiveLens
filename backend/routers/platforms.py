from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.collectors.remote_edge import RemoteEdgeWindowState
from backend.models import CaptureTask
from backend.routers.common import run_platform_edge_action, start_and_show_edge_for_task
from backend.services import store

router = APIRouter()


@router.post("/api/platforms/{platform}/start-edge")
async def start_platform_edge(platform: str) -> dict[str, Any]:
    result = await run_platform_edge_action(
        platform,
        "start",
        start_and_show_edge_for_task,
    )
    result["started"] = result["succeeded"]
    return result


@router.post("/api/platforms/{platform}/launch-edge")
async def launch_platform_edge(platform: str) -> dict[str, Any]:
    result = await run_platform_edge_action(
        platform,
        "launch",
        start_and_show_edge_for_task,
    )
    result["started"] = result["succeeded"]
    return result


@router.post("/api/platforms/{platform}/show-edge")
async def show_platform_edge(platform: str) -> dict[str, Any]:
    def show_running_only(client: Any, task: CaptureTask) -> Any:
        if not client.debug_available_quick():
            return RemoteEdgeWindowState(
                session_id=client.session_id,
                action="show_edge",
                stage="show:edge_not_running",
                debug_available=False,
                window_found=False,
                window_hwnd=0,
                window_pid=0,
                window_title="",
                window_action="",
                maximized=False,
                last_error="Edge 未运行，请先使用「启动Edge」启动后再显示",
                reason_code="edge_debug_unavailable",
            )
        return client.show_edge(store.preferred_launch_url_for_task(task))

    result = await run_platform_edge_action(platform, "show", show_running_only)
    result["shown"] = result["succeeded"]
    return result


@router.post("/api/platforms/{platform}/hide-edge")
async def hide_platform_edge(platform: str) -> dict[str, Any]:
    result = await run_platform_edge_action(platform, "hide", lambda client, task: client.hide_edge())
    result["hidden"] = result["succeeded"]
    return result


@router.post("/api/platforms/{platform}/close-edge")
async def close_platform_edge(platform: str) -> dict[str, Any]:
    result = await run_platform_edge_action(platform, "close", lambda client, task: client.close_edge())
    result["closed"] = result["succeeded"]
    return result
