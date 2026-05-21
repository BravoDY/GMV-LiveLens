import tomllib
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from backend.core.config import get_settings
from backend.main import app
from backend.routers.common import frontend_static_version
from backend.services.dashboard_dataset import DashboardDatasetRow, TargetRow
from backend.services.dashboard_query import build_dashboard_view
from backend.version import APP_VERSION

ROOT_DIR = Path(__file__).resolve().parents[1]


def test_dashboard_js_defines_render_snapshot() -> None:
    dashboard_js = ROOT_DIR / "frontend" / "dashboard-shared.js"

    content = dashboard_js.read_text(encoding="utf-8")

    assert "function renderSnapshot(" in content
    assert "renderDashboard();" in content


def test_internal_dashboard_entry_loads_shop_configs_before_tasks() -> None:
    app_js = ROOT_DIR / "frontend" / "app.js"

    content = app_js.read_text(encoding="utf-8")

    assert "function startInternalDashboard()" in content
    assert 'window.location.pathname !== "/dashboard"' in content
    assert "await loadShopConfigs();" in content
    assert "await loadTasks();" in content
    assert content.index("await loadShopConfigs();") < content.index("await loadTasks();")


def test_internal_dashboard_binds_nav_before_async_initialization() -> None:
    app_js = ROOT_DIR / "frontend" / "app.js"
    styles_css = ROOT_DIR / "frontend" / "styles.css"
    official_html = ROOT_DIR / "frontend" / "index.html"

    app_content = app_js.read_text(encoding="utf-8")
    styles_content = styles_css.read_text(encoding="utf-8")
    html_content = official_html.read_text(encoding="utf-8")

    assert "function bindInternalDashboardNav()" in app_content
    assert "nav.dataset.navBound" in app_content
    assert app_content.index("bindInternalDashboardNav();") < app_content.index("await loadShopConfigs();")
    assert "position: relative;\n  z-index: 2;" in styles_content
    assert ".test-dataset-nav-row {\n  display: none;\n  pointer-events: none;" in styles_content
    assert "pointer-events: auto;" in styles_content
    assert '<nav class="header-nav">' in html_content


def test_ws_status_helper_is_defined_before_app_entry_uses_it() -> None:
    core_js = ROOT_DIR / "frontend" / "core.js"
    app_js = ROOT_DIR / "frontend" / "app.js"

    core_content = core_js.read_text(encoding="utf-8")
    app_content = app_js.read_text(encoding="utf-8")

    assert "function setWsStatus(" in core_content
    assert 'const el = $("wsStatus");' in core_content
    assert "el.replaceChildren(dot, document.createTextNode" in core_content
    assert 'setWsStatus("Local admin connected");' in app_content
    assert 'setWsStatus("Local dashboard failed", "bad");' in app_content


def test_internal_dashboard_initializes_debug_panel() -> None:
    app_js = ROOT_DIR / "frontend" / "app.js"
    debug_js = ROOT_DIR / "frontend" / "debug.js"

    app_content = app_js.read_text(encoding="utf-8")
    debug_content = debug_js.read_text(encoding="utf-8")

    assert "function setupDebugPanel()" in debug_content
    assert 'if (typeof setupDebugPanel === "function") {' in app_content
    assert "setupDebugPanel();" in app_content
    assert app_content.index("setupDebugPanel();") < app_content.index("await loadShopConfigs();")


def test_dashboard_cache_refresh_uses_token_aware_api_wrapper() -> None:
    dashboard_public_js = ROOT_DIR / "frontend" / "dashboard-public.js"
    styles_css = ROOT_DIR / "frontend" / "styles.css"
    content = dashboard_public_js.read_text(encoding="utf-8")
    styles_content = styles_css.read_text(encoding="utf-8")

    assert 'fetch("/api/dashboard-cache/refresh"' not in content
    assert 'await api("/api/dashboard-cache/refresh", { method: "POST", cache: "no-store" });' in content
    assert 'refreshCacheBtn.dataset.publicReadonly = "1";' in content
    assert 'btn.dataset.publicReadonly === "1"' in content
    assert "body.public-dashboard-mode .header-actions .test-dataset-refresh-btn" in styles_content
    assert "body.test-dashboard-mode .header-actions .test-dataset-refresh-btn" in styles_content
    assert "公网看板为只读入口，请在本机管理员页面刷新周期缓存" in content
    assert "当前入口禁止刷新，请在本机管理员页面填写 Token 后重试" not in content
    assert "请确认 API Token 与部署入口权限" in content


def test_platform_edge_failures_show_user_visible_message() -> None:
    dashboard_js = ROOT_DIR / "frontend" / "dashboard.js"
    content = dashboard_js.read_text(encoding="utf-8")

    assert "function bindManagerActionButtons()" in content
    assert "await callPlatformEdgeAction(platform, action);" in content
    assert "showMessage(errorMsg, true);" in content
    assert "console.error(`平台操作失败: ${label}`, err);" in content


def test_capture_all_reports_business_failures() -> None:
    core_js = ROOT_DIR / "frontend" / "core.js"
    content = core_js.read_text(encoding="utf-8")

    assert "function showMessage(text, isError = false)" in content
    assert 'toast.id = "globalMessage";' in content
    assert "async function captureAllTasks()" in content
    assert "const results = await Promise.all(promises);" in content
    assert "const failed = results.filter((item) => {" in content
    assert "个任务返回异常" in content
    assert "所有启用任务均已发送采集指令（${results.length} 个）。" in content


def test_global_ocr_engine_persists_runtime_settings() -> None:
    core_js = ROOT_DIR / "frontend" / "core.js"
    app_js = ROOT_DIR / "frontend" / "app.js"
    content = core_js.read_text(encoding="utf-8")
    app_content = app_js.read_text(encoding="utf-8")

    assert "async function loadRuntimeSettings()" in content
    assert "async function saveRuntimeSettingsFromControls()" in content
    assert 'await api("/api/settings", {' in content
    assert 'ocr_engine: engine' in content
    assert 'interval_seconds: intervalSeconds' in content
    assert '$("globalOcrEngine")?.addEventListener("change"' in content
    assert 'await loadRuntimeSettings();' in app_content
    assert app_content.index("await loadRuntimeSettings();") < app_content.index("await loadTasks();")


def test_public_dashboard_polling_keeps_header_connection_label() -> None:
    dashboard_public_js = ROOT_DIR / "frontend" / "dashboard-public.js"
    content = dashboard_public_js.read_text(encoding="utf-8")

    assert 'setPublicDashboardStatus("实时连接");' in content
    assert "看板刷新：" not in content
    assert "看板刷新异常" not in content
    assert "最后更新：" not in content


def test_dashboard_entries_share_public_dashboard_module() -> None:
    test_html = (ROOT_DIR / "frontend" / "test-dashboard" / "index.html").read_text(encoding="utf-8")
    test_app = (ROOT_DIR / "frontend" / "test-dashboard" / "app.js").read_text(encoding="utf-8")
    official_html = (ROOT_DIR / "frontend" / "index.html").read_text(encoding="utf-8")
    official_app = (ROOT_DIR / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "/static/dashboard-public.js" in test_html
    assert "/static/dashboard-public.js" in official_html
    assert "/static/test-dashboard/dashboard.js" in test_html
    assert "/static/test-dashboard/app.js" in test_html
    assert "/static/test-dashboard/" not in official_html
    assert "startSharedPublicDashboard({ publicMode: true })" in test_app
    assert "startSharedPublicDashboard({ publicMode: true })" in official_app
    assert "preserveLocalSnapshot: true" in official_app
    assert "/api/dashboard-test" not in test_app
    assert "/api/dashboard-datasets-test" not in test_app


def test_dashboard_html_responses_rewrite_static_asset_versions() -> None:
    client = TestClient(app)
    version = frontend_static_version()

    for path in ["/", "/dashboard", "/dashboard-test"]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
        assert f"/static/styles.css?v={version}" in response.text
        assert f"/static/dashboard-public.js?v={version}" in response.text
        assert "dashboard-public.js?v=20260516-unified-dashboard-0001" not in response.text


def test_backend_version_matches_pyproject_and_health_payload(monkeypatch) -> None:
    pyproject = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    client = TestClient(app)

    assert APP_VERSION == pyproject["project"]["version"]
    assert app.version == APP_VERSION
    assert client.get("/api/health").json()["data"]["version"] == APP_VERSION

    monkeypatch.setenv("GMV_DEBUG_API_ENABLED", "true")
    get_settings.cache_clear()
    try:
        debug_payload = client.get("/api/debug/status").json()["data"]
    finally:
        get_settings.cache_clear()
    assert debug_payload["app"]["version"] == APP_VERSION


def test_ci_check_runs_key_pytest_regressions() -> None:
    ci_check = ROOT_DIR / "scripts" / "ci_check.py"
    content = ci_check.read_text(encoding="utf-8")

    assert "PYTEST_REGRESSION_FILES" in content
    assert '"tests/test_dashboard_regression.py"' in content
    assert '"tests/test_screen_readonly_hardening.py"' in content
    assert '[sys.executable, "-m", "pytest", *PYTEST_REGRESSION_FILES]' in content


def test_dashboard_mobile_responsive_rules_hide_time_and_prevent_overflow() -> None:
    styles_css = ROOT_DIR / "frontend" / "styles.css"
    official_html = ROOT_DIR / "frontend" / "index.html"
    test_html = ROOT_DIR / "frontend" / "test-dashboard" / "index.html"

    styles_content = styles_css.read_text(encoding="utf-8")
    official_content = official_html.read_text(encoding="utf-8")
    test_content = test_html.read_text(encoding="utf-8")

    assert "@media (max-width: 768px)" in styles_content
    assert "@media (max-width: 420px)" in styles_content
    assert ".summary-time-row {\n    display: none;" in styles_content
    assert ".summary-card-row {" in styles_content
    assert ".platform-summary-grid {" in styles_content
    assert "grid-template-columns: repeat(var(--summary-columns, 4), minmax(0, 1fr));" in styles_content
    assert "grid-column: span var(--total-span, 2);" in styles_content
    assert ".platform-summary-grid {\n  display: contents;" in styles_content
    assert ".summary-grid,\n  .summary-card-row {\n    grid-template-columns: minmax(0, 1fr);" in styles_content
    assert ".platform-summary-grid {\n    display: grid;\n    grid-template-columns: repeat(2, minmax(0, 1fr));" in styles_content
    assert ".total-card-shell,\n  .total-card {\n    grid-column: 1 / -1;" in styles_content
    assert 'grid-template-areas:\n      "target ."\n      "progress yoy";' in styles_content
    assert ".brand-store-grid {\n    grid-template-columns: repeat(2, minmax(0, 1fr));" in styles_content
    assert ".store-metrics {\n    display: flex;\n    flex-direction: column;" in styles_content
    assert ".store-metrics-sep {\n    display: none;" in styles_content
    assert "body.dashboard-page.public-dashboard-mode .app-header .test-dataset-nav-row" in styles_content
    assert "overflow-x: hidden;" in styles_content
    assert "overflow-x: auto;" in styles_content
    assert "clamp(18px, 5.6vw, 23px)" in styles_content
    assert "@media (max-width: 380px)" in styles_content
    assert "20260518-mobile-yoy-line-offset-0013" in official_content
    assert "20260518-mobile-yoy-line-offset-0013" in test_content
    assert ".store-status-tags-inline {\n    display: none;" in styles_content
    assert ".store-status-tags-mobile {\n    display: flex;" in styles_content
    assert ".store-card .card-badge" in styles_content


def test_store_card_renders_mobile_status_row() -> None:
    dashboard_js = ROOT_DIR / "frontend" / "dashboard-shared.js"
    content = dashboard_js.read_text(encoding="utf-8")

    assert "store-status-tags store-status-tags-inline" in content
    assert "store-status-tags store-status-tags-mobile" in content
    assert content.index('<div class="store-gmv">') < content.index('store-status-tags store-status-tags-mobile')


def test_dashboard_summary_grid_uses_fluid_resize_observer() -> None:
    dashboard_js = ROOT_DIR / "frontend" / "dashboard-shared.js"
    content = dashboard_js.read_text(encoding="utf-8")

    assert "function updateSummaryCardLayout()" in content
    assert "new ResizeObserver(updateSummaryCardLayout)" in content
    assert "--summary-columns" in content
    assert "--total-span" in content
    assert 'row.dataset.layout = "featured-line";' in content
    assert 'row.dataset.layout = "stacked-featured";' in content
    assert 'row.style.setProperty("--total-span", String(featuredTotalSpan));' in content
    assert 'row.style.setProperty("--total-span", String(columns));' in content
    assert "--total-span\", \"1\"" not in content
    assert "const featuredTotalSpan = 2;" in content
    assert "const featuredColumns = platformCount + featuredTotalSpan;" in content
    assert "const minPlatformWidth = 214;" in content


def test_dashboard_api_and_test_api_share_realtime_payload() -> None:
    client = TestClient(app)

    dashboard_payload = client.get("/api/dashboard").json()["data"]
    dashboard_realtime_payload = client.get("/api/dashboard?dataset_id=realtime").json()["data"]
    test_payload = client.get("/api/dashboard-test?dataset_id=realtime").json()["data"]

    keys = ["mode", "summary", "shops", "platforms", "datasets", "selected_dataset_id"]
    assert {key: dashboard_payload.get(key) for key in keys} == {key: test_payload.get(key) for key in keys}
    assert {key: dashboard_realtime_payload.get(key) for key in keys} == {key: test_payload.get(key) for key in keys}


def test_dashboard_api_and_test_api_share_period_payload(monkeypatch) -> None:
    import backend.routers.common as common

    monkeypatch.setattr(
        common,
        "build_snapshot",
        lambda: {
            "updated_at": "2026-05-21 12:00:00",
            "tasks": [
                {
                    "id": 1,
                    "enabled": True,
                    "companyshop_name": "shop-a",
                    "shop_name": "shop-a",
                    "platform": "tmall",
                    "brand": "main",
                    "last_trusted_value": 12345,
                    "status": "ok",
                }
            ],
        },
    )

    client = TestClient(app)
    datasets = client.get("/api/dashboard-datasets").json()["data"]["datasets"]
    period = next((item for item in datasets if item.get("type") == "period"), None)
    if not period:
        return

    dataset_id = period["dataset_id"]
    dashboard_payload = client.get(f"/api/dashboard?dataset_id={dataset_id}").json()["data"]
    test_payload = client.get(f"/api/dashboard-test?dataset_id={dataset_id}").json()["data"]

    keys = ["mode", "summary", "shops", "platforms", "datasets", "selected_dataset_id"]
    assert {key: dashboard_payload.get(key) for key in keys} == {key: test_payload.get(key) for key in keys}


def test_period_payload_accumulates_only_effective_to_date_rows(monkeypatch) -> None:
    import backend.services.dashboard_query as dashboard_query

    class FixedDateTime:
        @classmethod
        def now(cls):
            return datetime(2026, 5, 21, 12, 0, 0)

        strptime = staticmethod(datetime.strptime)

    first_rows = [
        DashboardDatasetRow("First Wave", "618第一波", "2026/5/13", "2025/5/16"),
        DashboardDatasetRow("First Wave", "618第一波", "2026/5/20", "2025/5/20"),
    ]
    second_rows = [
        DashboardDatasetRow("second Wave", "618第二波", "2026/5/21", "2025/5/21"),
        DashboardDatasetRow("second Wave", "618第二波", "2026/5/22", "2025/5/22"),
    ]
    rows = [*first_rows, *second_rows]
    overview = {
        "by_product": {
            "618第一波": {
                "dataset_id": "product:618第一波",
                "type": "period",
                "dates": [row.date for row in first_rows],
            },
            "618第二波": {
                "dataset_id": "product:618第二波",
                "type": "period",
                "dates": [row.date for row in second_rows],
            },
        }
    }
    cache = {
        "query_ok": True,
        "date_index": {
            "2026-05-13": {"shop-a": 100},
            "2026-05-20": {"shop-a": 200},
            "2026-05-21": {"shop-a": 400},
        },
        "to_index": {
            "2025-05-16": {"shop-a": 70},
            "2025-05-20": {"shop-a": 30},
            "2025-05-21": {"shop-a": 350},
        },
    }
    tasks = [
        {
            "id": 1,
            "enabled": True,
            "companyshop_name": "shop-a",
            "shop_name": "shop-a",
            "platform": "tmall",
            "brand": "main",
            "last_trusted_value": 1000,
            "status": "ok",
        }
    ]

    monkeypatch.setattr(dashboard_query, "datetime", FixedDateTime)
    monkeypatch.setattr(dashboard_query, "build_dataset_overview", lambda: overview)
    monkeypatch.setattr(dashboard_query, "load_to_date_rows", lambda: rows)
    monkeypatch.setattr(
        dashboard_query,
        "load_target_rows",
        lambda: [
            TargetRow("shop-a", "2026/5/13", 10),
            TargetRow("shop-a", "2026/5/20", 20),
            TargetRow("shop-a", "2026/5/21", 40),
        ],
    )
    monkeypatch.setattr(dashboard_query, "_load_cache", lambda: cache)
    monkeypatch.setattr(dashboard_query, "_is_cache_stale", lambda *_: (False, ""))
    monkeypatch.setattr(dashboard_query, "_refresh_cache", lambda: True)

    first_payload = dashboard_query._build_period_payload("product:618第一波", tasks)
    second_payload = dashboard_query._build_period_payload("product:618第二波", tasks)

    assert first_payload["date_range"] == {"start": "2026-05-13", "end": "2026-05-20"}
    assert first_payload["to_date_range"] == {"start": "2025-05-16", "end": "2025-05-20"}
    assert first_payload["summary"]["total_gmv"] == 300
    assert first_payload["summary"]["total_target"] == 30

    assert second_payload["date_range"] == {"start": "2026-05-21", "end": "2026-05-21"}
    assert second_payload["to_date_range"] == {"start": "2025-05-21", "end": "2025-05-21"}
    assert second_payload["summary"]["total_gmv"] == 1400
    assert second_payload["summary"]["total_target"] == 40


def test_realtime_dashboard_test_payload_contains_shops(monkeypatch) -> None:
    def fake_snapshot() -> dict[str, object]:
        return {
            "updated_at": "2026-05-14 19:30:00",
            "tasks": [
                {
                    "id": 1,
                    "enabled": True,
                    "platform": "tmall",
                    "brand": "main",
                    "shop_name": "shop-a",
                    "last_trusted_value": 12345,
                    "target": 20000,
                    "status": "ok",
                    "last_sample_at": "2026-05-14 19:29:59",
                    "value_source": "screen_readonly",
                },
                {
                    "id": 2,
                    "enabled": False,
                    "platform": "jd",
                    "shop_name": "shop-disabled",
                    "last_trusted_value": 999,
                },
            ],
        }

    import backend.routers.common as common
    import backend.services.dashboard_query as dashboard_query

    monkeypatch.setattr(common, "build_snapshot", fake_snapshot)
    monkeypatch.setattr(dashboard_query, "_today", lambda: "2026-05-14")
    monkeypatch.setattr(
        dashboard_query,
        "load_target_rows",
        lambda: [TargetRow(companyshop_name="shop-a", date="2026/05/14", target=20000)],
    )

    payload = build_dashboard_view("realtime")

    assert payload["summary"]["total_gmv"] == 12345
    assert payload["summary"]["total_target"] == 20000
    assert payload["summary"]["active_tasks"] == 1
    assert payload["shops"] == [
        {
            "task_id": 1,
            "companyshop_name": "shop-a",
            "shop_name": "shop-a",
            "platform": "tmall",
            "brand": "main",
            "gmv": 12345,
            "target": 20000,
            "status": "ok",
            "updated_at": "2026-05-14 19:29:59",
            "value_source": "screen_readonly",
            "yoy": "--",
        }
    ]
    assert payload["platforms"][0]["platform"] == "tmall"
    assert payload["platforms"][0]["total_gmv"] == 12345
