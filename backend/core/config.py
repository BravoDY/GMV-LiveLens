from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _bool_env(name: str, default: bool = False) -> bool:
    raw = _env(name, "")
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppSettings:
    app_env: str
    api_token: str
    require_api_token: bool
    cors_origin_regex: str
    debug_api_enabled: bool

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    app_env = _env("GMV_APP_ENV", _env("APP_ENV", "development")) or "development"
    api_token = _env("GMV_API_TOKEN", _env("API_TOKEN", ""))
    require_api_token = _bool_env("GMV_REQUIRE_API_TOKEN", False)
    cors_origin_regex = _env(
        "GMV_CORS_ORIGIN_REGEX",
        r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    )
    debug_api_enabled = _bool_env("GMV_DEBUG_API_ENABLED", app_env.lower() != "production")
    return AppSettings(
        app_env=app_env,
        api_token=api_token,
        require_api_token=require_api_token,
        cors_origin_regex=cors_origin_regex,
        debug_api_enabled=debug_api_enabled,
    )
