from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 8100
HEALTH_URL = f"http://{HOST}:{PORT}/api/health"
PYTEST_REGRESSION_FILES = [
    "tests/test_dashboard_regression.py",
    "tests/test_screen_readonly_hardening.py",
]


def resolve_ruff_command() -> list[str]:
    candidates = [
        shutil.which("ruff"),
        str(ROOT_DIR / ".venv" / "Scripts" / "ruff.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return [candidate]
    return [sys.executable, "-m", "ruff"]


def run_step(title: str, command: list[str], *, cwd: Path | None = None) -> None:
    print(f"\n[CI] {title}")
    print(f"[CMD] {' '.join(command)}")
    subprocess.run(command, cwd=str(cwd or ROOT_DIR), check=True)


def wait_for_http(url: str, *, timeout_seconds: float = 30.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return
        except urllib.error.URLError as exc:
            last_error = str(exc)
        except Exception as exc:  # pragma: no cover - CI only
            last_error = str(exc)
        time.sleep(1.0)
    raise RuntimeError(f"等待服务启动超时: {url} ; last_error={last_error}")


def run_api_smoke() -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", HOST, "--port", str(PORT)],
        cwd=str(ROOT_DIR),
        env=env,
    )
    try:
        wait_for_http(HEALTH_URL, timeout_seconds=45.0)
        run_step("Run API smoke tests", [sys.executable, "tests/smoke_api.py"])
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GMV-LiveLens CI checks")
    parser.add_argument(
        "--with-api",
        action="store_true",
        help="启动本地 uvicorn 并执行 tests/smoke_api.py",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    run_step(
        "Ruff check (CI scope)",
        resolve_ruff_command()
        + [
            "check",
            "backend/main.py",
            "backend/logging_config.py",
            "backend/routers",
            "backend/services/store.py",
            "backend/services/scheduler.py",
            "backend/collectors/remote_edge.py",
            "backend/collectors/edge",
            "backend/collectors/ocr_reader.py",
            "backend/tools/full_test.py",
            "tests",
            "scripts/ci_check.py",
        ],
    )
    run_step("Run pytest regression tests", [sys.executable, "-m", "pytest", *PYTEST_REGRESSION_FILES])
    run_step("Run full_test (skip API)", [sys.executable, "tests/full_test.py", "--skip-api"])
    run_step("Run smoke_edge", [sys.executable, "tests/smoke_edge.py"])

    if args.with_api:
        run_api_smoke()

    print("\n[CI] All configured checks passed.")


if __name__ == "__main__":
    main()
