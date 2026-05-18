from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from backend.core.response import success_response
from backend.routers.common import FRONTEND_DIR, html_with_static_version
from backend.services.dashboard_dataset import build_dataset_overview
from backend.services.dashboard_query import build_dashboard_view, force_refresh_cache, get_cache_status

router = APIRouter(tags=["dashboard-test"])


@router.get("/dashboard-test")
async def dashboard_test_page() -> HTMLResponse:
    return html_with_static_version(FRONTEND_DIR / "test-dashboard" / "index.html")


@router.get("/api/dashboard-test")
async def dashboard_test(dataset_id: str | None = None) -> dict[str, object]:
    return success_response(build_dashboard_view(dataset_id or "realtime"))


@router.get("/api/dashboard-datasets-test")
async def dashboard_datasets_test() -> dict[str, object]:
    return success_response(build_dataset_overview())


@router.post("/api/dashboard-cache/refresh")
async def dashboard_cache_refresh() -> dict[str, object]:
    return success_response(force_refresh_cache())


@router.get("/api/dashboard-cache/status")
async def dashboard_cache_status() -> dict[str, object]:
    return success_response(get_cache_status())
