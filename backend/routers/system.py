from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse

from backend.core.config import get_settings as get_app_settings
from backend.core.response import success_response
from backend.core.security import public_security_status
from backend.routers.common import (
    FRONTEND_DIR,
    SettingsPayload,
    _load_shops_default,
    broadcast_snapshot,
    build_snapshot,
    clients,
    html_with_static_version,
)
from backend.services import store
from backend.services.dashboard_query import build_dashboard_view
from backend.services.scheduler import scheduler
from backend.version import APP_VERSION

router = APIRouter()


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "assets" / "descente-logo.png", media_type="image/png")


@router.get("/api/task-previews/{filename}", include_in_schema=False)
async def task_preview_image(filename: str) -> FileResponse:
    if "/" in filename or "\\" in filename or not filename.startswith("task_preview_") or not filename.endswith(".png"):
        raise HTTPException(status_code=404, detail="preview_not_found")
    path = (store.SCREENSHOT_DIR / filename).resolve()
    root = store.SCREENSHOT_DIR.resolve()
    if root not in path.parents or not path.exists():
        raise HTTPException(status_code=404, detail="preview_not_found")
    return FileResponse(path, media_type="image/png")


@router.get("/")
async def index() -> HTMLResponse:
    return html_with_static_version(FRONTEND_DIR / "index.html")


@router.get("/dashboard")
async def public_dashboard_page() -> HTMLResponse:
    return html_with_static_version(FRONTEND_DIR / "index.html")


@router.get("/api/windows")
async def windows() -> list[dict[str, Any]]:
    from backend.collectors.window_capture import list_windows

    return [window.__dict__ for window in list_windows()]


@router.get("/api/settings")
def get_runtime_settings() -> dict[str, Any]:
    return {
        "ocr_engine": store.get_setting("ocr_engine", "auto"),
        "interval_seconds": float(store.get_setting("interval_seconds", "1.0")),
    }


@router.post("/api/settings")
def update_settings(payload: SettingsPayload) -> dict[str, str]:
    store.set_setting("ocr_engine", payload.ocr_engine)
    store.set_setting("interval_seconds", str(payload.interval_seconds))
    return {"status": "ok"}


@router.get("/api/scheduler")
async def scheduler_status() -> dict[str, Any]:
    return scheduler.status()


@router.post("/api/scheduler/start")
async def scheduler_start() -> dict[str, Any]:
    scheduler.resume()
    await broadcast_snapshot()
    return scheduler.status()


@router.post("/api/scheduler/pause")
async def scheduler_pause() -> dict[str, Any]:
    scheduler.pause()
    await broadcast_snapshot()
    return scheduler.status()


@router.get("/api/health")
async def health() -> dict[str, Any]:
    return success_response(
        {
            "status": "ok",
            "version": APP_VERSION,
            "scheduler": scheduler.status(),
        }
    )


@router.get("/api/config/public")
async def public_config() -> dict[str, Any]:
    settings = get_app_settings()
    return success_response(
        {
            "app_env": settings.app_env,
            "security": public_security_status(),
        }
    )


@router.get("/api/debug/status")
async def debug_status() -> dict[str, Any]:
    settings = get_app_settings()
    if not settings.debug_api_enabled:
        raise HTTPException(status_code=404, detail="debug_api_disabled")
    return success_response(
        {
            "app": {
                "name": "GMV-LiveLens",
                "version": APP_VERSION,
                "env": settings.app_env,
            },
            "security": public_security_status(),
            "scheduler": scheduler.status(),
            "counts": {
                "tasks": len(store.list_tasks(include_disabled=True)),
                "edge_sessions": len(store.list_edge_sessions()),
                "shops": len(_load_shops_default()),
            },
            "paths": {
                "frontend_dir": str(FRONTEND_DIR),
                "screenshot_dir": str(store.SCREENSHOT_DIR),
            },
        }
    )


@router.get("/api/realtime")
async def realtime() -> dict[str, Any]:
    return build_snapshot()


@router.get("/api/dashboard")
async def dashboard(dataset_id: str | None = None) -> dict[str, Any]:
    return success_response(build_dashboard_view(dataset_id or "realtime"))


@router.get("/api/history/{task_id}")
async def history(task_id: int, limit: int = Query(default=50, ge=1, le=500)) -> list[dict[str, Any]]:
    if store.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    return store.recent_samples(task_id, limit)


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    await websocket.accept()
    clients.add(websocket)
    try:
        await websocket.send_json(build_snapshot())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.discard(websocket)
    except Exception:
        clients.discard(websocket)
