from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import pymysql

from backend.services.dashboard_dataset import DATA_DIR, TO_DATE_PATH, build_dataset_overview, load_target_rows, load_to_date_rows

logger = logging.getLogger(__name__)

MYSQL_HOST = os.environ.get("MYSQL_HOST", "")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "")
MYSQL_SOURCE_TABLE = os.environ.get("MYSQL_SOURCE_TABLE", "descente_al店铺整体取数源")

MYSQL_COL_PLATFORM = os.environ.get("MYSQL_COL_PLATFORM", "平台")
MYSQL_COL_DATE = os.environ.get("MYSQL_COL_DATE", "统计日期")
MYSQL_COL_AMOUNT = os.environ.get("MYSQL_COL_AMOUNT", "支付金额")

CACHE_DIR = DATA_DIR / ".cache"
CACHE_PATH = CACHE_DIR / "period_gmv.json"


def _parse_date(value: str):
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _compute_to_date_hash() -> str:
    if not TO_DATE_PATH.exists():
        return ""
    return hashlib.sha256(TO_DATE_PATH.read_bytes()).hexdigest()


def _is_cache_stale(cached_at_str: str, to_date_hash: str) -> tuple[bool, str]:
    """返回 (是否过期, 原因)。过期规则: to_date_hash 不一致 或 跨天且当前时间>10:00"""
    if not cached_at_str:
        return (True, "no_cache")

    current_hash = _compute_to_date_hash()
    if current_hash and to_date_hash and current_hash != to_date_hash:
        return (True, "csv_changed")

    try:
        cached_dt = datetime.fromisoformat(cached_at_str)
    except ValueError:
        return (True, "invalid_timestamp")

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    refresh_deadline = today_start.replace(hour=10, minute=0)

    if cached_dt < today_start and now >= refresh_deadline:
        return (True, "cross_day")

    return (False, "")


def _load_cache() -> dict[str, Any] | None:
    if not CACHE_PATH.exists():
        return None
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(payload: dict[str, Any]) -> None:
    _ensure_cache_dir()
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _query_mysql_or_range(cur_start: str, cur_end: str, ly_start: str, ly_end: str) -> tuple[bool, list[dict[str, Any]]]:
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset="utf8mb4",
            connect_timeout=10,
            read_timeout=30,
        )
        with conn:
            with conn.cursor() as cur:
                sql = (
                    f"SELECT `{MYSQL_COL_PLATFORM}`, `{MYSQL_COL_DATE}`, `{MYSQL_COL_AMOUNT}` "
                    f"FROM `{MYSQL_SOURCE_TABLE}` "
                    f"WHERE ( `{MYSQL_COL_DATE}` >= %s AND `{MYSQL_COL_DATE}` <= %s ) "
                    f"   OR ( `{MYSQL_COL_DATE}` >= %s AND `{MYSQL_COL_DATE}` <= %s )"
                )
                cur.execute(sql, (cur_start, cur_end, ly_start, ly_end))
                rows = cur.fetchall()
    except pymysql.err.OperationalError as exc:
        logger.warning("MySQL 连接失败 (OperationalError): %s", exc)
        return (False, [])
    except Exception as exc:
        logger.warning("MySQL 查询异常: %s", exc)
        return (False, [])

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append({
            "platform": str(row[0] or "").strip(),
            "date": str(row[1] or "").strip(),
            "pay_amount": float(row[2] or 0),
        })
    return (True, result)


def _query_all_periods_mysql() -> dict[str, Any]:
    """一次 MySQL OR 查询覆盖本期+同期，返回 {periods, date_index, to_index, query_ok}"""
    overview = build_dataset_overview()
    period_datasets = overview.get("by_product", {})

    if not period_datasets:
        return {"cached_at": datetime.now().isoformat(), "to_date_hash": _compute_to_date_hash(), "query_ok": True, "periods": {}, "date_index": {}, "to_index": {}}

    all_dates: list[str] = []
    all_to_dates: list[str] = []
    for ds in period_datasets.values():
        for d in ds.get("dates") or []:
            if d and d not in all_dates:
                all_dates.append(d)
        for d in ds.get("to_dates") or []:
            if d and d not in all_to_dates:
                all_to_dates.append(d)

    parsed = sorted([d for d in (_parse_date(d) for d in all_dates) if d is not None])
    to_parsed = sorted([d for d in (_parse_date(d) for d in all_to_dates) if d is not None])

    if not parsed:
        return {"cached_at": datetime.now().isoformat(), "to_date_hash": _compute_to_date_hash(), "query_ok": True, "periods": {}, "date_index": {}, "to_index": {}}

    cur_start = parsed[0].strftime("%Y-%m-%d")
    cur_end = parsed[-1].strftime("%Y-%m-%d")
    ly_start = to_parsed[0].strftime("%Y-%m-%d") if to_parsed else cur_start
    ly_end = to_parsed[-1].strftime("%Y-%m-%d") if to_parsed else cur_end

    ok, all_rows = _query_mysql_or_range(cur_start, cur_end, ly_start, ly_end)
    if not ok:
        return {"cached_at": datetime.now().isoformat(), "to_date_hash": _compute_to_date_hash(), "query_ok": False, "periods": {}, "date_index": {}, "to_index": {}}

    date_index: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    to_index: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in all_rows:
        platform = row["platform"]
        date = row["date"]
        if not platform or not date:
            continue
        amt = float(row["pay_amount"] or 0)
        pd = _parse_date(date)
        if pd is None:
            continue
        d_normalized = pd.strftime("%Y-%m-%d")
        if d_normalized >= cur_start and d_normalized <= cur_end:
            date_index[d_normalized][platform] += amt
        if d_normalized >= ly_start and d_normalized <= ly_end:
            to_index[d_normalized][platform] += amt

    periods: dict[str, dict[str, float]] = {}
    ly_periods: dict[str, dict[str, float]] = {}
    for ds_id, ds in period_datasets.items():
        raw_dates = set(ds.get("dates") or [])
        ds_dates = set()
        for rd in raw_dates:
            pd = _parse_date(rd)
            if pd:
                ds_dates.add(pd.strftime("%Y-%m-%d"))
        ds_map: dict[str, float] = defaultdict(float)
        for d in ds_dates:
            for csn, amt in date_index.get(d, {}).items():
                ds_map[csn] += amt
        periods[ds_id] = dict(ds_map)

        raw_to_dates = set(ds.get("to_dates") or [])
        ds_to_dates = set()
        for rd in raw_to_dates:
            pd = _parse_date(rd)
            if pd:
                ds_to_dates.add(pd.strftime("%Y-%m-%d"))
        ly_map: dict[str, float] = defaultdict(float)
        for d in ds_to_dates:
            for csn, amt in to_index.get(d, {}).items():
                ly_map[csn] += amt
        ly_periods[ds_id] = dict(ly_map)

    return {
        "cached_at": datetime.now().isoformat(),
        "to_date_hash": _compute_to_date_hash(),
        "query_ok": True,
        "periods": periods,
        "ly_periods": {k: dict(v) for k, v in ly_periods.items()},
        "date_index": {k: dict(v) for k, v in date_index.items()},
        "to_index": {k: dict(v) for k, v in to_index.items()},
    }


def _refresh_cache() -> bool:
    """刷新缓存，返回是否成功"""
    try:
        payload = _query_all_periods_mysql()
        if not payload["query_ok"]:
            logger.warning("缓存刷新失败：MySQL 连接不可用")
            return False
        _save_cache(payload)
        logger.info("缓存刷新完成，cached_at=%s", payload["cached_at"])
        return True
    except Exception:
        logger.exception("缓存刷新异常")
        return False


def _query_mysql_range(start_date: str, end_date: str) -> tuple[bool, list[dict[str, Any]]]:
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset="utf8mb4",
            connect_timeout=10,
            read_timeout=30,
        )
        with conn:
            with conn.cursor() as cur:
                sql = (
                    f"SELECT `{MYSQL_COL_PLATFORM}`, `{MYSQL_COL_DATE}`, `{MYSQL_COL_AMOUNT}` "
                    f"FROM `{MYSQL_SOURCE_TABLE}` "
                    f"WHERE `{MYSQL_COL_DATE}` >= %s AND `{MYSQL_COL_DATE}` <= %s"
                )
                cur.execute(sql, (start_date, end_date))
                rows = cur.fetchall()
    except pymysql.err.OperationalError as exc:
        logger.warning("MySQL 连接失败 (OperationalError): %s", exc)
        return (False, [])
    except Exception as exc:
        logger.warning("MySQL 查询异常: %s", exc)
        return (False, [])

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append({
            "platform": str(row[0] or "").strip(),
            "date": str(row[1] or "").strip(),
            "pay_amount": float(row[2] or 0),
        })
    return (True, result)


def _load_cache_to_index() -> dict:
    cache = _load_cache()
    if cache and cache.get("query_ok"):
        return cache.get("to_index", {})
    return {}


def _compute_realtime_platform_yoy(tasks: list[dict[str, Any]], to_index: dict) -> tuple[dict[str, str], dict[str, int], dict[str, float], str]:
    today = datetime.now()
    today_tgb = f"{today.year}/{today.month}/{today.day}"
    to_date_rows = load_to_date_rows()
    ly_date = ""
    for r in to_date_rows:
        if r.chinese_product == "实时" and r.date == today_tgb:
            ly_date = r.to_date
            break
    if not ly_date:
        return ({}, {}, {}, "")

    cur_by_csn: dict[str, int] = defaultdict(int)
    for t in tasks:
        if not t.get("enabled"):
            continue
        csn = str(t.get("companyshop_name") or "").strip()
        cur_by_csn[csn] += int(t.get("last_trusted_value") or 0)

    ly_d = _parse_date(ly_date)
    if ly_d is None:
        return ({}, {}, {}, "")
    ly_str = ly_d.strftime("%Y-%m-%d")
    ly_day = to_index.get(ly_str, {})

    yoy_by_csn: dict[str, str] = {}
    ly_by_csn: dict[str, float] = {}
    for csn in cur_by_csn:
        cur_val = cur_by_csn.get(csn, 0)
        ly_val = float(ly_day.get(csn, 0))
        ly_by_csn[csn] = ly_val
        if ly_val > 0 and cur_val > 0:
            yoy_by_csn[csn] = f"{(cur_val / ly_val - 1) * 100:.0f}%"
        else:
            yoy_by_csn[csn] = "--"
    return (yoy_by_csn, dict(cur_by_csn), ly_by_csn, ly_date)


def _build_realtime_payload(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    enabled_tasks = [task for task in tasks if task.get("enabled")]
    shop_rows: list[dict[str, Any]] = []
    platform_map: dict[str, dict[str, Any]] = {}

    target_rows = load_target_rows()
    today_str = _today()
    today_target_map: dict[str, int] = {}
    for row in target_rows:
        try:
            normalized = datetime.strptime(row.date, "%Y/%m/%d").strftime("%Y-%m-%d")
        except ValueError:
            continue
        if normalized == today_str:
            today_target_map[row.companyshop_name] = row.target

    for task in enabled_tasks:
        platform = str(task.get("platform") or "").strip()
        shop_name = str(task.get("shop_name") or "").strip()
        value = int(task.get("last_trusted_value") or 0)
        status = str(task.get("status") or "unknown")
        shop_item = {
            "task_id": task.get("id"),
            "companyshop_name": str(task.get("companyshop_name") or task.get("shop_name") or "").strip(),
            "shop_name": shop_name,
            "platform": platform,
            "brand": str(task.get("brand") or "").strip(),
            "gmv": value,
            "target": today_target_map.get(str(task.get("companyshop_name") or task.get("shop_name") or "").strip(), 0),
            "status": status,
            "updated_at": task.get("last_sample_at") or task.get("updated_at"),
            "value_source": task.get("last_value_source") or task.get("value_source") or "ocr",
            "yoy": "--",
        }
        shop_rows.append(shop_item)

        if platform not in platform_map:
            platform_map[platform] = {
                "platform": platform,
                "total_gmv": 0,
                "task_count": 0,
                "ok_tasks": 0,
                "alert_tasks": 0,
                "shops": [],
            }
        platform_entry = platform_map[platform]
        platform_entry["total_gmv"] += value
        platform_entry["task_count"] += 1
        if status == "ok":
            platform_entry["ok_tasks"] += 1
        else:
            platform_entry["alert_tasks"] += 1
        platform_entry["shops"].append(shop_item)

    total = sum(item["gmv"] for item in shop_rows)
    total_target = sum(item["target"] for item in shop_rows)

    platform_order: list[str] = []
    for t in enabled_tasks:
        p = str(t.get("platform") or "").strip()
        if p and p not in platform_order:
            platform_order.append(p)
    platforms = sorted(platform_map.values(), key=lambda item: platform_order.index(item["platform"]) if item["platform"] in platform_order else 999)
    for platform in platforms:
        platform["shops"].sort(key=lambda shop: next((i for i, t in enumerate(enabled_tasks) if str(t.get("shop_name") or "").strip() == shop.get("shop_name", "") and str(t.get("platform") or "").strip() == platform["platform"]), 999))

    yoy_map, cur_map, ly_map, ly_date_str = _compute_realtime_platform_yoy(enabled_tasks, _load_cache_to_index())

    for item in shop_rows:
        item["yoy"] = yoy_map.get(str(item.get("companyshop_name") or "").strip(), "--")

    _platform_cur: dict[str, float] = defaultdict(float)
    _platform_ly: dict[str, float] = defaultdict(float)
    for item in shop_rows:
        p = str(item.get("platform") or "").strip()
        csn = str(item.get("companyshop_name") or "").strip()
        _platform_cur[p] += float(item.get("gmv", 0))
        _platform_ly[p] += float(ly_map.get(csn, 0))
    for p_entry in platforms:
        p = str(p_entry.get("platform") or "")
        cur = _platform_cur.get(p, 0)
        ly = _platform_ly.get(p, 0)
        if ly > 0 and cur > 0:
            p_entry["yoy"] = f"{(cur / ly - 1) * 100:.0f}%"
        else:
            p_entry["yoy"] = "--"

    _all_cur = sum(_platform_cur.values())
    _all_ly = sum(_platform_ly.values())
    if _all_ly > 0 and _all_cur > 0:
        yoy = f"{(_all_cur / _all_ly - 1) * 100:.0f}%"
    else:
        yoy = "--"

    return {
        "mode": "realtime",
        "date": _today(),
        "total_gmv": total,
        "yoy_date": {"cur": f"{datetime.now().year}/{datetime.now().month}/{datetime.now().day}", "ly": ly_date_str},
        "summary": {
            "total_gmv": total,
            "total_target": total_target,
            "yoy": yoy,
            "active_tasks": len(enabled_tasks),
            "ok_tasks": sum(1 for task in enabled_tasks if task.get("status") == "ok"),
            "alert_tasks": sum(1 for task in enabled_tasks if task.get("status") != "ok"),
        },
        "shops": shop_rows,
        "platforms": platforms,
    }


def _build_period_payload(dataset_id: str, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    overview = build_dataset_overview()
    chinese_key = dataset_id.replace("product:", "")
    dataset = overview.get("by_product", {}).get(chinese_key)
    if not dataset:
        return {
            "mode": "period",
            "dataset_id": dataset_id,
            "data_status": "no_data",
            "status_message": "未找到该周期数据集配置",
            "summary": {},
            "platforms": [],
            "shops": [],
        }

    dates = [d for d in dataset.get("dates") or [] if _parse_date(d)]
    if not dates:
        return {
            "mode": "period",
            "dataset_id": dataset_id,
            "data_status": "no_data",
            "status_message": "该周期数据集未配置有效日期",
            "summary": {},
            "platforms": [],
            "shops": [],
        }

    parsed_dates = [d for d in (_parse_date(d) for d in dates) if d is not None]
    start_date = min(parsed_dates).strftime("%Y-%m-%d")
    today_date = datetime.now().date()
    end_date = today_date.strftime("%Y-%m-%d")

    cache = _load_cache()
    stale, stale_reason = _is_cache_stale(str(cache.get("cached_at") or "") if cache else "", str(cache.get("to_date_hash") or "") if cache else "")

    if stale:
        logger.info("周期缓存过期 (reason=%s)，执行全量刷新", stale_reason)
        _refresh_cache()
        cache = _load_cache()

    target_rows = load_target_rows()
    target_map: dict[str, int] = defaultdict(int)
    date_set = set(dates)
    for row in target_rows:
        if row.date not in date_set:
            continue
        parsed = _parse_date(row.date)
        if parsed is None:
            continue
        if parsed <= today_date:
            target_map[row.companyshop_name] += row.target

    today_gmv_map: dict[str, int] = {}
    for task in tasks:
        if not task.get("enabled"):
            continue
        csn = str(task.get("companyshop_name") or "").strip()
        if csn:
            today_gmv_map[csn] = int(task.get("last_trusted_value") or 0)

    to_date_range_default = {"start": "", "end": ""}
    if cache and cache.get("query_ok"):
        cache_periods = cache.get("periods", {})
        current_map: dict[str, float] = {str(k): float(v) for k, v in cache_periods.get(chinese_key, {}).items()}
        to_date_rows = load_to_date_rows()
        filtered_rows: list[Any] = []
        for r in to_date_rows:
            if r.chinese_product == chinese_key:
                pd = _parse_date(r.date)
                if pd is not None and pd <= today_date:
                    filtered_rows.append(r)
        if filtered_rows:
            ly_dates = []
            for r in filtered_rows:
                td = _parse_date(r.to_date)
                if td is not None:
                    ly_dates.append(td)
            if ly_dates:
                ly_start_d = min(ly_dates)
                ly_end_d = max(ly_dates)
                to_date_range_default = {"start": ly_start_d.strftime("%Y-%m-%d"), "end": ly_end_d.strftime("%Y-%m-%d")}
            ly_to_dates = {d.strftime("%Y-%m-%d") for d in ly_dates}
            to_idx = cache.get("to_index", {})
            ly_acc: dict[str, float] = defaultdict(float)
            for d in ly_to_dates:
                for csn, amt in to_idx.get(d, {}).items():
                    ly_acc[csn] += amt
            ly_map = dict(ly_acc)
        else:
            ly_map = {}
        data_status = "ok" if current_map else "no_data"
        status_message = "" if current_map else "该周期暂无历史数据"
    elif cache and not cache.get("query_ok"):
        current_map = {}
        ly_map = {}
        data_status = "query_failed"
        status_message = "历史数据查询失败，请检查数据库连接"
    else:
        current_map = {}
        ly_map = {}
        data_status = "no_data"
        status_message = "暂无周期历史数据"

    shop_rows: list[dict[str, Any]] = []

    for task in tasks:
        if not task.get("enabled"):
            continue
        csn = str(task.get("companyshop_name") or "").strip()
        platform = str(task.get("platform") or "").strip()
        if not csn:
            continue
        current_value = float(current_map.get(csn, 0)) + today_gmv_map.get(csn, 0)
        target_value = int(target_map.get(csn, 0))
        shop_rows.append({
            "task_id": task.get("id"),
            "companyshop_name": csn,
            "shop_name": str(task.get("shop_name") or "").strip(),
            "platform": platform,
            "brand": str(task.get("brand") or "").strip(),
            "gmv": current_value,
            "target": target_value,
            "status": str(task.get("status") or "unknown"),
            "updated_at": task.get("last_sample_at") or task.get("updated_at"),
            "value_source": task.get("last_value_source") or task.get("value_source") or "ocr",
            "yoy": "--",
        })

    total_gmv = sum(item["gmv"] for item in shop_rows)
    total_target = sum(item["target"] for item in shop_rows)

    platforms = []
    platform_map: dict[str, dict[str, Any]] = {}
    for item in shop_rows:
        p = item["platform"]
        if p not in platform_map:
            platform_map[p] = {"platform": p, "total_gmv": 0, "shop_count": 0}
        platform_map[p]["total_gmv"] += item["gmv"]
        platform_map[p]["shop_count"] += 1

    platform_order: list[str] = []
    for t in tasks:
        if not t.get("enabled"):
            continue
        p = str(t.get("platform") or "").strip()
        if p and p not in platform_order:
            platform_order.append(p)
    for p in platform_order:
        if p in platform_map:
            platforms.append(platform_map[p])

    for item in shop_rows:
        csn = str(item.get("companyshop_name") or "").strip()
        gmv = float(item.get("gmv", 0))
        ly_val = float(ly_map.get(csn, 0))
        if ly_val > 0 and gmv > 0:
            item["yoy"] = f"{(gmv / ly_val - 1) * 100:.0f}%"
        else:
            item["yoy"] = "--"

    _platform_cur: dict[str, float] = defaultdict(float)
    _platform_ly: dict[str, float] = defaultdict(float)
    for item in shop_rows:
        p = str(item.get("platform") or "").strip()
        csn = str(item.get("companyshop_name") or "").strip()
        _platform_cur[p] += float(item.get("gmv", 0))
        _platform_ly[p] += float(ly_map.get(csn, 0))
    for p_entry in platforms:
        p = str(p_entry.get("platform") or "")
        cur = _platform_cur.get(p, 0)
        ly = _platform_ly.get(p, 0)
        if ly > 0 and cur > 0:
            p_entry["yoy"] = f"{(cur / ly - 1) * 100:.0f}%"
        else:
            p_entry["yoy"] = "--"

    _all_cur = sum(_platform_cur.values())
    _all_ly = sum(_platform_ly.values())
    if _all_ly > 0 and _all_cur > 0:
        summary_yoy = f"{(_all_cur / _all_ly - 1) * 100:.0f}%"
    else:
        summary_yoy = "--"

    return {
        "mode": "period",
        "dataset_id": dataset_id,
        "date_range": {"start": start_date, "end": end_date},
        "to_date_range": to_date_range_default,
        "data_status": data_status,
        "status_message": status_message,
        "summary": {
            "total_gmv": total_gmv,
            "total_target": total_target,
            "yoy": summary_yoy,
        },
        "shops": shop_rows,
        "platforms": platforms,
    }


def build_dashboard_view(dataset_id: str | None = None) -> dict[str, Any]:
    from backend.routers.common import build_snapshot

    snapshot = build_snapshot()
    tasks = snapshot.get("tasks", [])
    overview = build_dataset_overview()
    datasets = overview.get("datasets", [])
    available_ids = {str(item.get("dataset_id") or "").strip() for item in datasets}
    selected = str(dataset_id or "realtime").strip() or "realtime"
    if selected not in available_ids:
        selected = "realtime" if "realtime" in available_ids else next(iter(available_ids), "realtime")
    if selected == "realtime":
        payload = _build_realtime_payload(tasks)
    else:
        payload = _build_period_payload(selected, tasks)
    payload["datasets"] = datasets
    payload["selected_dataset_id"] = selected
    payload["generated_at"] = snapshot.get("updated_at")
    return payload


def get_cache_status() -> dict[str, Any]:
    cache = _load_cache()
    if not cache:
        return {"cached": False, "cached_at": None, "to_date_hash": None, "stale": True, "stale_reason": "no_cache"}
    stale, reason = _is_cache_stale(str(cache.get("cached_at") or ""), str(cache.get("to_date_hash") or ""))
    return {
        "cached": True,
        "cached_at": cache.get("cached_at"),
        "to_date_hash": cache.get("to_date_hash"),
        "query_ok": cache.get("query_ok", False),
        "stale": stale,
        "stale_reason": reason,
    }


def force_refresh_cache() -> dict[str, Any]:
    ok = _refresh_cache()
    cache = _load_cache()
    return {
        "status": "ok" if ok else "failed",
        "cached_at": str(cache.get("cached_at") or "") if cache else "",
    }


async def _cache_refresh_loop() -> None:
    while True:
        now = datetime.now()
        next_run = now.replace(hour=10, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        wait_seconds = (next_run - now).total_seconds()
        logger.info("缓存调度器：下次刷新时间 %s（等待 %.0f 秒）", next_run.isoformat(), wait_seconds)
        await asyncio.sleep(wait_seconds)
        try:
            _refresh_cache()
        except Exception:
            logger.exception("缓存定时刷新异常")

_cache_scheduler_task: "asyncio.Task[None] | None" = None


def start_cache_scheduler() -> None:
    global _cache_scheduler_task
    if _cache_scheduler_task is not None and not _cache_scheduler_task.done():
        return
    _cache_scheduler_task = asyncio.ensure_future(_cache_refresh_loop())
    logger.info("缓存调度器已启动")


def stop_cache_scheduler() -> None:
    global _cache_scheduler_task
    if _cache_scheduler_task is not None and not _cache_scheduler_task.done():
        _cache_scheduler_task.cancel()
        _cache_scheduler_task = None
        logger.info("缓存调度器已停止")
