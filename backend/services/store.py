from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from backend.models import CaptureTask, EdgeSession
from backend.services import shop_config

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
EDGE_PROFILE_DIR = DATA_DIR / "edge_profiles"
DB_PATH = DATA_DIR / "gmv_livelens.sqlite3"
CAPTURE_TASK_SHOP_UNIQUE_INDEX = "idx_capture_tasks_platform_shop_unique"


def normalize_value_source(value_source: Any) -> str:
    text = str(value_source or "").strip().lower()
    if text in {"screen_readonly", "page_readonly", "readonly"}:
        return "screen_readonly"
    return "ocr"


def normalize_runtime_value_source(value_source: Any) -> str:
    text = str(value_source or "").strip().lower()
    if text in {"screen_readonly", "page_readonly", "readonly"}:
        return "screen_readonly"
    if text in {"ocr", "manual"}:
        return text
    return ""


def normalize_session_mode(session_mode: Any, user_data_dir: str, session_id: str = "") -> str:
    text = str(session_mode or "").strip().lower()
    if text in {"isolated", "real_profile"}:
        return text
    return "real_profile" if not user_data_dir and session_id == "default_real_edge" else "isolated"


def _safe_load_shop_configs() -> list[shop_config.ShopConfig]:
    try:
        return shop_config.load_shop_configs()
    except Exception:
        return []


def _edge_session_config_maps() -> tuple[
    dict[str, shop_config.ShopConfig],
    dict[tuple[str, str], shop_config.ShopConfig],
]:
    configs = _safe_load_shop_configs()
    by_session_id = {
        config.edge_session_id: config
        for config in configs
        if str(config.edge_session_id or "").strip()
    }
    by_identity = {
        (config.platform, config.shop_name): config
        for config in configs
        if str(config.platform or "").strip() and str(config.shop_name or "").strip()
    }
    return by_session_id, by_identity


def _load_shop_snapshot_rows() -> list[dict[str, Any]]:
    try:
        if not shop_config.SHOPS_JSON_PATH.exists():
            return []
        payload = json.loads(shop_config.SHOPS_JSON_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def _snapshot_bindings_by_shop_id() -> dict[str, dict[str, Any]]:
    bindings: dict[str, dict[str, Any]] = {}
    for row in _load_shop_snapshot_rows():
        if not isinstance(row, dict):
            continue
        shop_id = str(row.get("shop_id") or "").strip()
        if not shop_id:
            continue
        bindings[shop_id] = row
    return bindings


def _pick_preserved_session_binding(
    existing_row: sqlite3.Row | None,
    *,
    snapshot_user_data_dir: str,
    snapshot_session_mode: str,
    fallback_user_data_dir: str,
    fallback_session_mode: str = "isolated",
) -> tuple[str, str]:
    if existing_row is not None:
        raw_mode = str(existing_row["session_mode"] or "").strip().lower()
        raw_user_data_dir = str(existing_row["user_data_dir"] or "")
        if raw_mode in {"isolated", "real_profile"}:
            return raw_user_data_dir if raw_mode == "isolated" else "", raw_mode
        normalized_mode = normalize_session_mode(raw_mode, raw_user_data_dir, str(existing_row["session_id"] or ""))
        if normalized_mode == "real_profile":
            return "", normalized_mode
        if raw_user_data_dir:
            return raw_user_data_dir, normalized_mode
    snapshot_mode = str(snapshot_session_mode or "").strip().lower()
    if snapshot_mode == "real_profile":
        return "", "real_profile"
    if snapshot_user_data_dir:
        return snapshot_user_data_dir, "isolated"
    normalized_fallback_mode = normalize_session_mode(fallback_session_mode, fallback_user_data_dir, "")
    if normalized_fallback_mode == "real_profile":
        return "", normalized_fallback_mode
    return str(fallback_user_data_dir or ""), "isolated"


def _normalized_dir_for_compare(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(Path(text).resolve(strict=False)).lower()
    except Exception:
        return text.replace("\\", "/").rstrip("/").lower()


def _edge_session_diagnostics(
    session_id: str,
    platform: str,
    shop_name: str,
    session_mode: str,
    user_data_dir: str,
    config_by_session_id: dict[str, shop_config.ShopConfig] | None = None,
    config_by_identity: dict[tuple[str, str], shop_config.ShopConfig] | None = None,
) -> dict[str, Any]:
    config_by_session_id = config_by_session_id or {}
    config_by_identity = config_by_identity or {}
    binding_source = "manual"
    binding_source_detail = "会话未命中店铺配置，当前按手动创建/历史保留会话处理。"
    expected_user_data_dir = ""

    if session_id == "default_real_edge":
        binding_source = "default_real_profile"
        binding_source_detail = "默认真实 Edge 会话，固定绑定个人日常浏览器 Profile。"
        expected_user_data_dir = ""
    else:
        matched_config = config_by_session_id.get(session_id)
        if matched_config is not None:
            binding_source = "shop_config_session"
            binding_source_detail = "会话 session_id 命中店铺配置，按店铺固定 Profile 稳定绑定。"
            expected_user_data_dir = str(matched_config.user_data_dir or "").strip()
        else:
            identity_key = (str(platform or "").strip(), str(shop_name or "").strip())
            matched_config = config_by_identity.get(identity_key)
            if matched_config is not None:
                binding_source = "shop_config_identity"
                binding_source_detail = (
                    "会话 platform/shop_name 命中店铺配置；当前保留历史绑定，未自动迁移到新推导目录。"
                )
                expected_user_data_dir = str(matched_config.user_data_dir or "").strip()
            elif session_mode == "isolated":
                expected_user_data_dir = str(EDGE_PROFILE_DIR / session_id) if session_id else ""
                binding_source_detail = "独立会话未命中店铺配置，诊断目录按 session_id 默认 Profile 路径推导。"

    current_normalized = _normalized_dir_for_compare(user_data_dir)
    expected_normalized = _normalized_dir_for_compare(expected_user_data_dir)
    user_data_dir_differs = current_normalized != expected_normalized
    if not user_data_dir_differs:
        user_data_dir_diff_detail = "当前 user_data_dir 与期望目录一致。"
    elif expected_user_data_dir and not user_data_dir:
        user_data_dir_diff_detail = f"当前 user_data_dir 为空，期望目录为: {expected_user_data_dir}"
    elif not expected_user_data_dir and user_data_dir:
        user_data_dir_diff_detail = f"当前 user_data_dir 为: {user_data_dir}；期望目录应为空。"
    else:
        user_data_dir_diff_detail = (
            f"当前 user_data_dir 为: {user_data_dir or '(空)'}；"
            f"期望目录为: {expected_user_data_dir or '(空)'}"
        )

    return {
        "binding_source": binding_source,
        "binding_source_detail": binding_source_detail,
        "expected_user_data_dir": expected_user_data_dir,
        "user_data_dir_differs": user_data_dir_differs,
        "user_data_dir_diff_detail": user_data_dir_diff_detail,
    }


def now_sql() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    EDGE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capture_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capture_mode TEXT NOT NULL DEFAULT 'window_capture',
                value_source TEXT NOT NULL DEFAULT 'ocr',
                page_id TEXT NOT NULL DEFAULT '',
                page_url TEXT NOT NULL DEFAULT '',
                target_page_url TEXT NOT NULL DEFAULT '',
                page_title TEXT NOT NULL DEFAULT '',
                browser_profile TEXT NOT NULL DEFAULT 'default',
                edge_session_id TEXT NOT NULL DEFAULT 'default_real_edge',
                platform TEXT NOT NULL,
                shop_name TEXT NOT NULL,
                window_keyword TEXT NOT NULL,
                keyword_hint TEXT NOT NULL DEFAULT '',
                interval_seconds REAL NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                base_width INTEGER NOT NULL,
                base_height INTEGER NOT NULL,
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                x_ratio REAL NOT NULL,
                y_ratio REAL NOT NULL,
                width_ratio REAL NOT NULL,
                height_ratio REAL NOT NULL,
                safety_margin REAL NOT NULL DEFAULT 0.05,
                confirm_count INTEGER NOT NULL DEFAULT 2,
                last_trusted_value INTEGER,
                pending_value INTEGER,
                pending_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending_confirm',
                last_success_at TEXT,
                last_sample_at TEXT,
                last_ocr_text TEXT NOT NULL DEFAULT '',
                last_reason TEXT NOT NULL DEFAULT '',
                last_reason_code TEXT NOT NULL DEFAULT '',
                last_value_source TEXT NOT NULL DEFAULT '',
                last_screenshot_path TEXT NOT NULL DEFAULT '',
                last_page_preview_path TEXT NOT NULL DEFAULT '',
                last_page_preview_at TEXT,
                last_page_preview_status TEXT NOT NULL DEFAULT 'pending',
                last_page_preview_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gmv_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                sampled_at TEXT NOT NULL,
                ocr_text TEXT NOT NULL DEFAULT '',
                candidates_json TEXT NOT NULL DEFAULT '[]',
                selected_value INTEGER,
                trusted_value INTEGER,
                status TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                screenshot_path TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(task_id) REFERENCES capture_tasks(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS edge_sessions (
                session_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                platform TEXT NOT NULL DEFAULT '',
                shop_name TEXT NOT NULL DEFAULT '',
                debug_port INTEGER NOT NULL UNIQUE,
                user_data_dir TEXT NOT NULL,
                session_mode TEXT NOT NULL DEFAULT 'isolated',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_samples_task_time ON gmv_samples(task_id, sampled_at DESC)")
        _ensure_columns(conn)
        _ensure_default_edge_session(conn)
        configs = shop_config.load_shop_configs()
        _migrate_legacy_group_sessions(conn, configs)
        _ensure_shop_edge_sessions(conn, configs)
        _ensure_capture_task_shop_uniqueness(conn)
        conn.commit()


def _ensure_columns(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(capture_tasks)").fetchall()
    columns = {row["name"] for row in rows}
    additions = {
        "capture_mode": "TEXT NOT NULL DEFAULT 'window_capture'",
        "value_source": "TEXT NOT NULL DEFAULT 'ocr'",
        "page_id": "TEXT NOT NULL DEFAULT ''",
        "page_url": "TEXT NOT NULL DEFAULT ''",
        "target_page_url": "TEXT NOT NULL DEFAULT ''",
        "page_title": "TEXT NOT NULL DEFAULT ''",
        "browser_profile": "TEXT NOT NULL DEFAULT 'default'",
        "edge_session_id": "TEXT NOT NULL DEFAULT 'default_real_edge'",
        "safety_margin": "REAL NOT NULL DEFAULT 0.05",
        "confirm_count": "INTEGER NOT NULL DEFAULT 2",
        "status": "TEXT NOT NULL DEFAULT 'pending_confirm'",
        "last_trusted_value": "INTEGER",
        "pending_value": "INTEGER",
        "pending_count": "INTEGER NOT NULL DEFAULT 0",
        "last_success_at": "TEXT",
        "last_sample_at": "TEXT",
        "last_ocr_text": "TEXT NOT NULL DEFAULT ''",
        "last_reason": "TEXT NOT NULL DEFAULT ''",
        "last_reason_code": "TEXT NOT NULL DEFAULT ''",
        "last_value_source": "TEXT NOT NULL DEFAULT ''",
        "last_screenshot_path": "TEXT NOT NULL DEFAULT ''",
        "last_page_preview_path": "TEXT NOT NULL DEFAULT ''",
        "last_page_preview_at": "TEXT",
        "last_page_preview_status": "TEXT NOT NULL DEFAULT 'pending'",
        "last_page_preview_reason": "TEXT NOT NULL DEFAULT ''",
        "target": "INTEGER NOT NULL DEFAULT 0",
        "sort_order": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, ddl in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE capture_tasks ADD COLUMN {name} {ddl}")
    sample_rows = conn.execute("PRAGMA table_info(gmv_samples)").fetchall()
    sample_columns = {row["name"] for row in sample_rows}
    sample_additions = {
        "selected_candidate_engine": "TEXT NOT NULL DEFAULT ''",
        "selected_candidate_variant": "TEXT NOT NULL DEFAULT ''",
        "selected_candidate_source_kind": "TEXT NOT NULL DEFAULT ''",
        "selected_candidate_correction_count": "INTEGER NOT NULL DEFAULT 0",
        "required_confirms": "INTEGER NOT NULL DEFAULT 0",
        "accepted_after_confirms": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, ddl in sample_additions.items():
        if name not in sample_columns:
            conn.execute(f"ALTER TABLE gmv_samples ADD COLUMN {name} {ddl}")


def _delete_task_with_conn(conn: sqlite3.Connection, task_id: int) -> None:
    conn.execute("DELETE FROM gmv_samples WHERE task_id = ?", (task_id,))
    conn.execute("DELETE FROM capture_tasks WHERE id = ?", (task_id,))


def _shop_config_by_edge_session() -> dict[str, shop_config.ShopConfig]:
    return {
        config.edge_session_id: config
        for config in shop_config.load_shop_configs()
        if str(config.edge_session_id or "").strip()
    }


def _list_tasks_for_identity(
    conn: sqlite3.Connection,
    platform: str,
    shop_name: str,
) -> list[CaptureTask]:
    rows = conn.execute(
        "SELECT * FROM capture_tasks WHERE platform = ? AND shop_name = ? ORDER BY sort_order ASC, id ASC",
        (platform, shop_name),
    ).fetchall()
    return [row_to_task(row) for row in rows]


def _dedupe_capture_tasks(
    conn: sqlite3.Connection,
    identities: set[tuple[str, str]] | None = None,
    *,
    delete_duplicates: bool = False,
) -> dict[str, Any]:
    config_by_identity = shop_config.config_by_shop()
    params: list[Any] = []
    query = """
        SELECT platform, shop_name
        FROM capture_tasks
    """
    if identities:
        conditions = " OR ".join("(platform = ? AND shop_name = ?)" for _ in identities)
        query += f" WHERE {conditions}"
        for platform, shop_name in sorted(identities):
            params.extend([platform, shop_name])
    query += " GROUP BY platform, shop_name HAVING COUNT(*) > 1"
    groups = conn.execute(query, tuple(params)).fetchall()
    deleted_duplicates = 0
    duplicate_tasks = 0
    deduped_shops: list[str] = []
    duplicate_shops: list[str] = []
    for row in groups:
        platform = row["platform"]
        shop_name = row["shop_name"]
        tasks = _list_tasks_for_identity(conn, platform, shop_name)
        if len(tasks) <= 1:
            continue
        config = config_by_identity.get((platform, shop_name))
        primary = max(tasks, key=lambda item: _task_activity_rank(item, config))
        duplicates = [task for task in tasks if task.id != primary.id]
        duplicate_count = len(duplicates)
        duplicate_tasks += duplicate_count
        if duplicate_count:
            duplicate_shops.append(f"{platform} / {shop_name}")
        if not delete_duplicates:
            continue
        for duplicate in duplicates:
            if duplicate.id is None:
                continue
            _delete_task_with_conn(conn, int(duplicate.id))
            deleted_duplicates += 1
        if duplicates:
            deduped_shops.append(f"{platform} / {shop_name}")
    return {
        "deleted_duplicates": deleted_duplicates,
        "deduped_shops": deduped_shops,
        "duplicate_tasks": duplicate_tasks,
        "duplicate_shops": duplicate_shops,
    }


def _ensure_capture_task_shop_uniqueness(conn: sqlite3.Connection) -> dict[str, Any]:
    dedupe_result = _dedupe_capture_tasks(conn, delete_duplicates=False)
    if int(dedupe_result.get("duplicate_tasks") or 0) == 0:
        conn.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {CAPTURE_TASK_SHOP_UNIQUE_INDEX} "
            "ON capture_tasks(platform, shop_name)"
        )
    return dedupe_result


_DEFAULT_SESSIONS = [
    {
        "session_id": "default_real_edge",
        "name": "真实 Edge Default",
        "platform": "",
        "debug_port": 9222,
        "user_data_dir": "",
        "session_mode": "real_profile",
    },
]

_LEGACY_GROUP_SESSIONS = ("taobao_group", "jd_group", "douyin_group", "other_group")


def _ensure_default_edge_session(conn: sqlite3.Connection) -> None:
    for sess in _DEFAULT_SESSIONS:
        udir = sess["user_data_dir"] or str(EDGE_PROFILE_DIR / sess["session_id"]) if sess["session_id"] != "default_real_edge" else ""
        row = conn.execute("SELECT session_id FROM edge_sessions WHERE session_id = ?", (sess["session_id"],)).fetchone()
        if row:
            conn.execute(
                """
                UPDATE edge_sessions
                SET name = ?, debug_port = ?, user_data_dir = ?, session_mode = ?, updated_at = ?
                WHERE session_id = ?
                  AND (session_mode IS NULL OR TRIM(session_mode) = ''
                       OR (session_id = 'default_real_edge' AND session_mode != 'real_profile'))
                """,
                (sess["name"], sess["debug_port"], udir, sess["session_mode"], now_sql(), sess["session_id"]),
            )
            continue
        conn.execute(
            """
            INSERT INTO edge_sessions (
                session_id, name, platform, shop_name, debug_port, user_data_dir, session_mode, enabled, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                sess["session_id"],
                sess["name"],
                sess["platform"],
                "",
                sess["debug_port"],
                udir,
                sess["session_mode"],
                now_sql(),
                now_sql(),
            ),
        )


def _migrate_legacy_group_sessions(conn: sqlite3.Connection, configs: list[shop_config.ShopConfig]) -> None:
    if not configs:
        return
    by_shop = {(item.platform, item.shop_name): item for item in configs}
    rows = conn.execute(
        "SELECT id, platform, shop_name FROM capture_tasks WHERE edge_session_id IN (?, ?, ?, ?)",
        _LEGACY_GROUP_SESSIONS,
    ).fetchall()
    for row in rows:
        config = by_shop.get((row["platform"], row["shop_name"]))
        if config is None:
            continue
        conn.execute(
            "UPDATE capture_tasks SET edge_session_id = ?, browser_profile = ?, updated_at = ? WHERE id = ?",
            (config.edge_session_id, config.edge_session_id, now_sql(), row["id"]),
        )
    conn.execute(
        "DELETE FROM edge_sessions WHERE session_id IN (?, ?, ?, ?)",
        _LEGACY_GROUP_SESSIONS,
    )


def _reassign_edge_session_references(conn: sqlite3.Connection, old_session_id: str, new_session_id: str) -> None:
    if not old_session_id or old_session_id == new_session_id:
        return
    conn.execute(
        "UPDATE capture_tasks SET edge_session_id = ?, browser_profile = ?, updated_at = ? WHERE edge_session_id = ?",
        (new_session_id, new_session_id, now_sql(), old_session_id),
    )


def _ensure_shop_edge_sessions(conn: sqlite3.Connection, configs: list[shop_config.ShopConfig]) -> None:
    snapshot_bindings = _snapshot_bindings_by_shop_id()
    for config in configs:
        snapshot_row = snapshot_bindings.get(str(config.shop_id or "").strip(), {})
        snapshot_session_id = str(snapshot_row.get("edge_session_id") or "").strip()
        snapshot_user_data_dir = str(snapshot_row.get("user_data_dir") or "").strip()
        snapshot_session_mode = str(snapshot_row.get("session_mode") or "").strip()
        existing_by_id = conn.execute(
            "SELECT * FROM edge_sessions WHERE session_id = ?",
            (config.edge_session_id,),
        ).fetchone()
        existing_by_port = conn.execute(
            "SELECT * FROM edge_sessions WHERE debug_port = ?",
            (config.debug_port,),
        ).fetchone()
        existing_by_snapshot = None
        if snapshot_session_id and snapshot_session_id != config.edge_session_id:
            existing_by_snapshot = conn.execute(
                "SELECT * FROM edge_sessions WHERE session_id = ?",
                (snapshot_session_id,),
            ).fetchone()

        if (
            existing_by_snapshot
            and not existing_by_id
            and existing_by_snapshot["session_id"] != config.edge_session_id
        ):
            preserved_user_data_dir, preserved_session_mode = _pick_preserved_session_binding(
                existing_by_snapshot,
                snapshot_user_data_dir=snapshot_user_data_dir,
                snapshot_session_mode=snapshot_session_mode,
                fallback_user_data_dir=config.user_data_dir,
            )
            _reassign_edge_session_references(conn, str(existing_by_snapshot["session_id"] or ""), config.edge_session_id)
            conn.execute(
                """
                UPDATE edge_sessions
                SET session_id = ?, name = ?, platform = ?, shop_name = ?, debug_port = ?, user_data_dir = ?, session_mode = ?, enabled = 1, updated_at = ?
                WHERE session_id = ?
                """,
                (
                    config.edge_session_id,
                    config.edge_session_id,
                    config.platform,
                    config.shop_name,
                    config.debug_port,
                    preserved_user_data_dir,
                    preserved_session_mode,
                    now_sql(),
                    str(existing_by_snapshot["session_id"] or ""),
                ),
            )
            continue

        if existing_by_id and existing_by_port and existing_by_port["session_id"] != config.edge_session_id:
            _reassign_edge_session_references(conn, existing_by_port["session_id"], config.edge_session_id)
            conn.execute("DELETE FROM edge_sessions WHERE session_id = ?", (existing_by_port["session_id"],))

        if existing_by_id:
            preserved_user_data_dir, preserved_session_mode = _pick_preserved_session_binding(
                existing_by_id,
                snapshot_user_data_dir=snapshot_user_data_dir,
                snapshot_session_mode=snapshot_session_mode,
                fallback_user_data_dir=config.user_data_dir,
            )
            conn.execute(
                """
                UPDATE edge_sessions
                SET name = ?, platform = ?, shop_name = ?, debug_port = ?, user_data_dir = ?, session_mode = ?, enabled = 1, updated_at = ?
                WHERE session_id = ?
                """,
                (
                    config.edge_session_id,
                    config.platform,
                    config.shop_name,
                    config.debug_port,
                    preserved_user_data_dir,
                    preserved_session_mode,
                    now_sql(),
                    config.edge_session_id,
                ),
            )
            continue

        if existing_by_port:
            old_session_id = str(existing_by_port["session_id"] or "")
            preserved_user_data_dir, preserved_session_mode = _pick_preserved_session_binding(
                existing_by_port,
                snapshot_user_data_dir=snapshot_user_data_dir,
                snapshot_session_mode=snapshot_session_mode,
                fallback_user_data_dir=config.user_data_dir,
            )
            _reassign_edge_session_references(conn, old_session_id, config.edge_session_id)
            conn.execute(
                """
                UPDATE edge_sessions
                SET session_id = ?, name = ?, platform = ?, shop_name = ?, debug_port = ?, user_data_dir = ?, session_mode = ?, enabled = 1, updated_at = ?
                WHERE session_id = ?
                """,
                (
                    config.edge_session_id,
                    config.edge_session_id,
                    config.platform,
                    config.shop_name,
                    config.debug_port,
                    preserved_user_data_dir,
                    preserved_session_mode,
                    now_sql(),
                    old_session_id,
                ),
            )
            continue

        conn.execute(
            """
            INSERT INTO edge_sessions (
                session_id, name, platform, shop_name, debug_port, user_data_dir, session_mode, enabled, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                config.edge_session_id,
                config.edge_session_id,
                config.platform,
                config.shop_name,
                config.debug_port,
                config.user_data_dir,
                "isolated",
                now_sql(),
                now_sql(),
            ),
        )


def row_to_task(row: sqlite3.Row) -> CaptureTask:
    return CaptureTask(
        id=row["id"],
        capture_mode=row["capture_mode"],
        value_source=normalize_value_source(row["value_source"] if "value_source" in row.keys() else "ocr"),
        page_id=row["page_id"],
        page_url=row["page_url"],
        target_page_url=row["target_page_url"],
        page_title=row["page_title"],
        browser_profile=row["browser_profile"],
        edge_session_id=row["edge_session_id"],
        platform=row["platform"],
        shop_name=row["shop_name"],
        window_keyword=row["window_keyword"],
        keyword_hint=row["keyword_hint"],
        interval_seconds=float(row["interval_seconds"]),
        enabled=bool(row["enabled"]),
        base_width=int(row["base_width"]),
        base_height=int(row["base_height"]),
        x=int(row["x"]),
        y=int(row["y"]),
        width=int(row["width"]),
        height=int(row["height"]),
        x_ratio=float(row["x_ratio"]),
        y_ratio=float(row["y_ratio"]),
        width_ratio=float(row["width_ratio"]),
        height_ratio=float(row["height_ratio"]),
        safety_margin=float(row["safety_margin"]),
        confirm_count=int(row["confirm_count"]),
        last_trusted_value=row["last_trusted_value"],
        pending_value=row["pending_value"],
        pending_count=int(row["pending_count"]),
        status=row["status"],
        last_success_at=row["last_success_at"],
        last_sample_at=row["last_sample_at"],
        last_ocr_text=row["last_ocr_text"],
        last_reason=row["last_reason"],
        last_reason_code=row["last_reason_code"] if "last_reason_code" in row.keys() else "",
        last_value_source=normalize_runtime_value_source(
            row["last_value_source"] if "last_value_source" in row.keys() else ""
        ),
        last_screenshot_path=row["last_screenshot_path"],
        last_page_preview_path=row["last_page_preview_path"],
        last_page_preview_at=row["last_page_preview_at"],
        last_page_preview_status=row["last_page_preview_status"],
        last_page_preview_reason=row["last_page_preview_reason"],
        target=int(row["target"] if "target" in row.keys() else 0),
        sort_order=int(row["sort_order"] if "sort_order" in row.keys() else 0),
    )


def list_tasks(include_disabled: bool = True) -> list[CaptureTask]:
    query = "SELECT * FROM capture_tasks"
    params: tuple[Any, ...] = ()
    if not include_disabled:
        query += " WHERE enabled = 1"
    query += " ORDER BY sort_order ASC, id ASC"
    with connect() as conn:
        return [row_to_task(row) for row in conn.execute(query, params)]


def _task_activity_rank(task: CaptureTask, config: shop_config.ShopConfig | None = None) -> tuple[Any, ...]:
    config_session_id = (config.edge_session_id if config else "") or ""
    expected_sort_order = config.sort_order if config else None
    last_seen = task.last_success_at or task.last_sample_at or task.last_page_preview_at or ""
    preview_seen = task.last_page_preview_at or ""
    return (
        1 if config_session_id and task.edge_session_id == config_session_id else 0,
        1 if task.page_id else 0,
        1 if task.last_success_at else 0,
        1 if task.last_sample_at else 0,
        1 if task.last_page_preview_at else 0,
        1 if task.enabled else 0,
        1 if task.target_page_url else 0,
        1 if task.page_url else 0,
        1 if expected_sort_order is not None and task.sort_order == expected_sort_order else 0,
        last_seen,
        preview_seen,
        int(task.id or 0),
    )


def get_task(task_id: int) -> CaptureTask | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM capture_tasks WHERE id = ?", (task_id,)).fetchone()
        return row_to_task(row) if row else None


def get_task_by_identity(platform: str, shop_name: str) -> CaptureTask | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM capture_tasks WHERE platform = ? AND shop_name = ? LIMIT 1",
            ((platform or "").strip(), (shop_name or "").strip()),
        ).fetchone()
        return row_to_task(row) if row else None


def preferred_launch_url_for_task(task: CaptureTask) -> str:
    # target_page_url 是 shop_config 中配置的固定业务入口，优先使用；
    # page_url 是运行时绑定的页面 URL，仅在 target_page_url 未设置时作兜底。
    target_page_url = (task.target_page_url or "").strip()
    page_url = (task.page_url or "").strip()
    if target_page_url.startswith(("http://", "https://")):
        return target_page_url
    if page_url.startswith(("http://", "https://")):
        return page_url
    return ""


def preferred_launch_url_for_session(session_id: str) -> str:
    tasks = [task for task in list_tasks(include_disabled=True) if (task.edge_session_id or "").strip() == (session_id or "").strip()]
    for task in tasks:
        url = preferred_launch_url_for_task(task)
        if url:
            return url
    return ""


def _row_to_edge_session(
    row: sqlite3.Row,
    config_by_session_id: dict[str, shop_config.ShopConfig] | None = None,
    config_by_identity: dict[tuple[str, str], shop_config.ShopConfig] | None = None,
) -> EdgeSession:
    session_mode = normalize_session_mode(row["session_mode"], row["user_data_dir"], row["session_id"])
    diagnostics = _edge_session_diagnostics(
        session_id=row["session_id"],
        platform=row["platform"],
        shop_name=row["shop_name"],
        session_mode=session_mode,
        user_data_dir=row["user_data_dir"],
        config_by_session_id=config_by_session_id,
        config_by_identity=config_by_identity,
    )
    return EdgeSession(
        session_id=row["session_id"],
        name=row["name"],
        platform=row["platform"],
        shop_name=row["shop_name"],
        debug_port=int(row["debug_port"]),
        user_data_dir=row["user_data_dir"],
        session_mode=session_mode,
        binding_source=str(diagnostics["binding_source"]),
        binding_source_detail=str(diagnostics["binding_source_detail"]),
        expected_user_data_dir=str(diagnostics["expected_user_data_dir"]),
        user_data_dir_differs=bool(diagnostics["user_data_dir_differs"]),
        user_data_dir_diff_detail=str(diagnostics["user_data_dir_diff_detail"]),
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def row_to_edge_session(row: sqlite3.Row) -> EdgeSession:
    config_by_session_id, config_by_identity = _edge_session_config_maps()
    return _row_to_edge_session(
        row,
        config_by_session_id=config_by_session_id,
        config_by_identity=config_by_identity,
    )


def list_edge_sessions() -> list[EdgeSession]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM edge_sessions ORDER BY debug_port").fetchall()
    config_by_session_id, config_by_identity = _edge_session_config_maps()
    return [
        _row_to_edge_session(
            row,
            config_by_session_id=config_by_session_id,
            config_by_identity=config_by_identity,
        )
        for row in rows
    ]


def get_edge_session(session_id: str) -> EdgeSession | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM edge_sessions WHERE session_id = ?", (session_id,)).fetchone()
    if row is None:
        return None
    config_by_session_id, config_by_identity = _edge_session_config_maps()
    return _row_to_edge_session(
        row,
        config_by_session_id=config_by_session_id,
        config_by_identity=config_by_identity,
    )


def next_edge_debug_port() -> int:
    used = {session.debug_port for session in list_edge_sessions()}
    port = 9221
    while port in used:
        port += 1
        if port > 65000:
            raise ValueError("无法分配调试端口：9221-65000 范围内端口已全部占用")
    return port


def upsert_edge_session(payload: dict[str, Any]) -> EdgeSession:
    raw_id = (payload.get("session_id") or "").strip()
    name = (payload.get("name") or raw_id or "Edge 会话").strip()
    platform = (payload.get("platform") or "").strip()
    shop_name = (payload.get("shop_name") or "").strip()
    session_id = raw_id or _slugify(f"{platform}_{shop_name}_{name}") or f"edge_{int(time.time())}"
    debug_port = int(payload.get("debug_port") or next_edge_debug_port())
    if not (1024 <= debug_port <= 65535):
        raise ValueError(f"debug_port 必须在 1024-65535 范围内，当前值: {debug_port}")
    user_data_dir = (payload.get("user_data_dir") or "").strip()
    session_mode = normalize_session_mode(payload.get("session_mode"), user_data_dir, session_id)
    if session_mode == "isolated" and not user_data_dir:
        user_data_dir = str(EDGE_PROFILE_DIR / session_id)
    if session_mode == "real_profile":
        user_data_dir = ""
    if session_mode == "isolated" and not user_data_dir:
        raise ValueError("独立店铺模式必须使用独立 user_data_dir")
    enabled = 1 if payload.get("enabled", True) else 0
    with connect() as conn:
        exists = conn.execute("SELECT session_id FROM edge_sessions WHERE session_id = ?", (session_id,)).fetchone()
        if exists:
            conn.execute(
                """
                UPDATE edge_sessions
                SET name = ?, platform = ?, shop_name = ?, debug_port = ?, user_data_dir = ?, session_mode = ?, enabled = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (name, platform, shop_name, debug_port, user_data_dir, session_mode, enabled, now_sql(), session_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO edge_sessions (
                    session_id, name, platform, shop_name, debug_port, user_data_dir, session_mode, enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, name, platform, shop_name, debug_port, user_data_dir, session_mode, enabled, now_sql(), now_sql()),
            )
        conn.commit()
    session = get_edge_session(session_id)
    if session is None:
        raise RuntimeError("edge_session_save_failed")
    return session


def delete_edge_session(session_id: str) -> None:
    if session_id == "default_real_edge":
        raise ValueError("default_session_cannot_be_deleted")
    reset_reason = "原 Edge 会话已删除，原页面绑定已清空，请重新扫描并绑定页面。"
    with connect() as conn:
        conn.execute(
            """
            UPDATE capture_tasks
            SET edge_session_id = 'default_real_edge',
                browser_profile = 'default',
                page_id = '',
                page_url = '',
                page_title = '',
                last_page_preview_path = '',
                last_page_preview_at = NULL,
                last_page_preview_status = 'pending',
                last_page_preview_reason = '',
                last_reason = ?,
                last_reason_code = 'edge_session_deleted_requires_rebind',
                updated_at = ?
            WHERE edge_session_id = ?
            """,
            (reset_reason, now_sql(), session_id),
        )
        conn.execute("DELETE FROM edge_sessions WHERE session_id = ?", (session_id,))
        conn.commit()


def get_setting(key: str, default: str = "") -> str:
    with connect() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        conn.commit()


def edge_session_to_dict(session: EdgeSession) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "name": session.name,
        "platform": session.platform,
        "shop_name": session.shop_name,
        "debug_port": session.debug_port,
        "user_data_dir": session.user_data_dir,
        "session_mode": session.session_mode,
        "binding_source": session.binding_source,
        "binding_source_detail": session.binding_source_detail,
        "expected_user_data_dir": session.expected_user_data_dir,
        "user_data_dir_differs": session.user_data_dir_differs,
        "user_data_dir_diff_detail": session.user_data_dir_diff_detail,
        "enabled": session.enabled,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def _slugify(value: str) -> str:
    import re

    text = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value.strip())
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:64]


def sync_tasks_with_shop_configs(prune_stale: bool = False) -> dict[str, Any]:
    configs = shop_config.load_shop_configs()
    if not configs:
        return {
            "created": 0,
            "updated": 0,
            "unchanged": 0,
            "orphaned": 0,
            "orphaned_shops": [],
            "deleted_stale": 0,
            "deleted_shops": [],
            "deleted_duplicates": 0,
            "deduped_shops": [],
            "duplicate_tasks": 0,
            "duplicate_shops": [],
        }

    shop_config.save_shop_configs_snapshot(configs)

    config_by_session = {
        config.edge_session_id: config
        for config in configs
        if str(config.edge_session_id or "").strip()
    }
    config_identities = {(config.platform, config.shop_name) for config in configs}
    existing_tasks = list_tasks(include_disabled=True)
    existing_by_edge_session = {
        task.edge_session_id: task for task in existing_tasks if task.edge_session_id
    }
    existing_by_identity = {(task.platform, task.shop_name): task for task in existing_tasks}

    created = 0
    updated = 0
    unchanged = 0
    synced_fields = (
        "capture_mode",
        "browser_profile",
        "edge_session_id",
        "platform",
        "shop_name",
        "target_page_url",
        "keyword_hint",
        "interval_seconds",
        # "enabled" 不同步：保留用户手动启用/禁用的决策，避免每次重启把手动 enable 的任务强制 disable 回 CSV 默认值
        "confirm_count",
        "safety_margin",
        "target",
        "sort_order",
    )

    for config in configs:
        payload = config.to_task_payload()
        payload = {
            k: v
            for k, v in payload.items()
            if k != "shop_id" and k not in ("url_patterns", "url_must_contain", "debug_port", "user_data_dir")
        }
        payload["enabled"] = bool(payload.get("enabled", False))
        payload["browser_profile"] = payload.get("edge_session_id", "default")

        # Ensure target is correctly passed through
        payload["target"] = config.target

        existing_task = (
            existing_by_edge_session.get(payload["edge_session_id"])
            or existing_by_identity.get((payload["platform"], payload["shop_name"]))
        )
        if existing_task is None:
            upsert_task(payload)
            created += 1
            continue

        data = task_to_dict(existing_task)
        changed = False
        for field in synced_fields:
            if data.get(field) != payload.get(field):
                data[field] = payload.get(field)
                changed = True

        if not data.get("page_id"):
            expected_page_url = payload.get("target_page_url", "")
            if data.get("page_url") != expected_page_url:
                data["page_url"] = expected_page_url
                changed = True

        if changed:
            upsert_task(data)
            updated += 1
        else:
            unchanged += 1

    with connect() as conn:
        stale_tasks = conn.execute(
            "SELECT id, platform, shop_name, edge_session_id FROM capture_tasks ORDER BY id ASC"
        ).fetchall()
        deleted_stale = 0
        deleted_shops: list[str] = []
        orphaned_shops: list[str] = []
        for row in stale_tasks:
            task_id = int(row["id"])
            platform = str(row["platform"] or "").strip()
            shop_name = str(row["shop_name"] or "").strip()
            edge_session_id = str(row["edge_session_id"] or "").strip()
            if edge_session_id in config_by_session:
                continue
            if (platform, shop_name) in config_identities:
                continue
            label = f"{platform or '-'} / {shop_name or '-'}"
            if prune_stale:
                _delete_task_with_conn(conn, task_id)
                deleted_stale += 1
                deleted_shops.append(label)
            else:
                orphaned_shops.append(label)
        dedupe_result = _dedupe_capture_tasks(conn, delete_duplicates=False)
        conn.commit()
    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "orphaned": len(orphaned_shops),
        "orphaned_shops": orphaned_shops,
        "deleted_stale": deleted_stale,
        "deleted_shops": deleted_shops,
        "deleted_duplicates": int(dedupe_result.get("deleted_duplicates") or 0),
        "deduped_shops": list(dedupe_result.get("deduped_shops") or []),
        "duplicate_tasks": int(dedupe_result.get("duplicate_tasks") or 0),
        "duplicate_shops": list(dedupe_result.get("duplicate_shops") or []),
    }


def upsert_task(payload: dict[str, Any]) -> CaptureTask:
    payload = dict(payload)
    session_id = str(payload.get("edge_session_id") or payload.get("browser_profile") or "").strip()
    config = _shop_config_by_edge_session().get(session_id)
    if config is not None:
        payload["platform"] = config.platform
        payload["shop_name"] = config.shop_name
        payload["sort_order"] = config.sort_order
    task_id = payload.get("id")
    platform = str(payload.get("platform", "")).strip()
    shop_name = str(payload.get("shop_name", "")).strip()
    existing_task = get_task(int(task_id)) if task_id else None
    identity_task = get_task_by_identity(platform, shop_name) if platform and shop_name else None
    if existing_task is None and identity_task is not None:
        existing_task = identity_task
        task_id = identity_task.id
    target_page_url = payload.get("target_page_url", "")
    if existing_task is not None and not str(target_page_url or "").strip():
        target_page_url = existing_task.target_page_url
    value_source = payload.get("value_source", None)
    if existing_task is not None and value_source is None:
        value_source = existing_task.value_source
    # Avoid clobbering persisted values when callers send partial payloads.
    # In particular, UI save flows previously dropped these fields at the API layer.
    target = payload.get("target", None)
    if existing_task is not None and target is None:
        target = existing_task.target
    sort_order = payload.get("sort_order", None)
    if existing_task is not None and sort_order is None:
        sort_order = existing_task.sort_order
    fields = {
        "capture_mode": payload.get("capture_mode", "window_capture").strip() or "window_capture",
        "value_source": normalize_value_source(value_source),
        "page_id": payload.get("page_id", "").strip(),
        "page_url": payload.get("page_url", "").strip(),
        "target_page_url": str(target_page_url or "").strip(),
        "page_title": payload.get("page_title", "").strip(),
        "browser_profile": payload.get("browser_profile", "default").strip() or "default",
        "edge_session_id": payload.get("edge_session_id", payload.get("browser_profile", "default_real_edge")).strip()
        or "default_real_edge",
        "platform": platform,
        "shop_name": shop_name,
        "window_keyword": payload["window_keyword"].strip(),
        "keyword_hint": payload.get("keyword_hint", "").strip(),
        "interval_seconds": max(0.5, float(payload.get("interval_seconds", 1))),
        "enabled": 1 if payload.get("enabled", True) else 0,
        "base_width": int(payload["base_width"]),
        "base_height": int(payload["base_height"]),
        "x": int(payload["x"]),
        "y": int(payload["y"]),
        "width": int(payload["width"]),
        "height": int(payload["height"]),
        "x_ratio": float(payload["x_ratio"]),
        "y_ratio": float(payload["y_ratio"]),
        "width_ratio": float(payload["width_ratio"]),
        "height_ratio": float(payload["height_ratio"]),
        "safety_margin": max(0, min(0.08, float(payload.get("safety_margin", 0.05)))),
        "confirm_count": max(1, int(payload.get("confirm_count", 2))),
        "target": int(target or 0),
        "sort_order": int(sort_order or 0),
    }
    with connect() as conn:
        if task_id:
            assignments = ", ".join(f"{key} = ?" for key in fields)
            values = list(fields.values()) + [now_sql(), task_id]
            conn.execute(f"UPDATE capture_tasks SET {assignments}, updated_at = ? WHERE id = ?", values)
            saved_id = int(task_id)
        else:
            keys = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            cur = conn.execute(
                f"INSERT INTO capture_tasks ({keys}, created_at, updated_at) VALUES ({placeholders}, ?, ?)",
                list(fields.values()) + [now_sql(), now_sql()],
            )
            saved_id = int(cur.lastrowid)
        conn.commit()
    task = get_task(saved_id)
    if task is None:
        raise RuntimeError("task_save_failed")
    return task


def set_task_enabled(task_id: int, enabled: bool) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE capture_tasks SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, now_sql(), task_id),
        )
        conn.commit()


def delete_task(task_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM gmv_samples WHERE task_id = ?", (task_id,))
        conn.execute("DELETE FROM capture_tasks WHERE id = ?", (task_id,))
        conn.commit()


def update_task_runtime(task_id: int, updates: dict[str, Any]) -> None:
    allowed = {
        "last_trusted_value",
        "pending_value",
        "pending_count",
        "status",
        "last_success_at",
        "last_sample_at",
        "last_ocr_text",
        "last_reason",
        "last_reason_code",
        "last_value_source",
        "last_screenshot_path",
        "last_page_preview_path",
        "last_page_preview_at",
        "last_page_preview_status",
        "last_page_preview_reason",
    }
    safe = {key: value for key, value in updates.items() if key in allowed}
    if not safe:
        return
    assignments = ", ".join(f"{key} = ?" for key in safe)
    with connect() as conn:
        conn.execute(
            f"UPDATE capture_tasks SET {assignments}, updated_at = ? WHERE id = ?",
            list(safe.values()) + [now_sql(), task_id],
        )
        conn.commit()


def add_sample(
    task_id: int,
    ocr_text: str,
    candidates: list[dict[str, Any]],
    selected_value: int | None,
    trusted_value: int | None,
    status: str,
    reason: str,
    screenshot_path: str,
    sample_meta: dict[str, Any] | None = None,
) -> None:
    meta = sample_meta or {}
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO gmv_samples (
                task_id, sampled_at, ocr_text, candidates_json, selected_value,
                trusted_value, status, reason, screenshot_path,
                selected_candidate_engine, selected_candidate_variant,
                selected_candidate_source_kind, selected_candidate_correction_count,
                required_confirms, accepted_after_confirms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                now_sql(),
                ocr_text,
                json.dumps(candidates, ensure_ascii=False),
                selected_value,
                trusted_value,
                status,
                reason,
                screenshot_path,
                str(meta.get("selected_candidate_engine") or ""),
                str(meta.get("selected_candidate_variant") or ""),
                str(meta.get("selected_candidate_source_kind") or ""),
                int(meta.get("selected_candidate_correction_count") or 0),
                int(meta.get("required_confirms") or 0),
                int(meta.get("accepted_after_confirms") or 0),
            ),
        )
        conn.commit()


def recent_samples(task_id: int, limit: int = 20) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM gmv_samples WHERE task_id = ? ORDER BY sampled_at DESC LIMIT ?",
            (task_id, limit),
        ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            item["candidates"] = json.loads(item.pop("candidates_json") or "[]")
        except json.JSONDecodeError:
            item["candidates"] = []
        items.append(item)
    return items


def task_to_dict(task: CaptureTask) -> dict[str, Any]:
    config = shop_config.config_by_shop().get((task.platform, task.shop_name))
    return {
        "id": task.id,
        "capture_mode": task.capture_mode,
        "value_source": task.value_source,
        "page_id": task.page_id,
        "page_url": task.page_url,
        "target_page_url": task.target_page_url,
        "page_title": task.page_title,
        "browser_profile": task.browser_profile,
        "edge_session_id": task.edge_session_id,
        "platform": task.platform,
        "shop_name": task.shop_name,
        "companyshop_name": str(getattr(config, "companyshop_name", "") or ""),
        "brand": str(getattr(config, "brand", "") or ""),
        "window_keyword": task.window_keyword,
        "keyword_hint": task.keyword_hint,
        "interval_seconds": task.interval_seconds,
        "enabled": task.enabled,
        "base_width": task.base_width,
        "base_height": task.base_height,
        "x": task.x,
        "y": task.y,
        "width": task.width,
        "height": task.height,
        "x_ratio": task.x_ratio,
        "y_ratio": task.y_ratio,
        "width_ratio": task.width_ratio,
        "height_ratio": task.height_ratio,
        "safety_margin": task.safety_margin,
        "confirm_count": task.confirm_count,
        "last_trusted_value": task.last_trusted_value,
        "pending_value": task.pending_value,
        "pending_count": task.pending_count,
        "status": task.status,
        "last_success_at": task.last_success_at,
        "last_sample_at": task.last_sample_at,
        "last_ocr_text": task.last_ocr_text,
        "last_reason": task.last_reason,
        "last_reason_code": task.last_reason_code,
        "last_value_source": task.last_value_source,
        "last_screenshot_path": task.last_screenshot_path,
        "last_page_preview_path": task.last_page_preview_path,
        "last_page_preview_at": task.last_page_preview_at,
        "last_page_preview_status": task.last_page_preview_status,
        "last_page_preview_reason": task.last_page_preview_reason,
        "target": task.target,
        "sort_order": task.sort_order,
        "page_preview_url": _preview_url(task),
    }


def _preview_url(task: CaptureTask) -> str:
    if not task.last_page_preview_path:
        return ""
    filename = Path(task.last_page_preview_path).name
    if not filename:
        return ""
    version = str(task.last_page_preview_at or task.last_page_preview_status or int(time.time()))
    return f"/api/task-previews/{filename}?v={version}"
