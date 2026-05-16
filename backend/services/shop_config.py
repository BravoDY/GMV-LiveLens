from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
SHOPS_CSV_PATH = DATA_DIR / "shops.csv"
SHOPS_JSON_PATH = DATA_DIR / "shops_default.json"
SHOPS_PAGE_DATA_PATH = DATA_DIR / "shops_page_data.json"
EDGE_PROFILE_DIR = DATA_DIR / "edge_profiles"

PLATFORM_PORT_BASE = {
    "天猫": 9231,
    "京东": 9241,
    "抖音": 9251,
    "得物": 9618,
    "其他平台": 9261,
}
DEFAULT_PORT_BASE = 9301
SCREEN_READONLY_SUPPORTED_PLATFORM_KEYS = ("天猫", "京东", "唯品会", "抖音", "得物")


@dataclass(frozen=True)
class ShopConfig:
    shop_id: str
    platform: str
    brand: str
    shop_name: str
    edge_session_id: str
    debug_port: int
    user_data_dir: str
    keyword_hint: str = ""
    companyshop_name: str = ""
    default_page_url: str = ""
    url_patterns: tuple[str, ...] = ()
    url_must_contain: tuple[str, ...] = ()
    interval_seconds: float = 1
    confirm_count: int = 2
    safety_margin: float = 0.2
    enabled: bool = False
    capture_mode: str = "remote_edge"
    browser_profile: str = "default"
    base_width: int = 1920
    base_height: int = 1080
    x: int = 0
    y: int = 0
    width: int = 200
    height: int = 60
    x_ratio: float = 0.0
    y_ratio: float = 0.0
    width_ratio: float = 0.1
    height_ratio: float = 0.06
    target: int = 0
    sort_order: int = 0

    def to_task_payload(self) -> dict[str, Any]:
        item = asdict(self)
        item["default_page_url"] = self.default_page_url
        item["url_patterns"] = list(self.url_patterns)
        item["url_must_contain"] = list(self.url_must_contain)
        item.update(
            {
                "page_id": "",
                "page_url": self.default_page_url,
                "target_page_url": self.default_page_url,
                "page_title": "",
                "window_keyword": "",
                "target": self.target,
                "sort_order": self.sort_order,
            }
        )
        return item


def slugify(value: str) -> str:
    text = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value.strip())
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:96]


def edge_session_id_for(platform: str, shop_name: str) -> str:
    return slugify(f"{platform}_{shop_name}")


def platform_key(platform: str) -> str:
    text = (platform or "").strip()
    if "天猫" in text or "淘宝" in text or "生意参谋" in text:
        return "天猫"
    if "京东" in text or "商智" in text:
        return "京东"
    if "唯品" in text or "唯品会" in text or "vip" in text.lower():
        return "唯品会"
    if "抖音" in text or "巨量" in text:
        return "抖音"
    if "得物" in text or "dewu" in text.lower():
        return "得物"
    return text or "其他平台"


def screen_readonly_supported(platform: str) -> bool:
    return platform_key(platform) in SCREEN_READONLY_SUPPORTED_PLATFORM_KEYS


def split_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    text = str(value).strip()
    if not text:
        return ()
    parts = re.split(r"[;；,\n]+", text)
    return tuple(part.strip() for part in parts if part.strip())


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "启用", "是"}


def default_page_url_for(row: dict[str, str]) -> str:
    explicit = str(row.get("default_page_url", "") or "").strip()
    if explicit.startswith(("http://", "https://")):
        return explicit
    for pattern in split_list(row.get("url_patterns")):
        if pattern.startswith(("http://", "https://")):
            return pattern
    return ""


def _read_csv_text_with_fallbacks(path: Path) -> str:
    raw = path.read_bytes()
    errors: list[str] = []
    for encoding in ("utf-8-sig", "gb18030", "utf-8", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
    raise ValueError(
        "shops.csv 编码无法识别，请保存为 UTF-8 或 GBK/GB18030。"
        f" 详细错误: {' | '.join(errors)}"
    )


def _rows_from_csv() -> list[dict[str, Any]]:
    if not SHOPS_CSV_PATH.exists():
        return []
    text = _read_csv_text_with_fallbacks(SHOPS_CSV_PATH)
    return [dict(row) for row in csv.DictReader(io.StringIO(text, newline=""))]


def _rows_from_json() -> list[dict[str, Any]]:
    if not SHOPS_JSON_PATH.exists():
        return []
    with SHOPS_JSON_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _rows_from_page_data() -> list[dict[str, Any]]:
    if not SHOPS_PAGE_DATA_PATH.exists():
        return []
    with SHOPS_PAGE_DATA_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save_shop_configs_snapshot(configs: list[ShopConfig]) -> None:
    payload = [config.to_task_payload() for config in configs]
    with SHOPS_JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_shop_configs() -> list[ShopConfig]:
    if SHOPS_CSV_PATH.exists():
        rows = _rows_from_csv()
    elif SHOPS_PAGE_DATA_PATH.exists():
        rows = _rows_from_page_data()
    else:
        rows = _rows_from_json()
    if not rows:
        return []

    seen: set[tuple[str, str]] = set()
    port_offsets: dict[str, int] = {}
    configs: list[ShopConfig] = []
    used_ids: set[str] = set()

    for index, row in enumerate(rows):
        row_number = index + 2
        normalized_row = {
            str(key).strip(): ("" if value is None else str(value).strip())
            for key, value in row.items()
        }
        if not any(normalized_row.values()):
            continue

        platform = normalized_row.get("platform", "")
        shop_name = normalized_row.get("shop_name", "")
        if not platform or not shop_name:
            raise ValueError(
                f"shops.csv 第 {row_number} 行缺少 platform 或 shop_name，请检查是否有半空行或未填完整。"
            )

        dedupe_key = (platform, shop_name)
        if dedupe_key in seen:
            raise ValueError(f"duplicate shop config: {platform} / {shop_name}")
        seen.add(dedupe_key)

        session_id = edge_session_id_for(platform, shop_name)
        if not session_id or session_id in used_ids:
            raise ValueError(f"duplicate generated edge_session_id: {session_id}")
        used_ids.add(session_id)

        key = platform_key(platform)
        if key in PLATFORM_PORT_BASE:
            base = PLATFORM_PORT_BASE[key]
        else:
            # 用平台名哈希计算固定 base，避免因 CSV 行序变化导致端口漂移
            hash_val = int.from_bytes(hashlib.md5(key.encode("utf-8")).digest()[:2], "big") % 500
            base = DEFAULT_PORT_BASE + hash_val
        offset = port_offsets.get(key, 0)
        port_offsets[key] = offset + 1

        target_str = normalized_row.get("Target") or normalized_row.get("target") or "0"
        try:
            target_val = int(float(target_str.replace(",", "").replace(" ", "")))
        except ValueError:
            target_val = 0

        configs.append(
            ShopConfig(
                shop_id=normalized_row.get("shop_id") or session_id,
                platform=platform,
                brand=normalized_row.get("brand", ""),
                shop_name=shop_name,
                companyshop_name=normalized_row.get("companyshop_name", ""),
                edge_session_id=session_id,
                debug_port=int(normalized_row.get("debug_port") or base + offset),
                user_data_dir=str(EDGE_PROFILE_DIR / session_id),
                keyword_hint=normalized_row.get("keyword_hint") or "成交金额",
                default_page_url=default_page_url_for(normalized_row),
                url_patterns=split_list(normalized_row.get("url_patterns")),
                url_must_contain=split_list(normalized_row.get("url_must_contain")),
                interval_seconds=float(normalized_row.get("interval_seconds") or 1),
                confirm_count=int(normalized_row.get("confirm_count") or 2),
                safety_margin=float(normalized_row.get("safety_margin") or 0.2),
                enabled=parse_bool(normalized_row.get("enabled"), False),
                target=target_val,
                sort_order=index,
            )
        )
    return configs


def shop_configs_as_dicts() -> list[dict[str, Any]]:
    return [config.to_task_payload() for config in load_shop_configs()]


def config_by_shop() -> dict[tuple[str, str], ShopConfig]:
    return {(config.platform, config.shop_name): config for config in load_shop_configs()}
