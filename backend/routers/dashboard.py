from __future__ import annotations

from fastapi import APIRouter

from backend.core.response import success_response
from backend.services.dashboard_dataset import build_dataset_overview

router = APIRouter(prefix="/api/dashboard-datasets", tags=["dashboard-datasets"])


@router.get("")
async def list_dashboard_datasets() -> dict[str, object]:
    return success_response(build_dataset_overview())
