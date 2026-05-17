from __future__ import annotations

import subprocess
import time

from backend.collectors.window_control import (
    EdgeProcessActionResult,
    EdgeWindowActionResult,
    close_edge_window_native,
    edge_window_diagnostics,
    hide_edge_window,
    invalidate_edge_process_cache,
    show_edge_window,
)

from ._session import RemoteEdgeCloseState, RemoteEdgeWindowState, RemotePageInfo


class RemoteEdgeWindowMixin:
    def _show_edge(self, launch_url: str = "") -> RemoteEdgeWindowState:
        self._window_op_running = True
        try:
            return self.__show_edge(launch_url)
        finally:
            self._window_op_running = False

    def __show_edge(self, launch_url: str = "") -> RemoteEdgeWindowState:
        self._reset_action_context("show_edge")
        self._last_action = "show_real_edge_window"
        self._set_stage("show:starting_session")
        target_url = self._normalize_launch_url(launch_url)
        existing_diagnostics = self._window_diagnostics()
        if existing_diagnostics.get("window_found") and not self._debug_available():
            self._set_stage("show:finding_existing_window")
            existing_result = self._try_show_window()
            if existing_result.ok:
                self._last_error = "已显示当前店铺 Edge 窗口，但调试端口尚未接通"
                self._last_reason_code = "edge_debug_unavailable"
                self._cached_hwnd = existing_result.hwnd
                if existing_result.pid:
                    self._last_pid = existing_result.pid
                return RemoteEdgeWindowState(
                    session_id=self.session_id,
                    action="show_edge",
                    stage="show:window_ready_without_debug",
                    debug_available=False,
                    window_found=True,
                    window_hwnd=existing_result.hwnd,
                    window_pid=existing_result.pid,
                    window_title=existing_result.title,
                    window_action=existing_result.action,
                    maximized=existing_result.maximized,
                    last_error=self._last_error,
                    reason_code=self._last_reason_code,
                    recovery_attempted=[],
                    window_diagnostics=self._window_diagnostics(),
                    **self._state_flags(),
                    **self._page_cleanup_fields(),
                )
        health = self._start_edge(target_url, reset_context=False, visible=True)
        if not health.debug_available:
            return RemoteEdgeWindowState(
                session_id=self.session_id,
                action="show_edge",
                stage=self._action_stage,
                debug_available=False,
                window_found=False,
                window_hwnd=0,
                window_pid=0,
                window_title="",
                window_action="",
                maximized=False,
                reason_code=health.reason_code or "debug_port_unavailable",
                recovery_attempted=[],
                window_diagnostics=self._window_diagnostics(),
                last_error=self._last_error or "真实 Edge 调试端口未打开",
                **self._state_flags(),
                **self._page_cleanup_fields(),
            )
        recovery_attempted: list[str] = []
        reason_code = ""
        restart_blocked_for_safety = False

        def classify_window_failure(message: str, diagnostics_payload: dict[str, object]) -> str:
            text = str(message or "")
            if "屏幕外" in text:
                return "window_still_offscreen"
            if "最小化" in text or "不可见" in text or "主屏前台" in text:
                return "show_window_failed"
            if diagnostics_payload.get("has_no_startup_window"):
                return "no_startup_window"
            if diagnostics_payload.get("candidate_pids"):
                return "show_window_failed" if text else "window_not_found"
            return "window_not_found"

        diagnostics = self._window_diagnostics()
        self._set_stage("show:finding_window")
        result = self._try_show_window()
        if not result.ok:
            reason_code = classify_window_failure(result.error, diagnostics)
            self._last_reason_code = reason_code
            if not diagnostics.get("candidate_pids") and self._spawn_native_window(target_url):
                self._set_stage("show:spawn_native_window")
                recovery_attempted.append("spawn_native_window")
                result = self._try_show_window()
                diagnostics = self._window_diagnostics()
            if not result.ok and diagnostics.get("candidate_pids"):
                self._restart_edge_for_window(target_url)
                if self._last_reason_code == "window_restart_blocked_for_login_safety":
                    restart_blocked_for_safety = True
                    reason_code = self._last_reason_code
        if result.ok:
            self._enforce_single_page(target_url)
            self._last_error = ""
            self._last_action = f"show_real_edge_window:{result.hwnd}"
            reason_code = ""
            self._last_reason_code = ""
            self._set_stage("show:window_ready")
            self._cached_hwnd = result.hwnd
            diagnostics = self._window_diagnostics()
        else:
            diagnostics = self._window_diagnostics()
            if not restart_blocked_for_safety:
                reason_code = classify_window_failure(result.error, diagnostics) if result.error else (reason_code or classify_window_failure("", diagnostics))
            self._last_reason_code = reason_code
            if not restart_blocked_for_safety:
                self._last_error = result.error or self._window_not_found_message(diagnostics, recovery_attempted)
            self._set_stage("show:window_failed")
        if result.pid:
            self._last_pid = result.pid
        self._last_recovery_attempted = list(recovery_attempted)
        return RemoteEdgeWindowState(
            session_id=self.session_id,
            action="show_edge",
            stage=self._action_stage,
            debug_available=True,
            window_found=result.ok,
            window_hwnd=result.hwnd,
            window_pid=result.pid,
            window_title=result.title,
            window_action=result.action,
            maximized=result.maximized,
            reason_code=reason_code,
            recovery_attempted=recovery_attempted,
            window_diagnostics=diagnostics,
            last_error=self._last_error,
            **self._state_flags(),
            **self._page_cleanup_fields(),
        )

    def _try_show_window(self) -> EdgeWindowActionResult:
        return show_edge_window(
            debug_port=self.debug_port,
            user_data_dir=self.user_data_dir,
            pid=self._last_pid,
            cached_hwnd=self._cached_hwnd,
            timeout_seconds=8.0,
        )

    def _window_diagnostics(self) -> dict[str, object]:
        diagnostics = edge_window_diagnostics(
            debug_port=self.debug_port,
            user_data_dir=self.user_data_dir,
            pid=self._last_pid,
        )
        diagnostics["session_id"] = self.session_id
        diagnostics["session_mode"] = self.session_mode
        diagnostics["debug_port"] = self.debug_port
        diagnostics["user_data_dir"] = self.user_data_dir
        diagnostics["window_found"] = bool(diagnostics.get("candidate_windows"))
        return diagnostics

    def _window_not_found_message(self, diagnostics: dict[str, object], recovery_attempted: list[str]) -> str:
        if diagnostics.get("has_no_startup_window"):
            base = "当前 Edge 会话正在后台无窗运行（检测到 --no-startup-window）"
        elif diagnostics.get("candidate_pids"):
            base = "当前 Edge 会话已运行，但没有可显示的本地主窗口"
        else:
            base = "当前 Edge 调试端口已打开，但未识别到对应的 Edge 窗口进程"
        if recovery_attempted:
            return f"{base}，系统已尝试：{'、'.join(recovery_attempted)}"
        return base

    def _spawn_native_window(self, launch_url: str = "") -> bool:
        edge = self._find_edge()
        if not edge:
            return False
        args = [edge, "--new-window", self._normalize_launch_url(launch_url) or "about:blank"]
        if self.user_data_dir:
            args.insert(1, f"--user-data-dir={self.user_data_dir}")
        else:
            args.insert(1, f"--profile-directory={self.profile_directory}")
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            return False
        time.sleep(1.0)
        return True

    def _restart_edge_for_window(self, launch_url: str = "") -> bool:
        self._last_error = "当前 Edge 会话有进程存在但没有可显示主窗口。为保护登录态，系统不会自动强杀重启；请手动关闭该店铺 Edge 后再启动。"
        self._last_reason_code = "window_restart_blocked_for_login_safety"
        return False

    def _ensure_window_page(self) -> RemotePageInfo | None:
        try:
            pages = self._list_pages()
            if pages:
                return pages[0]
        except Exception:
            pass
        try:
            return self._open_page("about:blank")
        except Exception as exc:
            self._last_error = f"真实 Edge 调试端口已开启，但没有可显示窗口，补建新标签失败: {exc}"
            return None

    def _hide_edge(self) -> RemoteEdgeWindowState:
        self._window_op_running = True
        try:
            return self.__hide_edge()
        finally:
            self._window_op_running = False

    def __hide_edge(self) -> RemoteEdgeWindowState:
        self._reset_action_context("hide_edge")
        self._last_action = "hide_real_edge_window"
        self._set_stage("hide:checking_debug_port")
        diagnostics = self._window_diagnostics()
        debug_available = self._debug_available()
        if not debug_available and not diagnostics.get("window_found"):
            self._health()
            return RemoteEdgeWindowState(
                session_id=self.session_id,
                action="hide_edge",
                stage=self._action_stage,
                debug_available=False,
                window_found=False,
                window_hwnd=0,
                window_pid=0,
                window_title="",
                window_action="",
                maximized=False,
                reason_code="edge_debug_unavailable",
                recovery_attempted=[],
                window_diagnostics=diagnostics,
                last_error=self._last_error or "真实 Edge 调试端口未打开",
                **self._state_flags(),
                **self._page_cleanup_fields(),
            )
        self._set_stage("hide:finding_window")
        result = hide_edge_window(
            debug_port=self.debug_port,
            user_data_dir=self.user_data_dir,
            pid=self._last_pid,
            cached_hwnd=self._cached_hwnd,
            timeout_seconds=8.0,
        )
        if result.ok:
            self._last_error = ""
            self._last_action = f"hide_real_edge_window:{result.hwnd}"
            self._last_reason_code = ""
            self._set_stage("hide:hidden")
            self._cached_hwnd = result.hwnd
            diagnostics = self._window_diagnostics()
        else:
            diagnostics = self._window_diagnostics()
            self._last_error = result.error or "未找到对应的 Edge 主窗口"
            if not diagnostics.get("window_found"):
                self._last_reason_code = "window_not_found"
            elif "仍停留在主屏可见区域" in self._last_error:
                self._last_reason_code = "window_still_visible"
            elif "仅最小化" in self._last_error or "仅移到屏幕外" in self._last_error:
                self._last_reason_code = "hide_verification_failed"
            elif not debug_available:
                self._last_reason_code = "edge_debug_unavailable"
            else:
                self._last_reason_code = "hide_window_failed"
            self._set_stage("hide:window_failed")
        if result.pid:
            self._last_pid = result.pid
        return RemoteEdgeWindowState(
            session_id=self.session_id,
            action="hide_edge",
            stage=self._action_stage,
            debug_available=debug_available,
            window_found=result.ok,
            window_hwnd=result.hwnd,
            window_pid=result.pid,
            window_title=result.title,
            window_action=result.action,
            maximized=False,
            reason_code=self._last_reason_code,
            recovery_attempted=[],
            window_diagnostics=diagnostics,
            last_error=self._last_error,
            **self._state_flags(),
            **self._page_cleanup_fields(),
        )

    def _close_edge(self) -> RemoteEdgeCloseState:
        self._window_op_running = True
        try:
            return self.__close_edge()
        finally:
            self._window_op_running = False

    def __close_edge(self) -> RemoteEdgeCloseState:
        self._reset_action_context("close_edge")
        self._last_action = "safe_close_edge"
        graceful_attempted = False
        force_kill_used = False
        close_mode = "graceful"
        profile_diagnostics = self._profile_diagnostics()
        self._set_stage("close:graceful_shutdown")
        graceful_ok = self._try_graceful_shutdown()
        if not graceful_ok:
            close_mode = "safe_close_failed"
            graceful_attempted = True
            self._set_stage("close:safe_close_timeout")
            result = EdgeProcessActionResult(ok=False, pids=[], error="安全关闭超时。为保护登录态，系统未自动强杀 Edge；请手动关闭对应店铺 Edge 窗口后重试。")
        else:
            result = EdgeProcessActionResult(ok=True, pids=[self._last_pid] if self._last_pid else [], error="")
        self._reset_browser()
        self._last_pid = 0
        self._cached_hwnd = 0
        for _ in range(12):
            if not self._debug_available():
                break
            time.sleep(0.25)
        self._set_stage("close:verifying_shutdown")
        debug_available = self._debug_available()
        profile_diagnostics = self._profile_diagnostics()
        window_diagnostics = self._window_diagnostics()
        residual_pids = [int(item) for item in (window_diagnostics.get("candidate_pids") or []) if int(item or 0) > 0]
        if result.ok and not debug_available and not residual_pids:
            self._stale = False
            self._stale_reason = ""
            self._last_error = ""
            self._last_reason_code = ""
            self._set_stage("close:closed")
            invalidate_edge_process_cache()
        else:
            if result.ok and not debug_available and residual_pids:
                self._last_error = f"调试端口已关闭，但仍检测到 Profile 进程残留: {residual_pids}"
                self._last_reason_code = "profile_process_still_running"
                self._set_stage("close:process_residual")
            else:
                self._last_error = result.error or ("Edge 进程已结束，但调试端口仍可访问" if debug_available else "关闭 Edge 失败")
                if close_mode == "safe_close_failed":
                    self._last_reason_code = "safe_close_timeout"
                else:
                    self._last_reason_code = "close_verification_failed" if debug_available else "close_failed"
                self._set_stage("close:failed")
        return RemoteEdgeCloseState(
            session_id=self.session_id,
            action="close_edge",
            stage=self._action_stage,
            debug_available=debug_available,
            closed=bool(result.ok and not debug_available and not residual_pids),
            closed_pids=result.pids,
            window_pid=0,
            last_error=self._last_error,
            reason_code=self._last_reason_code,
            close_mode=close_mode,
            graceful_attempted=graceful_attempted or graceful_ok,
            force_kill_used=force_kill_used,
            profile_initialized=self._profile_initialized(),
            profile_path=self.user_data_dir,
            profile_diagnostics=profile_diagnostics,
            recovery_attempted=[],
            window_diagnostics=window_diagnostics,
            **self._state_flags(),
            **self._page_cleanup_fields(),
        )

    def _try_graceful_shutdown(self) -> bool:
        # 优先：向主窗口发 WM_CLOSE，与用户点 X 完全等效，Edge 自己负责 flush Cookie
        try:
            result = close_edge_window_native(
                debug_port=self.debug_port,
                user_data_dir=self.user_data_dir,
                pid=self._last_pid,
                timeout_seconds=8.0,
            )
            if result.ok:
                return True
        except Exception:
            pass

        # 备用：通过 CDP 关闭（Edge 不在屏幕上无法找到窗口时走这里）
        try:
            if self._browser is not None and self._browser.is_connected():
                try:
                    for context in list(self._browser.contexts):
                        for page in list(context.pages):
                            try:
                                page.close(run_before_unload=True)
                            except Exception:
                                continue
                    self._browser.close()
                except Exception:
                    try:
                        self._browser.close()
                    except Exception:
                        return False
                time.sleep(1.0)  # 等待 Edge 将 Cookies WAL flush 到主文件
                for _ in range(20):
                    if not self._debug_available():
                        return True
                    time.sleep(0.25)
        except Exception:
            return False
        return not self._debug_available()
