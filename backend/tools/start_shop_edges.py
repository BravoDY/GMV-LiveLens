from __future__ import annotations

# ruff: noqa: E402
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.services import shop_config

APP_ORIGIN = "http://127.0.0.1:8100"


def find_edge() -> str:
    found = shutil.which("msedge")
    if found:
        return found
    candidates = [
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def start_edge(edge_exe: str, config: shop_config.ShopConfig) -> None:
    profile = Path(config.user_data_dir)
    profile.mkdir(parents=True, exist_ok=True)
    args = [
        edge_exe,
        f"--user-data-dir={profile}",
        f"--remote-debugging-port={config.debug_port}",
        "--remote-debugging-address=127.0.0.1",
        f"--remote-allow-origins={APP_ORIGIN}",
        "--no-first-run",
        "--new-window",
        config.default_page_url or "about:blank",
    ]
    subprocess.Popen(args, cwd=str(ROOT_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start one isolated Edge session for each configured shop.")
    parser.add_argument("--platform", required=True, help="Platform name from data/shops.csv, for example 天猫")
    parser.add_argument("--dry-run", action="store_true", help="Print planned sessions without starting Edge.")
    args = parser.parse_args()

    configs = [item for item in shop_config.load_shop_configs() if item.platform == args.platform]
    if not configs:
        print(f"[ERROR] No shops found for platform: {args.platform}")
        return 1

    edge = find_edge()
    if not edge:
        print("[ERROR] Microsoft Edge not found.")
        return 1

    print(f"Starting {len(configs)} Edge session(s) for {args.platform}.")
    for config in configs:
        if not args.dry_run:
            start_edge(edge, config)
        print(f"[OK] {config.shop_name} | port={config.debug_port} | profile={config.user_data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
