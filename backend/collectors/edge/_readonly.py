from __future__ import annotations

from playwright.sync_api import Page

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


class RemoteEdgeReadonlyMixin:
    def _resolve_screen_target(self, page: Page) -> tuple[str, object | None]:
        try:
            if "sycm.taobao.com/datawar/screen.htm" in (page.url or ""):
                return "天猫", page
            if "sz.jd.com/sz/view/realTime/realKanBans.html" in (page.url or ""):
                return "京东", page
            if "compass.vip.com/live/index.html#/daily" in (page.url or ""):
                return "唯品会", page
            if "compass.jinritemai.com/screen/shop/single" in (page.url or ""):
                return "抖音", page
            if "stark.dewu.com/main/transaction/adjustment" in (page.url or ""):
                return "得物", page
        except Exception:
            pass
        for frame in page.frames:
            try:
                if "sycm.taobao.com/datawar/screen.htm" in (frame.url or ""):
                    return "天猫", frame
                if "sz.jd.com/sz/view/realTime/realKanBans.html" in (frame.url or ""):
                    return "京东", frame
                if "compass.vip.com/live/index.html#/daily" in (frame.url or ""):
                    return "唯品会", frame
                if "compass.jinritemai.com/screen/shop/single" in (frame.url or ""):
                    return "抖音", frame
                if "stark.dewu.com/main/transaction/adjustment" in (frame.url or ""):
                    return "得物", frame
            except Exception:
                continue
        return "", None

    def _read_tmall_screen_pay_amount(self, target) -> dict[str, object]:
        return target.evaluate(
            r"""async () => {
              const capturedAt = new Date().toISOString();
              const screenUrl = window.location.href;
              const resources = performance.getEntriesByType("resource")
                .map((item) => String(item?.name || ""))
                .filter(Boolean);
              let sourceUrl = resources
                .filter((url) => url.includes("/datawar/v3/screen/reception/overview.json"))
                .slice(-1)[0] || "";
              const token = String(window.__microdata?.legalityToken || "");
              if (!sourceUrl) {
                if (!token) {
                  return {
                    ready: false,
                    reason_code: "screen_overview_source_not_found",
                    message: "当前大屏页还没有发现 overview 数据源，请稍等页面加载完成后再试。",
                    frame_url: screenUrl,
                    captured_at: capturedAt,
                    update_time: "",
                    interval_seconds: 0,
                    pay_amt: null,
                    pay_amt_wl: null,
                    pay_cnt: null,
                    pay_amt_wl_ratio: null,
                    source_url: "",
                    metric_label: "payAmt.value",
                    platform_key: "天猫",
                  };
                }
                sourceUrl = `/datawar/v3/screen/reception/overview.json?effectType=payAmt&secondEffectList=payAmt,payCnt&_=${Date.now()}&token=${encodeURIComponent(token)}`;
              }
              try {
                const response = await fetch(sourceUrl, { credentials: "include" });
                const rawText = await response.text();
                let payload = null;
                try {
                  payload = JSON.parse(rawText);
                } catch (_) {
                  payload = null;
                }
                if (!response.ok) {
                  return {
                    ready: false,
                    reason_code: "screen_overview_http_error",
                    message: `大屏 overview 接口返回 HTTP ${response.status}`,
                    frame_url: screenUrl,
                    captured_at: capturedAt,
                    update_time: "",
                    interval_seconds: 0,
                    pay_amt: null,
                    pay_amt_wl: null,
                    pay_cnt: null,
                    pay_amt_wl_ratio: null,
                    source_url: sourceUrl,
                    http_status: response.status,
                    response_preview: rawText.slice(0, 500),
                    metric_label: "payAmt.value",
                    platform_key: "天猫",
                  };
                }
                if (!payload || Number(payload.code) !== 0) {
                  return {
                    ready: false,
                    reason_code: "screen_overview_payload_invalid",
                    message: "大屏 overview 接口返回异常，当前无法读取 payAmt。",
                    frame_url: screenUrl,
                    captured_at: capturedAt,
                    update_time: "",
                    interval_seconds: 0,
                    pay_amt: null,
                    pay_amt_wl: null,
                    pay_cnt: null,
                    pay_amt_wl_ratio: null,
                    source_url: sourceUrl,
                    response_preview: rawText.slice(0, 500),
                    metric_label: "payAmt.value",
                    platform_key: "天猫",
                  };
                }
                const data = payload?.data?.data || {};
                const payAmt = Number(data?.payAmt?.value);
                if (!Number.isFinite(payAmt)) {
                  return {
                    ready: false,
                    reason_code: "screen_payamt_missing",
                    message: "大屏页已打开，但当前响应里没有读到 payAmt.value。",
                    frame_url: screenUrl,
                    captured_at: capturedAt,
                    update_time: String(payload?.data?.updateTime || ""),
                    interval_seconds: Number(payload?.data?.interval || 0),
                    pay_amt: null,
                    pay_amt_wl: Number.isFinite(Number(data?.payAmtWl?.value)) ? Number(data.payAmtWl.value) : null,
                    pay_cnt: Number.isFinite(Number(data?.payCnt?.value)) ? Number(data.payCnt.value) : null,
                    pay_amt_wl_ratio: Number.isFinite(Number(data?.payAmtWlRatio?.value)) ? Number(data.payAmtWlRatio.value) : null,
                    source_url: sourceUrl,
                    timestamp: Number(payload?.data?.timestamp || 0),
                    metric_label: "payAmt.value",
                    platform_key: "天猫",
                  };
                }
                return {
                  ready: true,
                  reason_code: "",
                  message: "",
                  frame_url: screenUrl,
                  captured_at: capturedAt,
                  update_time: String(payload?.data?.updateTime || ""),
                  interval_seconds: Number(payload?.data?.interval || 0),
                  pay_amt: payAmt,
                  pay_amt_wl: Number.isFinite(Number(data?.payAmtWl?.value)) ? Number(data.payAmtWl.value) : null,
                  pay_cnt: Number.isFinite(Number(data?.payCnt?.value)) ? Number(data.payCnt.value) : null,
                  pay_amt_wl_ratio: Number.isFinite(Number(data?.payAmtWlRatio?.value)) ? Number(data.payAmtWlRatio.value) : null,
                  source_url: sourceUrl,
                  timestamp: Number(payload?.data?.timestamp || 0),
                  metric_label: "payAmt.value",
                  platform_key: "天猫",
                };
              } catch (error) {
                return {
                  ready: false,
                  reason_code: "screen_overview_fetch_failed",
                  message: String(error || "screen_overview_fetch_failed"),
                  frame_url: screenUrl,
                  captured_at: capturedAt,
                  update_time: "",
                  interval_seconds: 0,
                  pay_amt: null,
                  pay_amt_wl: null,
                  pay_cnt: null,
                  pay_amt_wl_ratio: null,
                  source_url: sourceUrl,
                  metric_label: "payAmt.value",
                  platform_key: "天猫",
                };
              }
            }"""
        )

    def _read_jd_screen_pay_amount(self, target) -> dict[str, object]:
        return target.evaluate(
            r"""() => {
              const capturedAt = new Date().toISOString();
              const screenUrl = window.location.href;
              const pageText = String(document.body?.innerText || "");
              const realtimeEntries = performance.getEntriesByType("resource")
                .map((item) => ({
                  name: String(item?.name || ""),
                  initiatorType: String(item?.initiatorType || ""),
                  startTime: Number(item?.startTime || 0),
                  responseEnd: Number(item?.responseEnd || 0),
                }))
                .filter((item) => {
                  if (!item.name || !Number.isFinite(item.startTime) || item.startTime <= 0) {
                    return false;
                  }
                  if (!["fetch", "xmlhttprequest"].includes(item.initiatorType)) {
                    return false;
                  }
                  return item.name.includes("/sz/api/realTime/");
                });
              const timingCandidates = [
                /getKanBanTotoalSaleData\.ajax/i,
                /getKanBanServeyData\.ajax/i,
                /getKanBanSaleListData\.ajax/i,
                /getShopRankingRealBoard\.ajax/i,
                /getKanBanSaleSeries\.ajax/i,
              ];
              const buildTimingPayload = (pattern) => {
                const matched = realtimeEntries
                  .filter((item) => pattern.test(item.name))
                  .map((item) => ({
                    name: item.name,
                    marker: Number.isFinite(item.responseEnd) && item.responseEnd > 0
                      ? item.responseEnd
                      : item.startTime,
                  }))
                  .filter((item) => Number.isFinite(item.marker) && item.marker > 0)
                  .sort((a, b) => a.marker - b.marker);
                if (!matched.length) {
                  return null;
                }
                const last = matched[matched.length - 1];
                let intervalSeconds = 0;
                if (matched.length >= 2) {
                  const prev = [...matched]
                    .reverse()
                    .slice(1)
                    .find((item) => (last.marker - item.marker) >= 1000);
                  if (prev) {
                    const seconds = (last.marker - prev.marker) / 1000;
                    if (Number.isFinite(seconds) && seconds >= 1 && seconds <= 300) {
                      intervalSeconds = Number(seconds.toFixed(3));
                    }
                  }
                }
                return {
                  interval_seconds: intervalSeconds,
                  latest_response_end_seconds: Number((last.marker / 1000).toFixed(3)),
                  latest_response_source: last.name,
                };
              };
              const resolveRealtimeTiming = () => {
                for (const pattern of timingCandidates) {
                  const timing = buildTimingPayload(pattern);
                  if (timing) {
                    return timing;
                  }
                }
                const fallback = realtimeEntries
                  .map((item) => ({
                    name: item.name,
                    marker: Number.isFinite(item.responseEnd) && item.responseEnd > 0
                      ? item.responseEnd
                      : item.startTime,
                  }))
                  .filter((item) => Number.isFinite(item.marker) && item.marker > 0)
                  .sort((a, b) => a.marker - b.marker);
                if (!fallback.length) {
                  return {
                    interval_seconds: 0,
                    latest_response_end_seconds: 0,
                    latest_response_source: "",
                  };
                }
                const last = fallback[fallback.length - 1];
                let intervalSeconds = 0;
                if (fallback.length >= 2) {
                  const prev = fallback[fallback.length - 2];
                  const seconds = (last.marker - prev.marker) / 1000;
                  if (Number.isFinite(seconds) && seconds >= 1 && seconds <= 300) {
                    intervalSeconds = Number(seconds.toFixed(3));
                  }
                }
                return {
                  interval_seconds: intervalSeconds,
                  latest_response_end_seconds: Number((last.marker / 1000).toFixed(3)),
                  latest_response_source: last.name,
                };
              };
              const realtimeTiming = resolveRealtimeTiming();
              const resolvePollingIntervalSeconds = () => {
                return Number(realtimeTiming.interval_seconds || 0);
              };
              const pollingIntervalSeconds = resolvePollingIntervalSeconds();
              const normalizeNumberText = (value) => String(value || "")
                .replace(/\s+/g, "")
                .replace(/[^\d,.\-]/g, "");
              const parseMoney = (value) => {
                const cleaned = normalizeNumberText(value);
                if (!cleaned) return null;
                const parsed = Number(cleaned.replace(/,/g, ""));
                return Number.isFinite(parsed) ? parsed : null;
              };
              const root = document.querySelector(".today-order-sum");
              if (!root) {
                return {
                  ready: false,
                  reason_code: "jd_screen_root_not_found",
                  message: "当前页还没有进入京东实时看板，或“今日成交金额累计”区域尚未渲染完成。",
                  frame_url: screenUrl,
                  captured_at: capturedAt,
                  update_time: "",
                  interval_seconds: pollingIntervalSeconds,
                  latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                  latest_response_source: realtimeTiming.latest_response_source,
                  pay_amt: null,
                  source_url: screenUrl,
                  metric_label: "今日成交金额累计",
                  platform_key: "京东",
                };
              }
              const bindEl = root.querySelector("[ng-bind*='todayOrdAmt']") || root.querySelector(".realtime-summary .num-font") || root.querySelector(".realtime-summary");
              const zeroPrefix = Array.from(root.querySelectorAll(".zero-x-cnt .zero-x span, .zero-x-cnt span"))
                .map((el) => String(el.textContent || "").trim())
                .filter(Boolean)
                .join("")
                .replace(/[^\d]/g, "")
                .slice(0, 1);
              const bindText = bindEl ? normalizeNumberText(bindEl.textContent || "") : "";
              let scopeValue = null;
              try {
                if (window.angular && bindEl) {
                  const scope = window.angular.element(bindEl).scope?.();
                  const candidate = Number(scope?.left?.todayOrdAmt);
                  if (Number.isFinite(candidate)) scopeValue = candidate;
                }
              } catch (_) {}
              const displayValue = [zeroPrefix, bindText].filter(Boolean).join("");
              const parsedDisplayValue = parseMoney(displayValue);
              const payAmt = Number.isFinite(scopeValue) ? scopeValue : parsedDisplayValue;
              const updateMatch = pageText.match(/20\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}/);
              const updateTime = updateMatch ? String(updateMatch[0]) : "";
              if (!Number.isFinite(payAmt)) {
                return {
                  ready: false,
                  reason_code: "jd_screen_payamt_missing",
                  message: "京东实时看板已打开，但当前还没有读到“今日成交金额累计”。",
                  frame_url: screenUrl,
                  captured_at: capturedAt,
                  update_time: updateTime,
                  interval_seconds: pollingIntervalSeconds,
                  latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                  latest_response_source: realtimeTiming.latest_response_source,
                  pay_amt: null,
                  source_url: screenUrl,
                  display_value: displayValue,
                  metric_label: "今日成交金额累计",
                  platform_key: "京东",
                };
              }
              return {
                ready: true,
                reason_code: "",
                message: "",
                frame_url: screenUrl,
                captured_at: capturedAt,
                update_time: updateTime,
                interval_seconds: pollingIntervalSeconds,
                latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                latest_response_source: realtimeTiming.latest_response_source,
                pay_amt: payAmt,
                source_url: screenUrl,
                display_value: displayValue,
                metric_label: "今日成交金额累计",
                platform_key: "京东",
              };
            }"""
        )

    def _read_vip_screen_pay_amount(self, target) -> dict[str, object]:
        return target.evaluate(
            r"""() => {
              const capturedAt = new Date().toISOString();
              const screenUrl = window.location.href;
              const normalizeNumberText = (value) => String(value || "")
                .replace(/\s+/g, "")
                .replace(/[^\d,.\-]/g, "");
              const parseMoney = (value) => {
                const cleaned = normalizeNumberText(value);
                if (!cleaned) return null;
                const parsed = Number(cleaned.replace(/,/g, ""));
                return Number.isFinite(parsed) ? parsed : null;
              };
              const realtimeEntries = performance.getEntriesByType("resource")
                .map((item) => ({
                  name: String(item?.name || ""),
                  initiatorType: String(item?.initiatorType || ""),
                  startTime: Number(item?.startTime || 0),
                  responseEnd: Number(item?.responseEnd || 0),
                }))
                .filter((item) => {
                  if (!item.name || !Number.isFinite(item.startTime) || item.startTime <= 0) {
                    return false;
                  }
                  if (!["fetch", "xmlhttprequest"].includes(item.initiatorType)) {
                    return false;
                  }
                  return item.name.includes("compass.vip.com/");
                });
              const timingCandidates = [
                /\/realtime\/dailylive\/queryVendorRealTimeMetric/i,
                /\/promotion\/queryValueOfPayRealTimeMetric/i,
                /\/realtime\/dailylive\/queryCategoryRankingV2/i,
              ];
              const buildTimingPayload = (pattern) => {
                const matched = realtimeEntries
                  .filter((item) => pattern.test(item.name))
                  .map((item) => ({
                    name: item.name,
                    marker: Number.isFinite(item.responseEnd) && item.responseEnd > 0
                      ? item.responseEnd
                      : item.startTime,
                  }))
                  .filter((item) => Number.isFinite(item.marker) && item.marker > 0)
                  .sort((a, b) => a.marker - b.marker);
                if (!matched.length) {
                  return null;
                }
                const last = matched[matched.length - 1];
                let intervalSeconds = 0;
                if (matched.length >= 2) {
                  const prev = matched[matched.length - 2];
                  const seconds = (last.marker - prev.marker) / 1000;
                  if (Number.isFinite(seconds) && seconds >= 1 && seconds <= 300) {
                    intervalSeconds = Number(seconds.toFixed(3));
                  }
                }
                const wallClockMs = performance.timeOrigin + last.marker;
                return {
                  interval_seconds: intervalSeconds,
                  latest_response_end_seconds: Number((last.marker / 1000).toFixed(3)),
                  latest_response_source: last.name,
                  latest_response_time: Number.isFinite(wallClockMs) ? new Date(wallClockMs).toISOString() : "",
                };
              };
              const resolveRealtimeTiming = () => {
                for (const pattern of timingCandidates) {
                  const timing = buildTimingPayload(pattern);
                  if (timing) {
                    return timing;
                  }
                }
                return {
                  interval_seconds: 0,
                  latest_response_end_seconds: 0,
                  latest_response_source: "",
                  latest_response_time: "",
                };
              };
              const realtimeTiming = resolveRealtimeTiming();
              const root = document.querySelector(".living-header-div");
              if (!root) {
                return {
                  ready: false,
                  reason_code: "vip_screen_root_not_found",
                  message: "当前页还没有进入唯品会魔方日常直播间，或顶部实时GMV区域尚未渲染完成。",
                  frame_url: screenUrl,
                  captured_at: capturedAt,
                  update_time: realtimeTiming.latest_response_time,
                  interval_seconds: Number(realtimeTiming.interval_seconds || 0),
                  latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                  latest_response_source: realtimeTiming.latest_response_source,
                  pay_amt: null,
                  source_url: screenUrl,
                  metric_label: "实时GMV",
                  platform_key: "唯品会",
                };
              }
              const amountEl = root.querySelector(".living-intime-money-p .inner-number")
                || root.querySelector(".living-intime-money-p")
                || root.querySelector(".inner-number");
              const displayValue = amountEl ? normalizeNumberText(amountEl.textContent || "") : "";
              const payAmt = parseMoney(displayValue);
              if (!Number.isFinite(payAmt)) {
                return {
                  ready: false,
                  reason_code: "vip_screen_payamt_missing",
                  message: "唯品会魔方日常直播间已打开，但当前还没有读到顶部“实时GMV”。",
                  frame_url: screenUrl,
                  captured_at: capturedAt,
                  update_time: realtimeTiming.latest_response_time,
                  interval_seconds: Number(realtimeTiming.interval_seconds || 0),
                  latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                  latest_response_source: realtimeTiming.latest_response_source,
                  pay_amt: null,
                  source_url: screenUrl,
                  display_value: displayValue,
                  metric_label: "实时GMV",
                  platform_key: "唯品会",
                };
              }
              return {
                ready: true,
                reason_code: "",
                message: "",
                frame_url: screenUrl,
                captured_at: capturedAt,
                update_time: realtimeTiming.latest_response_time || capturedAt,
                interval_seconds: Number(realtimeTiming.interval_seconds || 0),
                latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                latest_response_source: realtimeTiming.latest_response_source,
                pay_amt: payAmt,
                source_url: screenUrl,
                display_value: displayValue,
                metric_label: "实时GMV",
                platform_key: "唯品会",
              };
            }"""
        )

    def _read_douyin_screen_pay_amount(self, target) -> dict[str, object]:
        return target.evaluate(
            r"""() => {
              const capturedAt = new Date().toISOString();
              const screenUrl = window.location.href;
              const targetPath = "compass.jinritemai.com/screen/shop/single";
              const normalizeNumberText = (value) => String(value || "")
                .replace(/\s+/g, "")
                .replace(/[^\d,.\-]/g, "");
              const escapeRegExp = (value) => String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
              const compactText = (value) => String(value || "").replace(/\s+/g, "");
              const displayText = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const parseMoney = (value) => {
                const cleaned = normalizeNumberText(value);
                if (!cleaned) return null;
                const parsed = Number(cleaned.replace(/,/g, ""));
                return Number.isFinite(parsed) ? parsed : null;
              };
              const pageText = String(document.body?.innerText || "").replace(/\s+/g, " ").trim();
              const realtimeEntries = performance.getEntriesByType("resource")
                .map((item) => ({
                  name: String(item?.name || ""),
                  initiatorType: String(item?.initiatorType || ""),
                  startTime: Number(item?.startTime || 0),
                  responseEnd: Number(item?.responseEnd || 0),
                }))
                .filter((item) => {
                  if (!item.name || !Number.isFinite(item.startTime) || item.startTime <= 0) {
                    return false;
                  }
                  if (!["fetch", "xmlhttprequest"].includes(item.initiatorType)) {
                    return false;
                  }
                  return item.name.includes("compass.jinritemai.com");
                });
              const buildTiming = () => {
                const matched = realtimeEntries
                  .map((item) => ({
                    name: item.name,
                    marker: Number.isFinite(item.responseEnd) && item.responseEnd > 0
                      ? item.responseEnd
                      : item.startTime,
                  }))
                  .filter((item) => Number.isFinite(item.marker) && item.marker > 0)
                  .sort((a, b) => a.marker - b.marker);
                if (!matched.length) {
                  return {
                    interval_seconds: 0,
                    latest_response_end_seconds: 0,
                    latest_response_source: "",
                    latest_response_time: "",
                  };
                }
                const last = matched[matched.length - 1];
                let intervalSeconds = 0;
                if (matched.length >= 2) {
                  const prev = [...matched]
                    .reverse()
                    .slice(1)
                    .find((item) => (last.marker - item.marker) >= 1000);
                  if (prev) {
                    const seconds = (last.marker - prev.marker) / 1000;
                    if (Number.isFinite(seconds) && seconds >= 1 && seconds <= 300) {
                      intervalSeconds = Number(seconds.toFixed(3));
                    }
                  }
                }
                const wallClockMs = performance.timeOrigin + last.marker;
                return {
                  interval_seconds: intervalSeconds,
                  latest_response_end_seconds: Number((last.marker / 1000).toFixed(3)),
                  latest_response_source: last.name,
                  latest_response_time: Number.isFinite(wallClockMs) ? new Date(wallClockMs).toISOString() : "",
                };
              };
              const realtimeTiming = buildTiming();
              const metricLabel = "今日用户支付金额";
              const excludedMetricLabel = "今日用户支付金额(含异常交易)";
              const normalizedMetricLabel = compactText(metricLabel);
              const normalizedExcludedMetricLabel = compactText(excludedMetricLabel);
              const isExcludedText = (value) => compactText(value || "").includes(normalizedExcludedMetricLabel);
              const collectAmountCandidates = (root) => {
                if (!root) return [];
                const elements = [root, ...root.querySelectorAll("div, span, p, strong, h1, h2, h3, h4, h5")];
                const seen = new Set();
                const candidates = [];
                for (const element of elements) {
                  const text = displayText(element.textContent || "");
                  if (!text || compactText(text) === normalizedMetricLabel || isExcludedText(text)) continue;
                  const matches = [...text.matchAll(/¥?\s*([\d,]+(?:\.\d+)?)/g)];
                  for (const match of matches) {
                    const amountText = String(match?.[1] || "").trim();
                    const parsed = parseMoney(amountText);
                    if (!Number.isFinite(parsed)) continue;
                    const key = `${amountText}::${text}`;
                    if (seen.has(key)) continue;
                    seen.add(key);
                    candidates.push({
                      amountText,
                      value: parsed,
                      textLength: text.length,
                    });
                  }
                }
                return candidates.sort((left, right) => left.textLength - right.textLength);
              };
              const pickSingleAmount = (root) => {
                const amountCandidates = collectAmountCandidates(root);
                if (amountCandidates.length !== 1) {
                  return null;
                }
                return {
                  metricRoot: root,
                  amountText: amountCandidates[0].amountText,
                  amountCandidateCount: amountCandidates.length,
                };
              };
              const parseLinearMetricAmount = () => {
                const startIndex = pageText.indexOf(metricLabel);
                if (startIndex < 0) {
                  return null;
                }
                const excludedIndex = pageText.indexOf(excludedMetricLabel, startIndex + metricLabel.length);
                const tail = excludedIndex > startIndex
                  ? pageText.slice(startIndex + metricLabel.length, excludedIndex)
                  : pageText.slice(startIndex + metricLabel.length, startIndex + metricLabel.length + 80);
                const amountMatch = tail.match(/[¥￥]?\s*([0-9][\d\s,]*(?:\.\d+)?)\s*(万|亿)?/);
                if (!amountMatch) {
                  return null;
                }
                const amountText = normalizeNumberText(amountMatch[1]).replace(/,/g, "");
                const payAmt = parseMoney(amountText);
                if (!Number.isFinite(payAmt)) {
                  return null;
                }
                return {
                  amountText,
                  payAmt,
                  amountCandidateCount: 1,
                  sourceKind: "linear_text",
                };
              };
              const resolveMetricCard = () => {
                const labelNodes = [
                  ...document.querySelectorAll("div, span, p, strong, h1, h2, h3, h4, h5, section, article"),
                ].filter((element) => compactText(element.textContent || "") === normalizedMetricLabel);
                const matchesTargetCard = (element) => {
                  const cardText = displayText(element?.textContent || "");
                  const compactCardText = compactText(cardText);
                  return (
                    compactCardText.includes(normalizedMetricLabel)
                    && !compactCardText.includes(normalizedExcludedMetricLabel)
                  );
                };
                const siblingCandidatesFor = (labelNode) => {
                  const candidates = [];
                  const pushCandidate = (element) => {
                    if (!element) return;
                    if (!(element instanceof Element)) return;
                    if (candidates.includes(element)) return;
                    if (isExcludedText(element.textContent || "")) return;
                    candidates.push(element);
                  };
                  pushCandidate(labelNode.nextElementSibling);
                  pushCandidate(labelNode.parentElement?.nextElementSibling);
                  if (labelNode.parentElement) {
                    for (const child of labelNode.parentElement.children) {
                      if (child === labelNode) continue;
                      if (child.contains(labelNode)) continue;
                      pushCandidate(child);
                    }
                  }
                  const labelContainer = labelNode.parentElement;
                  if (labelContainer?.parentElement) {
                    for (const sibling of labelContainer.parentElement.children) {
                      if (sibling === labelContainer) continue;
                      pushCandidate(sibling);
                    }
                  }
                  return candidates;
                };
                for (const seed of labelNodes) {
                  for (const candidate of siblingCandidatesFor(seed)) {
                    const picked = pickSingleAmount(candidate);
                    if (picked) {
                      return picked;
                    }
                  }
                  let current = seed.parentElement;
                  for (let depth = 0; current && depth < 6; depth += 1, current = current.parentElement) {
                    if (!matchesTargetCard(current)) {
                      continue;
                    }
                    const picked = pickSingleAmount(current);
                    if (picked) {
                      return picked;
                    }
                  }
                }
                const fallbackCards = [
                  ...document.querySelectorAll("div, section, article"),
                ]
                  .filter((element) => matchesTargetCard(element))
                  .sort((left, right) => {
                    const leftLength = displayText(left.textContent || "").length;
                    const rightLength = displayText(right.textContent || "").length;
                    return leftLength - rightLength;
                  });
                for (const current of fallbackCards) {
                  const picked = pickSingleAmount(current);
                  if (picked) {
                    return picked;
                  }
                }
                return {
                  metricRoot: null,
                  amountText: "",
                  amountCandidateCount: 0,
                };
              };
              if (!screenUrl.includes(targetPath)) {
                return {
                  ready: false,
                  reason_code: "screen_target_not_found",
                  message: "当前页还没有进入抖音单店大屏，请先切到 screen/shop/single 后再开启只读。",
                  frame_url: screenUrl,
                  captured_at: capturedAt,
                  update_time: realtimeTiming.latest_response_time,
                  interval_seconds: Number(realtimeTiming.interval_seconds || 0),
                  latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                  latest_response_source: realtimeTiming.latest_response_source,
                  pay_amt: null,
                  source_url: screenUrl,
                  metric_label: metricLabel,
                  platform_key: "抖音",
                };
              }
              const { metricRoot, amountText, amountCandidateCount } = resolveMetricCard();
              const linearMetric = parseLinearMetricAmount();
              if (!metricRoot && !linearMetric) {
                return {
                  ready: false,
                  reason_code: "douyin_screen_root_not_found",
                  message: "当前页还没有进入抖音单店大屏，或“今日用户支付金额”区域尚未渲染完成。",
                  frame_url: screenUrl,
                  captured_at: capturedAt,
                  update_time: realtimeTiming.latest_response_time,
                  interval_seconds: Number(realtimeTiming.interval_seconds || 0),
                  latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                  latest_response_source: realtimeTiming.latest_response_source,
                  pay_amt: null,
                  source_url: screenUrl,
                  metric_label: metricLabel,
                  platform_key: "抖音",
                };
              }
              const payAmt = Number.isFinite(linearMetric?.payAmt) ? linearMetric.payAmt : parseMoney(amountText);
              const resolvedDisplayValue = linearMetric?.amountText || amountText;
              const resolvedCandidateCount = Number(linearMetric?.amountCandidateCount || amountCandidateCount || 0);
              const updateMatch = pageText.match(/数据更新\s*(20\d{2}\/\d{2}\/\d{2}\s+\d{2}:\d{2}:\d{2})/);
              const updateTime = updateMatch ? String(updateMatch[1]) : (realtimeTiming.latest_response_time || "");
              if (!Number.isFinite(payAmt)) {
                return {
                  ready: false,
                  reason_code: "douyin_screen_payamt_missing",
                  message: "抖音单店大屏已打开，但当前还没有读到“今日用户支付金额”。",
                  frame_url: screenUrl,
                  captured_at: capturedAt,
                  update_time: updateTime,
                  interval_seconds: Number(realtimeTiming.interval_seconds || 0),
                  latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                  latest_response_source: realtimeTiming.latest_response_source,
                  pay_amt: null,
                  source_url: screenUrl,
                  display_value: resolvedDisplayValue,
                  amount_candidate_count: resolvedCandidateCount,
                  metric_label: metricLabel,
                  platform_key: "抖音",
                };
              }
              return {
                ready: true,
                reason_code: "",
                message: "",
                frame_url: screenUrl,
                captured_at: capturedAt,
                update_time: updateTime || capturedAt,
                interval_seconds: Number(realtimeTiming.interval_seconds || 0),
                latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                latest_response_source: realtimeTiming.latest_response_source,
                pay_amt: payAmt,
                source_url: screenUrl,
                display_value: resolvedDisplayValue,
                amount_candidate_count: resolvedCandidateCount,
                metric_label: metricLabel,
                platform_key: "抖音",
              };
            }"""
        )

    def _read_dewu_screen_pay_amount(self, target) -> dict[str, object]:
        return target.evaluate(
            r"""() => {
              const capturedAt = new Date().toISOString();
              const screenUrl = window.location.href;
              const targetPath = "stark.dewu.com/main/transaction/adjustment";
              const metricLabel = "今日成交额";
              const normalizeNumberText = (value) => String(value || "")
                .replace(/\s+/g, "")
                .replace(/[^\d,.\-]/g, "");
              const compactText = (value) => String(value || "").replace(/\s+/g, "");
              const displayText = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const escapeRegExp = (value) => String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
              const parseMoney = (value) => {
                const cleaned = normalizeNumberText(value);
                if (!cleaned) return null;
                const parsed = Number(cleaned.replace(/,/g, ""));
                return Number.isFinite(parsed) ? parsed : null;
              };
              const pageText = String(document.body?.innerText || "").replace(/\s+/g, " ").trim();
              const realtimeEntries = performance.getEntriesByType("resource")
                .map((item) => ({
                  name: String(item?.name || ""),
                  initiatorType: String(item?.initiatorType || ""),
                  startTime: Number(item?.startTime || 0),
                  responseEnd: Number(item?.responseEnd || 0),
                }))
                .filter((item) => {
                  if (!item.name || !Number.isFinite(item.startTime) || item.startTime <= 0) {
                    return false;
                  }
                  if (!["fetch", "xmlhttprequest"].includes(item.initiatorType)) {
                    return false;
                  }
                  return item.name.includes("stark.dewu.com");
                });
              const buildTiming = () => {
                const matched = realtimeEntries
                  .map((item) => ({
                    name: item.name,
                    marker: Number.isFinite(item.responseEnd) && item.responseEnd > 0
                      ? item.responseEnd
                      : item.startTime,
                  }))
                  .filter((item) => Number.isFinite(item.marker) && item.marker > 0)
                  .sort((a, b) => a.marker - b.marker);
                if (!matched.length) {
                  return {
                    interval_seconds: 0,
                    latest_response_end_seconds: 0,
                    latest_response_source: "",
                    latest_response_time: "",
                  };
                }
                const last = matched[matched.length - 1];
                let intervalSeconds = 0;
                if (matched.length >= 2) {
                  const prev = [...matched]
                    .reverse()
                    .slice(1)
                    .find((item) => (last.marker - item.marker) >= 1000);
                  if (prev) {
                    const seconds = (last.marker - prev.marker) / 1000;
                    if (Number.isFinite(seconds) && seconds >= 1 && seconds <= 300) {
                      intervalSeconds = Number(seconds.toFixed(3));
                    }
                  }
                }
                const wallClockMs = performance.timeOrigin + last.marker;
                return {
                  interval_seconds: intervalSeconds,
                  latest_response_end_seconds: Number((last.marker / 1000).toFixed(3)),
                  latest_response_source: last.name,
                  latest_response_time: Number.isFinite(wallClockMs) ? new Date(wallClockMs).toISOString() : "",
                };
              };
              const realtimeTiming = buildTiming();
              const normalizedMetricLabel = compactText(metricLabel);
              const parseAmountFromText = (value) => {
                const text = displayText(value || "");
                if (!text) {
                  return "";
                }
                const currencyMatch = text.match(/[¥￥]\s*([\d,]+(?:\.\d+)?)/);
                if (currencyMatch?.[1]) {
                  return String(currencyMatch[1]).trim();
                }
                return "";
              };
              const extractCardValue = (labelNode) => {
                if (!labelNode) {
                  return { amountText: "", amountCandidateCount: 0 };
                }
                const candidates = [];
                const seen = new Set();
                const pushCandidate = (rawText) => {
                  const amountText = parseAmountFromText(rawText);
                  if (!amountText || seen.has(amountText)) {
                    return;
                  }
                  seen.add(amountText);
                  candidates.push(amountText);
                };
                pushCandidate(labelNode.nextElementSibling?.textContent || "");
                if (labelNode.parentElement) {
                  for (const child of labelNode.parentElement.children) {
                    if (child === labelNode) {
                      continue;
                    }
                    pushCandidate(child.textContent || "");
                  }
                }
                let current = labelNode.parentElement;
                const inlinePattern = new RegExp(`${escapeRegExp(metricLabel)}\\s*[¥￥]\\s*([\\d,]+(?:\\.\\d+)?)`);
                for (let depth = 0; current && depth < 4; depth += 1, current = current.parentElement) {
                  const text = displayText(current.textContent || "");
                  const match = text.match(inlinePattern);
                  if (match?.[1]) {
                    pushCandidate(match[1]);
                    break;
                  }
                }
                return {
                  amountText: candidates[0] || "",
                  amountCandidateCount: candidates.length,
                };
              };
              const resolveMetricCard = () => {
                const labelNodes = [...document.querySelectorAll("div, span, p, strong, h1, h2, h3, h4, h5")]
                  .filter((element) => compactText(element.textContent || "") === normalizedMetricLabel);
                for (const node of labelNodes) {
                  const value = extractCardValue(node);
                  if (value.amountText) {
                    return { metricRoot: node.parentElement || node, ...value };
                  }
                }
                const inlinePattern = new RegExp(`${escapeRegExp(metricLabel)}\\s*[¥￥]\\s*([\\d,]+(?:\\.\\d+)?)`);
                const inlineMatch = pageText.match(inlinePattern);
                if (inlineMatch?.[1]) {
                  return { metricRoot: document.body, amountText: String(inlineMatch[1]).trim(), amountCandidateCount: 1 };
                }
                return { metricRoot: null, amountText: "", amountCandidateCount: 0 };
              };
              if (!screenUrl.includes(targetPath)) {
                return {
                  ready: false,
                  reason_code: "screen_target_not_found",
                  message: "当前页还没有进入得物交易看板，请先切到 main/transaction/adjustment?noLayout=1 后再开启只读。",
                  frame_url: screenUrl,
                  captured_at: capturedAt,
                  update_time: realtimeTiming.latest_response_time,
                  interval_seconds: Number(realtimeTiming.interval_seconds || 0),
                  latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                  latest_response_source: realtimeTiming.latest_response_source,
                  pay_amt: null,
                  source_url: screenUrl,
                  metric_label: metricLabel,
                  platform_key: "得物",
                };
              }
              const { metricRoot, amountText, amountCandidateCount } = resolveMetricCard();
              if (!metricRoot) {
                return {
                  ready: false,
                  reason_code: "dewu_screen_root_not_found",
                  message: "当前页还没有进入得物交易看板，或“今日成交额”区域尚未渲染完成。",
                  frame_url: screenUrl,
                  captured_at: capturedAt,
                  update_time: realtimeTiming.latest_response_time,
                  interval_seconds: Number(realtimeTiming.interval_seconds || 0),
                  latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                  latest_response_source: realtimeTiming.latest_response_source,
                  pay_amt: null,
                  source_url: screenUrl,
                  metric_label: metricLabel,
                  platform_key: "得物",
                };
              }
              const payAmt = parseMoney(amountText);
              if (!Number.isFinite(payAmt)) {
                return {
                  ready: false,
                  reason_code: "dewu_screen_payamt_missing",
                  message: "得物交易看板已打开，但当前还没有读到“今日成交额”。",
                  frame_url: screenUrl,
                  captured_at: capturedAt,
                  update_time: realtimeTiming.latest_response_time,
                  interval_seconds: Number(realtimeTiming.interval_seconds || 0),
                  latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                  latest_response_source: realtimeTiming.latest_response_source,
                  pay_amt: null,
                  source_url: screenUrl,
                  display_value: amountText,
                  amount_candidate_count: amountCandidateCount,
                  metric_label: metricLabel,
                  platform_key: "得物",
                };
              }
              return {
                ready: true,
                reason_code: "",
                message: "",
                frame_url: screenUrl,
                captured_at: capturedAt,
                update_time: realtimeTiming.latest_response_time || capturedAt,
                interval_seconds: Number(realtimeTiming.interval_seconds || 0),
                latest_response_end_seconds: realtimeTiming.latest_response_end_seconds,
                latest_response_source: realtimeTiming.latest_response_source,
                pay_amt: payAmt,
                source_url: screenUrl,
                display_value: amountText,
                amount_candidate_count: amountCandidateCount,
                metric_label: metricLabel,
                platform_key: "得物",
              };
            }"""
        )

    def read_screen_pay_amount(self, page_id: str) -> dict[str, object]:
        return self._call("read_screen_pay_amount", lambda: self._read_screen_pay_amount(page_id))

    def _read_screen_pay_amount(self, page_id: str) -> dict[str, object]:
        page, info = self._network_watch_page(page_id)
        platform_key, target = self._resolve_screen_target(page)
        if target is None:
            screen = {
                "ready": False,
                "reason_code": "screen_target_not_found",
                "message": "当前页还没有进入受支持的大屏页，请先在业务页切到目标大屏后再开启只读。",
                "frame_url": "",
                "captured_at": "",
                "update_time": "",
                "interval_seconds": 0,
                "pay_amt": None,
                "pay_amt_wl": None,
                "pay_cnt": None,
                "pay_amt_wl_ratio": None,
                "source_url": "",
                "metric_label": "",
                "platform_key": "",
            }
            return {
                "page": info.__dict__,
                "screen": screen,
                **self._screen_readonly_summary(screen),
            }
        if platform_key == "京东":
            result = self._read_jd_screen_pay_amount(target)
        elif platform_key == "唯品会":
            result = self._read_vip_screen_pay_amount(target)
        elif platform_key == "抖音":
            result = self._read_douyin_screen_pay_amount(target)
        elif platform_key == "得物":
            result = self._read_dewu_screen_pay_amount(target)
        else:
            result = self._read_tmall_screen_pay_amount(target)
        return {
            "page": info.__dict__,
            "screen": result,
            **self._screen_readonly_summary(result),
        }

    @staticmethod
    def _screen_readonly_summary(screen: dict[str, object]) -> dict[str, object]:
        reason_code = str(screen.get("reason_code") or "")
        ready = bool(screen.get("ready"))
        if ready:
            status = "ok"
        elif reason_code in SCREEN_READONLY_WAITING_REASON_CODES:
            status = "readonly_waiting"
        else:
            status = "readonly_failed"
        return {
            "ready": ready,
            "status": status,
            "reason_code": reason_code,
            "message": str(screen.get("message") or ""),
            "pay_amt": screen.get("pay_amt"),
            "captured_at": str(screen.get("captured_at") or ""),
            "update_time": str(screen.get("update_time") or ""),
            "interval_seconds": screen.get("interval_seconds") if screen.get("interval_seconds") is not None else 0,
            "source_url": str(screen.get("source_url") or ""),
            "metric_label": str(screen.get("metric_label") or ""),
            "platform_key": str(screen.get("platform_key") or ""),
            "value_source": "screen_readonly",
        }
