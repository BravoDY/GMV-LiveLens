from __future__ import annotations

from backend.models import AUTO_REFRESH_RESULT_NONE, AUTO_REFRESH_STATUS_IDLE, CaptureTask
from backend.routers.common import (
    protect_session_tasks_for_manual_intervention,
    protect_task_for_manual_intervention,
)


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
        "last_success_at": None,
        "last_sample_at": None,
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


def test_protect_task_for_manual_intervention_marks_remote_edge_task(monkeypatch) -> None:
    task = _task()
    protected: list[dict[str, object]] = []

    monkeypatch.setattr("backend.routers.common.store.now_sql", lambda: "2026-06-18 12:00:00")
    monkeypatch.setattr(
        "backend.routers.common.store.sql_after_seconds",
        lambda base, seconds: "2026-06-18 13:00:00",
    )
    monkeypatch.setattr(
        "backend.routers.common.store.protect_task_auto_refresh_manually",
        lambda task_id, **kwargs: protected.append({"task_id": task_id, **kwargs}),
    )

    changed = protect_task_for_manual_intervention(
        task,
        source="test_entry",
        reason="进入人工处理流程",
    )

    assert changed is True
    assert protected == [
        {
            "task_id": 1,
            "protected_at": "2026-06-18 12:00:00",
            "protect_seconds": 3600,
            "reason": "进入人工处理流程",
        }
    ]


def test_protect_session_tasks_for_manual_intervention_filters_session_and_mode(monkeypatch) -> None:
    tasks = [
        _task(id=1, edge_session_id="session-1", capture_mode="remote_edge"),
        _task(id=2, edge_session_id="session-2", capture_mode="remote_edge"),
        _task(id=3, edge_session_id="session-1", capture_mode="window_capture"),
    ]
    protected: list[int] = []

    monkeypatch.setattr("backend.routers.common.store.list_tasks", lambda include_disabled=True: tasks)
    monkeypatch.setattr(
        "backend.routers.common.protect_task_for_manual_intervention",
        lambda task, **kwargs: protected.append(int(task.id or 0)) or True,
    )

    result = protect_session_tasks_for_manual_intervention(
        "session-1",
        source="test_session_entry",
        reason="进入会话级人工处理流程",
    )

    assert result == [1]
    assert protected == [1]
