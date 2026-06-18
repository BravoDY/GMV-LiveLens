// ===== Shared public dashboard dataset navigation and polling =====

const PUBLIC_DASHBOARD_REFRESH_MS = 1200;
const PUBLIC_DASHBOARD_DATASET_KEY = "gmv_public_dashboard_dataset_id";

const publicDashboardState = {
  datasetId: "realtime",
  datasets: [],
  loading: false,
  requestSeq: 0,
  pollingTimer: null,
  lastUpdatedAt: "-",
};

window.__DASHBOARD_DATASET_ID__ = "realtime";

function publicDashboardItems() {
  return Array.isArray(publicDashboardState.datasets) ? publicDashboardState.datasets : [];
}

function getStoredPublicDatasetId() {
  try {
    return window.localStorage.getItem(PUBLIC_DASHBOARD_DATASET_KEY) || "";
  } catch (_) {
    return "";
  }
}

function setStoredPublicDatasetId(datasetId) {
  try {
    window.localStorage.setItem(PUBLIC_DASHBOARD_DATASET_KEY, datasetId);
  } catch (_) {
    // ignore storage errors in private mode
  }
}

function resolvePublicDatasetId(candidate) {
  const datasets = publicDashboardItems();
  if (!datasets.length) return "realtime";
  const match = datasets.find((item) => item.dataset_id === candidate);
  if (match) return match.dataset_id;
  const realtime = datasets.find((item) => item.dataset_id === "realtime");
  if (realtime) return realtime.dataset_id;
  return datasets[0].dataset_id;
}

function setPublicDatasetId(datasetId, { persist = true } = {}) {
  const resolved = resolvePublicDatasetId(datasetId);
  const changed = publicDashboardState.datasetId !== resolved;
  publicDashboardState.datasetId = resolved;
  window.__DASHBOARD_DATASET_ID__ = resolved;
  if (persist) setStoredPublicDatasetId(resolved);
  return { datasetId: resolved, changed };
}

function setPublicDashboardStatus(text, tone = "ok") {
  if (typeof setWsStatus === "function") {
    setWsStatus(text, tone);
  }
}

function formatPublicDashboardUpdatedAt(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleTimeString("zh-CN", { hour12: false });
}

function setPublicNavLoading(isLoading) {
  publicDashboardState.loading = Boolean(isLoading);
  const nav = document.querySelector("#testDatasetNav");
  if (nav) {
    nav.classList.toggle("is-loading", publicDashboardState.loading);
    nav.setAttribute("aria-busy", publicDashboardState.loading ? "true" : "false");
  }
  document.querySelectorAll(".test-dataset-chip").forEach((node) => {
    node.disabled = publicDashboardState.loading;
    node.classList.toggle("is-disabled", publicDashboardState.loading);
  });
}

function renderPublicDatasetNav() {
  const nav = document.querySelector("#testDatasetNav");
  if (!nav) return;
  nav.innerHTML = "";
  const datasets = publicDashboardItems();
  if (!datasets.length) {
    nav.innerHTML = '<div class="test-dataset-empty">暂无可用导航</div>';
    return;
  }
  datasets.forEach((item) => nav.appendChild(createPublicDatasetButton(item)));
}

function createPublicDatasetButton(item) {
  const button = document.createElement("button");
  button.className = `test-dataset-chip${item.dataset_id === publicDashboardState.datasetId ? " is-active" : ""}`;
  button.type = "button";
  button.textContent = item.title || item.chinese_product || "未命名";
  button.dataset.datasetId = item.dataset_id;
  button.addEventListener("click", async () => {
    if (publicDashboardState.loading || item.dataset_id === publicDashboardState.datasetId) return;
    const previous = publicDashboardState.datasetId;
    setPublicDatasetId(item.dataset_id);
    renderPublicDatasetNav();
    setPublicNavLoading(true);
    try {
      await loadSharedDashboard({ syncSelectedFromPayload: true });
    } catch (error) {
      console.error("Dataset switch failed", error);
      setPublicDatasetId(previous);
      renderPublicDatasetNav();
      setPublicDashboardStatus("看板切换失败", "bad");
    } finally {
      setPublicNavLoading(false);
    }
  });
  return button;
}

async function loadSharedDashboardDatasets() {
  const nav = document.querySelector("#testDatasetNav");
  if (nav) nav.innerHTML = '<div class="test-dataset-empty">正在加载导航...</div>';
  const payload = await api("/api/dashboard-datasets");
  publicDashboardState.datasets = Array.isArray(payload?.data?.datasets) ? payload.data.datasets : [];
  const preferred = getStoredPublicDatasetId() || publicDashboardState.datasetId || "realtime";
  setPublicDatasetId(preferred, { persist: Boolean(getStoredPublicDatasetId()) });
  renderPublicDatasetNav();
  return publicDashboardState.datasets;
}

function renderPublicDashboardPayload(payload, { preserveLocalSnapshot = false } = {}) {
  if (!preserveLocalSnapshot) {
    renderSnapshot(normalizePublicDashboardSnapshot(payload));
    return;
  }
  const dashboard = payload?.data || payload || {};
  const tasks = tasksFromPublicDashboardPayload(payload);
  const model = buildDashboardViewModel(tasks);
  const summary = dashboard.summary || {};
  if (summary && typeof summary === "object") {
    if (summary.total_gmv !== undefined) model.total.gmv = Number(summary.total_gmv || model.total.gmv);
    if (summary.total_target !== undefined) model.total.target = Number(summary.total_target || model.total.target);
    if (summary.yoy !== undefined) model.total.yoy = String(summary.yoy || "--");
    model.total.progress = calcProgress(model.total.gmv, model.total.target);
  }
  const platformYoy = {};
  const shopYoy = {};
  if (Array.isArray(dashboard.platforms)) {
    dashboard.platforms.forEach((p) => { if (p.yoy) platformYoy[p.platform] = p.yoy; });
  }
  if (Array.isArray(dashboard.shops)) {
    dashboard.shops.forEach((s) => { if (s.yoy) shopYoy[s.companyshop_name || s.shop_name] = s.yoy; });
  }
  const dateRange = {
    mode: dashboard.mode,
    cur: dashboard.mode === "realtime" ? (dashboard.yoy_date?.cur || "") : (dashboard.date_range?.start || ""),
    end: dashboard.mode === "period" ? (dashboard.date_range?.end || "") : "",
    ly: dashboard.mode === "realtime" ? (dashboard.yoy_date?.ly || "") : (dashboard.to_date_range?.start || ""),
    lyEnd: dashboard.mode === "period" ? (dashboard.to_date_range?.end || "") : "",
  };
  renderSummaryGrid(model, platformYoy, dateRange);
  renderStoreGrid(model.stores, model.total.yoy, shopYoy);
  if (typeof renderDataStatusBanner === "function") renderDataStatusBanner();
  state.dashboardSnapshot = {
    type: "snapshot",
    updated_at: dashboard.generated_at || new Date().toISOString(),
    summary,
    tasks,
    public_dashboard: dashboard,
  };
}

async function loadSharedDashboard(options = {}) {
  const { syncSelectedFromPayload = false, preserveLocalSnapshot = false } = options;
  const requestId = ++publicDashboardState.requestSeq;
  const datasetId = publicDashboardState.datasetId || "realtime";
  const payload = await api(`/api/dashboard?dataset_id=${encodeURIComponent(datasetId)}`);
  if (requestId !== publicDashboardState.requestSeq) return payload;

  renderPublicDashboardPayload(payload, { preserveLocalSnapshot });
  const dashboard = payload?.data || {};
  if (syncSelectedFromPayload) {
    const selection = setPublicDatasetId(dashboard.selected_dataset_id || datasetId);
    if (selection.changed) renderPublicDatasetNav();
  }
  const updatedAt = formatPublicDashboardUpdatedAt(dashboard.generated_at || payload?.timestamp);
  publicDashboardState.lastUpdatedAt = updatedAt;
  setPublicDashboardStatus("实时连接");
  return payload;
}

function startSharedDashboardPolling(options = {}) {
  const { preserveLocalSnapshot = false } = options;
  const poll = async () => {
    try {
      await loadSharedDashboard({ syncSelectedFromPayload: true, preserveLocalSnapshot });
    } catch (error) {
      console.error("Dashboard refresh failed", error);
      setPublicDashboardStatus("连接异常", "bad");
    }
  };
  poll();
  if (publicDashboardState.pollingTimer) return;
  publicDashboardState.pollingTimer = window.setInterval(poll, PUBLIC_DASHBOARD_REFRESH_MS);
}

function applyPublicDashboardMode() {
  document.body.classList.add("public-dashboard-mode");
  document.querySelectorAll(".header-nav, #config, #manager").forEach((el) => {
    if (el) el.style.display = "none";
  });
  const refreshCacheBtn = document.querySelector("#refreshCacheBtn");
  if (refreshCacheBtn) {
    refreshCacheBtn.dataset.publicReadonly = "1";
    refreshCacheBtn.disabled = true;
    refreshCacheBtn.style.display = "none";
  }
  document.querySelectorAll("#captureAllButton, #schedulerToggle, #debugPanelToggle, #debugStatusPanel").forEach((el) => {
    if (el) el.style.display = "none";
  });
  document.querySelectorAll(".control-group").forEach((el) => {
    el.style.display = "none";
  });
  const dashboardView = $("dashboard");
  if (dashboardView) dashboardView.classList.add("active");
}

function bindSharedRefreshButton(options = {}) {
  const btn = document.querySelector("#refreshCacheBtn");
  if (!btn || btn.dataset.sharedRefreshBound === "1" || btn.dataset.publicReadonly === "1") return;
  btn.dataset.sharedRefreshBound = "1";
  btn.addEventListener("click", async () => {
    if (btn.disabled) return;
    btn.disabled = true;
    btn.classList.add("is-refreshing");
    btn.textContent = "刷新中...";
    try {
      await api("/api/dashboard-cache/refresh", { method: "POST", cache: "no-store" });
      await loadSharedDashboard({ syncSelectedFromPayload: true, preserveLocalSnapshot: Boolean(options.preserveLocalSnapshot) });
      setPublicDashboardStatus("周期数据缓存刷新完成");
    } catch (error) {
      console.error("Dashboard cache refresh failed", error);
      const detail = parseApiError(error);
      const forbidden = String(detail || "").includes("403") || String(detail || "").toLowerCase().includes("forbidden");
      const hint = forbidden
        ? "公网看板为只读入口，请在本机管理员页面刷新周期缓存"
        : (detail || "请确认 API Token 与部署入口权限");
      setPublicDashboardStatus(`周期数据缓存刷新失败：${hint}`, "bad");
    } finally {
      btn.disabled = false;
      btn.classList.remove("is-refreshing");
      btn.textContent = "刷新数据";
    }
  });
}

async function startSharedPublicDashboard(options = {}) {
  const { publicMode = true, preserveLocalSnapshot = false } = options;
  if (publicMode) applyPublicDashboardMode();
  bindSharedRefreshButton({ preserveLocalSnapshot });
  setPublicNavLoading(true);
  try {
    await loadSharedDashboardDatasets();
    await loadSharedDashboard({ syncSelectedFromPayload: true, preserveLocalSnapshot });
    startSharedDashboardPolling({ preserveLocalSnapshot });
  } finally {
    setPublicNavLoading(false);
  }
}
