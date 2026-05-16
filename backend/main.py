# ruff: noqa: E402
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.core.config import get_settings
from backend.core.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from backend.core.middleware import RequestIdMiddleware, WriteTokenMiddleware
from backend.logging_config import setup_logging
from backend.routers import ALL_ROUTERS
from backend.routers.common import FRONTEND_DIR, broadcast_snapshot
from backend.services import store
from backend.services.dashboard_query import start_cache_scheduler, stop_cache_scheduler
from backend.services.scheduler import scheduler

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title="GMV-LiveLens", version="0.1.0")
app.add_middleware(RequestIdMiddleware)
app.add_middleware(WriteTokenMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Request-ID", "X-API-Token"],
)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

for router in ALL_ROUTERS:
    app.include_router(router)


@app.on_event("startup")
async def startup() -> None:
    setup_logging()
    store.init_db()
    try:
        store.sync_tasks_with_shop_configs()
    except Exception:
        logger.exception("shops.csv 校验失败，已跳过启动阶段自动同步，保留当前运行态任务。")
    scheduler.add_callback(broadcast_snapshot)
    if os.getenv("GMV_SCHEDULER_AUTOSTART", "true").strip().lower() in {"0", "false", "no", "off"}:
        logger.info("GMV scheduler autostart disabled by GMV_SCHEDULER_AUTOSTART")
    else:
        scheduler.start()
    start_cache_scheduler()


@app.on_event("shutdown")
async def shutdown() -> None:
    stop_cache_scheduler()
    await scheduler.stop()
