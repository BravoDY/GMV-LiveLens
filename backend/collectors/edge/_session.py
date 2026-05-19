from __future__ import annotations

import logging
import os
import queue
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

if TYPE_CHECKING:
    from . import RemoteEdge

logger = logging.getLogger(__name__)

DEBUG_HOST = "127.0.0.1"
DEBUG_PORT = 9222
DEBUG_URL = f"http://{DEBUG_HOST}:{DEBUG_PORT}"

_WORKER_IDLE_TIMEOUT = float(os.environ.get("GMV_EDGE_WORKER_IDLE_TIMEOUT", "300"))
_JOBS_QUEUE_MAXSIZE = int(os.environ.get("GMV_EDGE_JOBS_QUEUE_MAXSIZE", "10"))
_WORKER_JOIN_TIMEOUT = float(os.environ.get("GMV_EDGE_WORKER_JOIN_TIMEOUT", "5.0"))

_ROOT_DIR = Path(__file__).resolve().parents[2]
_ALLOWED_PROFILE_BASE = (_ROOT_DIR / "data" / "edge_profiles").resolve()
ACTION_TIMEOUTS = {
    "start_edge": 35.0,
    "show_edge": 35.0,
    "hide_edge": 22.0,
    "close_edge": 35.0,
    "health": 6.0,
    "list_pages": 15.0,
    "open_page": 20.0,
    "screenshot_page": 35.0,
    "reload_page": 15.0,
    "ensure_page": 15.0,
    "find_page": 10.0,
}


class EdgeActionTimeoutError(RuntimeError):
    def __init__(self, action: str, stage: str, timeout_seconds: float):
        self.action = action
        self.stage = stage or "unknown"
        self.timeout_seconds = float(timeout_seconds)
        self.reason_code = "edge_action_timeout"
        super().__init__(f"Edge 动作超时: {action} @ {self.stage} ({self.timeout_seconds:.1f}s)")


def _validate_user_data_dir(user_data_dir: str) -> str:
    if not user_data_dir:
        return user_data_dir
    if ".." in Path(user_data_dir).parts:
        raise ValueError(f"user_data_dir 不能包含 '..' 路径遍历: {user_data_dir}")
    return str(Path(user_data_dir).resolve())

SCREEN_READONLY_WAITING_REASON_CODES = {
    "screen_target_not_found",
    "screen_frame_not_found",
    "screen_overview_source_not_found",
    "screen_payamt_missing",
    "jd_screen_root_not_found",
    "jd_screen_payamt_missing",
    "vip_screen_root_not_found",
    "vip_screen_payamt_missing",
    "douyin_screen_root_not_found",
    "douyin_screen_payamt_missing",
    "dewu_screen_root_not_found",
    "dewu_screen_payamt_missing",
}


@dataclass
class RemotePageInfo:
    page_id: str
    title: str
    url: str
    is_closed: bool


@dataclass
class RemoteEdgeHealth:
    session_id: str
    name: str
    action: str
    stage: str
    session_mode: str
    debug_port: int
    debug_available: bool
    connected: bool
    total_pages: int
    visible_pages: int
    user_data_dir: str
    profile_initialized: bool
    mode_label: str
    mode_hint: str
    last_error: str
    last_action: str
    edge_command: str
    reason_code: str = ""
    recovery_attempted: list[str] = field(default_factory=list)
    window_diagnostics: dict[str, object] = field(default_factory=dict)
    profile_diagnostics: dict[str, object] = field(default_factory=dict)
    is_window_op_running: bool = False
    is_stale: bool = False
    stale_reason: str = ""
    page_count: int = 0
    primary_page_id: str = ""
    primary_page_url: str = ""
    closed_extra_pages_count: int = 0
    closed_extra_pages: list[str] = field(default_factory=list)


@dataclass
class RemoteEdgeWindowState:
    session_id: str
    action: str
    stage: str
    debug_available: bool
    window_found: bool
    window_hwnd: int
    window_pid: int
    window_title: str
    window_action: str
    maximized: bool
    last_error: str
    reason_code: str = ""
    recovery_attempted: list[str] = field(default_factory=list)
    window_diagnostics: dict[str, object] = field(default_factory=dict)
    is_window_op_running: bool = False
    is_stale: bool = False
    stale_reason: str = ""
    page_count: int = 0
    primary_page_id: str = ""
    primary_page_url: str = ""
    closed_extra_pages_count: int = 0
    closed_extra_pages: list[str] = field(default_factory=list)


@dataclass
class RemoteEdgeCloseState:
    session_id: str
    action: str
    stage: str
    debug_available: bool
    closed: bool
    closed_pids: list[int]
    window_pid: int
    last_error: str
    reason_code: str = ""
    close_mode: str = "force_kill"
    graceful_attempted: bool = False
    force_kill_used: bool = False
    profile_initialized: bool = False
    profile_path: str = ""
    profile_diagnostics: dict[str, object] = field(default_factory=dict)
    recovery_attempted: list[str] = field(default_factory=list)
    window_diagnostics: dict[str, object] = field(default_factory=dict)
    is_window_op_running: bool = False
    is_stale: bool = False
    stale_reason: str = ""
    page_count: int = 0
    primary_page_id: str = ""
    primary_page_url: str = ""
    closed_extra_pages_count: int = 0
    closed_extra_pages: list[str] = field(default_factory=list)


@dataclass
class RemoteEdgeNavigationState:
    session_id: str
    action: str
    stage: str
    target_url: str
    opened: bool
    target_found: bool
    page_id: str
    page_title: str
    page_url: str
    last_error: str
    reason_code: str = ""
    is_window_op_running: bool = False
    is_stale: bool = False
    stale_reason: str = ""


@dataclass
class PageCleanupResult:
    page_count: int = 0
    primary_page_id: str = ""
    primary_page_url: str = ""
    closed_extra_pages_count: int = 0
    closed_extra_pages: list[str] = field(default_factory=list)

T = TypeVar("T")


class RemoteEdgeSessionMixin:
    def __init__(
        self,
        session_id: str = "default_real_edge",
        name: str = "Real Edge Default",
        debug_port: int = DEBUG_PORT,
        user_data_dir: str = "",
        session_mode: str = "isolated",
        profile_directory: str = "Default",
    ) -> None:
        self.session_id = session_id
        self.name = name
        self.debug_host = DEBUG_HOST
        self.debug_port = int(debug_port)
        self.debug_url = f"http://{self.debug_host}:{self.debug_port}"
        self.user_data_dir = _validate_user_data_dir(user_data_dir)
        self.session_mode = "real_profile" if session_mode == "real_profile" else ("real_profile" if not self.user_data_dir else "isolated")
        self.profile_directory = profile_directory or "Default"
        self._jobs: queue.Queue = queue.Queue(maxsize=_JOBS_QUEUE_MAXSIZE)
        self._ready = threading.Event()
        self._worker_stop = threading.Event()
        self._worker_exited = threading.Event()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._pages: dict[str, Page] = {}
        self._prepared_context_ids: set[int] = set()
        self._network_watch_page_configs: dict[int, dict[str, object]] = {}
        self._network_watch_listener_pages: set[int] = set()
        self._last_error = ""
        self._last_action = "init"
        self._current_action = "init"
        self._action_stage = "idle"
        self._last_reason_code = ""
        self._last_recovery_attempted: list[str] = []
        self._last_pid: int = 0
        self._cached_hwnd: int = 0
        self._window_op_running: bool = False
        self._stale: bool = False
        self._stale_reason: str = ""
        self._last_page_cleanup = PageCleanupResult()
        self._thread = threading.Thread(target=self._worker_loop, name="gmv-remote-edge", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10)

    def _worker_loop(self) -> None:
        self._ready.set()
        while not self._worker_stop.is_set():
            try:
                job = self._jobs.get(timeout=5.0)
            except queue.Empty:
                continue
            action_name, func, result_queue, job_id = job
            try:
                result = func()
                if not self._worker_stop.is_set():
                    try:
                        result_queue.put((True, result), timeout=1.0)
                    except queue.Full:
                        logger.warning(
                            "worker result_queue full, discarding result for action=%s job_id=%s",
                            action_name,
                            job_id,
                        )
            except Exception as exc:
                self._last_error = str(exc)
                from backend.utils.log_throttle import global_throttle

                fp = f"worker:{action_name}:{type(exc).__name__}:{str(exc)[:120]}"
                if global_throttle.should_log(fp):
                    logger.error("worker action=%s failed: %s", action_name, exc, exc_info=True)
                if not self._worker_stop.is_set():
                    try:
                        result_queue.put((False, exc), timeout=1.0)
                    except queue.Full:
                        logger.warning(
                            "worker result_queue full, discarding exception for action=%s job_id=%s: %s",
                            action_name,
                            job_id,
                            exc,
                        )
        self._worker_exited.set()
        logger.info("worker thread exiting gracefully, session_id=%s", self.session_id)

    def _shutdown_worker(self) -> None:
        if not self._thread.is_alive():
            return
        self._worker_stop.set()
        try:
            self._jobs.put(("__shutdown__", lambda: None, queue.Queue(maxsize=1), -1), timeout=1.0)
        except queue.Full:
            pass
        self._thread.join(timeout=_WORKER_JOIN_TIMEOUT)
        if self._thread.is_alive():
            logger.warning("worker thread did not exit in time for session_id=%s", self.session_id)

    def _call(self, action_name: str, func: Callable[[], T], timeout_seconds: float | None = None) -> T:
        if self._worker_stop.is_set() or not self._thread.is_alive():
            exc = RuntimeError(f"Edge worker 已停止，无法执行 {action_name}")
            self._stale = True
            self._stale_reason = f"worker_stopped:{action_name}"
            raise exc
        if self._window_op_running and action_name in ("show_edge", "hide_edge", "close_edge"):
            exc = RuntimeError(f"窗口操作正在进行中，当前无法执行 {action_name}")
            exc.reason_code = "window_op_in_progress"
            self._last_reason_code = "window_op_in_progress"
            self._last_error = str(exc)
            raise exc
        result_queue: queue.Queue = queue.Queue(maxsize=1)
        self._current_action = action_name
        self._action_stage = f"{action_name}:queued"
        job_id = id(result_queue)
        effective_timeout = float(timeout_seconds or ACTION_TIMEOUTS.get(action_name, 20.0))
        try:
            self._jobs.put((action_name, func, result_queue, job_id), timeout=effective_timeout * 0.5)
        except queue.Full as exc:
            self._stale = True
            self._stale_reason = f"job_queue_full:{action_name}"
            self._last_reason_code = "edge_action_timeout"
            self._last_error = f"Edge 任务队列已满，无法提交动作: {action_name}"
            raise EdgeActionTimeoutError(action_name, "queue_full", effective_timeout) from exc
        self._action_stage = f"{action_name}:waiting"
        try:
            ok, value = result_queue.get(timeout=effective_timeout)
        except queue.Empty as exc:
            self._stale = True
            self._stale_reason = f"{action_name}@{self._action_stage}"
            self._last_reason_code = "edge_action_timeout"
            self._last_error = f"Edge 动作超时: {action_name} @ {self._action_stage} ({effective_timeout:.1f}s)"
            raise EdgeActionTimeoutError(action_name, self._action_stage, effective_timeout) from exc
        if ok:
            self._last_error = ""
            self._last_reason_code = ""
            return value
        raise value

    def start_edge(self, launch_url: str = "") -> RemoteEdgeHealth:
        return self._call("start_edge", lambda: self._start_edge(launch_url))

    def show_edge(self, launch_url: str = "") -> RemoteEdgeWindowState:
        return self._call("show_edge", lambda: self._show_edge(launch_url))

    def hide_edge(self) -> RemoteEdgeWindowState:
        return self._call("hide_edge", self._hide_edge)

    def close_edge(self) -> RemoteEdgeCloseState:
        return self._call("close_edge", self._close_edge)

    def ensure_launch_page(self, launch_url: str) -> RemoteEdgeNavigationState:
        return self._call("open_page", lambda: self._ensure_launch_page_action(launch_url), timeout_seconds=ACTION_TIMEOUTS.get("open_page", 20.0))

    @property
    def is_window_op_running(self) -> bool:
        return self._window_op_running

    @property
    def is_stale(self) -> bool:
        return self._stale

    def mark_stale(self, reason: str = "") -> None:
        self._stale = True
        if reason:
            self._stale_reason = reason

    def _state_flags(self) -> dict[str, object]:
        return {
            "is_window_op_running": bool(self._window_op_running),
            "is_stale": bool(self._stale),
            "stale_reason": self._stale_reason or "",
        }

    def _page_cleanup_fields(self) -> dict[str, object]:
        cleanup = self._last_page_cleanup
        return {
            "page_count": int(cleanup.page_count or 0),
            "primary_page_id": cleanup.primary_page_id or "",
            "primary_page_url": cleanup.primary_page_url or "",
            "closed_extra_pages_count": int(cleanup.closed_extra_pages_count or 0),
            "closed_extra_pages": list(cleanup.closed_extra_pages or []),
        }

    def _set_stage(self, stage: str) -> None:
        self._action_stage = stage

    def _reset_action_context(self, action: str) -> None:
        self._current_action = action
        self._last_reason_code = ""
        self._last_recovery_attempted = []
        self._set_stage(f"{action}:ready")

    def _edge_running(self) -> bool:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq msedge.exe"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return "msedge.exe" in result.stdout.lower()
        except Exception:
            return False

    def _find_edge(self) -> str:
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

    def _debug_available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.debug_url}/json/version", timeout=1.5) as response:
                return response.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def _try_restore_browser_connection(self, failed_stage: str = "") -> bool:
        try:
            browser = self._ensure_browser()
        except Exception as exc:
            self._last_error = str(exc)
            self._last_reason_code = "edge_debug_unavailable" if not self._debug_available() else "edge_debug_disconnected"
            if failed_stage:
                self._set_stage(failed_stage)
            return False
        self._last_error = ""
        self._last_reason_code = ""
        return bool(browser.is_connected())

    def _ensure_browser(self) -> Browser:
        if self._browser is not None and self._browser.is_connected():
            return self._browser
        if not self._debug_available():
            raise RuntimeError("真实 Edge 调试端口未连接，请先点击“启动真实 Edge 调试”")
        self._last_action = "connect_remote_edge"
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.connect_over_cdp(self.debug_url)
        except Exception as exc:
            self._last_error = f"连接真实 Edge 失败: {exc}"
            raise RuntimeError(self._last_error) from exc
        self._last_error = ""
        for context in self._browser.contexts:
            self._prepare_context(context)
        return self._browser

    def _reset_browser(self) -> None:
        self._pages = {}
        self._prepared_context_ids = set()
        self._last_page_cleanup = PageCleanupResult()
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
        self._browser = None

    def debug_available_quick(self) -> bool:
        """不走 worker queue，直接 HTTP 检查调试端口是否在线（约 1.5s 超时）。
        不操作 Playwright，可在 worker 忙碌时安全调用。"""
        return self._debug_available()

    def health_quick(self) -> dict:
        """不走 worker queue，返回轻量健康摘要 dict。
        仅检查端口可达性并读取内存状态字段，不涉及 Playwright，线程安全。
        适用于 worker 可能繁忙（如正在截图）的场景，避免 health() 超时级联。"""
        debug_available = self._debug_available()
        return {
            "debug_available": debug_available,
            "connected": debug_available and self._browser is not None,
            "stage": self._action_stage,
            "is_window_op_running": bool(self._window_op_running),
            "is_stale": bool(self._stale),
            "stale_reason": self._stale_reason or "",
            "last_error": self._last_error,
            "reason_code": self._last_reason_code,
            "session_mode": self.session_mode,
            "session_id": self.session_id,
            "name": self.name,
            "debug_port": self.debug_port,
            "profile_initialized": self._profile_initialized(),
        }

    def health(self) -> RemoteEdgeHealth:
        return self._call("health", self._health)

    def _health(self) -> RemoteEdgeHealth:
        debug_available = self._debug_available()
        if not debug_available and self._browser is not None:
            self._reset_browser()
        connected = debug_available and self._browser is not None and self._browser.is_connected()
        if debug_available and not connected:
            connected = self._try_restore_browser_connection("health:browser_restore_failed")
        total = 0
        visible = 0
        if connected:
            live = [page for page in self._pages.values() if self._page_alive(page)]
            total = len(live)
            visible = sum(1 for page in live if self._is_user_page(self._safe_url(page)))
        mode_label = "独立店铺环境" if self.session_mode == "isolated" else "真实个人环境"
        mode_hint = (
            "每个会话首次手动登录一次，后续长期复用；不要在多个账号之间混用同一会话。"
            if self.session_mode == "isolated"
            else "尽量贴近你的日常 Edge 环境，但不适合多账号并行；启动前需关闭所有普通 Edge。"
        )
        profile_initialized = self._profile_initialized()
        reason_code = self._last_reason_code
        last_error = self._last_error
        if not debug_available:
            reason_code = "edge_debug_unavailable" if profile_initialized else (reason_code or "debug_port_unavailable")
            if not last_error:
                last_error = (
                    "当前店铺登录态/Profile 仍保留，但 Edge 调试端口未接通。请先启动或显示当前店铺 Edge。"
                    if profile_initialized
                    else "当前 Edge 调试端口未接通，请先启动或显示当前店铺 Edge。"
                )
        elif not connected:
            reason_code = "edge_debug_disconnected"
            if not last_error:
                last_error = "当前 Edge 调试端口已打开，但自动控制连接尚未恢复。请稍候重试，或先显示当前店铺 Edge。"
        return RemoteEdgeHealth(
            session_id=self.session_id,
            name=self.name,
            action=self._current_action,
            stage=self._action_stage,
            session_mode=self.session_mode,
            debug_port=self.debug_port,
            debug_available=debug_available,
            connected=connected,
            total_pages=total,
            visible_pages=visible,
            user_data_dir=self.user_data_dir,
            profile_initialized=profile_initialized,
            mode_label=mode_label,
            mode_hint=mode_hint,
            last_error=last_error,
            last_action=self._last_action,
            edge_command=self.edge_command(),
            reason_code=reason_code,
            recovery_attempted=list(self._last_recovery_attempted),
            window_diagnostics=self._window_diagnostics(),
            profile_diagnostics=self._profile_diagnostics(),
            **self._state_flags(),
            **self._page_cleanup_fields(),
        )

    def edge_command(self) -> str:
        profile_arg = f'--user-data-dir="{self.user_data_dir}"' if self.user_data_dir else f"--profile-directory={self.profile_directory}"
        return (
            f"msedge.exe {profile_arg} --remote-debugging-port={self.debug_port} "
            f"--remote-debugging-address={self.debug_host} --remote-allow-origins={self.debug_url}"
        )

    def _profile_initialized(self) -> bool:
        if self.session_mode == "real_profile":
            return True
        if not self.user_data_dir:
            return False
        profile_dir = Path(self.user_data_dir)
        if not profile_dir.exists():
            return False
        try:
            return any(profile_dir.iterdir())
        except OSError:
            return False

    def _profile_diagnostics(self) -> dict[str, object]:
        if self.session_mode == "real_profile":
            return {
                "session_mode": self.session_mode,
                "profile_path": "",
                "exists": True,
                "entry_count": None,
                "cookie_files": [],
                "last_modified": None,
            }
        profile_dir = Path(self.user_data_dir) if self.user_data_dir else None
        if profile_dir is None:
            return {
                "session_mode": self.session_mode,
                "profile_path": "",
                "exists": False,
                "entry_count": 0,
                "cookie_files": [],
                "last_modified": None,
            }
        exists = profile_dir.exists()
        entries: list[Path] = []
        cookie_files: list[str] = []
        last_modified = 0.0
        if exists:
            try:
                entries = list(profile_dir.iterdir())
                for item in entries:
                    try:
                        if item.is_file():
                            last_modified = max(last_modified, float(item.stat().st_mtime))
                    except OSError:
                        continue
                cookie_candidates = [
                    profile_dir / "Default" / "Network" / "Cookies",
                    profile_dir / "Default" / "Network" / "Cookies-journal",
                    profile_dir / "Default" / "Cookies",
                    profile_dir / "Default" / "Cookies-journal",
                    profile_dir / "Default" / "Safe Browsing Network" / "Safe Browsing Cookies",
                    profile_dir / "Default" / "Safe Browsing Network" / "Safe Browsing Cookies-journal",
                ]
                for item in cookie_candidates:
                    try:
                        if item.exists():
                            last_modified = max(last_modified, float(item.stat().st_mtime))
                            cookie_files.append(str(item.relative_to(profile_dir)))
                    except OSError:
                        continue
            except OSError:
                entries = []
        return {
            "session_mode": self.session_mode,
            "profile_path": str(profile_dir),
            "exists": exists,
            "entry_count": len(entries),
            "cookie_files": cookie_files[:8],
            "last_modified": last_modified or None,
        }




class RemoteEdgeManager:
    def __init__(self) -> None:
        self._clients: dict[str, RemoteEdge] = {}
        self._lock = threading.Lock()

    def _dispose_client(self, client: RemoteEdge) -> None:
        try:
            client.mark_stale("manager_dispose")
            client._shutdown_worker()
        except Exception:
            pass

    def get_client(
        self,
        session_id: str = "default_real_edge",
        *,
        name: str = "",
        debug_port: int = DEBUG_PORT,
        user_data_dir: str = "",
        session_mode: str = "isolated",
        profile_directory: str = "Default",
    ) -> RemoteEdge:
        session_id = (session_id or "default_real_edge").strip()
        with self._lock:
            client = self._clients.get(session_id)
            if client is not None:
                should_replace = (
                    client.debug_port != int(debug_port)
                    or client.user_data_dir != user_data_dir
                    or client.session_mode != ("real_profile" if session_mode == "real_profile" else ("real_profile" if not user_data_dir else "isolated"))
                    or client.profile_directory != (profile_directory or "Default")
                    or client.is_stale
                )
                if should_replace:
                    if not client.is_stale:
                        client.mark_stale("manager_replaced")
                    self._dispose_client(client)
                    del self._clients[session_id]
                    client = None
            if client is None:
                from . import RemoteEdge

                client = RemoteEdge(
                    session_id=session_id,
                    name=name or session_id,
                    debug_port=debug_port,
                    user_data_dir=user_data_dir,
                    session_mode=session_mode,
                    profile_directory=profile_directory,
                )
                self._clients[session_id] = client
            return client

    def reset_client(self, session_id: str) -> None:
        session_id = (session_id or "default_real_edge").strip()
        with self._lock:
            client = self._clients.pop(session_id, None)
        if client is not None:
            self._dispose_client(client)

    def default_client(self) -> RemoteEdge:
        return self.get_client("default_real_edge", name="真实 Edge Default", debug_port=DEBUG_PORT)
