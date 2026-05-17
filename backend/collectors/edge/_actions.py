from __future__ import annotations

import subprocess
import time
from pathlib import Path

from ._session import RemoteEdgeHealth, RemoteEdgeNavigationState


class RemoteEdgeActionsMixin:
    def _ensure_launch_page(self, launch_url: str) -> None:
        target = self._normalize_launch_url(launch_url)
        if not target:
            return
        try:
            pages = self._list_pages()
        except Exception:
            pages = []
        if any(self._urls_match(page.url, target) for page in pages):
            return
        self._set_stage(f"{self._current_action}:opening_target_page")
        try:
            self._open_page(target)
        except Exception as exc:
            self._last_error = f"目标页面已尝试打开，但导航未完成: {exc}"

    def _ensure_launch_page_action(self, launch_url: str) -> RemoteEdgeNavigationState:
        self._reset_action_context("open_page")
        self._last_action = "ensure_launch_page"
        target = self._normalize_launch_url(launch_url)
        if not target:
            self._last_error = "当前任务缺少目标业务页 URL，无法自动继续。"
            self._last_reason_code = "target_page_url_required"
            self._set_stage("open_page:missing_target_url")
            return RemoteEdgeNavigationState(
                session_id=self.session_id,
                action="ensure_launch_page",
                stage=self._action_stage,
                target_url="",
                opened=False,
                target_found=False,
                page_id="",
                page_title="",
                page_url="",
                last_error=self._last_error,
                reason_code=self._last_reason_code,
                **self._state_flags(),
            )
        self._set_stage("open_page:listing_pages")
        pages = self._list_pages()
        existing = next((page for page in pages if self._urls_match(page.url, target)), None)
        if existing is not None:
            self._last_error = ""
            self._last_reason_code = ""
            self._set_stage("open_page:target_page_ready")
            return RemoteEdgeNavigationState(
                session_id=self.session_id,
                action="ensure_launch_page",
                stage=self._action_stage,
                target_url=target,
                opened=False,
                target_found=True,
                page_id=existing.page_id,
                page_title=existing.title,
                page_url=existing.url,
                last_error="",
                reason_code="",
                **self._state_flags(),
            )
        self._set_stage("open_page:opening_target_page")
        opened_page = self._open_page(target)
        for _ in range(8):
            self._set_stage("open_page:waiting_target_page")
            time.sleep(0.5)
            pages = self._list_pages()
            matched = next((page for page in pages if self._urls_match(page.url, target)), None)
            if matched is not None:
                self._last_error = ""
                self._last_reason_code = ""
                self._set_stage("open_page:target_page_ready")
                return RemoteEdgeNavigationState(
                    session_id=self.session_id,
                    action="ensure_launch_page",
                    stage=self._action_stage,
                    target_url=target,
                    opened=True,
                    target_found=True,
                    page_id=matched.page_id,
                    page_title=matched.title,
                    page_url=matched.url,
                    last_error="",
                    reason_code="",
                    **self._state_flags(),
                )
        self._last_reason_code = "target_page_not_found"
        if not self._last_error:
            self._last_error = "已尝试打开目标业务页，但当前会话里仍未识别到目标页。"
        return RemoteEdgeNavigationState(
            session_id=self.session_id,
            action="ensure_launch_page",
            stage=self._action_stage,
            target_url=target,
            opened=True,
            target_found=False,
            page_id=opened_page.page_id,
            page_title=opened_page.title,
            page_url=opened_page.url,
            last_error=self._last_error,
            reason_code=self._last_reason_code,
            **self._state_flags(),
        )

    def _start_edge(self, launch_url: str = "", reset_context: bool = True, visible: bool = False) -> RemoteEdgeHealth:
        if reset_context:
            self._reset_action_context("start_edge")
        _prev_action = self._last_action
        self._last_action = "start_real_edge_debug"
        self._set_stage("start:locating_edge")
        target_url = self._normalize_launch_url(launch_url)
        edge = self._find_edge()
        if not edge:
            self._last_error = "未找到 msedge.exe"
            self._last_reason_code = "edge_binary_not_found"
            return self._health()
        if self._debug_available():
            self._last_error = ""
            self._set_stage("start:debug_port_ready")
            self._ensure_launch_page(target_url)
            self._enforce_single_page(target_url)
            return self._health()
        if not self.user_data_dir and self._edge_running():
            self._last_error = "检测到普通 Edge 已经在运行。真实 Profile 只能由第一个 Edge 进程决定调试端口，请先关闭所有 Edge 窗口和后台进程，再点击启动真实 Edge 调试。"
            self._last_reason_code = "edge_running_conflict"
            self._set_stage("start:conflict_detected")
            return self._health()
        if self.user_data_dir:
            if _prev_action == "safe_close_edge":
                pass
            else:
                diagnostics = self._window_diagnostics()
                commands = [str(item or "") for item in diagnostics.get("candidate_commands", [])]
                has_profile_process = bool(diagnostics.get("candidate_pids"))
                has_debug_flag = any(f"--remote-debugging-port={self.debug_port}" in command for command in commands)
                if has_profile_process and not has_debug_flag:
                    self._last_error = "当前店铺 Profile 已被一个未开启调试端口的 Edge 进程占用。为保护登录态，系统不会自动强杀重启；请手动关闭该店铺 Edge 窗口后再启动。"
                    self._last_reason_code = "profile_locked_without_debug"
                    self._set_stage("start:profile_locked_without_debug")
                    return self._health()

        # 多会话模式：每个会话有独立 user_data_dir，将窗口移出可见屏幕区域
        # CDP 截图不依赖窗口可见性，这样所有 Edge 进程都可以隐藏在看板后面
        offscreen = self.user_data_dir != "" and not visible
        args = [
            edge,
            f"--remote-debugging-port={self.debug_port}",
            f"--remote-debugging-address={self.debug_host}",
            f"--remote-allow-origins={self.debug_url}",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
            target_url or "about:blank",
        ]
        if offscreen:
            # 将窗口定位到屏幕外（不最小化，保留渲染能力）
            args.extend(["--window-position=32000,0", "--window-size=1280,800"])
        elif self.user_data_dir:
            args.extend(["--window-position=80,80", "--window-size=1280,800"])
        if self.user_data_dir:
            Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)
            args.insert(1, f"--user-data-dir={self.user_data_dir}")
        else:
            args.insert(1, f"--profile-directory={self.profile_directory}")
        self._set_stage("start:launching_process")
        try:
            process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._last_pid = int(process.pid or 0)
        except Exception as exc:
            self._last_error = f"启动真实 Edge 调试失败: {exc}"
            self._last_reason_code = "edge_launch_failed"
            self._set_stage("start:launch_failed")
            return self._health()

        self._set_stage("start:waiting_debug_port")
        for _ in range(20):
            if self._debug_available():
                self._last_error = ""
                self._set_stage("start:debug_port_ready")
                break
            time.sleep(0.5)
        else:
            self._last_error = "真实 Edge 调试端口未打开。请先关闭所有普通 Edge，再点击启动真实 Edge 调试。"
            self._last_reason_code = "debug_port_unavailable"
            self._set_stage("start:debug_port_timeout")
        if self._debug_available():
            self._set_stage("start:connecting_browser")
            if not self._try_restore_browser_connection("start:browser_connect_failed"):
                return self._health()
            self._ensure_launch_page(target_url)
            self._enforce_single_page(target_url)
        return self._health()

    def click_page_text(
        self,
        page_id: str,
        text: str,
        *,
        exact: bool = False,
        timeout_ms: int = 8000,
    ) -> dict[str, object]:
        return self._call(
            "click_page_text",
            lambda: self._click_page_text(
                page_id,
                text,
                exact=exact,
                timeout_ms=timeout_ms,
            ),
        )

    def inspect_page_text(
        self,
        page_id: str,
        text: str,
        *,
        exact: bool = False,
    ) -> dict[str, object]:
        return self._call(
            "inspect_page_text",
            lambda: self._inspect_page_text(
                page_id,
                text,
                exact=exact,
            ),
        )

    def _click_page_text(
        self,
        page_id: str,
        text: str,
        *,
        exact: bool = False,
        timeout_ms: int = 8000,
    ) -> dict[str, object]:
        page, info = self._network_watch_page(page_id)
        before_url = info.url
        before_title = info.title
        needle = str(text or "").strip()
        if not needle:
            raise ValueError("click_text_required")
        self._install_same_tab_guard(page)
        self._install_network_watch_bootstrap(page)
        click_result: dict[str, object] | None = None
        selectors = [
            "button",
            "[role='button']",
            "a",
            "input[type='button']",
            "input[type='submit']",
            ".btn",
            ".button",
        ]
        for frame in page.frames:
            try:
                locator = frame.get_by_text(needle, exact=bool(exact)).first
                if locator.count():
                    locator.scroll_into_view_if_needed(timeout=max(500, int(timeout_ms)))
                    locator.click(timeout=max(500, int(timeout_ms)))
                    click_result = {
                        "clicked": True,
                        "matchedText": needle,
                        "frameUrl": frame.url,
                    }
                    break
            except Exception:
                pass
            try:
                for selector in selectors:
                    locator = frame.locator(selector).filter(has_text=needle).first
                    if locator.count():
                        locator.scroll_into_view_if_needed(timeout=max(500, int(timeout_ms)))
                        locator.click(timeout=max(500, int(timeout_ms)))
                        click_result = {
                            "clicked": True,
                            "matchedText": needle,
                            "frameUrl": frame.url,
                        }
                        break
                if click_result:
                    break
            except Exception:
                pass
        if click_result is None:
            click_result = page.evaluate(
                """(payload) => {
                  const needle = String(payload?.text || "").trim();
                  const exact = Boolean(payload?.exact);
                  if (!needle) return { clicked: false, reason: "click_text_required" };
                  const normalize = (value) => String(value || "").replace(/\\s+/g, " ").trim();
                  const matcher = (value) => {
                    const current = normalize(value);
                    return exact ? current === needle : current.includes(needle);
                  };
                  const selectors = [
                    "button",
                    "[role='button']",
                    "a",
                    "input[type='button']",
                    "input[type='submit']",
                    ".btn",
                    ".button",
                  ];
                  const elements = Array.from(document.querySelectorAll(selectors.join(",")));
                  const candidate = elements.find((element) => {
                    const textValue = normalize(
                      element.innerText
                      || element.textContent
                      || element.value
                      || element.getAttribute("aria-label")
                      || element.getAttribute("title")
                    );
                    return matcher(textValue);
                  });
                  if (!candidate) {
                    return { clicked: false, reason: "click_target_not_found" };
                  }
                  const matchedText = normalize(
                    candidate.innerText
                    || candidate.textContent
                    || candidate.value
                    || candidate.getAttribute("aria-label")
                    || candidate.getAttribute("title")
                  );
                  candidate.scrollIntoView({ block: "center", inline: "center" });
                  candidate.click();
                  return { clicked: true, matchedText, frameUrl: window.location.href };
                }""",
                {"text": needle, "exact": bool(exact)},
            )
        if not click_result.get("clicked"):
            raise ValueError(str(click_result.get("reason") or "click_target_not_found"))
        try:
            page.wait_for_load_state("domcontentloaded", timeout=max(500, int(timeout_ms)))
        except Exception:
            pass
        time.sleep(1.0)
        latest = self._page_info(page_id, page)
        return {
            "clicked": True,
            "matched_text": str(click_result.get("matchedText") or needle),
            "before_url": before_url,
            "after_url": latest.url,
            "before_title": before_title,
            "after_title": latest.title,
            "url_changed": before_url != latest.url,
            "page": latest.__dict__,
        }

    def _inspect_page_text(
        self,
        page_id: str,
        text: str,
        *,
        exact: bool = False,
    ) -> dict[str, object]:
        page, info = self._network_watch_page(page_id)
        needle = str(text or "").strip()
        if not needle:
            raise ValueError("inspect_text_required")
        frames_summary: list[dict[str, object]] = []
        total_matches = 0
        for index, frame in enumerate(page.frames):
            match_count = 0
            sample = ""
            frame_url = ""
            try:
                frame_url = frame.url
            except Exception:
                frame_url = ""
            try:
                match_count = frame.get_by_text(needle, exact=bool(exact)).count()
            except Exception:
                match_count = 0
            try:
                body = frame.locator("body")
                if body.count():
                    sample = (body.inner_text(timeout=1000) or "").replace("\n", " ").strip()[:240]
            except Exception:
                sample = ""
            total_matches += int(match_count or 0)
            frames_summary.append(
                {
                    "frame_index": index,
                    "frame_url": frame_url,
                    "text_matches": int(match_count or 0),
                    "sample_text": sample,
                }
            )
        return {
            "page": info.__dict__,
            "query": needle,
            "exact": bool(exact),
            "total_matches": total_matches,
            "frames": frames_summary,
        }
