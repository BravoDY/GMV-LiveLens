"""GMV-LiveLens 统一日志配置

在应用启动时调用 setup_logging()，日志同时输出到控制台和文件。
文件使用 RotatingFileHandler，自动轮转，避免磁盘撑满。
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path | None = None, *, level: int = logging.INFO) -> None:
    """配置全局日志：控制台 + 轮转文件 (UTF-8, 10MB×5)。"""
    if log_dir is None:
        log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    # 避免重复添加 handler（uvicorn reload 可能多次调用 startup）
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)-7s] %(name)s request_id=%(request_id)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        class RequestIdFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                from backend.core.request_id import get_request_id

                record.request_id = get_request_id()
                return True

        request_id_filter = RequestIdFilter()

        console = logging.StreamHandler()
        console.addFilter(request_id_filter)
        console.setFormatter(fmt)
        root.addHandler(console)

        file_handler = RotatingFileHandler(
            log_dir / "gmv_livelens.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.addFilter(request_id_filter)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
