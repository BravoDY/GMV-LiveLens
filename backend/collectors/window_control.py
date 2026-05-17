from __future__ import annotations

import ctypes
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
kernel32 = ctypes.windll.kernel32 if hasattr(ctypes, "windll") else None

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

SW_RESTORE = 9
SW_SHOW = 5
SW_HIDE = 0
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
WM_CLOSE = 0x0010

SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


@dataclass
class EdgeWindowInfo:
    hwnd: int
    title: str
    pid: int
    left: int
    top: int
    width: int
    height: int
    is_visible: bool
    is_minimized: bool
    is_maximized: bool
    is_offscreen: bool


@dataclass
class EdgeWindowActionResult:
    ok: bool
    hwnd: int = 0
    pid: int = 0
    title: str = ""
    action: str = ""
    error: str = ""
    maximized: bool = False


@dataclass
class EdgeProcessActionResult:
    ok: bool
    pids: list[int]
    error: str = ""


def _normalize_path(value: str) -> str:
    if not value:
        return ""
    try:
        return str(Path(value).resolve()).replace("/", "\\").lower()
    except Exception:
        return value.replace("/", "\\").lower()


def _virtual_screen_rect() -> tuple[int, int, int, int]:
    if user32 is None:
        return (0, 0, 0, 0)
    left = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
    top = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
    width = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
    height = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
    return left, top, left + width, top + height


def _rect_intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def _window_title(hwnd: int) -> str:
    length = int(user32.GetWindowTextLengthW(hwnd))
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value.strip()


def _window_rect(hwnd: int) -> RECT | None:
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect


def _window_pid(hwnd: int) -> int:
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def _is_real_top_level_window(hwnd: int) -> bool:
    if not user32.IsWindow(hwnd):
        return False
    if user32.GetParent(hwnd):
        return False
    if user32.GetWindow(hwnd, 4):  # GW_OWNER
        return False
    return True


def list_edge_windows() -> list[EdgeWindowInfo]:
    if user32 is None:
        return []

    windows: list[EdgeWindowInfo] = []
    virtual = _virtual_screen_rect()

    def callback(hwnd: int, _: int) -> bool:
        if not _is_real_top_level_window(hwnd):
            return True
        title = _window_title(hwnd)
        if not title:
            return True
        rect = _window_rect(hwnd)
        if rect is None:
            return True
        width = max(0, int(rect.right - rect.left))
        height = max(0, int(rect.bottom - rect.top))
        if width < 300 or height < 200:
            return True
        pid = _window_pid(hwnd)
        if pid <= 0:
            return True
        win_rect = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
        windows.append(
            EdgeWindowInfo(
                hwnd=int(hwnd),
                title=title,
                pid=pid,
                left=int(rect.left),
                top=int(rect.top),
                width=width,
                height=height,
                is_visible=bool(user32.IsWindowVisible(hwnd)),
                is_minimized=bool(user32.IsIconic(hwnd)),
                is_maximized=bool(user32.IsZoomed(hwnd)),
                is_offscreen=not _rect_intersects(win_rect, virtual),
            )
        )
        return True

    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)(callback)
    user32.EnumWindows(enum_proc, 0)
    return windows


_EDGE_PROC_CACHE: tuple[float, list[dict[str, object]]] = (0.0, [])
_EDGE_PROC_CACHE_TTL = 1.0


def _edge_processes() -> list[dict[str, object]]:
    global _EDGE_PROC_CACHE
    now = time.monotonic()
    if now - _EDGE_PROC_CACHE[0] < _EDGE_PROC_CACHE_TTL:
        return _EDGE_PROC_CACHE[1]
    command = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" "
        "| Select-Object ProcessId,CommandLine "
        "| ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except Exception:
        _EDGE_PROC_CACHE = (now, [])
        return []
    if result.returncode != 0 or not result.stdout.strip():
        _EDGE_PROC_CACHE = (now, [])
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        _EDGE_PROC_CACHE = (now, [])
        return []
    items = data if isinstance(data, list) else [data]
    normalized: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        pid = int(item.get("ProcessId") or 0)
        if pid <= 0:
            continue
        normalized.append(
            {
                "pid": pid,
                "command_line": str(item.get("CommandLine") or ""),
            }
        )
    _EDGE_PROC_CACHE = (now, normalized)
    return normalized


def invalidate_edge_process_cache() -> None:
    """强制刷新 Edge 进程缓存，用于 close 后验证等关键路径"""
    global _EDGE_PROC_CACHE
    _EDGE_PROC_CACHE = (0.0, [])


def _match_edge_processes(
    *,
    debug_port: int = 0,
    user_data_dir: str = "",
    pid: int = 0,
) -> list[dict[str, object]]:
    target_pid = int(pid or 0)
    normalized_dir = _normalize_path(user_data_dir)
    matched: list[dict[str, object]] = []
    seen: set[int] = set()
    if target_pid > 0:
        matched.append({"pid": target_pid, "command_line": ""})
        seen.add(target_pid)
    for proc in _edge_processes():
        proc_pid = int(proc.get("pid") or 0)
        if proc_pid <= 0:
            continue
        command_line = str(proc.get("command_line") or "")
        normalized_command = _normalize_path(command_line)
        if (
            (debug_port and f"--remote-debugging-port={int(debug_port)}" in command_line)
            or (normalized_dir and normalized_dir in normalized_command)
            or (target_pid and proc_pid == target_pid)
        ):
            if proc_pid not in seen:
                matched.append({"pid": proc_pid, "command_line": command_line})
                seen.add(proc_pid)
            elif command_line:
                for item in matched:
                    if int(item.get("pid") or 0) == proc_pid and not item.get("command_line"):
                        item["command_line"] = command_line
                        break
    return matched


def edge_window_diagnostics(
    *,
    debug_port: int = 0,
    user_data_dir: str = "",
    pid: int = 0,
) -> dict[str, object]:
    matched_processes = _match_edge_processes(debug_port=debug_port, user_data_dir=user_data_dir, pid=pid)
    candidate_pids = [int(item.get("pid") or 0) for item in matched_processes if int(item.get("pid") or 0) > 0]
    windows = [window for window in list_edge_windows() if window.pid in set(candidate_pids)]
    windows.sort(
        key=lambda item: (
            item.is_minimized,
            not item.is_visible,
            item.is_offscreen,
            -item.width * item.height,
            item.hwnd,
        )
    )
    return {
        "candidate_pids": candidate_pids,
        "candidate_windows": [
            {
                "hwnd": window.hwnd,
                "pid": window.pid,
                "title": window.title,
                "visible": window.is_visible,
                "minimized": window.is_minimized,
                "maximized": window.is_maximized,
                "offscreen": window.is_offscreen,
            }
            for window in windows
        ],
        "has_no_startup_window": any("--no-startup-window" in str(item.get("command_line") or "") for item in matched_processes),
        "candidate_commands": [
            str(item.get("command_line") or "")
            for item in matched_processes
            if str(item.get("command_line") or "").strip()
        ],
    }


def find_edge_window(
    *,
    debug_port: int = 0,
    user_data_dir: str = "",
    pid: int = 0,
) -> EdgeWindowInfo | None:
    if user32 is None:
        return None
    diagnostics = edge_window_diagnostics(debug_port=debug_port, user_data_dir=user_data_dir, pid=pid)
    candidate_windows = diagnostics.get("candidate_windows", [])
    if not candidate_windows:
        return None
    w = candidate_windows[0]
    return EdgeWindowInfo(
        hwnd=int(w["hwnd"]),
        title=str(w.get("title", "")),
        pid=int(w["pid"]),
        left=0, top=0, width=1280, height=800,
        is_visible=bool(w.get("visible")),
        is_minimized=bool(w.get("minimized")),
        is_maximized=bool(w.get("maximized")),
        is_offscreen=bool(w.get("offscreen")),
    )


def find_edge_process_ids(
    *,
    debug_port: int = 0,
    user_data_dir: str = "",
    pid: int = 0,
    allow_pid_fallback: bool = True,
) -> list[int]:
    target_pid = int(pid or 0)
    matched = {int(item.get("pid") or 0) for item in _match_edge_processes(debug_port=debug_port, user_data_dir=user_data_dir, pid=pid)}
    matched.discard(0)
    if not matched and allow_pid_fallback and target_pid > 0:
        matched.add(target_pid)
    return sorted(matched)


def _move_window_into_view(window: EdgeWindowInfo) -> None:
    if user32 is None or not window.is_offscreen:
        return
    width = max(1200, window.width or 1200)
    height = max(800, window.height or 800)
    user32.SetWindowPos(window.hwnd, 0, 80, 80, width, height, SWP_SHOWWINDOW)


def _move_window_offscreen(window: EdgeWindowInfo) -> None:
    if user32 is None:
        return
    width = max(1200, window.width or 1200)
    height = max(800, window.height or 800)
    user32.SetWindowPos(window.hwnd, 0, 32000, 0, width, height, SWP_SHOWWINDOW)


def _activate_window(hwnd: int) -> None:
    if user32 is None or kernel32 is None:
        return

    foreground = int(user32.GetForegroundWindow())
    current_thread = int(kernel32.GetCurrentThreadId())
    target_thread = int(user32.GetWindowThreadProcessId(hwnd, None))
    foreground_thread = int(user32.GetWindowThreadProcessId(foreground, None)) if foreground else 0

    attached_pairs: list[tuple[int, int]] = []
    for first, second in (
        (current_thread, target_thread),
        (foreground_thread, target_thread),
        (foreground_thread, current_thread),
    ):
        if first and second and first != second and user32.AttachThreadInput(first, second, True):
            attached_pairs.append((first, second))

    try:
        user32.AllowSetForegroundWindow(-1)
    except Exception:
        pass

    try:
        user32.BringWindowToTop(hwnd)
        user32.SetActiveWindow(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        for first, second in reversed(attached_pairs):
            try:
                user32.AttachThreadInput(first, second, False)
            except Exception:
                pass


def _check_cached_hwnd(
    cached_hwnd: int,
    *,
    debug_port: int = 0,
    user_data_dir: str = "",
    pid: int = 0,
) -> EdgeWindowInfo | None:
    """验证缓存的 hwnd 是否仍然有效，有效则直接返回，省去全量窗口枚举。"""
    if not cached_hwnd or user32 is None:
        return None
    if not user32.IsWindow(cached_hwnd):
        return None
    win_pid = _window_pid(cached_hwnd)
    if win_pid <= 0:
        return None
    # pid 匹配校验（宽松：只要 pid 非零且窗口存在即认为有效）
    if pid and win_pid != pid:
        return None
    rect = _window_rect(cached_hwnd)
    if rect is None:
        return None
    virtual = _virtual_screen_rect()
    width = max(0, int(rect.right - rect.left))
    height = max(0, int(rect.bottom - rect.top))
    if width < 100 or height < 100:
        return None
    win_rect = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    return EdgeWindowInfo(
        hwnd=int(cached_hwnd),
        title=_window_title(cached_hwnd),
        pid=win_pid,
        left=int(rect.left),
        top=int(rect.top),
        width=width,
        height=height,
        is_visible=bool(user32.IsWindowVisible(cached_hwnd)),
        is_minimized=bool(user32.IsIconic(cached_hwnd)),
        is_maximized=bool(user32.IsZoomed(cached_hwnd)),
        is_offscreen=not _rect_intersects(win_rect, virtual),
    )


def _window_is_presentable(window: EdgeWindowInfo) -> bool:
    return bool(window.is_visible and not window.is_minimized and not window.is_offscreen)


def _window_is_hidden_like(window: EdgeWindowInfo) -> bool:
    return bool((not window.is_visible) or window.is_minimized or window.is_offscreen)


def _window_sort_key(window: EdgeWindowInfo, *, prefer_recovery: bool) -> tuple[int, int, int, int, int, int]:
    if prefer_recovery:
        return (
            0 if not _window_is_presentable(window) else 1,
            0 if window.is_offscreen else 1,
            0 if window.is_minimized else 1,
            0 if not window.is_visible else 1,
            -(window.width * window.height),
            window.hwnd,
        )
    return (
        0 if _window_is_presentable(window) else 1,
        0 if window.is_visible else 1,
        0 if not window.is_offscreen else 1,
        0 if not window.is_minimized else 1,
        -(window.width * window.height),
        window.hwnd,
    )


def _find_edge_window_for_action(
    *,
    debug_port: int = 0,
    user_data_dir: str = "",
    pid: int = 0,
    prefer_recovery: bool = False,
) -> EdgeWindowInfo | None:
    if user32 is None:
        return None
    candidate_pids = set(find_edge_process_ids(debug_port=debug_port, user_data_dir=user_data_dir, pid=pid, allow_pid_fallback=False))
    if not candidate_pids:
        return None
    windows = [window for window in list_edge_windows() if window.pid in candidate_pids]
    if not windows:
        return None
    windows.sort(key=lambda item: _window_sort_key(item, prefer_recovery=prefer_recovery))
    return windows[0]


def _wait_for_edge_window(
    *,
    debug_port: int = 0,
    user_data_dir: str = "",
    pid: int = 0,
    cached_hwnd: int = 0,
    timeout_seconds: float = 8.0,
    prefer_recovery: bool = False,
) -> EdgeWindowInfo | None:
    # 先尝试缓存的 hwnd，命中则跳过全量枚举
    if cached_hwnd:
        info = _check_cached_hwnd(cached_hwnd, debug_port=debug_port, user_data_dir=user_data_dir, pid=pid)
        if info is not None:
            return info
    deadline = time.time() + max(0.5, timeout_seconds)
    last_window: EdgeWindowInfo | None = None
    while time.time() < deadline:
        last_window = _find_edge_window_for_action(
            debug_port=debug_port,
            user_data_dir=user_data_dir,
            pid=pid,
            prefer_recovery=prefer_recovery,
        )
        if last_window is not None:
            return last_window
        time.sleep(0.1)
    return None


def show_edge_window(
    *,
    debug_port: int = 0,
    user_data_dir: str = "",
    pid: int = 0,
    cached_hwnd: int = 0,
    timeout_seconds: float = 8.0,
) -> EdgeWindowActionResult:
    if user32 is None:
        return EdgeWindowActionResult(ok=False, error="当前环境不支持 Windows 窗口控制")
    last_window = _wait_for_edge_window(
        debug_port=debug_port,
        user_data_dir=user_data_dir,
        pid=pid,
        cached_hwnd=cached_hwnd,
        timeout_seconds=timeout_seconds,
        prefer_recovery=True,
    )
    if last_window is None:
        return EdgeWindowActionResult(ok=False, error="未找到对应的 Edge 主窗口")

    try:
        current = last_window
        for _ in range(3):
            user32.ShowWindow(current.hwnd, SW_SHOW)
            user32.ShowWindow(current.hwnd, SW_RESTORE)
            _move_window_into_view(current)
            _activate_window(current.hwnd)
            user32.ShowWindow(current.hwnd, SW_MAXIMIZE)
            time.sleep(0.2)
            current = _find_edge_window_for_action(
                debug_port=debug_port,
                user_data_dir=user_data_dir,
                pid=current.pid,
                prefer_recovery=False,
            ) or current
            if _window_is_presentable(current):
                return EdgeWindowActionResult(
                    ok=True,
                    hwnd=current.hwnd,
                    pid=current.pid,
                    title=current.title,
                    action="restore_foreground_maximize",
                    maximized=current.is_maximized or bool(user32.IsZoomed(current.hwnd)),
                )
        if current.is_offscreen:
            error = "已找到 Edge 窗口，但窗口仍停留在屏幕外"
        elif current.is_minimized:
            error = "已找到 Edge 窗口，但窗口仍处于最小化状态"
        elif not current.is_visible:
            error = "已找到 Edge 窗口，但窗口仍不可见"
        else:
            error = "已找到 Edge 窗口，但未能确认窗口回到主屏前台"
        return EdgeWindowActionResult(
            ok=False,
            hwnd=current.hwnd,
            pid=current.pid,
            title=current.title,
            error=error,
        )
    except Exception as exc:
        return EdgeWindowActionResult(
            ok=False,
            hwnd=last_window.hwnd,
            pid=last_window.pid,
            title=last_window.title,
            error=str(exc),
        )


def close_edge_window_native(
    *,
    debug_port: int = 0,
    user_data_dir: str = "",
    pid: int = 0,
    timeout_seconds: float = 8.0,
) -> EdgeWindowActionResult:
    """向 Edge 主窗口发送 WM_CLOSE，与用户点击 X 按钮完全等效。"""
    invalidate_edge_process_cache()
    if user32 is None:
        return EdgeWindowActionResult(ok=False, error="当前环境不支持 Windows 窗口控制")
    window = find_edge_window(debug_port=debug_port, user_data_dir=user_data_dir, pid=pid)
    if window is None:
        return EdgeWindowActionResult(ok=False, error="未找到对应的 Edge 主窗口")
    try:
        user32.PostMessageW(window.hwnd, WM_CLOSE, 0, 0)
    except Exception as exc:
        return EdgeWindowActionResult(ok=False, hwnd=window.hwnd, pid=window.pid, error=str(exc))
    deadline = time.time() + max(1.0, timeout_seconds)
    while time.time() < deadline:
        invalidate_edge_process_cache()
        remaining = find_edge_process_ids(
            debug_port=debug_port,
            user_data_dir=user_data_dir,
            pid=pid,
            allow_pid_fallback=False,
        )
        if not remaining:
            return EdgeWindowActionResult(
                ok=True, hwnd=window.hwnd, pid=window.pid, title=window.title, action="wm_close"
            )
        time.sleep(0.25)
    return EdgeWindowActionResult(
        ok=False,
        hwnd=window.hwnd,
        pid=window.pid,
        title=window.title,
        error="WM_CLOSE 已发送但进程未在超时内退出",
    )


def hide_edge_window(
    *,
    debug_port: int = 0,
    user_data_dir: str = "",
    pid: int = 0,
    cached_hwnd: int = 0,
    timeout_seconds: float = 8.0,
) -> EdgeWindowActionResult:
    if user32 is None:
        return EdgeWindowActionResult(ok=False, error="当前环境不支持 Windows 窗口控制")
    last_window = _wait_for_edge_window(
        debug_port=debug_port,
        user_data_dir=user_data_dir,
        pid=pid,
        cached_hwnd=cached_hwnd,
        timeout_seconds=timeout_seconds,
        prefer_recovery=False,
    )
    if last_window is None:
        return EdgeWindowActionResult(ok=False, error="未找到对应的 Edge 主窗口")

    try:
        current = last_window
        for action_name in ("move_offscreen", "minimize_window", "hide_window"):
            if action_name == "move_offscreen":
                if current.is_minimized:
                    user32.ShowWindow(current.hwnd, SW_RESTORE)
                user32.ShowWindow(current.hwnd, SW_SHOW)
                _move_window_offscreen(current)
            elif action_name == "minimize_window":
                user32.ShowWindow(current.hwnd, SW_MINIMIZE)
            else:
                user32.ShowWindow(current.hwnd, SW_HIDE)
            time.sleep(0.15)
            current = find_edge_window(debug_port=debug_port, user_data_dir=user_data_dir, pid=last_window.pid) or current
            if _window_is_hidden_like(current):
                return EdgeWindowActionResult(
                    ok=True,
                    hwnd=current.hwnd,
                    pid=current.pid,
                    title=current.title,
                    action=action_name,
                    maximized=False,
                )
        error = "已找到 Edge 窗口，但窗口仍停留在主屏可见区域"
        if current.is_visible and current.is_minimized:
            error = "已找到 Edge 窗口，但窗口仅最小化，未完全隐藏"
        elif current.is_visible and current.is_offscreen:
            error = "已找到 Edge 窗口，但窗口仅移到屏幕外，隐藏验收未通过"
        return EdgeWindowActionResult(
            ok=False,
            hwnd=current.hwnd,
            pid=current.pid,
            title=current.title,
            error=error,
        )
    except Exception as exc:
        return EdgeWindowActionResult(
            ok=False,
            hwnd=last_window.hwnd,
            pid=last_window.pid,
            title=last_window.title,
            error=str(exc),
        )
