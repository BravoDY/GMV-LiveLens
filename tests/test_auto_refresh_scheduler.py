from __future__ import annotations

from types import SimpleNamespace

from backend.models import (
    AUTO_REFRESH_RESULT_NONE,
    AUTO_REFRESH_STATUS_IDLE,
    AUTO_REFRESH_STATUS_OBSERVING,
    CaptureTask,
)
from backend.services.scheduler import CaptureScheduler


def _task(**overrides) -> CaptureTask:
    defaults = {
        "id": 1,
        "capture_mode": "remote_edge",
        "value_source": "ocr",
        "page_id": "page-1",
        "page_url": "https://shop.example.com/dashboard",
        "target_page_url": "https://shop.example.com/dashboard",
        "page_title": "店铺后台",
        "browser_profile": "profile-1",
        "edge_session_id": "session-1",
        "platform": "天猫",
        "shop_name": "测试店铺",
        "window_keyword": "",
        "keyword_hint": "成交金额",
        "interval_seconds": 2.0,
        "enabled": True,
        "base_width": 1280,
        "base_height": 720,
        "x": 0,
        "y": 0,
        "width": 100,
        "height": 100,
        "x_ratio": 0.0,
        "y_ratio": 0.0,
        "width_ratio": 0.1,
        "height_ratio": 0.1,
        "safety_margin": 0.05,
        "confirm_count": 2,
        "last_trusted_value": None,
        "pending_value": None,
        "pending_count": 0,
        "status": "ok",
        "last_success_at": "2026-06-18 09:00:00",
        "last_sample_at": "2026-06-18 09:00:10",
        "last_ocr_text": "",
        "last_reason": "",
        "last_reason_code": "",
        "last_value_source": "ocr",
        "last_screenshot_path": "",
        "last_page_preview_path": "",
        "last_page_preview_at": None,
        "last_page_preview_status": "pending",
        "last_page_preview_reason": "",
        "target": 0,
        "sort_order": 0,
        "auto_refresh_status": AUTO_REFRESH_STATUS_IDLE,
        "auto_refresh_reason_code": "",
        "auto_refresh_reason": "",
        "auto_refresh_anchor_at": "2026-06-18 06:00:00",
        "auto_refresh_started_at": None,
        "auto_refresh_observe_until": None,
        "auto_refresh_cooldown_until": None,
        "auto_refresh_last_result": AUTO_REFRESH_RESULT_NONE,
        "auto_refresh_last_result_at": None,
        "auto_refresh_last_success_at": None,
        "auto_refresh_manual_protect_until": None,
    }
    defaults.update(overrides)
    return CaptureTask(**defaults)


def test_select_auto_refresh_candidate_prefers_oldest_eligible() -> None:
    scheduler = CaptureScheduler()
    newest = _task(id=1, auto_refresh_anchor_at="2026-06-18 08:30:00")
    cooled = _task(id=2, auto_refresh_cooldown_until="2099-06-18 12:00:00")
    oldest = _task(id=3, auto_refresh_anchor_at="2026-06-18 05:00:00")

    selected = scheduler._select_auto_refresh_candidate([newest, cooled, oldest])

    assert selected is not None
    assert selected.id == 3


def test_trigger_auto_refresh_marks_observing_and_global_running(monkeypatch) -> None:
    scheduler = CaptureScheduler()
    task = _task()
    session = SimpleNamespace(
        session_id="session-1",
        name="session-1",
        debug_port=9222,
        user_data_dir="",
        session_mode="isolated",
    )
    started: list[dict] = []
    observing: list[dict] = []
    global_runs: list[dict] = []

    class Client:
        is_window_op_running = False

        def find_page(self, page_id):
            return SimpleNamespace(page_id=page_id, url=task.page_url, title=task.page_title)

        def reload_page(self, page_id):
            return SimpleNamespace(page_id=page_id)

    monkeypatch.setattr("backend.services.scheduler.store.get_edge_session", lambda _sid: session)
    monkeypatch.setattr("backend.services.scheduler.remote_edge_manager.get_client", lambda *args, **kwargs: Client())
    monkeypatch.setattr(
        "backend.services.scheduler.store.start_task_auto_refresh",
        lambda task_id, **kwargs: started.append({"task_id": task_id, **kwargs}),
    )
    monkeypatch.setattr(
        "backend.services.scheduler.store.mark_task_auto_refresh_observing",
        lambda task_id, **kwargs: observing.append({"task_id": task_id, **kwargs}),
    )
    monkeypatch.setattr(
        "backend.services.scheduler.store.start_auto_refresh_global_run",
        lambda task_id, **kwargs: global_runs.append({"task_id": task_id, **kwargs}),
    )

    changed = scheduler._trigger_auto_refresh(task)

    assert changed is True
    assert started[-1]["task_id"] == 1
    assert global_runs[-1]["task_id"] == 1
    assert observing[-1]["task_id"] == 1
    assert observing[-1]["observe_seconds"] == 60


def test_finalize_auto_refresh_failure_enters_cooldown(monkeypatch) -> None:
    scheduler = CaptureScheduler()
    latest = _task(
        auto_refresh_status=AUTO_REFRESH_STATUS_OBSERVING,
        auto_refresh_started_at="2026-06-18 09:00:00",
        auto_refresh_observe_until="2026-06-18 09:01:00",
        last_sample_at="2026-06-18 08:59:00",
    )
    session = SimpleNamespace(
        session_id="session-1",
        name="session-1",
        debug_port=9222,
        user_data_dir="",
        session_mode="isolated",
    )
    failures: list[dict] = []
    cleared: list[bool] = []

    class Client:
        is_window_op_running = False

        def find_page(self, page_id):
            return SimpleNamespace(page_id=page_id, url=latest.page_url, title=latest.page_title)

    monkeypatch.setattr("backend.services.scheduler.store.get_task", lambda _task_id: latest)
    monkeypatch.setattr("backend.services.scheduler.store.get_edge_session", lambda _sid: session)
    monkeypatch.setattr("backend.services.scheduler.remote_edge_manager.get_client", lambda *args, **kwargs: Client())
    monkeypatch.setattr(
        "backend.services.scheduler.store.mark_task_auto_refresh_failure",
        lambda task_id, **kwargs: failures.append({"task_id": task_id, **kwargs}),
    )
    monkeypatch.setattr(
        "backend.services.scheduler.store.clear_auto_refresh_global_run",
        lambda: cleared.append(True),
    )

    changed = scheduler._finalize_auto_refresh(latest)

    assert changed is True
    assert failures[-1]["task_id"] == 1
    assert failures[-1]["reason_code"] == "observe_timeout"
    assert failures[-1]["cooldown_seconds"] == 7200
    assert cleared
