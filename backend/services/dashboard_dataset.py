from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
TO_DATE_PATH = DATA_DIR / "to_date.csv"
TARGET_PATH = DATA_DIR / "target.csv"
SHOPS_NAME_PATH = DATA_DIR / "shops_name.csv"


@dataclass(frozen=True)
class DashboardDatasetRow:
    product: str
    chinese_product: str
    date: str
    to_date: str


@dataclass(frozen=True)
class TargetRow:
    companyshop_name: str
    date: str
    target: int


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    raw_bytes = path.read_bytes()
    text = ""
    for encoding in ("utf-8-sig", "gb18030", "utf-8", "gbk"):
        try:
            text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def load_to_date_rows() -> list[DashboardDatasetRow]:
    rows: list[DashboardDatasetRow] = []
    for row in _read_csv(TO_DATE_PATH):
        chinese_product = str(row.get("chinese_product") or "").strip()
        product = str(row.get("product") or "").strip()
        date = str(row.get("date") or "").strip()
        to_date = str(row.get("to_date") or "").strip()
        if not chinese_product or not date:
            continue
        rows.append(DashboardDatasetRow(product=product, chinese_product=chinese_product, date=date, to_date=to_date))
    return rows


def load_target_rows() -> list[TargetRow]:
    rows: list[TargetRow] = []
    for row in _read_csv(TARGET_PATH):
        company = str(row.get("companyshop_name") or "").strip()
        date = str(row.get("date") or "").strip()
        target_raw = str(row.get("target") or "0").strip().replace(",", "")
        if not company or not date:
            continue
        try:
            target = int(float(target_raw))
        except ValueError:
            target = 0
        rows.append(TargetRow(companyshop_name=company, date=date, target=target))
    return rows


def load_shop_names() -> list[str]:
    rows = _read_csv(SHOPS_NAME_PATH)
    return [str(row.get("companyshop_name") or "").strip() for row in rows if str(row.get("companyshop_name") or "").strip()]


def build_dashboard_datasets() -> list[dict[str, Any]]:
    rows = load_to_date_rows()
    grouped: dict[str, list[DashboardDatasetRow]] = defaultdict(list)
    for row in rows:
        grouped[row.chinese_product].append(row)

    datasets: list[dict[str, Any]] = []
    today = datetime.now()
    today_slash = f"{today.year}/{today.month}/{today.day}"

    datasets.append({
        "dataset_id": "realtime",
        "title": "实时",
        "type": "realtime",
        "dates": [today_slash],
        "to_dates": [],
        "product": "realtime",
    })

    by_product: dict[str, Any] = {}
    for chinese_product, items in grouped.items():
        if chinese_product == "实时":
            continue
        items_sorted = sorted(items, key=lambda item: item.date)
        row_dates = [item.date for item in items_sorted]
        row_to_dates = [item.to_date for item in items_sorted if item.to_date]
        dataset = {
            "dataset_id": f"product:{chinese_product}",
            "title": chinese_product,
            "type": "period",
            "product": items_sorted[0].product if items_sorted else "",
            "chinese_product": chinese_product,
            "dates": row_dates,
            "to_dates": row_to_dates,
            "row_count": len(items_sorted),
            "start_date": min(row_dates) if row_dates else "",
            "end_date": max(row_dates) if row_dates else "",
            "start_to_date": min(row_to_dates) if row_to_dates else "",
            "end_to_date": max(row_to_dates) if row_to_dates else "",
        }
        datasets.append(dataset)
        by_product[chinese_product] = dataset

    return datasets


def build_dataset_overview() -> dict[str, Any]:
    datasets = build_dashboard_datasets()
    target_rows = load_target_rows()
    targets_by_date: dict[str, int] = defaultdict(int)
    for row in target_rows:
        targets_by_date[row.date] += row.target
    return {
        "datasets": datasets,
        "by_product": {item["chinese_product"]: item for item in datasets if item.get("type") == "period"},
        "target_dates": sorted(targets_by_date.keys()),
        "target_totals": dict(targets_by_date),
        "shop_names": load_shop_names(),
    }
