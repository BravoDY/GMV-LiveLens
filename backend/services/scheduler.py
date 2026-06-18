from __future__ import annotations

import asyncio
import logging
import math
import os
import random
import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from PIL import Image

from backend.collectors.ocr_reader import candidates_to_dicts, extract_candidates, read_text
from backend.collectors.remote_edge import EdgeActionTimeoutError, remote_edge_manager
from backend.collectors.window_capture import capture_window, crop_by_ratio, find_window, save_thumbnail
from backend.models import (
    AUTO_REFRESH_STATUS_OBSERVING,
    AUTO_REFRESH_STATUS_COOLDOWN,
    AUTO_REFRESH_STATUS_RUNNING,
    CaptureTask,
)
from backend.services import edge_binding, shop_config, store

logger = logging.getLogger(__name__)

_SCREENSHOT_MAX_AGE_DAYS = int(os.environ.get("GMV_SCREENSHOT_MAX_AGE_DAYS", "1"))
_SCREENSHOT_MAX_COUNT_PER_TASK = int(os.environ.get("GMV_SCREENSHOT_MAX_COUNT_PER_TASK", "200"))
_PREVIEW_MIN_INTERVAL_SECONDS = int(os.environ.get("GMV_PREVIEW_MIN_INTERVAL_SECONDS", "180"))
_PREVIEW_MAX_INTERVAL_SECONDS = int(os.environ.get("GMV_PREVIEW_MAX_INTERVAL_SECONDS", "480"))
_PREVIEW_MAX_WIDTH = int(os.environ.get("GMV_PREVIEW_MAX_WIDTH", "720"))
_SCREEN_READONLY_MAX_PAY_AMT = int(os.environ.get("GMV_SCREEN_READONLY_MAX_PAY_AMT", "1000000000000"))
_SCREEN_READONLY_FAILURE_BACKOFF_SECONDS = float(os.environ.get("GMV_SCREEN_READONLY_FAILURE_BACKOFF_SECONDS", "10"))
_AUTO_REFRESH_MIN_RUNTIME_SECONDS = int(os.environ.get("GMV_AUTO_REFRESH_MIN_RUNTIME_SECONDS", "10800"))
_AUTO_REFRESH_STAGGER_SECONDS = int(os.environ.get("GMV_AUTO_REFRESH_STAGGER_SECONDS", "600"))
_AUTO_REFRESH_OBSERVE_SECONDS = int(os.environ.get("GMV_AUTO_REFRESH_OBSERVE_SECONDS", "60"))
_AUTO_REFRESH_FAILURE_COOLDOWN_SECONDS = int(os.environ.get("GMV_AUTO_REFRESH_FAILURE_COOLDOWN_SECONDS", "7200"))
_SQLITE_INT64_MAX = 2**63 - 1

SnapshotCallback = Callable[[], Awaitable[None]]


DATASET_DIR = Path(__file__).resolve().parents[2] / "data" / "ocr_datasets"

class CaptureScheduler:
    def __init__(self) -> None:
        self._runner: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._last_run: dict[int, float] = {}
        self._next_readonly_run: dict[int, float] = {}
        self._readonly_response_markers: dict[int, str] = {}
        self._next_preview_run: dict[int, float] = {}
        self._auto_refresh_skip_markers: dict[int, str] = {}
        self._callbacks: list[SnapshotCallback] = []
        self._running = False
        self._cached_global_interval_seconds = 1.0
        self._global_interval_loaded_at = 0.0

    def add_callback(self, callback: SnapshotCallback) -> None:
        self._callbacks.append(callback)

    def start(self) -> None:
        self._running = True
        if self._runner is None or self._runner.done():
            self._stop.clear()
            self._runner = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        self._stop.set()
        if self._runner:
            await self._runner

    def pause(self) -> None:
        self._running = False

    def resume(self) -> None:
        self._running = True

    def status(self) -> dict:
        auto_refresh = store.get_auto_refresh_global_state()
        return {
            "running": self._running,
            "loop_alive": self._runner is not None and not self._runner.done(),
            "tracked_tasks": len(self._last_run),
            "tracked_readonly_tasks": len(self._next_readonly_run),
            "tracked_preview_tasks": len(self._next_preview_run),
            "auto_refresh": auto_refresh,
        }

    def _restore_remote_task_binding(self, task: CaptureTask, client: Any, session_id: str) -> CaptureTask:
        if task.id is None:
            return task
        try:
            pages = client.list_pages()
            restored_task, _decision = edge_binding.restore_task_binding_from_pages(task, session_id, pages)
            return restored_task
        except Exception as exc:
            logger.warning(
                "edge_bind_restore_failed task_id=%s session=%s platform=%s shop=%s error=%s",
                task.id, session_id, task.platform, task.shop_name, exc,
            )
            return task

    async def _notify(self) -> None:
        for callback in list(self._callbacks):
            try:
                await callback()
            except Exception:
                pass

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                if not self._running:
                    await asyncio.sleep(0.5)
                    continue
                tasks = store.list_tasks(include_disabled=False)
                now = time.time()
                global_interval = self._global_interval_seconds(now)
                active_ids = {int(task.id) for task in tasks if task.id is not None}
                self._trim_runtime_trackers(active_ids)
                due_tasks: list[CaptureTask] = []
                for task in tasks:
                    if task.id is None:
                        continue
                    task_interval = self._task_interval_seconds(task, global_interval)
                    if task.value_source == "screen_readonly":
                        due_at = self._next_readonly_run.get(task.id, 0)
                        if now >= due_at:
                            due_tasks.append(task)
                        continue
                    last = self._last_run.get(task.id, 0)
                    if now - last >= task_interval:
                        due_tasks.append(task)
                if due_tasks:
                    results = await asyncio.gather(
                        *[asyncio.to_thread(self.capture_once, int(task.id)) for task in due_tasks]
                    )
                    finished_at = time.time()
                    should_notify = False
                    for task, result in zip(due_tasks, results, strict=False):
                        task_id = int(task.id or 0)
                        self._last_run[task_id] = finished_at
                        if task.value_source == "screen_readonly":
                            readonly_interval = self._readonly_next_interval_seconds(
                                task,
                                global_interval,
                                str((result or {}).get("status") or ""),
                            )
                            self._next_readonly_run[task_id] = finished_at + readonly_interval
                            result_status = str((result or {}).get("status") or "")
                            if result_status != "readonly_no_new_data" or task.status != "readonly_no_new_data":
                                should_notify = True
                            continue
                        should_notify = True
                    if should_notify:
                        await self._notify()
                preview_id = self._next_due_preview_task_id(tasks, now)
                if preview_id is not None:
                    await asyncio.to_thread(self.refresh_page_preview_once, preview_id)
                    await self._notify()
                refreshed_tasks = store.list_tasks(include_disabled=False)
                if await asyncio.to_thread(self._finalize_due_auto_refreshs, refreshed_tasks):
                    await self._notify()
                    refreshed_tasks = store.list_tasks(include_disabled=False)
                if await asyncio.to_thread(self._maybe_trigger_auto_refresh, refreshed_tasks):
                    await self._notify()
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                from backend.utils.log_throttle import global_throttle

                fp = f"run_loop:{type(exc).__name__}:{str(exc)[:120]}"
                if global_throttle.should_log(fp):
                    logger.error("调度循环发生未预期异常，1s 后继续：%s", exc, exc_info=True)
                else:
                    logger.warning("调度循环异常（已限流）: %s", exc)
                await asyncio.sleep(1.0)

    def _next_due_preview_task_id(self, tasks: list[CaptureTask], now: float) -> int | None:
        for task in tasks:
            if task.id is None or task.capture_mode != "remote_edge" or not task.page_id:
                continue
            due_at = self._next_preview_run.get(task.id)
            if due_at is None:
                due_at = now + self._preview_interval_seconds()
                self._next_preview_run[task.id] = due_at
            if now >= due_at:
                self._next_preview_run[task.id] = now + self._preview_interval_seconds()
                return task.id
        return None

    @staticmethod
    def _preview_interval_seconds() -> int:
        low = max(30, _PREVIEW_MIN_INTERVAL_SECONDS)
        high = max(low, _PREVIEW_MAX_INTERVAL_SECONDS)
        return random.randint(low, high)

    def _trim_runtime_trackers(self, active_ids: set[int]) -> None:
        self._last_run = {task_id: value for task_id, value in self._last_run.items() if task_id in active_ids}
        self._next_readonly_run = {
            task_id: value for task_id, value in self._next_readonly_run.items() if task_id in active_ids
        }
        self._readonly_response_markers = {
            task_id: value for task_id, value in self._readonly_response_markers.items() if task_id in active_ids
        }
        self._next_preview_run = {
            task_id: value for task_id, value in self._next_preview_run.items() if task_id in active_ids
        }
        self._auto_refresh_skip_markers = {
            task_id: value for task_id, value in self._auto_refresh_skip_markers.items() if task_id in active_ids
        }

    def _global_interval_seconds(self, now: float) -> float:
        if now - self._global_interval_loaded_at < 1.0:
            return self._cached_global_interval_seconds
        try:
            interval_seconds = float(store.get_setting("interval_seconds", "1.0"))
        except (TypeError, ValueError):
            interval_seconds = 1.0
        self._cached_global_interval_seconds = max(0.5, interval_seconds)
        self._global_interval_loaded_at = now
        return self._cached_global_interval_seconds

    @staticmethod
    def _task_interval_seconds(task: CaptureTask, global_interval: float) -> float:
        try:
            task_interval = float(task.interval_seconds)
        except (TypeError, ValueError):
            task_interval = 0.0
        return max(0.5, task_interval or global_interval)

    def _readonly_next_interval_seconds(self, task: CaptureTask, global_interval: float, status: str) -> float:
        interval = self._task_interval_seconds(task, global_interval)
        if status in {"ok", "readonly_no_new_data", "readonly_waiting", "skipped_window_op_in_progress"}:
            return interval
        return max(interval, _SCREEN_READONLY_FAILURE_BACKOFF_SECONDS)

    @staticmethod
    def _auto_refresh_sort_key(task: CaptureTask) -> tuple[datetime, int]:
        baseline = (
            store.parse_sql_time(task.auto_refresh_last_success_at)
            or store.parse_sql_time(task.auto_refresh_last_result_at)
            or store.parse_sql_time(task.auto_refresh_anchor_at)
            or datetime.min
        )
        return baseline, int(task.id or 0)

    def _sync_auto_refresh_global_state(self, tasks: list[CaptureTask]) -> None:
        state = store.get_auto_refresh_global_state()
        active_task_id = int(state.get("active_task_id") or 0)
        if active_task_id <= 0:
            return
        task_map = {int(task.id): task for task in tasks if task.id is not None}
        active_task = task_map.get(active_task_id)
        if active_task is None or active_task.auto_refresh_status not in {
            AUTO_REFRESH_STATUS_RUNNING,
            AUTO_REFRESH_STATUS_OBSERVING,
        }:
            store.clear_auto_refresh_global_run()

    def _record_auto_refresh_skip(self, task: CaptureTask, reason_code: str, reason: str) -> bool:
        if task.id is None:
            return False
        marker = f"{reason_code}:{reason}"
        if self._auto_refresh_skip_markers.get(task.id) == marker:
            return False
        self._auto_refresh_skip_markers[task.id] = marker
        store.mark_task_auto_refresh_skip(task.id, reason_code=reason_code, reason=reason)
        self._log_auto_refresh_event(
            "skip",
            task,
            result="skipped",
            reason_code=reason_code,
            reason=reason,
        )
        return True

    def _clear_auto_refresh_skip_marker(self, task_id: int | None) -> None:
        if task_id is None:
            return
        self._auto_refresh_skip_markers.pop(task_id, None)

    def _log_auto_refresh_event(
        self,
        stage: str,
        task: CaptureTask,
        *,
        level: int = logging.INFO,
        session_id: str = "",
        page_id: str = "",
        status: str = "",
        result: str = "",
        reason_code: str = "",
        reason: str = "",
        started_at: str = "",
        observe_until: str = "",
        cooldown_until: str = "",
    ) -> None:
        logger.log(
            level,
            "auto_refresh_event stage=%s task_id=%s session=%s platform=%s shop=%s page_id=%s "
            "status=%s result=%s reason_code=%s started_at=%s observe_until=%s cooldown_until=%s reason=%s",
            stage,
            task.id,
            session_id or task.edge_session_id,
            task.platform,
            task.shop_name,
            page_id or task.page_id,
            status or task.auto_refresh_status,
            result or task.auto_refresh_last_result,
            reason_code,
            started_at,
            observe_until,
            cooldown_until,
            reason,
        )

    def _auto_refresh_candidate_reason(self, task: CaptureTask, now_dt: datetime) -> tuple[str, str]:
        if task.capture_mode != "remote_edge":
            return store.AUTO_REFRESH_REASON_NOT_REMOTE_EDGE, "当前任务不是网页直连模式。"
        if not str(task.page_id or "").strip():
            return store.AUTO_REFRESH_REASON_PAGE_NOT_BOUND, "当前任务还没有绑定有效页面。"
        observe_until = store.parse_sql_time(task.auto_refresh_observe_until)
        if observe_until is not None and observe_until > now_dt:
            return store.AUTO_REFRESH_REASON_OBSERVING, "当前任务仍处于自动刷新观察期。"
        manual_until = store.parse_sql_time(task.auto_refresh_manual_protect_until)
        if manual_until is not None and manual_until > now_dt:
            return store.AUTO_REFRESH_REASON_MANUAL_PROTECTED, "当前任务仍在人工保护期内。"
        cooldown_until = store.parse_sql_time(task.auto_refresh_cooldown_until)
        if cooldown_until is not None and cooldown_until > now_dt:
            return store.AUTO_REFRESH_REASON_FAILURE_COOLDOWN, "当前任务仍在自动刷新失败冷却期内。"
        anchor_at = store.parse_sql_time(task.auto_refresh_anchor_at)
        if anchor_at is None:
            return "anchor_not_ready", "当前任务还没有建立自动刷新计时基线。"
        if (now_dt - anchor_at).total_seconds() < _AUTO_REFRESH_MIN_RUNTIME_SECONDS:
            return "not_due_yet", "当前任务距离上次自动刷新基线尚未满 3 小时。"
        return store.AUTO_REFRESH_REASON_ELIGIBLE, ""

    def _select_auto_refresh_candidate(self, tasks: list[CaptureTask]) -> CaptureTask | None:
        now_dt = datetime.now()
        candidates: list[CaptureTask] = []
        for task in tasks:
            if task.id is None:
                continue
            reason_code, _reason = self._auto_refresh_candidate_reason(task, now_dt)
            if reason_code == store.AUTO_REFRESH_REASON_ELIGIBLE:
                candidates.append(task)
        if not candidates:
            return None
        candidates.sort(key=self._auto_refresh_sort_key)
        return candidates[0]

    def _maybe_trigger_auto_refresh(self, tasks: list[CaptureTask]) -> bool:
        self._sync_auto_refresh_global_state(tasks)
        global_state = store.get_auto_refresh_global_state()
        if global_state.get("running"):
            return False
        last_started_at = store.parse_sql_time(global_state.get("last_started_at"))
        if last_started_at is not None and (datetime.now() - last_started_at).total_seconds() < _AUTO_REFRESH_STAGGER_SECONDS:
            return False
        candidate = self._select_auto_refresh_candidate(tasks)
        if candidate is None:
            return False
        return self._trigger_auto_refresh(candidate)

    def _trigger_auto_refresh(self, task: CaptureTask) -> bool:
        if task.id is None:
            return False
        session = store.get_edge_session(task.edge_session_id or "default_real_edge")
        if session is None:
            return self._record_auto_refresh_skip(
                task,
                store.AUTO_REFRESH_REASON_EDGE_SESSION_NOT_FOUND,
                "自动刷新跳过：没有找到绑定的 Edge 会话。",
            )
        try:
            client = remote_edge_manager.get_client(
                session.session_id,
                name=session.name,
                debug_port=session.debug_port,
                user_data_dir=session.user_data_dir,
                session_mode=session.session_mode,
            )
        except Exception:
            return self._record_auto_refresh_skip(
                task,
                store.AUTO_REFRESH_REASON_EDGE_DEBUG_UNAVAILABLE,
                "自动刷新跳过：当前 Edge 调试链路不可用。",
            )
        if client.is_window_op_running:
            return self._record_auto_refresh_skip(
                task,
                store.AUTO_REFRESH_REASON_WINDOW_OP_IN_PROGRESS,
                "自动刷新跳过：当前 Edge 窗口操作正在进行中。",
            )
        task = self._restore_remote_task_binding(task, client, session.session_id)
        if not str(task.page_id or "").strip():
            return self._record_auto_refresh_skip(
                task,
                store.AUTO_REFRESH_REASON_BINDING_INVALIDATED,
                "自动刷新跳过：当前任务的页面绑定已失效，等待重新绑定。",
            )
        page_info = client.find_page(task.page_id)
        if page_info is None:
            return self._record_auto_refresh_skip(
                task,
                store.AUTO_REFRESH_REASON_REMOTE_PAGE_NOT_FOUND,
                "自动刷新跳过：当前绑定页签已不存在。",
            )
        _score, flags = edge_binding.page_match_score(
            task,
            {"page_id": page_info.page_id, "url": page_info.url, "title": page_info.title},
        )
        if flags.get("is_login_page") or task.status == "edge_login_page_bound":
            return self._record_auto_refresh_skip(
                task,
                store.AUTO_REFRESH_REASON_LOGIN_PAGE,
                "自动刷新跳过：当前页仍处于登录页或待登录状态。",
            )
        if task.status == "edge_page_bound" and not flags.get("matches_target_url"):
            return self._record_auto_refresh_skip(
                task,
                store.AUTO_REFRESH_REASON_LOGIN_REQUIRED,
                "自动刷新跳过：当前页尚未回到目标业务页。",
            )

        started_at = store.now_sql()
        self._log_auto_refresh_event(
            "candidate",
            task,
            session_id=session.session_id,
            page_id=task.page_id,
            status=AUTO_REFRESH_STATUS_RUNNING,
            result=task.auto_refresh_last_result,
            reason_code=store.AUTO_REFRESH_REASON_ELIGIBLE,
            reason="满足自动刷新条件，已选中当前任务进入 reload 流程。",
            started_at=started_at,
        )
        store.start_task_auto_refresh(
            task.id,
            started_at=started_at,
            reason_code=store.AUTO_REFRESH_REASON_ELIGIBLE,
            reason="满足自动刷新条件，准备触发页面 reload。",
        )
        store.start_auto_refresh_global_run(task.id, started_at=started_at)
        try:
            client.reload_page(task.page_id)
        except Exception as exc:
            store.mark_task_auto_refresh_failure(
                task.id,
                finished_at=store.now_sql(),
                cooldown_seconds=_AUTO_REFRESH_FAILURE_COOLDOWN_SECONDS,
                reason_code=store.AUTO_REFRESH_REASON_RELOAD_TRIGGER_FAILED,
                reason=f"自动刷新失败：触发 reload 失败（{exc}）。",
            )
            store.clear_auto_refresh_global_run()
            self._clear_auto_refresh_skip_marker(task.id)
            self._log_auto_refresh_event(
                "failure",
                task,
                level=logging.WARNING,
                session_id=session.session_id,
                page_id=task.page_id,
                status=AUTO_REFRESH_STATUS_COOLDOWN,
                result="failure",
                reason_code=store.AUTO_REFRESH_REASON_RELOAD_TRIGGER_FAILED,
                reason=f"自动刷新失败：触发 reload 失败（{exc}）。",
                started_at=started_at,
                cooldown_until=store.sql_after_seconds(started_at, _AUTO_REFRESH_FAILURE_COOLDOWN_SECONDS),
            )
            return True

        observe_until = store.sql_after_seconds(started_at, _AUTO_REFRESH_OBSERVE_SECONDS)
        store.mark_task_auto_refresh_observing(
            task.id,
            started_at=started_at,
            observe_seconds=_AUTO_REFRESH_OBSERVE_SECONDS,
            reason_code=store.AUTO_REFRESH_REASON_OBSERVING,
            reason="已触发页面 reload，进入 60 秒观察期。",
        )
        self._clear_auto_refresh_skip_marker(task.id)
        self._log_auto_refresh_event(
            "start",
            task,
            session_id=session.session_id,
            page_id=task.page_id,
            status=AUTO_REFRESH_STATUS_OBSERVING,
            result=task.auto_refresh_last_result,
            reason_code=store.AUTO_REFRESH_REASON_OBSERVING,
            reason="已触发页面 reload，进入自动刷新观察期。",
            started_at=started_at,
            observe_until=observe_until,
        )
        return True

    def _finalize_due_auto_refreshs(self, tasks: list[CaptureTask]) -> bool:
        self._sync_auto_refresh_global_state(tasks)
        now_dt = datetime.now()
        changed = False
        for task in tasks:
            if task.id is None or task.auto_refresh_status != AUTO_REFRESH_STATUS_OBSERVING:
                continue
            observe_until = store.parse_sql_time(task.auto_refresh_observe_until)
            if observe_until is None or observe_until > now_dt:
                continue
            if self._finalize_auto_refresh(task):
                changed = True
        return changed

    def _finalize_auto_refresh(self, task: CaptureTask) -> bool:
        if task.id is None:
            return False
        latest = store.get_task(task.id)
        if latest is None:
            store.clear_auto_refresh_global_run()
            return False
        finished_at = store.now_sql()
        started_at = store.parse_sql_time(latest.auto_refresh_started_at)
        session = store.get_edge_session(latest.edge_session_id or "default_real_edge")
        if session is None:
            store.mark_task_auto_refresh_failure(
                latest.id,
                finished_at=finished_at,
                cooldown_seconds=_AUTO_REFRESH_FAILURE_COOLDOWN_SECONDS,
                reason_code=store.AUTO_REFRESH_REASON_EDGE_SESSION_NOT_FOUND,
                reason="自动刷新观察期结束，但当前任务缺少可用的 Edge 会话。",
            )
            store.clear_auto_refresh_global_run()
            return True
        try:
            client = remote_edge_manager.get_client(
                session.session_id,
                name=session.name,
                debug_port=session.debug_port,
                user_data_dir=session.user_data_dir,
                session_mode=session.session_mode,
            )
            if client.is_window_op_running:
                raise RuntimeError(store.AUTO_REFRESH_REASON_WINDOW_OP_IN_PROGRESS)
            if not str(latest.page_id or "").strip():
                raise RuntimeError(store.AUTO_REFRESH_REASON_OBSERVE_PAGE_INVALID)
            page_info = client.find_page(latest.page_id)
            if page_info is None:
                raise RuntimeError(store.AUTO_REFRESH_REASON_OBSERVE_PAGE_INVALID)
            _score, flags = edge_binding.page_match_score(
                latest,
                {"page_id": page_info.page_id, "url": page_info.url, "title": page_info.title},
            )
            if flags.get("is_login_page") or latest.status == "edge_login_page_bound":
                raise RuntimeError(store.AUTO_REFRESH_REASON_OBSERVE_LOGIN_REQUIRED)
        except Exception as exc:
            reason_code = str(exc) or store.AUTO_REFRESH_REASON_OBSERVE_PAGE_INVALID
            store.mark_task_auto_refresh_failure(
                latest.id,
                finished_at=finished_at,
                cooldown_seconds=_AUTO_REFRESH_FAILURE_COOLDOWN_SECONDS,
                reason_code=reason_code,
                reason="自动刷新观察期结束，但页面未恢复到可继续采集状态。",
            )
            store.clear_auto_refresh_global_run()
            self._log_auto_refresh_event(
                "failure",
                latest,
                level=logging.WARNING,
                page_id=latest.page_id,
                status=AUTO_REFRESH_STATUS_COOLDOWN,
                result="failure",
                reason_code=reason_code,
                reason="自动刷新观察期结束，但页面未恢复到可继续采集状态。",
                started_at=latest.auto_refresh_started_at or "",
                cooldown_until=store.sql_after_seconds(finished_at, _AUTO_REFRESH_FAILURE_COOLDOWN_SECONDS),
            )
            return True

        unhealthy_statuses = {
            "parse_failed",
            "needs_recalibration",
            "readonly_failed",
            "edge_login_page_bound",
            "remote_page_not_found",
            "edge_session_not_found",
            "edge_debug_unavailable",
            "edge_debug_disconnected",
        }
        unhealthy_reason_codes = {
            "remote_page_not_found",
            "binding_invalidated",
            "waiting_manual_bind",
            "edge_session_deleted_requires_rebind",
        }
        sample_at = store.parse_sql_time(latest.last_sample_at)
        if latest.status in unhealthy_statuses or latest.last_reason_code in unhealthy_reason_codes:
            reason_code = store.AUTO_REFRESH_REASON_OBSERVE_CAPTURE_UNHEALTHY
            reason = "自动刷新观察期结束，但页面采集状态仍不健康。"
            store.mark_task_auto_refresh_failure(
                latest.id,
                finished_at=finished_at,
                cooldown_seconds=_AUTO_REFRESH_FAILURE_COOLDOWN_SECONDS,
                reason_code=reason_code,
                reason=reason,
            )
            store.clear_auto_refresh_global_run()
            self._log_auto_refresh_event(
                "failure",
                latest,
                level=logging.WARNING,
                page_id=latest.page_id,
                status=AUTO_REFRESH_STATUS_COOLDOWN,
                result="failure",
                reason_code=reason_code,
                reason=reason,
                started_at=latest.auto_refresh_started_at or "",
                cooldown_until=store.sql_after_seconds(finished_at, _AUTO_REFRESH_FAILURE_COOLDOWN_SECONDS),
            )
            return True
        if started_at is not None and (sample_at is None or sample_at < started_at):
            store.mark_task_auto_refresh_failure(
                latest.id,
                finished_at=finished_at,
                cooldown_seconds=_AUTO_REFRESH_FAILURE_COOLDOWN_SECONDS,
                reason_code=store.AUTO_REFRESH_REASON_OBSERVE_TIMEOUT,
                reason="自动刷新观察期结束，但未观测到新的成功采样。",
            )
            store.clear_auto_refresh_global_run()
            self._log_auto_refresh_event(
                "failure",
                latest,
                level=logging.WARNING,
                page_id=latest.page_id,
                status=AUTO_REFRESH_STATUS_COOLDOWN,
                result="failure",
                reason_code=store.AUTO_REFRESH_REASON_OBSERVE_TIMEOUT,
                reason="自动刷新观察期结束，但未观测到新的成功采样。",
                started_at=latest.auto_refresh_started_at or "",
                cooldown_until=store.sql_after_seconds(finished_at, _AUTO_REFRESH_FAILURE_COOLDOWN_SECONDS),
            )
            return True

        store.mark_task_auto_refresh_success(
            latest.id,
            finished_at=finished_at,
            reason_code="",
            reason="自动刷新观察期结束，页面已恢复采样。",
        )
        store.clear_auto_refresh_global_run()
        self._clear_auto_refresh_skip_marker(latest.id)
        self._log_auto_refresh_event(
            "success",
            latest,
            page_id=latest.page_id,
            status=store.AUTO_REFRESH_STATUS_IDLE,
            result="success",
            reason="自动刷新观察期结束，页面已恢复采样。",
            started_at=latest.auto_refresh_started_at or "",
        )
        return True

    def _save_ocr_dataset(self, crop: Image.Image, task: CaptureTask, selected: int | None, ocr_text: str) -> None:
        try:
            DATASET_DIR.mkdir(parents=True, exist_ok=True)
            safe_platform = re.sub(r'[\\/*?:"<>|]', "", task.platform or "未知平台")
            safe_shop = re.sub(r'[\\/*?:"<>|]', "", task.shop_name or "未知店铺")
            safe_text = str(selected) if selected is not None else re.sub(r'[\\/*?:"<>|]', "", ocr_text or "未识别")
            filename = f"{safe_platform}_{safe_shop}_{safe_text}_{int(time.time() * 1000)}.png"
            crop.save(DATASET_DIR / filename)
        except Exception as e:
            logger.warning(f"Failed to save OCR dataset: {e}")

    def capture_once(self, task_id: int) -> dict:
        task = store.get_task(task_id)
        if task is None:
            return {"status": "task_not_found"}
        if not task.enabled:
            return {"status": "disabled"}

        sampled_at = store.now_sql()
        try:
            if task.value_source == "screen_readonly":
                return self._capture_screen_readonly_once(task, sampled_at)
            if task.capture_mode == "remote_edge":
                session = store.get_edge_session(task.edge_session_id or "default_real_edge")
                if session is None:
                    return self._record_failure(
                        task,
                        "edge_session_not_found",
                        "没有找到绑定的真实 Edge 会话",
                        "",
                        reason_code="edge_session_not_found",
                        value_source="ocr",
                    )
                client = remote_edge_manager.get_client(
                    session.session_id,
                    name=session.name,
                    debug_port=session.debug_port,
                    user_data_dir=session.user_data_dir,
                    session_mode=session.session_mode,
                )
                if client.is_window_op_running:
                    return {"status": "skipped_window_op_in_progress"}
                task = self._restore_remote_task_binding(task, client, session.session_id)
                page_info = client.find_page(task.page_id)
                if page_info is None:
                    return self._record_failure(
                        task,
                        "remote_page_not_found",
                        "没有找到真实 Edge 调试页面",
                        "",
                        reason_code="remote_page_not_found",
                        value_source="ocr",
                    )
                full_image, page_info = client.screenshot_page(task.page_id)
                if page_info.url and task.page_url and page_info.url != task.page_url:
                    store.update_task_runtime(task.id, {"last_reason": f"真实 Edge 页面 URL 已变化: {page_info.url}"})
            else:
                window = find_window(task.window_keyword)
                if window is None:
                    return self._record_failure(
                        task,
                        "window_not_found",
                        "没有找到匹配窗口",
                        "",
                        reason_code="window_not_found",
                        value_source="ocr",
                    )
                full_image, _ = capture_window(window.hwnd)

            crop, crop_rect = crop_by_ratio(
                full_image,
                task.x_ratio,
                task.y_ratio,
                task.width_ratio,
                task.height_ratio,
                task.safety_margin,
            )
            screenshot_path = str(store.SCREENSHOT_DIR / f"task_{task.id}_{int(time.time())}.png")
            save_thumbnail(crop, screenshot_path)
            self._cleanup_old_screenshots(task.id)
            ocr_text, details = read_text(
                crop,
                task.keyword_hint,
                task.last_trusted_value,
                platform=task.platform,
                shop_name=task.shop_name,
            )
            candidates = extract_candidates(ocr_text, details, task.keyword_hint, task.last_trusted_value)
            candidate_dicts = candidates_to_dicts(candidates)
            selected = candidates[0].value if candidates else None
            selected_candidate = candidate_dicts[0] if candidate_dicts else None

            # Save dataset for fine-tuning
            self._save_ocr_dataset(crop, task, selected, ocr_text)

            status, reason, trusted, pending_value, pending_count, required_confirms, accepted_after_confirms = self._judge(
                task,
                selected,
                selected_candidate,
            )
            updates = {
                "status": status,
                "last_sample_at": sampled_at,
                "last_ocr_text": ocr_text,
                "last_reason": reason,
                "last_reason_code": "",
                "last_value_source": "ocr",
                "last_screenshot_path": screenshot_path,
                "pending_value": pending_value,
                "pending_count": pending_count,
            }
            if trusted is not None:
                updates["last_trusted_value"] = trusted
                updates["last_success_at"] = sampled_at
            store.update_task_runtime(task.id, updates)
            store.add_sample(
                task.id,
                ocr_text,
                candidate_dicts,
                selected,
                trusted if trusted is not None else task.last_trusted_value,
                status,
                reason,
                screenshot_path,
                sample_meta={
                    "selected_candidate_engine": str((selected_candidate or {}).get("engine") or ""),
                    "selected_candidate_variant": str((selected_candidate or {}).get("variant") or ""),
                    "selected_candidate_source_kind": str((selected_candidate or {}).get("source_kind") or ""),
                    "selected_candidate_correction_count": int((selected_candidate or {}).get("correction_count") or 0),
                    "required_confirms": required_confirms,
                    "accepted_after_confirms": accepted_after_confirms,
                },
            )
            return {
                "status": status,
                "reason": reason,
                "selected_value": selected,
                "trusted_value": trusted,
                "ocr_text": ocr_text,
                "candidates": candidate_dicts,
                "crop_rect": crop_rect,
            }
        except EdgeActionTimeoutError as exc:
            if task.capture_mode == "remote_edge" and task.edge_session_id:
                remote_edge_manager.reset_client(task.edge_session_id)
            return self._record_failure(
                task,
                "edge_action_timeout",
                f"真实 Edge 动作超时: {exc.action} @ {exc.stage}",
                "",
                reason_code=getattr(exc, "reason_code", "edge_action_timeout"),
                value_source=task.value_source or "ocr",
            )
        except Exception as exc:
            from backend.utils.log_throttle import global_throttle

            fp = f"capture:task_{task.id}:{type(exc).__name__}:{str(exc)[:120]}"
            if global_throttle.should_log(fp):
                import traceback

                logger.error(
                    "Capture error task_id=%s platform=%s type=%s: %s\n%s",
                    task.id,
                    task.platform,
                    type(exc).__name__,
                    exc,
                    traceback.format_exc(),
                )
            else:
                logger.warning(
                    "Capture error (suppressed repeat) task_id=%s platform=%s type=%s: %s",
                    task.id,
                    task.platform,
                    type(exc).__name__,
                    exc,
                )
            if task.capture_mode == "remote_edge":
                if "真实 Edge 调试端口未连接" in str(exc):
                    return self._record_failure(
                        task,
                        "edge_debug_unavailable",
                        "当前店铺登录态/Profile 可能仍保留，但 Edge 调试端口未接通，请先启动或显示当前店铺 Edge",
                        "",
                        reason_code="edge_debug_unavailable",
                        value_source=task.value_source or "ocr",
                    )
                if "连接真实 Edge 失败" in str(exc):
                    if task.edge_session_id:
                        remote_edge_manager.reset_client(task.edge_session_id)
                    return self._record_failure(
                        task,
                        "edge_debug_disconnected",
                        "当前店铺调试端口已打开，但自动控制连接尚未恢复，请先显示当前店铺 Edge 后重试",
                        "",
                        reason_code="edge_debug_disconnected",
                        value_source=task.value_source or "ocr",
                    )
            return self._record_failure(
                task,
                "parse_failed",
                f"采集失败: {exc}",
                "",
                reason_code="parse_failed",
                value_source=task.value_source or "ocr",
            )

    def _capture_screen_readonly_once(self, task: CaptureTask, sampled_at: str) -> dict:
        if task.capture_mode != "remote_edge":
            return self._record_failure(
                task,
                "readonly_failed",
                "大屏只读模式仅支持真实 Edge 已绑定页面，请先切换为真实页面采集。",
                "",
                reason_code="screen_readonly_requires_remote_edge",
                value_source="screen_readonly",
            )
        if not shop_config.screen_readonly_supported(task.platform):
            platform_key = shop_config.platform_key(task.platform)
            return self._record_failure(
                task,
                "readonly_failed",
                f"{platform_key} 平台的大屏只读规则尚未配置，请先使用 OCR，或为该平台补充独立只读规则。",
                "",
                reason_code="screen_readonly_platform_unsupported",
                value_source="screen_readonly",
            )
        session = store.get_edge_session(task.edge_session_id or "default_real_edge")
        if session is None:
            return self._record_failure(
                task,
                "edge_session_not_found",
                "没有找到绑定的真实 Edge 会话",
                "",
                reason_code="edge_session_not_found",
                value_source="screen_readonly",
            )
        client = remote_edge_manager.get_client(
            session.session_id,
            name=session.name,
            debug_port=session.debug_port,
            user_data_dir=session.user_data_dir,
            session_mode=session.session_mode,
        )
        if client.is_window_op_running:
            return {"status": "skipped_window_op_in_progress"}
        task = self._restore_remote_task_binding(task, client, session.session_id)
        if not task.page_id:
            return self._record_failure(
                task,
                "readonly_waiting",
                "当前任务还没有绑定真实页面，无法读取大屏正式值。",
                "",
                reason_code="screen_readonly_page_not_bound",
                value_source="screen_readonly",
            )
        result = client.read_screen_pay_amount(task.page_id)
        screen = result.get("screen") or {}
        ready = bool(result.get("ready", screen.get("ready")))
        reason_code = str(result.get("reason_code") or screen.get("reason_code") or "")
        message = str(result.get("message") or screen.get("message") or "")
        pay_amt = result.get("pay_amt", screen.get("pay_amt"))
        raw_pay_amt = pay_amt
        coerced_pay_amt, invalid_reason = self._coerce_screen_readonly_amount(pay_amt)
        if invalid_reason:
            display_value = screen.get("display_value", result.get("display_value", ""))
            metric_label = screen.get("metric_label", result.get("metric_label", ""))
            logger.warning(
                "screen_readonly invalid pay_amt ignored task_id=%s platform=%s shop=%s pay_amt=%r reason=%s "
                "display_value=%r metric_label=%r",
                task.id,
                task.platform,
                task.shop_name,
                pay_amt,
                invalid_reason,
                display_value,
                metric_label,
            )
            ready = False
            pay_amt = None
            reason_code = "screen_payamt_invalid"
            message = "大屏只读返回了异常金额，已保留上次可信值。"
            screen["ready"] = False
            screen["pay_amt"] = None
            screen["reason_code"] = reason_code
            screen["message"] = message
            screen["invalid_pay_amt"] = str(raw_pay_amt)
            result["ready"] = False
            result["pay_amt"] = None
            result["reason_code"] = reason_code
            result["message"] = message
        elif coerced_pay_amt is not None:
            pay_amt = coerced_pay_amt
        screen_platform_key = str(result.get("platform_key") or screen.get("platform_key") or "")
        response_marker_raw = (
            result.get("latest_response_end_seconds", screen.get("latest_response_end_seconds"))
        )
        response_marker = ""
        try:
            marker_value = float(response_marker_raw)
            if marker_value > 0:
                response_marker = f"{marker_value:.3f}"
        except (TypeError, ValueError):
            response_marker = ""
        runtime_status = str(result.get("status") or ("ok" if ready else "readonly_failed"))
        if reason_code == "screen_payamt_invalid":
            runtime_status = "readonly_failed"
        if (
            ready
            and pay_amt is not None
            and task.id is not None
            and screen_platform_key == "京东"
            and response_marker
        ):
            previous_marker = self._readonly_response_markers.get(task.id, "")
            if previous_marker == response_marker:
                reason = "京东前端尚未返回新一轮数据，保留上次正式值。"
                if task.id is not None:
                    store.update_task_runtime(
                        task.id,
                        {
                            "status": "readonly_no_new_data",
                            "last_sample_at": sampled_at,
                            "last_reason": reason,
                            "last_reason_code": "screen_readonly_no_new_data",
                            "last_value_source": "screen_readonly",
                            "last_screenshot_path": "",
                            "pending_value": None,
                            "pending_count": 0,
                        },
                    )
                    store.add_sample(
                        task.id,
                        "",
                        [],
                        int(pay_amt),
                        task.last_trusted_value,
                        "readonly_no_new_data",
                        reason,
                        "",
                        sample_meta={
                            "selected_candidate_source_kind": "screen_readonly",
                            "required_confirms": 1,
                            "accepted_after_confirms": 0,
                        },
                    )
                return {
                    "status": "readonly_no_new_data",
                    "reason": reason,
                    "reason_code": "screen_readonly_no_new_data",
                    "selected_value": int(pay_amt),
                    "trusted_value": task.last_trusted_value,
                    "value_source": "screen_readonly",
                    "screen": screen,
                    "page": result.get("page") or {},
                }
        if ready and pay_amt is not None:
            updates = {
                "last_trusted_value": int(pay_amt),
                "pending_value": None,
                "pending_count": 0,
                "status": "ok",
                "last_success_at": sampled_at,
                "last_sample_at": sampled_at,
                "last_ocr_text": "",
                "last_reason": message or "大屏只读读取成功",
                "last_reason_code": "",
                "last_value_source": "screen_readonly",
                "last_screenshot_path": "",
            }
            if task.id is not None:
                if screen_platform_key == "京东" and response_marker:
                    self._readonly_response_markers[task.id] = response_marker
                store.update_task_runtime(task.id, updates)
                store.add_sample(
                    task.id,
                    "",
                    [],
                    int(pay_amt),
                    int(pay_amt),
                    "ok",
                    updates["last_reason"],
                    "",
                    sample_meta={
                        "selected_candidate_source_kind": "screen_readonly",
                        "required_confirms": 1,
                        "accepted_after_confirms": 1,
                    },
                )
            return {
                "status": "ok",
                "reason": updates["last_reason"],
                "reason_code": "",
                "selected_value": int(pay_amt),
                "trusted_value": int(pay_amt),
                "value_source": "screen_readonly",
                "screen": screen,
                "page": result.get("page") or {},
            }
        mapped_status = "readonly_waiting" if runtime_status == "readonly_waiting" else "readonly_failed"
        reason = message or ("大屏只读暂未就绪" if mapped_status == "readonly_waiting" else "大屏只读读取失败")
        if task.id is not None:
            store.update_task_runtime(
                task.id,
                {
                    "status": mapped_status,
                    "last_sample_at": sampled_at,
                    "last_ocr_text": "",
                    "last_reason": reason,
                    "last_reason_code": reason_code,
                    "last_value_source": "screen_readonly",
                    "last_screenshot_path": "",
                    "pending_value": None,
                    "pending_count": 0,
                },
            )
            store.add_sample(
                task.id,
                "",
                [],
                int(pay_amt) if pay_amt is not None else None,
                task.last_trusted_value,
                mapped_status,
                reason,
                "",
                sample_meta={
                    "selected_candidate_source_kind": "screen_readonly",
                    "required_confirms": 1,
                    "accepted_after_confirms": 0,
                },
            )
        return {
            "status": mapped_status,
            "reason": reason,
            "reason_code": reason_code,
            "selected_value": int(pay_amt) if pay_amt is not None else None,
            "trusted_value": task.last_trusted_value,
            "value_source": "screen_readonly",
            "screen": screen,
            "page": result.get("page") or {},
        }

    @staticmethod
    def _coerce_screen_readonly_amount(value: Any) -> tuple[int | None, str]:
        if value is None:
            return None, ""
        if isinstance(value, bool):
            return None, "not_numeric"
        if isinstance(value, int):
            amount = value
        elif isinstance(value, float):
            if not math.isfinite(value):
                return None, "not_finite"
            amount = int(value)
        elif isinstance(value, str):
            text = value.strip().replace(",", "")
            if not text:
                return None, "empty"
            if "e" in text.lower():
                return None, "scientific_notation"
            try:
                decimal_value = Decimal(text)
            except InvalidOperation:
                return None, "not_numeric"
            if not decimal_value.is_finite():
                return None, "not_finite"
            amount = int(decimal_value)
        else:
            return None, "not_numeric"
        if amount < 0:
            return None, "negative"
        if amount > _SQLITE_INT64_MAX:
            return None, "sqlite_int64_overflow"
        if amount > _SCREEN_READONLY_MAX_PAY_AMT:
            return None, "business_limit_exceeded"
        return amount, ""

    def refresh_page_preview_once(self, task_id: int) -> dict:
        task = store.get_task(task_id)
        if task is None:
            return {"status": "task_not_found"}
        if not task.enabled:
            return {"status": "disabled"}
        if task.capture_mode != "remote_edge":
            return {"status": "skipped", "reason": "preview_requires_bound_remote_edge_page"}
        try:
            session = store.get_edge_session(task.edge_session_id or "default_real_edge")
            if session is None:
                return self._record_page_preview_failure(task, "preview_edge_unavailable", "没有找到绑定的 Edge 会话")
            client = remote_edge_manager.get_client(
                session.session_id,
                name=session.name,
                debug_port=session.debug_port,
                user_data_dir=session.user_data_dir,
                session_mode=session.session_mode,
            )
            if client.is_window_op_running:
                return {"status": "skipped_window_op_in_progress"}
            task = self._restore_remote_task_binding(task, client, session.session_id)
            if not task.page_id:
                return self._record_page_preview_failure(task, "preview_page_not_found", "巡检未找到已绑定页签")
            page_info = client.find_page(task.page_id)
            if page_info is None:
                return self._record_page_preview_failure(task, "preview_page_not_found", "巡检未找到已绑定页签")
            image, _ = client.screenshot_page(task.page_id)
            return self._record_page_preview(task, image, "ok", "页面巡检正常")
        except EdgeActionTimeoutError as exc:
            if task.edge_session_id:
                remote_edge_manager.reset_client(task.edge_session_id)
            return self._record_page_preview_failure(
                task,
                "preview_timeout",
                f"页面巡检截图超时: {exc.action} @ {exc.stage}",
            )
        except Exception as exc:
            message = str(exc)
            if "remote_page_not_found" in message:
                return self._record_page_preview_failure(task, "preview_page_not_found", "巡检未找到已绑定页签")
            if "Edge" in message or "debug" in message.lower():
                return self._record_page_preview_failure(task, "preview_edge_unavailable", "页面巡检无法连接 Edge 调试端口")
            return self._record_page_preview_failure(task, "preview_failed", f"页面巡检失败: {exc}")

    def _record_page_preview(self, task: CaptureTask, image, status: str, reason: str) -> dict:
        if task.id is None:
            return {"status": status, "reason": reason}
        now = store.now_sql()
        preview_path = str(store.SCREENSHOT_DIR / f"task_preview_{task.id}_{int(time.time())}.png")
        save_thumbnail(image, preview_path, max_width=_PREVIEW_MAX_WIDTH)
        self._cleanup_old_screenshots(task.id)
        store.update_task_runtime(
            task.id,
            {
                "last_page_preview_path": preview_path,
                "last_page_preview_at": now,
                "last_page_preview_status": status,
                "last_page_preview_reason": reason,
            },
        )
        return {"status": status, "reason": reason, "preview_path": preview_path}

    def _record_page_preview_failure(self, task: CaptureTask, status: str, reason: str) -> dict:
        if task.id is not None:
            store.update_task_runtime(
                task.id,
                {
                    "last_page_preview_at": store.now_sql(),
                    "last_page_preview_status": status,
                    "last_page_preview_reason": reason,
                },
            )
        return {"status": status, "reason": reason}

    def _record_failure(
        self,
        task: CaptureTask,
        status: str,
        reason: str,
        screenshot_path: str,
        *,
        reason_code: str = "",
        value_source: str = "",
    ) -> dict:
        if task.id is None:
            return {"status": status, "reason": reason, "reason_code": reason_code}
        now = store.now_sql()
        store.update_task_runtime(
            task.id,
            {
                "status": status,
                "last_sample_at": now,
                "last_reason": reason,
                "last_reason_code": reason_code or status,
                "last_value_source": value_source or task.value_source or "",
                "last_screenshot_path": screenshot_path,
            },
        )
        store.add_sample(task.id, "", [], None, task.last_trusted_value, status, reason, screenshot_path)
        return {"status": status, "reason": reason, "reason_code": reason_code or status}

    def _judge(
        self,
        task: CaptureTask,
        selected: int | None,
        selected_candidate: dict[str, Any] | None = None,
    ) -> tuple[str, str, int | None, int | None, int, int, int]:
        if selected is None:
            failure_count = task.pending_count + 1 if task.status in {"parse_failed", "needs_recalibration", "suspect"} else 1
            status = "needs_recalibration" if failure_count >= 5 else "parse_failed"
            return status, "没有识别到可用金额候选", None, task.pending_value, failure_count, 0, 0

        last = task.last_trusted_value
        is_abnormal_jump = False
        abnormal_reason = ""

        # 跨天检测 (使用本地时间)
        is_cross_day = False
        if last is not None and task.last_success_at:
            try:
                last_success_str = str(task.last_success_at).strip()
                if not last_success_str:
                    raise ValueError("empty last_success_at")
                if isinstance(task.last_success_at, (int, float)):
                    last_date = datetime.fromtimestamp(task.last_success_at).date()
                else:
                    last_date = None
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                        try:
                            last_date = datetime.strptime(last_success_str, fmt).date()
                            break
                        except ValueError:
                            continue
                    if last_date is None:
                        raise ValueError(f"unrecognized last_success_at format: {last_success_str[:50]}")
                current_date = datetime.now().date()
                if current_date > last_date:
                    is_cross_day = True
            except Exception:
                logger.warning(
                    "cross_day_check_failed task_id=%s platform=%s shop=%s last_success_at=%s",
                    task.id, task.platform, task.shop_name, repr(task.last_success_at)[:80],
                )

        if last is not None:
            if selected < last:
                if is_cross_day:
                    # 跨天复位，直接接受新一天的初始值
                    return "ok", "跨天重置，接受最新GMV", selected, None, 0, 1, 1
                else:
                    # 同一天内下降（退款或OCR识别截断），永远忽略，不更新可信值
                    return "ok", f"同一天数值下降(从 {last} 降至 {selected})，已忽略", None, None, 0, 0, 0
            elif last > 0 and selected > last * 5:
                is_abnormal_jump = True
                abnormal_reason = f"金额相对上次可信值 {last} 跳变过大"

        guard_reason = self._candidate_guard_reason(selected_candidate)
        required_confirms = self._required_confirms(task.confirm_count, is_abnormal_jump, guard_reason)

        if required_confirms <= 1 and not is_abnormal_jump and not guard_reason:
            return "ok", "识别可信", selected, None, 0, required_confirms, 1

        if task.pending_value is None:
            pending_count = 1
        elif self._is_plausible_next(task.pending_value, selected):
            pending_count = task.pending_count + 1
        else:
            if len(str(abs(selected))) > len(str(abs(task.pending_value))) + 1:
                return (
                    "suspect" if is_abnormal_jump else "pending_confirm",
                    abnormal_reason if is_abnormal_jump else f"新候选量级更完整，等待再次确认 {selected}",
                    None,
                    selected,
                    1,
                    required_confirms,
                    0,
                )
            return (
                "suspect" if is_abnormal_jump else "pending_confirm",
                abnormal_reason if is_abnormal_jump else f"候选波动过大，保留上次候选 {task.pending_value}",
                None,
                task.pending_value,
                max(1, task.pending_count),
                required_confirms,
                0,
            )

        if pending_count >= required_confirms:
            reason_suffix = "（已接受异常跳变）" if is_abnormal_jump else ""
            if guard_reason:
                reason_suffix += f"（低置信来源已补充确认：{guard_reason}）"
            return "ok", f"连续 {pending_count} 次确认" + reason_suffix, selected, None, 0, required_confirms, pending_count

        status = "suspect" if is_abnormal_jump else "pending_confirm"
        if is_abnormal_jump:
            reason = abnormal_reason
        else:
            reason = f"等待连续确认 {pending_count}/{required_confirms}"
        if guard_reason:
            reason = f"{reason}（低置信来源：{guard_reason}）"
        return status, reason, None, selected, pending_count, required_confirms, 0

    @staticmethod
    def _required_confirms(base_confirm_count: int, is_abnormal_jump: bool, guard_reason: str) -> int:
        required_confirms = max(1, int(base_confirm_count or 1))
        if is_abnormal_jump:
            required_confirms = max(required_confirms + 1, 3)
        if not guard_reason:
            return required_confirms
        signals = {part for part in guard_reason.split("+") if part}
        required_confirms = max(required_confirms, 3)
        if {"ddddocr", "heavy_fix"} <= signals or {"joined_text", "heavy_fix"} <= signals:
            required_confirms = max(required_confirms, 4)
        if "weak_structure" in signals and ("joined_text" in signals or "binary_variant" in signals):
            required_confirms = max(required_confirms, 4)
        return required_confirms

    @staticmethod
    def _candidate_guard_reason(candidate: dict[str, Any] | None) -> str:
        if not candidate:
            return ""
        engine = str(candidate.get("engine") or "").strip()
        variant = str(candidate.get("variant") or "").strip()
        source_kind = str(candidate.get("source_kind") or "").strip()
        correction_count = int(candidate.get("correction_count") or 0)
        reasons = {part for part in str(candidate.get("reason") or "").split(",") if part}
        signals: list[str] = []
        if engine == "ddddocr":
            signals.append("ddddocr")
        if source_kind == "joined_text":
            signals.append("joined_text")
        if correction_count >= 2:
            signals.append("heavy_fix")
        if variant in {"otsu", "yellow_digits", "adaptive_binary", "invert_gray"} and correction_count >= 1:
            signals.append("binary_variant")
        if "currency" not in reasons and "separator" not in reasons and "thousand_sep" not in reasons:
            signals.append("weak_structure")
        if ("ddddocr" in signals and "heavy_fix" in signals) or ("joined_text" in signals and "heavy_fix" in signals):
            return "+".join(signals[:3])
        if len(signals) >= 3:
            return "+".join(signals[:3])
        return ""

    @staticmethod
    def _is_plausible_next(previous: int, current: int) -> bool:
        if previous <= 0 or current <= 0:
            return False
        previous_digits = len(str(abs(previous)))
        current_digits = len(str(abs(current)))
        if abs(previous_digits - current_digits) > 1:
            return False
        ratio = current / previous
        return 0.85 <= ratio <= 1.35

    @staticmethod
    def _cleanup_old_screenshots(task_id: int) -> None:
        cutoff = time.time() - _SCREENSHOT_MAX_AGE_DAYS * 86400
        patterns = (f"task_{task_id}_*.png", f"task_preview_{task_id}_*.png")
        try:
            for pattern in patterns:
                files = sorted(
                    store.SCREENSHOT_DIR.glob(pattern),
                    key=lambda f: f.stat().st_mtime,
                    reverse=True,
                )
                max_count = max(1, _SCREENSHOT_MAX_COUNT_PER_TASK)
                for file in files[max_count:]:
                    file.unlink(missing_ok=True)
                for file in files[:max_count]:
                    if file.stat().st_mtime < cutoff:
                        file.unlink(missing_ok=True)
        except Exception:
            pass


scheduler = CaptureScheduler()
