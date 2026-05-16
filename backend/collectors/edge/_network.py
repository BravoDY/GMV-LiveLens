from __future__ import annotations

from playwright.sync_api import Page

from ._session import RemotePageInfo

NETWORK_WATCH_BOOTSTRAP_SCRIPT = r"""
(() => {
  if (window.__gmvLiveLensNetworkWatchBootstrapInstalled) return;
  window.__gmvLiveLensNetworkWatchBootstrapInstalled = true;

  const trimText = (value, limit = 400) => {
    const text = String(value ?? "");
    return text.length > limit ? `${text.slice(0, limit)}...` : text;
  };
  const normalizeKeywords = (value) => (
    Array.isArray(value)
      ? value.map((item) => String(item || "").trim().toLowerCase()).filter(Boolean)
      : []
  );

  const state = window.__gmvLiveLensNetworkWatch = window.__gmvLiveLensNetworkWatch || {
    enabled: false,
    maxEvents: 80,
    urlKeywords: [],
    events: [],
    totalCaptured: 0,
    droppedCount: 0,
    startedAt: "",
    updatedAt: "",
  };

  const matchesUrl = (url) => {
    const lower = String(url || "").toLowerCase();
    const keywords = normalizeKeywords(state.urlKeywords);
    if (!keywords.length) return true;
    return keywords.some((keyword) => lower.includes(keyword));
  };

  const pushEvent = (entry) => {
    if (!state.enabled) return;
    const url = String(entry?.url || "");
    if (!matchesUrl(url)) return;
    state.totalCaptured += 1;
    state.updatedAt = new Date().toISOString();
    state.events.push({
      id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
      capturedAt: state.updatedAt,
      source: String(entry?.source || "unknown"),
      method: String(entry?.method || "GET"),
      url,
      status: Number(entry?.status || 0),
      ok: Boolean(entry?.ok),
      durationMs: Number(entry?.durationMs || 0),
      contentType: trimText(entry?.contentType || "", 120),
      responsePreview: trimText(entry?.responsePreview || "", 500),
      error: trimText(entry?.error || "", 240),
    });
    if (state.events.length > state.maxEvents) {
      state.droppedCount += state.events.length - state.maxEvents;
      state.events = state.events.slice(-state.maxEvents);
    }
  };

  if (typeof window.fetch === "function" && !window.__gmvLiveLensFetchWrapped) {
    const originalFetch = window.fetch.bind(window);
    window.__gmvLiveLensFetchWrapped = true;
    window.fetch = async (...args) => {
      const started = Date.now();
      let url = "";
      let method = "GET";
      try {
        const input = args[0];
        const init = args[1];
        url = typeof input === "string" ? input : String(input?.url || "");
        method = String(init?.method || input?.method || "GET");
      } catch (_) {}
      try {
        const response = await originalFetch(...args);
        let preview = "";
        let contentType = "";
        try {
          contentType = response.headers?.get?.("content-type") || "";
          if (contentType.includes("json") || contentType.includes("text")) {
            preview = await response.clone().text();
          }
        } catch (_) {}
        pushEvent({
          source: "fetch",
          method,
          url,
          status: response.status,
          ok: response.ok,
          durationMs: Date.now() - started,
          contentType,
          responsePreview: preview,
        });
        return response;
      } catch (error) {
        pushEvent({
          source: "fetch",
          method,
          url,
          status: 0,
          ok: false,
          durationMs: Date.now() - started,
          error: String(error || "fetch_error"),
        });
        throw error;
      }
    };
  }

  if (window.XMLHttpRequest?.prototype && !window.__gmvLiveLensXhrWrapped) {
    const proto = window.XMLHttpRequest.prototype;
    const originalOpen = proto.open;
    const originalSend = proto.send;
    window.__gmvLiveLensXhrWrapped = true;

    proto.open = function(method, url, ...rest) {
      this.__gmvLiveLensWatchMeta = {
        method: String(method || "GET"),
        url: String(url || ""),
      };
      return originalOpen.call(this, method, url, ...rest);
    };

    proto.send = function(...args) {
      const started = Date.now();
      let finalized = false;
      const meta = this.__gmvLiveLensWatchMeta || {};
      const finalize = (errorText = "") => {
        if (finalized) return;
        finalized = true;
        let preview = "";
        let contentType = "";
        try {
          contentType = this.getResponseHeader?.("content-type") || "";
          if ((contentType.includes("json") || contentType.includes("text") || !contentType) && typeof this.responseText === "string") {
            preview = this.responseText;
          }
        } catch (_) {}
        const status = Number(this.status || 0);
        pushEvent({
          source: "xhr",
          method: String(meta.method || "GET"),
          url: String(meta.url || ""),
          status,
          ok: status >= 200 && status < 400,
          durationMs: Date.now() - started,
          contentType,
          responsePreview: preview,
          error: errorText,
        });
      };
      this.addEventListener("loadend", () => finalize(""));
      this.addEventListener("error", () => finalize("xhr_error"));
      this.addEventListener("abort", () => finalize("xhr_abort"));
      return originalSend.apply(this, args);
    };
  }
})();
"""


class RemoteEdgeNetworkMixin:
    def _install_network_watch_bootstrap(self, page: Page) -> None:
        try:
            if not page.is_closed():
                page.evaluate(NETWORK_WATCH_BOOTSTRAP_SCRIPT)
        except Exception:
            pass

    def _remember_network_watch_config(self, page: Page, config: dict[str, object]) -> None:
        self._network_watch_page_configs[id(page)] = dict(config)
        page_key = id(page)
        if page_key in self._network_watch_listener_pages:
            return
        self._network_watch_listener_pages.add(page_key)
        try:
            page.on("domcontentloaded", lambda *_: self._restore_network_watch_after_navigation(page))
        except Exception:
            pass

    def _restore_network_watch_after_navigation(self, page: Page) -> None:
        config = self._network_watch_page_configs.get(id(page))
        if not config or not self._page_alive(page):
            return
        try:
            self._install_network_watch_bootstrap(page)
            page.evaluate(
                """(config) => {
                  const state = window.__gmvLiveLensNetworkWatch || {};
                  state.enabled = true;
                  state.maxEvents = Number(config?.maxEvents || 80);
                  state.urlKeywords = Array.isArray(config?.urlKeywords) ? config.urlKeywords : [];
                  state.startedAt = state.startedAt || new Date().toISOString();
                  state.updatedAt = state.updatedAt || state.startedAt;
                }""",
                config,
            )
        except Exception:
            pass

    def enable_page_network_watch(
        self,
        page_id: str,
        *,
        max_events: int = 80,
        url_keywords: list[str] | None = None,
        reset: bool = True,
    ) -> dict[str, object]:
        return self._call(
            "enable_network_watch",
            lambda: self._enable_page_network_watch(
                page_id,
                max_events=max_events,
                url_keywords=url_keywords,
                reset=reset,
            ),
        )

    def get_page_network_watch(self, page_id: str) -> dict[str, object]:
        return self._call("get_network_watch", lambda: self._get_page_network_watch(page_id))

    def clear_page_network_watch(self, page_id: str) -> dict[str, object]:
        return self._call("clear_network_watch", lambda: self._clear_page_network_watch(page_id))

    def _network_watch_page(self, page_id: str) -> tuple[Page, RemotePageInfo]:
        page = self._get_page(page_id)
        if page is None:
            self._list_pages()
            page = self._get_page(page_id)
        if page is None:
            raise ValueError("remote_page_not_found")
        self._install_network_watch_bootstrap(page)
        return page, self._page_info(page_id, page)

    def _enable_page_network_watch(
        self,
        page_id: str,
        *,
        max_events: int = 80,
        url_keywords: list[str] | None = None,
        reset: bool = True,
    ) -> dict[str, object]:
        page, info = self._network_watch_page(page_id)
        payload = {
            "maxEvents": max(10, min(int(max_events or 80), 200)),
            "urlKeywords": [str(item).strip() for item in (url_keywords or []) if str(item).strip()],
            "reset": bool(reset),
        }
        self._remember_network_watch_config(page, payload)
        watch = page.evaluate(
            """(config) => {
              const state = window.__gmvLiveLensNetworkWatch || {};
              state.enabled = true;
              state.maxEvents = Number(config?.maxEvents || 80);
              state.urlKeywords = Array.isArray(config?.urlKeywords) ? config.urlKeywords : [];
              if (config?.reset) {
                state.events = [];
                state.totalCaptured = 0;
                state.droppedCount = 0;
              }
              if (!state.startedAt || config?.reset) {
                state.startedAt = new Date().toISOString();
              }
              state.updatedAt = state.updatedAt || state.startedAt;
              return {
                enabled: Boolean(state.enabled),
                maxEvents: Number(state.maxEvents || 0),
                urlKeywords: Array.isArray(state.urlKeywords) ? state.urlKeywords : [],
                events: Array.isArray(state.events) ? state.events : [],
                totalCaptured: Number(state.totalCaptured || 0),
                droppedCount: Number(state.droppedCount || 0),
                startedAt: String(state.startedAt || ""),
                updatedAt: String(state.updatedAt || ""),
              };
            }""",
            payload,
        )
        return {"page": info.__dict__, "watch": watch}

    def _get_page_network_watch(self, page_id: str) -> dict[str, object]:
        page, info = self._network_watch_page(page_id)
        watch = page.evaluate(
            """() => {
              const state = window.__gmvLiveLensNetworkWatch || {};
              return {
                enabled: Boolean(state.enabled),
                maxEvents: Number(state.maxEvents || 0),
                urlKeywords: Array.isArray(state.urlKeywords) ? state.urlKeywords : [],
                events: Array.isArray(state.events) ? state.events : [],
                totalCaptured: Number(state.totalCaptured || 0),
                droppedCount: Number(state.droppedCount || 0),
                startedAt: String(state.startedAt || ""),
                updatedAt: String(state.updatedAt || ""),
              };
            }"""
        )
        return {"page": info.__dict__, "watch": watch}

    def _clear_page_network_watch(self, page_id: str) -> dict[str, object]:
        page, info = self._network_watch_page(page_id)
        self._network_watch_page_configs.pop(id(page), None)
        watch = page.evaluate(
            """() => {
              const state = window.__gmvLiveLensNetworkWatch || {};
              state.enabled = false;
              state.events = [];
              state.totalCaptured = 0;
              state.droppedCount = 0;
              state.updatedAt = new Date().toISOString();
              return {
                enabled: Boolean(state.enabled),
                maxEvents: Number(state.maxEvents || 0),
                urlKeywords: Array.isArray(state.urlKeywords) ? state.urlKeywords : [],
                events: [],
                totalCaptured: 0,
                droppedCount: 0,
                startedAt: String(state.startedAt || ""),
                updatedAt: String(state.updatedAt || ""),
              };
            }"""
        )
        return {"page": info.__dict__, "watch": watch}
