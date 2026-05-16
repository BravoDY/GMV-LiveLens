from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from backend.routers.common import build_snapshot
from backend.services.dashboard_dataset import build_dataset_overview


def _parse_date(value: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _today_ymd() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def build_public_dashboard() -> dict[str, Any]:
    """Build the single fixed public dashboard payload.

    This endpoint intentionally has no free-form filters. Public dashboards are
    fixed-display screens; future navigation pages should get their own route or
    payload shape instead of overloading this payload with ad-hoc filters.
    """
    snapshot = build_snapshot()
    tasks = snapshot.get("tasks", [])
    datasets = build_dataset_overview().get("datasets", [])
    active_dataset = next((item for item in datasets if item.get("type") == "realtime"), datasets[0] if datasets else {})

    enabled_tasks = [task for task in tasks if task.get("enabled")]
    platforms_map: dict[str, dict[str, Any]] = {}
    shops: list[dict[str, Any]] = []
    brand_totals: dict[str, int] = defaultdict(int)

    for task in enabled_tasks:
        platform = str(task.get("platform") or "其他平台").strip() or "其他平台"
        shop_name = str(task.get("shop_name") or "未命名店铺").strip() or "未命名店铺"
        brand = str(task.get("brand") or "").strip()
        value = int(task.get("last_trusted_value") or 0)
        status = str(task.get("status") or "unknown")

        if platform not in platforms_map:
            platforms_map[platform] = {
                "platform": platform,
                "total_gmv": 0,
                "task_count": 0,
                "ok_tasks": 0,
                "alert_tasks": 0,
                "shops": [],
            }

        platform_entry = platforms_map[platform]
        platform_entry["total_gmv"] += value
        platform_entry["task_count"] += 1
        if status == "ok":
            platform_entry["ok_tasks"] += 1
        else:
            platform_entry["alert_tasks"] += 1

        shop_item = {
            "task_id": task.get("id"),
            "shop_name": shop_name,
            "platform": platform,
            "brand": brand,
            "gmv": value,
            "status": status,
            "updated_at": task.get("last_sample_at") or task.get("updated_at") or snapshot.get("updated_at"),
            "value_source": task.get("last_value_source") or task.get("value_source") or "ocr",
        }
        platform_entry["shops"].append(shop_item)
        shops.append(shop_item)

        if brand:
            brand_totals[brand] += value

    platform_order: list[str] = []
    for t in enabled_tasks:
        p = str(t.get("platform") or "其他平台").strip()
        if p not in platform_order:
            platform_order.append(p)
    platforms = sorted(platforms_map.values(), key=lambda item: platform_order.index(item["platform"]) if item["platform"] in platform_order else 999)
    for item in platforms:
        item["shops"].sort(key=lambda shop: next((i for i, t in enumerate(enabled_tasks) if t.get("shop_name") == shop["shop_name"] and str(t.get("platform") or "").strip() == shop["platform"]), 999))
    brands = [
        {"brand": brand, "total_gmv": total}
        for brand, total in sorted(brand_totals.items(), key=lambda pair: pair[1], reverse=True)
    ]

    active_tasks = len(enabled_tasks)
    ok_tasks = sum(1 for task in enabled_tasks if task.get("status") == "ok")
    total_gmv = sum(int(task.get("last_trusted_value") or 0) for task in enabled_tasks)

    return {
        "summary": {
            "total_gmv": total_gmv,
            "active_tasks": active_tasks,
            "ok_tasks": ok_tasks,
            "alert_tasks": max(0, active_tasks - ok_tasks),
        },
        "platforms": platforms,
        "shops": shops,
        "brands": brands,
        "generated_at": snapshot.get("updated_at"),
        "source": "public_dashboard_v1",
        "active_dataset": active_dataset,
        "dashboard_datasets": datasets,
        "today": _today_ymd(),
    }
