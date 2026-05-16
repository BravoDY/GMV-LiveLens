// ===== 测试看板渲染 — 测试环境专属 =====
// 看板渲染函数在 ../../dashboard-shared.js 中（三个页面共享）
// 此处仅包含 /dashboard-test 页面的独有功能

function renderDataStatusBanner() {
  const bannerEl = document.getElementById("dataStatusBanner");
  if (!bannerEl) return;

  const dashboard = state.snapshot?.public_dashboard || {};
  const isPeriod = dashboard.mode === "period";
  const dataStatus = dashboard.data_status || "";

  if (!isPeriod || !dataStatus || dataStatus === "ok") {
    bannerEl.innerHTML = "";
    bannerEl.style.display = "none";
    return;
  }

  const isError = dataStatus === "query_failed";
  const icon = isError ? "⚠" : "ℹ";
  const message = dashboard.status_message || (isError ? "历史数据查询失败" : "暂无周期数据");
  const bannerClass = isError ? "is-error" : "is-empty";

  bannerEl.innerHTML = `
    <div class="data-status-banner ${bannerClass}">
      <span class="data-status-icon">${icon}</span>
      <span class="data-status-text">${escapeHtml(message)}</span>
    </div>
  `;
  bannerEl.style.display = "block";
}

function renderDashboard() {
  const tasks = liveTasks();
  const model = buildDashboardViewModel(tasks);
  const summary = state.snapshot?.summary || {};
  if (summary && typeof summary === "object") {
    if (summary.total_gmv !== undefined) model.total.gmv = Number(summary.total_gmv || model.total.gmv);
    if (summary.total_target !== undefined) model.total.target = Number(summary.total_target || model.total.target);
    if (summary.yoy !== undefined) model.total.yoy = String(summary.yoy || "--");
    model.total.progress = calcProgress(model.total.gmv, model.total.target);
  }
  
  const snapshotPlatformYoy = {};
  const snapshotShopYoy = {};
  const pd = state.snapshot?.public_dashboard;
  if (pd?.platforms) {
    pd.platforms.forEach(p => { if (p.yoy) snapshotPlatformYoy[p.platform] = p.yoy; });
  }
  if (pd?.shops) {
    pd.shops.forEach(s => { if (s.yoy) snapshotShopYoy[s.companyshop_name || s.shop_name] = s.yoy; });
  }

  const dateRange = pd ? {
    mode: pd.mode,
    cur: pd.mode === "realtime" ? (pd.yoy_date?.cur || "") : (pd.date_range?.start || ""),
    end: pd.mode === "period" ? (pd.date_range?.end || "") : "",
    ly: pd.mode === "realtime" ? (pd.yoy_date?.ly || "") : (pd.to_date_range?.start || ""),
    lyEnd: pd.mode === "period" ? (pd.to_date_range?.end || "") : "",
  } : null;

  renderSummaryGrid(model, snapshotPlatformYoy, dateRange);
  renderStoreGrid(model.stores, model.total.yoy, snapshotShopYoy);
  renderDataStatusBanner();
}
