from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.dashboard_dataset import TargetRow
from backend.services.dashboard_query import build_dashboard_view


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
    assert ".summary-grid {\n    grid-template-columns: repeat(2, minmax(0, 1fr));" in styles_content
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
    assert "20260517-mobile-two-col-0003" in official_content
    assert "20260517-mobile-two-col-0003" in test_content


def test_dashboard_api_and_test_api_share_realtime_payload() -> None:
    client = TestClient(app)

    dashboard_payload = client.get("/api/dashboard").json()["data"]
    dashboard_realtime_payload = client.get("/api/dashboard?dataset_id=realtime").json()["data"]
    test_payload = client.get("/api/dashboard-test?dataset_id=realtime").json()["data"]

    keys = ["mode", "summary", "shops", "platforms", "datasets", "selected_dataset_id"]
    assert {key: dashboard_payload.get(key) for key in keys} == {key: test_payload.get(key) for key in keys}
    assert {key: dashboard_realtime_payload.get(key) for key in keys} == {key: test_payload.get(key) for key in keys}


def test_dashboard_api_and_test_api_share_period_payload() -> None:
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
