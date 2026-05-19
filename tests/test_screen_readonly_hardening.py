from __future__ import annotations

import math
import re
from pathlib import Path
from types import SimpleNamespace

import backend.services.scheduler as scheduler_mod
from backend.models import CaptureTask
from backend.services.scheduler import CaptureScheduler

ROOT_DIR = Path(__file__).resolve().parents[1]


def _parse_first_douyin_amount_after_label(page_text: str) -> int | None:
    metric_label = "今日用户支付金额"
    excluded_metric_label = "今日用户支付金额(含异常交易)"
    search_from = 0
    start_index = -1
    while search_from < len(page_text):
        candidate_index = page_text.find(metric_label, search_from)
        if candidate_index < 0:
            break
        if not page_text.startswith(excluded_metric_label, candidate_index):
            start_index = candidate_index
            break
        search_from = candidate_index + len(metric_label)
    if start_index < 0:
        return None
    excluded_index = page_text.find(excluded_metric_label, start_index + len(metric_label))
    tail = (
        page_text[start_index + len(metric_label) : excluded_index]
        if excluded_index > start_index
        else page_text[start_index + len(metric_label) : start_index + len(metric_label) + 180]
    )
    tail = re.split(r"数据更新|更新时间|同比|环比|较昨日|昨日|近[37]日", tail)[0]

    def parse_token(amount_text: str, unit: str = "") -> int | None:
        if not re.match(r"^(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$", amount_text):
            return None
        digits_only = amount_text.replace(",", "").replace(".", "")
        if len(digits_only) > 13:
            return None
        value = float(amount_text.replace(",", ""))
        multiplier = 100000000 if unit == "亿" else 10000 if unit == "万" else 1
        return round(value * multiplier)

    def is_stable_fallback_amount(amount_text: str, unit: str, value: int) -> bool:
        if value == 0:
            return True
        if unit:
            return True
        if "," in amount_text:
            return True
        return len(re.sub(r"[^\d]", "", amount_text)) >= 4

    currency_match = re.search(r"[¥￥]", tail)
    if currency_match:
        amount_block = ""
        for char in tail[currency_match.end() :]:
            if re.match(r"[\d,.\s]", char):
                amount_block += char
                continue
            if char in {"万", "亿"}:
                break
            if amount_block.strip():
                break
        amount_text = re.sub(r"\s+", "", amount_block)
        if amount_text and re.search(r"\d", amount_text):
            parsed_currency = parse_token(amount_text)
            if parsed_currency is not None:
                return parsed_currency

    pattern = re.compile(r"(?:[¥￥]\s*)?((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(万|亿)?")
    for match in pattern.finditer(tail):
        amount_text = match.group(1)
        unit = match.group(2) or ""
        before = tail[max(0, match.start() - 2) : match.start()]
        after = tail[match.end() : match.end() + 4]
        if re.search(r"\d\s*$", before) or re.match(r"^\s+\d", after):
            continue
        parsed = parse_token(amount_text, unit)
        if parsed is not None and is_stable_fallback_amount(amount_text, unit, parsed):
            return parsed
    return None


def test_screen_readonly_amount_guard_accepts_normal_values() -> None:
    coerce = CaptureScheduler._coerce_screen_readonly_amount

    assert coerce(0) == (0, "")
    assert coerce(208623) == (208623, "")
    assert coerce(3387053.0) == (3387053, "")
    assert coerce("999,999,999,999") == (999999999999, "")


def test_screen_readonly_amount_guard_rejects_invalid_values() -> None:
    coerce = CaptureScheduler._coerce_screen_readonly_amount

    assert coerce(math.inf)[1] == "not_finite"
    assert coerce(math.nan)[1] == "not_finite"
    assert coerce(-1)[1] == "negative"
    assert coerce("2.89e+109")[1] == "scientific_notation"
    assert coerce(2**63)[1] == "sqlite_int64_overflow"
    assert coerce(1_000_000_000_001)[1] == "business_limit_exceeded"


def test_readonly_failure_backoff_only_applies_to_failures() -> None:
    scheduler = CaptureScheduler()

    class Task:
        interval_seconds = 1

    task = Task()
    assert scheduler._readonly_next_interval_seconds(task, 1, "ok") == 1
    assert scheduler._readonly_next_interval_seconds(task, 1, "readonly_waiting") == 1
    assert scheduler._readonly_next_interval_seconds(task, 1, "readonly_failed") >= 10


def _readonly_task(**overrides) -> CaptureTask:
    defaults = {
        "id": 99,
        "capture_mode": "remote_edge",
        "value_source": "screen_readonly",
        "page_id": "page-1",
        "page_url": "https://example.com/screen",
        "target_page_url": "https://example.com/screen",
        "page_title": "screen",
        "browser_profile": "",
        "edge_session_id": "session-1",
        "platform": "天猫",
        "shop_name": "shop-a",
        "window_keyword": "",
        "keyword_hint": "",
        "interval_seconds": 1.0,
        "enabled": True,
        "base_width": 100,
        "base_height": 100,
        "x": 0,
        "y": 0,
        "width": 10,
        "height": 10,
        "x_ratio": 0.0,
        "y_ratio": 0.0,
        "width_ratio": 0.1,
        "height_ratio": 0.1,
        "safety_margin": 0.0,
        "confirm_count": 1,
        "last_trusted_value": 200000,
        "last_success_at": "2026-05-19 00:00:00",
        "status": "edge_target_page_ready",
    }
    defaults.update(overrides)
    return CaptureTask(**defaults)


def _patch_readonly_runtime(monkeypatch, client, updates, samples) -> None:
    session = SimpleNamespace(
        session_id="session-1",
        name="session-1",
        debug_port=9222,
        user_data_dir="",
        session_mode="isolated",
    )
    monkeypatch.setattr(scheduler_mod.store, "get_edge_session", lambda _session_id: session)
    monkeypatch.setattr(scheduler_mod.remote_edge_manager, "get_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        scheduler_mod.store,
        "update_task_runtime",
        lambda task_id, payload: updates.append({"task_id": task_id, **payload}),
    )
    monkeypatch.setattr(
        scheduler_mod.store,
        "add_sample",
        lambda *args, **kwargs: samples.append({"args": args, "kwargs": kwargs}),
    )


def test_readonly_accepts_valid_lower_value_after_daily_reset(monkeypatch) -> None:
    updates: list[dict] = []
    samples: list[dict] = []

    class Client:
        is_window_op_running = False

        def read_screen_pay_amount(self, page_id):
            return {
                "ready": True,
                "status": "ok",
                "pay_amt": 50000,
                "screen": {"ready": True, "pay_amt": 50000, "platform_key": "天猫"},
                "page": {"page_id": page_id},
            }

    _patch_readonly_runtime(monkeypatch, Client(), updates, samples)

    result = CaptureScheduler()._capture_screen_readonly_once(
        _readonly_task(last_trusted_value=200000),
        "2026-05-19 07:00:00",
    )

    assert result["status"] == "ok"
    assert result["selected_value"] == 50000
    assert result["trusted_value"] == 50000
    assert updates[-1]["status"] == "ok"
    assert updates[-1]["last_trusted_value"] == 50000
    assert samples[-1]["args"][5] == "ok"


def test_readonly_no_new_data_updates_runtime(monkeypatch) -> None:
    updates: list[dict] = []
    samples: list[dict] = []

    class Client:
        is_window_op_running = False

        def read_screen_pay_amount(self, page_id):
            return {
                "ready": True,
                "status": "ok",
                "pay_amt": 200000,
                "latest_response_end_seconds": 123.456,
                "screen": {
                    "ready": True,
                    "pay_amt": 200000,
                    "platform_key": "京东",
                    "latest_response_end_seconds": 123.456,
                },
                "page": {"page_id": page_id},
            }

    scheduler = CaptureScheduler()
    scheduler._readonly_response_markers[99] = "123.456"
    _patch_readonly_runtime(monkeypatch, Client(), updates, samples)

    result = scheduler._capture_screen_readonly_once(
        _readonly_task(platform="京东", last_trusted_value=200000),
        "2026-05-19 07:00:00",
    )

    assert result["status"] == "readonly_no_new_data"
    assert result["trusted_value"] == 200000
    assert updates[-1]["status"] == "readonly_no_new_data"
    assert updates[-1]["last_reason_code"] == "screen_readonly_no_new_data"
    assert updates[-1]["last_sample_at"] == "2026-05-19 07:00:00"
    assert samples[-1]["args"][5] == "readonly_no_new_data"


def test_douyin_readonly_parser_uses_bounded_amount_tokens() -> None:
    content = (ROOT_DIR / "backend" / "collectors" / "edge" / "_readonly.py").read_text(encoding="utf-8")

    assert "今日用户支付金额" in content
    assert "今日用户支付金额(含异常交易)" in content
    assert "parseMoneyToken" in content
    assert "amountTokenPattern" in content
    assert "parseCurrencyBlockMetricAmount" in content
    assert r"[\d\s,]*" not in content
    assert r"[0-9][\d\s,]*" not in content
    assert "digitsOnly.length > 13" in content


def test_douyin_readonly_parser_regression_examples() -> None:
    assert (
        _parse_first_douyin_amount_after_label(
            "今日用户支付金额 ¥3,387,053 今日用户支付金额(含异常交易) 3,500,000 "
            "数据更新 2026/05/18 16:51:43 同比 12.3%"
        )
        == 3387053
    )
    assert _parse_first_douyin_amount_after_label("今日用户支付金额 338.70万 数据更新 2026/05/18") == 3387000
    assert _parse_first_douyin_amount_after_label("今日用户支付金额 ￥4,211,829 万 数据更新 2026/05/18") == 4211829
    assert _parse_first_douyin_amount_after_label("今日用户支付金额 ￥ 4 , 211 , 829 万 数据更新 2026/05/18") == 4211829
    assert _parse_first_douyin_amount_after_label("今日用户支付金额 ￥4 211 829 万 数据更新 2026/05/18") == 4211829
    assert _parse_first_douyin_amount_after_label("今日用户支付金额(含异常交易) ￥9,999") is None
    assert (
        _parse_first_douyin_amount_after_label(
            "今日用户支付金额 2 026 05 18 16 51 43 今日用户支付金额(含异常交易) 9,999"
        )
        is None
    )
    assert _parse_first_douyin_amount_after_label("今日用户支付金额 4 数据更新 2026/05/18") is None
