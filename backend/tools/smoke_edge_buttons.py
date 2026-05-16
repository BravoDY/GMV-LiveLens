from __future__ import annotations

# ruff: noqa: E402
import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.collectors.window_control import edge_window_diagnostics


def http_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 45.0) -> Any:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
            return json.loads(text) if text else None
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(text)
        except json.JSONDecodeError:
            detail = {"error": text}
        raise RuntimeError(json.dumps({"status": exc.code, "detail": detail}, ensure_ascii=False)) from exc


def cdp_pages(port: int, timeout: float = 3.0) -> list[dict[str, Any]]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
            return data if isinstance(data, list) else []
    except Exception:
        return []


def edge_process_commands() -> list[dict[str, Any]]:
    command = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" "
        "| Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=6,
        )
    except Exception:
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else [data]


def matching_processes(session: dict[str, Any]) -> list[dict[str, Any]]:
    port_text = f"--remote-debugging-port={int(session.get('debug_port') or 0)}"
    user_data_dir = str(session.get("user_data_dir") or "").replace("/", "\\").lower()
    matched = []
    for proc in edge_process_commands():
        command = str(proc.get("CommandLine") or "")
        normalized = command.replace("/", "\\").lower()
        if port_text in command or (user_data_dir and user_data_dir in normalized):
            matched.append(proc)
    return matched


def visible_cdp_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ignored = ("edge://", "chrome://", "about:blank")
    items = []
    for page in pages:
        url = str(page.get("url") or "")
        if url.startswith(ignored) or "ntp.msn.cn/edge/ntp" in url:
            continue
        items.append(page)
    return items


def cdp_tab_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [page for page in pages if page.get("type") == "page"]


def print_step(name: str, ok: bool, detail: dict[str, Any]) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}")
    print(json.dumps(detail, ensure_ascii=False, indent=2))


def session_snapshot(session: dict[str, Any], action_result: dict[str, Any] | None = None) -> dict[str, Any]:
    port = int(session.get("debug_port") or 0)
    pages = cdp_pages(port)
    tab_pages = cdp_tab_pages(pages)
    diagnostics = edge_window_diagnostics(
        debug_port=port,
        user_data_dir=str(session.get("user_data_dir") or ""),
    )
    return {
        "session_id": session.get("session_id"),
        "debug_port": port,
        "process_count": len(matching_processes(session)),
        "window_count": len(diagnostics.get("candidate_windows") or []),
        "cdp_page_count": len(tab_pages),
        "visible_cdp_page_count": len(visible_cdp_pages(tab_pages)),
        "cdp_pages": [{"title": item.get("title"), "url": item.get("url")} for item in tab_pages],
        "api_page_count": (action_result or {}).get("page_count"),
        "primary_page_url": (action_result or {}).get("primary_page_url"),
        "closed_extra_pages_count": (action_result or {}).get("closed_extra_pages_count"),
        "stage": (action_result or {}).get("stage"),
        "reason_code": (action_result or {}).get("reason_code"),
        "window_action": (action_result or {}).get("window_action"),
    }


def assert_single_tab(session: dict[str, Any], action_result: dict[str, Any], name: str) -> bool:
    snapshot = session_snapshot(session, action_result)
    ok = snapshot["window_count"] <= 1 and snapshot["cdp_page_count"] <= 1 and not action_result.get("last_error")
    print_step(name, ok, snapshot)
    return ok


def choose_session(base_url: str, session_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    sessions = http_json(base_url, "GET", "/api/edge-sessions", timeout=20)
    tasks_payload = http_json(base_url, "GET", "/api/tasks", timeout=20)
    tasks = [task for task in tasks_payload.get("tasks", []) if task.get("capture_mode") == "remote_edge" and task.get("edge_session_id")]
    if session_id:
        session = next((item for item in sessions if item.get("session_id") == session_id), None)
        task = next((item for item in tasks if item.get("edge_session_id") == session_id), {})
    else:
        task = tasks[0] if tasks else {}
        session = next((item for item in sessions if item.get("session_id") == task.get("edge_session_id")), None)
    if not session:
        raise RuntimeError("No Edge session found for smoke test.")
    return session, task


def action(base_url: str, session_id: str, action_name: str, launch_url: str = "", timeout: float = 60.0) -> dict[str, Any]:
    suffix = f"?launch_url={urllib.parse.quote(launch_url, safe='')}" if launch_url else ""
    return http_json(base_url, "POST", f"/api/edge-sessions/{urllib.parse.quote(session_id, safe='')}/{action_name}{suffix}", timeout=timeout)


def platform_action(base_url: str, platform: str, endpoint: str, timeout: float = 240.0) -> dict[str, Any]:
    encoded_platform = urllib.parse.quote(platform, safe="")
    return http_json(base_url, "POST", f"/api/platforms/{encoded_platform}/{endpoint}", timeout=timeout)


def summarize_platform_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform": result.get("platform"),
        "action": result.get("action"),
        "requested": result.get("requested"),
        "controlled_edge_tasks": result.get("controlled_edge_tasks"),
        "succeeded": result.get("succeeded"),
        "execution_mode": result.get("execution_mode"),
        "results": [
            {
                "shop_name": item.get("shop_name"),
                "task_id": item.get("task_id"),
                "edge_session_id": item.get("edge_session_id"),
                "debug_port": item.get("debug_port"),
                "ok": item.get("ok"),
                "stage": item.get("stage"),
                "reason_code": item.get("reason_code"),
                "window_action": item.get("window_action"),
                "page_count": item.get("page_count"),
                "primary_page_url": item.get("primary_page_url"),
                "closed_extra_pages_count": item.get("closed_extra_pages_count"),
                "closed": item.get("closed"),
                "last_error": item.get("last_error"),
            }
            for item in (result.get("results") or [])
        ],
    }


def platform_ok(result: dict[str, Any], *, expect_closed: bool = False) -> bool:
    items = result.get("results") or []
    if not items:
        return False
    for item in items:
        if not item.get("ok"):
            return False
        if expect_closed:
            if not item.get("closed"):
                return False
            continue
        page_count = int(item.get("page_count") or 0)
        if page_count > 1:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test GMV-LiveLens Edge four-button behavior.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8100")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--live", action="store_true", help="Actually start/show/hide/close real Edge sessions.")
    parser.add_argument("--loops", type=int, default=3)
    parser.add_argument("--include-platform", action="store_true")
    args = parser.parse_args()

    http_json(args.base_url, "GET", "/api/health", timeout=10)
    session, task = choose_session(args.base_url, args.session_id)
    launch_url = task.get("target_page_url") or task.get("page_url") or ""
    print_step("preflight", True, {"session": session, "task": task, "launch_url": launch_url})
    if not args.live:
        print("[INFO] Preflight only. Add --live to run destructive Edge button smoke tests.")
        return 0

    session_id = str(session["session_id"])
    failures = 0

    try:
        close_result = action(args.base_url, session_id, "close", timeout=45)
        print_step("cleanup close before cold start", bool(close_result.get("closed")), session_snapshot(session, close_result))
    except Exception as exc:
        print_step("cleanup close before cold start", True, {"warning": str(exc)})

    start_result = action(args.base_url, session_id, "show", launch_url, timeout=70)
    failures += 0 if assert_single_tab(session, start_result, "cold start via start/show single entry") else 1

    for index in range(1, 4):
        result = action(args.base_url, session_id, "show", launch_url, timeout=70)
        failures += 0 if assert_single_tab(session, result, f"idempotent start/show #{index}") else 1

    for index in range(1, max(1, args.loops) + 1):
        hide_result = action(args.base_url, session_id, "hide", timeout=45)
        print_step(f"hide #{index}", bool(hide_result.get("window_found")), session_snapshot(session, hide_result))
        show_result = action(args.base_url, session_id, "show", launch_url, timeout=70)
        failures += 0 if assert_single_tab(session, show_result, f"show after hide #{index}") else 1

    close_result = action(args.base_url, session_id, "close", timeout=60)
    print_step("close", bool(close_result.get("closed")), session_snapshot(session, close_result))
    restart_result = action(args.base_url, session_id, "show", launch_url, timeout=70)
    failures += 0 if assert_single_tab(session, restart_result, "restart after close") else 1

    if args.include_platform and task.get("platform"):
        platform = str(task["platform"])
        platform_steps = [
            ("platform launch-edge", "launch-edge", False),
            ("platform show-edge", "show-edge", False),
            ("platform hide-edge", "hide-edge", False),
            ("platform show-edge after hide", "show-edge", False),
            ("platform close-edge", "close-edge", True),
        ]
        for name, endpoint, expect_closed in platform_steps:
            platform_result = platform_action(args.base_url, platform, endpoint, timeout=300)
            ok = platform_ok(platform_result, expect_closed=expect_closed)
            print_step(name, ok, summarize_platform_result(platform_result))
            failures += 0 if ok else 1

    print_step("summary", failures == 0, {"failures": failures})
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
