from __future__ import annotations

from dataclasses import dataclass

AUTO_REFRESH_STATUS_IDLE = "idle"
AUTO_REFRESH_STATUS_RUNNING = "running"
AUTO_REFRESH_STATUS_OBSERVING = "observing"
AUTO_REFRESH_STATUS_COOLDOWN = "cooldown"

AUTO_REFRESH_RESULT_NONE = "none"
AUTO_REFRESH_RESULT_SUCCESS = "success"
AUTO_REFRESH_RESULT_FAILURE = "failure"
AUTO_REFRESH_RESULT_SKIPPED = "skipped"


@dataclass
class CaptureTask:
    id: int | None
    capture_mode: str
    value_source: str
    page_id: str
    page_url: str
    target_page_url: str
    page_title: str
    browser_profile: str
    edge_session_id: str
    platform: str
    shop_name: str
    window_keyword: str
    keyword_hint: str
    interval_seconds: float
    enabled: bool
    base_width: int
    base_height: int
    x: int
    y: int
    width: int
    height: int
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float
    safety_margin: float
    confirm_count: int
    target: int = 0
    sort_order: int = 0
    last_trusted_value: int | None = None
    pending_value: int | None = None
    pending_count: int = 0
    status: str = "pending_confirm"
    last_success_at: str | None = None
    last_sample_at: str | None = None
    last_ocr_text: str = ""
    last_reason: str = ""
    last_reason_code: str = ""
    last_value_source: str = ""
    last_screenshot_path: str = ""
    last_page_preview_path: str = ""
    last_page_preview_at: str | None = None
    last_page_preview_status: str = "pending"
    last_page_preview_reason: str = ""
    auto_refresh_status: str = AUTO_REFRESH_STATUS_IDLE
    auto_refresh_reason_code: str = ""
    auto_refresh_reason: str = ""
    auto_refresh_anchor_at: str | None = None
    auto_refresh_started_at: str | None = None
    auto_refresh_observe_until: str | None = None
    auto_refresh_cooldown_until: str | None = None
    auto_refresh_last_result: str = AUTO_REFRESH_RESULT_NONE
    auto_refresh_last_result_at: str | None = None
    auto_refresh_last_success_at: str | None = None
    auto_refresh_manual_protect_until: str | None = None


@dataclass
class CandidateAmount:
    value: int
    text: str
    score: float
    reason: str
    engine: str = ""
    variant: str = ""
    raw_fragment: str = ""
    raw_text: str = ""
    source_kind: str = ""
    correction_count: int = 0


@dataclass
class EdgeSession:
    session_id: str
    name: str
    platform: str
    shop_name: str
    debug_port: int
    user_data_dir: str
    session_mode: str = "isolated"
    binding_source: str = ""
    binding_source_detail: str = ""
    expected_user_data_dir: str = ""
    user_data_dir_differs: bool = False
    user_data_dir_diff_detail: str = ""
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""
