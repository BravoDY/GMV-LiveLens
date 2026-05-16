from __future__ import annotations

import io
import time
import uuid

from PIL import Image
from playwright.sync_api import BrowserContext, Page

from ._network import NETWORK_WATCH_BOOTSTRAP_SCRIPT
from ._session import PageCleanupResult, RemotePageInfo

SAME_TAB_SCRIPT = r"""
(() => {
  if (window.__gmvLiveLensSameTabInstalled) return;
  window.__gmvLiveLensSameTabInstalled = true;
  const sameTabOpen = (url) => {
    if (url && typeof url === "string") window.location.href = url;
    return window;
  };
  try { window.open = sameTabOpen; } catch (_) {}
  document.addEventListener("click", (event) => {
    const link = event.target && event.target.closest ? event.target.closest("a[target='_blank'], a[target='blank']") : null;
    if (!link) return;
    const href = link.href || link.getAttribute("href");
    if (!href || href.startsWith("javascript:")) return;
    event.preventDefault();
    event.stopPropagation();
    window.location.href = href;
  }, true);
  const cleanTargets = () => {
    document.querySelectorAll("a[target='_blank'], a[target='blank']").forEach((link) => link.setAttribute("target", "_self"));
  };
  cleanTargets();
  new MutationObserver(cleanTargets).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["target"] });
})();
"""


class RemoteEdgePageMixin:
    def _normalize_launch_url(self, launch_url: str) -> str:
        url = (launch_url or "").strip()
        if url.startswith(("http://", "https://")):
            return url
        return ""

    def _urls_match(self, current_url: str, target_url: str) -> bool:
        current = (current_url or "").strip().rstrip("/")
        target = (target_url or "").strip().rstrip("/")
        if not current or not target:
            return False
        return current == target or current.startswith(f"{target}/")

    def _is_login_like_page(self, page: Page) -> bool:
        url = self._safe_url(page).lower()
        try:
            title = page.title()
        except Exception:
            title = ""
        title_lower = title.lower()
        markers = ("login", "signin", "passport", "auth", "sso")
        return bool(any(marker in url for marker in markers) or any(marker in title_lower for marker in markers) or "登录" in title)

    @staticmethod
    def _is_noise_page_url(url: str) -> bool:
        text = (url or "").strip().lower()
        return (
            not text
            or text == "about:blank"
            or text.startswith("edge://")
            or text.startswith("chrome://")
            or "ntp.msn.cn/edge/ntp" in text
            or "microsoft-edge://" in text
        )

    def _page_sort_key_for_single_tab(self, page: Page, target_url: str) -> tuple[int, int, str]:
        url = self._safe_url(page)
        if target_url and self._urls_match(url, target_url):
            rank = 0
        elif self._is_login_like_page(page):
            rank = 1
        elif self._is_user_page(url):
            rank = 2
        elif not self._is_noise_page_url(url):
            rank = 3
        else:
            rank = 4
        return (rank, 0 if self._page_alive(page) else 1, url)

    def _enforce_single_page(self, launch_url: str = "") -> PageCleanupResult:
        target = self._normalize_launch_url(launch_url)
        try:
            browser = self._ensure_browser()
        except Exception:
            self._last_page_cleanup = PageCleanupResult()
            return self._last_page_cleanup

        pages: list[Page] = []
        for context in list(browser.contexts):
            self._prepare_context(context)
            for page in list(context.pages):
                if self._page_alive(page):
                    pages.append(page)

        if not pages:
            self._last_page_cleanup = PageCleanupResult()
            return self._last_page_cleanup

        pages.sort(key=lambda page: self._page_sort_key_for_single_tab(page, target))
        primary = pages[0]
        primary_id = self._register_page(primary)
        closed: list[str] = []
        for page in pages[1:]:
            url = self._safe_url(page)
            try:
                page.close()
                closed.append(url or "about:blank")
            except Exception as exc:
                closed.append(f"{url or 'about:blank'} (close_failed:{exc})")
            finally:
                self._unregister_page(page)

        remaining: list[Page] = []
        for context in list(browser.contexts):
            for page in list(context.pages):
                if self._page_alive(page):
                    remaining.append(page)
        self._last_page_cleanup = PageCleanupResult(
            page_count=len(remaining),
            primary_page_id=primary_id,
            primary_page_url=self._safe_url(primary),
            closed_extra_pages_count=len(closed),
            closed_extra_pages=closed[:20],
        )
        return self._last_page_cleanup

    def _prepare_context(self, context: BrowserContext) -> None:
        context_id = id(context)
        if context_id not in self._prepared_context_ids:
            try:
                context.add_init_script(SAME_TAB_SCRIPT)
                context.add_init_script(NETWORK_WATCH_BOOTSTRAP_SCRIPT)
                context.on("page", self._handle_popup_page)
                self._prepared_context_ids.add(context_id)
            except Exception:
                pass
        for page in context.pages:
            self._install_same_tab_guard(page)
            self._install_network_watch_bootstrap(page)

    def _install_same_tab_guard(self, page: Page) -> None:
        try:
            if not page.is_closed():
                page.evaluate(SAME_TAB_SCRIPT)
        except Exception:
            pass

    def _handle_popup_page(self, page: Page) -> None:
        self._register_page(page)
        self._install_same_tab_guard(page)
        try:
            opener = page.opener()
        except Exception:
            opener = None
        if opener is None:
            return
        url = ""
        for _ in range(20):
            try:
                url = page.url
            except Exception:
                url = ""
            if self._is_user_page(url):
                break
            time.sleep(0.25)
        if not self._is_user_page(url):
            try:
                page.close()
            except Exception:
                pass
            self._unregister_page(page)
            return
        try:
            opener.goto(url, wait_until="commit", timeout=8_000)
            page.close()
            self._unregister_page(page)
        except Exception as exc:
            self._last_error = f"真实 Edge 新标签已拦截，但同标签跳转失败: {exc}"

    def list_pages(self) -> list[RemotePageInfo]:
        return self._call("list_pages", self._list_pages)

    def open_page(self, url: str) -> RemotePageInfo:
        return self._call("open_page", lambda: self._open_page(url))

    def _open_page(self, url: str) -> RemotePageInfo:
        if not url.strip():
            raise ValueError("url_required")
        browser = self._ensure_browser()
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        self._prepare_context(context)
        page = context.new_page()
        page_id = self._register_page(page)
        self._last_action = f"open_remote_edge_page:{url}"
        try:
            page.goto(url.strip(), wait_until="commit", timeout=8_000)
        except Exception as exc:
            self._last_error = f"真实 Edge 页面已创建，但导航未完成: {exc}"
        try:
            page.bring_to_front()
        except Exception:
            pass
        self._install_same_tab_guard(page)
        return self._page_info(page_id, page)

    def _list_pages(self) -> list[RemotePageInfo]:
        browser = self._ensure_browser()
        for context in browser.contexts:
            self._prepare_context(context)
            for page in context.pages:
                if self._is_user_page(self._safe_url(page)):
                    self._register_page(page)
        stale_ids = [page_id for page_id, page in self._pages.items() if not self._page_alive(page)]
        for page_id in stale_ids:
            self._pages.pop(page_id, None)
        pages: list[RemotePageInfo] = []
        for page_id, page in list(self._pages.items()):
            try:
                page_info = self._page_info(page_id, page)
            except Exception:
                continue
            if self._is_user_page(page_info.url):
                pages.append(page_info)
        self._last_error = ""
        return pages

    def screenshot_page(self, page_id: str, full_page: bool = False) -> tuple[Image.Image, RemotePageInfo]:
        return self._call("screenshot_page", lambda: self._screenshot_page(page_id, full_page))

    def _screenshot_page(self, page_id: str, full_page: bool = False) -> tuple[Image.Image, RemotePageInfo]:
        page = self._get_page(page_id)
        if page is None:
            self._set_stage("screenshot_page:refresh_pages")
            self._list_pages()
            page = self._get_page(page_id)
        if page is None:
            raise ValueError("remote_page_not_found")
        self._set_stage("screenshot_page:wait_load")
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5_000)
        except Exception:
            pass
        self._set_stage("screenshot_page:capturing")
        try:
            png = page.screenshot(full_page=full_page, timeout=5_000, animations="disabled", caret="hide")
        except Exception as e:
            err = str(e)
            if "Timeout" in err:
                png = page.screenshot(full_page=full_page, timeout=5_000, caret="hide")
            elif any(k in err for k in ("closed", "Target page", "context or browser", "Navigation failed")):
                raise ValueError("remote_page_not_found") from e
            else:
                raise
        image = Image.open(io.BytesIO(png)).convert("RGB")
        self._last_error = ""
        return image, self._page_info(page_id, page)

    def reload_page(self, page_id: str) -> RemotePageInfo:
        return self._call("reload_page", lambda: self._reload_page(page_id))

    def _reload_page(self, page_id: str) -> RemotePageInfo:
        page = self._get_page(page_id)
        if page is None:
            raise ValueError("remote_page_not_found")
        try:
            page.reload(wait_until="domcontentloaded", timeout=15_000)
        except Exception:
            pass
        return self._page_info(page_id, page)

    def ensure_page(self, page_id: str, page_url: str) -> RemotePageInfo | None:
        return self._call("ensure_page", lambda: self._ensure_page(page_id, page_url))

    def find_page(self, page_id: str) -> RemotePageInfo | None:
        return self._call("find_page", lambda: self._find_page(page_id))

    def _ensure_page(self, page_id: str, page_url: str) -> RemotePageInfo | None:
        page = self._get_page(page_id)
        if page is not None:
            return self._page_info(page_id, page)
        self._list_pages()
        page = self._get_page(page_id)
        if page is not None:
            return self._page_info(page_id, page)
        if not page_url:
            return None
        browser = self._ensure_browser()
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        page_id = self._register_page(page, preferred_id=page_id)
        try:
            page.goto(page_url, wait_until="commit", timeout=8_000)
        except Exception as exc:
            self._last_error = f"真实 Edge 页面恢复创建成功，但导航未完成: {exc}"
        return self._page_info(page_id, page)

    def _find_page(self, page_id: str) -> RemotePageInfo | None:
        page = self._get_page(page_id)
        if page is not None:
            return self._page_info(page_id, page)
        self._list_pages()
        page = self._get_page(page_id)
        if page is not None:
            return self._page_info(page_id, page)
        return None

    def _register_page(self, page: Page, preferred_id: str = "") -> str:
        for page_id, existing in self._pages.items():
            if existing == page:
                if preferred_id and page_id != preferred_id:
                    self._pages.pop(page_id, None)
                    self._pages[preferred_id] = page
                    return preferred_id
                return page_id
        page_id = preferred_id or uuid.uuid4().hex[:12]
        self._pages[page_id] = page
        self._install_same_tab_guard(page)
        self._install_network_watch_bootstrap(page)
        return page_id

    def _unregister_page(self, page: Page) -> None:
        self._network_watch_page_configs.pop(id(page), None)
        self._network_watch_listener_pages.discard(id(page))
        stale = [page_id for page_id, existing in self._pages.items() if existing == page]
        for page_id in stale:
            self._pages.pop(page_id, None)

    def _get_page(self, page_id: str) -> Page | None:
        page = self._pages.get(page_id)
        if page is not None and self._page_alive(page):
            return page
        return None

    def _page_info(self, page_id: str, page: Page) -> RemotePageInfo:
        try:
            title = page.title()
        except Exception:
            title = ""
        return RemotePageInfo(page_id=page_id, title=title, url=self._safe_url(page), is_closed=not self._page_alive(page))

    def _safe_url(self, page: Page) -> str:
        try:
            return page.url
        except Exception:
            return ""

    def _page_alive(self, page: Page) -> bool:
        try:
            return not page.is_closed()
        except Exception:
            return False

    @staticmethod
    def _is_user_page(url: str) -> bool:
        if not url or url == "about:blank":
            return False
        if "ntp.msn.cn/edge/ntp" in url:
            return False
        return url.startswith("http://") or url.startswith("https://")
