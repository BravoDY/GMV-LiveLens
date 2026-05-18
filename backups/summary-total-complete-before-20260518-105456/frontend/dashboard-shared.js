// ===== 看板渲染 — 共享模块 =====
// 此文件由 /, /dashboard, /dashboard-test 三个页面共享
// 修改此处 → 三个页面自动同步

const _previousGmvValues = {
  total: undefined,
  platforms: {},
  stores: {}
};

const STATUS_BADGE_MAP = {
  suspect:                 '<span class="card-badge badge-warn">⚠ 异常</span>',
  parse_failed:            '<span class="card-badge badge-bad">识别失败</span>',
  needs_recalibration:     '<span class="card-badge badge-bad">需重标定</span>',
  readonly_waiting:        '<span class="card-badge badge-info">等待大屏</span>',
  readonly_failed:         '<span class="card-badge badge-warn">只读失败</span>',
  edge_debug_unavailable:  '<span class="card-badge badge-muted">未连接</span>',
  edge_debug_disconnected: '<span class="card-badge badge-muted">已断开</span>',
  edge_login_page_bound:   '<span class="card-badge badge-info">等待登录</span>',
  edge_session_not_found:  '<span class="card-badge badge-muted">会话缺失</span>',
  remote_page_not_found:   '<span class="card-badge badge-warn">页签失效</span>',
};

const BRAND_PANEL_LEFT = "大货独立店";
const BRAND_PANEL_RIGHT = "子品牌独立店";
let _beijingClockTimer = null;
let _summaryGridResizeObserver = null;

function formatCurrency(value) {
  return `¥${Math.round(Number(value || 0)).toLocaleString("zh-CN")}`;
}

function formatPercent(value) {
  return String(Math.round(Number(value || 0)));
}

function calcProgress(gmv, target) {
  const safeGmv = Number(gmv || 0);
  const safeTarget = Number(target || 0);

  if (!safeTarget || safeTarget <= 0) {
    return {
      progress: null,
      progressText: "--",
      progressWidth: "0%",
      hasTarget: false
    };
  }

  const pct = (safeGmv / safeTarget) * 100;
  return {
    progress: pct,
    progressText: `${formatPercent(pct)}%`,
    progressWidth: `${Math.min(pct, 100)}%`,
    hasTarget: true
  };
}

function formatTarget(value) {
  const num = Number(value || 0);
  if (!num || num <= 0) return "--";
  return formatCurrency(num);
}

function formatBeijingNow() {
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(new Date());

  const map = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${map.year}-${map.month}-${map.day} ${map.hour}:${map.minute}:${map.second}`;
}

function platformClassName(platform) {
  if (platform === "天猫") return "platform-taobao";
  if (platform === "京东") return "platform-jd";
  if (platform === "得物") return "platform-dewu";
  if (platform === "抖音") return "platform-douyin";
  if (platform === "唯品会") return "platform-vip";
  return "platform-other";
}

function normalizeBrandName(brand) {
  return String(brand || "").trim() === BRAND_PANEL_RIGHT ? BRAND_PANEL_RIGHT : BRAND_PANEL_LEFT;
}

function buildBrandGroups(stores) {
  const groups = {
    [BRAND_PANEL_LEFT]: [],
    [BRAND_PANEL_RIGHT]: [],
  };
  stores.forEach((store) => {
    groups[normalizeBrandName(store.brand)].push(store);
  });
  return groups;
}

function buildDashboardViewModel(tasks) {
  const total = { gmv: 0, target: 0, progress: 0 };
  const platformMap = new Map();
  const stores = [];

  tasks.forEach((task) => {
    if (task.enabled === false) return;

    const gmv = Number(task.last_trusted_value || 0);
    const target = Number(task.target || 0);
    const platform = normalizePlatform(task.platform);
    const brand = normalizeBrandName(task.brand);
    const meta = platformMeta[platform] || { 
      label: platform, 
      icon: platform.charAt(0), 
      color: "var(--color-other)", 
      glow: "rgba(142, 160, 184, 0.22)" 
    };
    
    total.gmv += gmv;
    total.target += target;

    if (!platformMap.has(platform)) {
      platformMap.set(platform, {
        platform,
        label: meta.label,
        icon: meta.icon,
        className: platformClassName(platform),
        gmv: 0,
        target: 0,
        progress: 0
      });
    }
    const pItem = platformMap.get(platform);
    pItem.gmv += gmv;
    pItem.target += target;

    stores.push({
      platform,
      platformLabel: meta.label,
      icon: meta.icon,
      className: platformClassName(platform),
      brand,
      shopName: task.shop_name || "未命名店铺",
      companyshopName: task.companyshop_name || task.shop_name || "未命名店铺",
      gmv,
      target,
      progress: calcProgress(gmv, target),
      updatedAt: fmtTime(task.last_success_at || task.last_sample_at),
      status: task.status,
      valueSourceLabel: valueSourceLabel(taskRuntimeValueSource(task)),
      valueSourceShortLabel: taskRuntimeValueSource(task) === "screen_readonly" ? "只读" : "OCR",
    });
  });

  total.progress = calcProgress(total.gmv, total.target);
  
  if (_previousGmvValues.total !== undefined && _previousGmvValues.total !== total.gmv) {
    total.changed = true;
  }
  _previousGmvValues.total = total.gmv;
  
  const platforms = Array.from(platformMap.values());
  platforms.forEach(p => {
    p.progress = calcProgress(p.gmv, p.target);
    if (_previousGmvValues.platforms[p.platform] !== undefined && _previousGmvValues.platforms[p.platform] !== p.gmv) {
      p.changed = true;
    }
    _previousGmvValues.platforms[p.platform] = p.gmv;
  });
  
  stores.forEach(s => {
    const key = `${s.platform}_${s.shopName}`;
    if (_previousGmvValues.stores[key] !== undefined && _previousGmvValues.stores[key] !== s.gmv) {
      s.changed = true;
    }
    _previousGmvValues.stores[key] = s.gmv;
  });

  const order = platformOrder();
  platforms.sort((a, b) => {
    const ai = order.indexOf(a.platform);
    const bi = order.indexOf(b.platform);
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
  });

  return { total, platforms, stores };
}

function formatDateRangeDisplay(dateRange) {
  if (!dateRange || !dateRange.mode) return "";
  const fmt = (d) => (d || "").replace(/-/g, "/");
  if (dateRange.mode === "realtime") {
    const cur = fmt(dateRange.cur);
    const ly = fmt(dateRange.ly);
    if (!cur || !ly) return "";
    return `[ ${cur} ]   同比   [ ${ly} ]`;
  }
  const cur = fmt(dateRange.cur), end = fmt(dateRange.end), ly = fmt(dateRange.ly), lyEnd = fmt(dateRange.lyEnd);
  if (!cur || !end || !ly || !lyEnd) return "";
  return `[ ${cur} 累计至 ${end} ]   同比   [ ${ly} 累计至 ${lyEnd} ]`;
}

function renderSummaryTimeRow(dateRange) {
  return `
    <div class="summary-time-row">
      <span class="total-card-time-left"><span class="total-card-time-label">北京时间：</span><span class="total-card-time-value" id="beijingTimeValue">${formatBeijingNow()}</span></span>
      <span class="total-card-date-range">${formatDateRangeDisplay(dateRange)}</span>
    </div>
  `;
}

function renderTotalCard(total) {
  const yoy = total.yoy || "--";
  const yoyClass = yoy.startsWith("-") ? " is-down" : (yoy !== "--" ? " is-up" : "");
  return `
    <div class="total-card-shell">
      <article class="total-card${total.changed ? ' is-flashing' : ''}">
        <div class="total-card-title">全渠道实时GMV</div>
        <div class="total-gmv">${formatCurrency(total.gmv)}</div>
        <div class="total-card-bottom">
          <div class="total-metrics">
            <div>
              <div class="metric-label">总目标</div>
              <div class="total-target">${formatTarget(total.target)}</div>
            </div>
            <div style="text-align:right;">
              <div class="metric-label">总达成进度</div>
              <div class="total-progress-value${total.progress.hasTarget && total.progress.progress < 100 ? ' is-below-target' : ''}">${total.progress.progressText}</div>
            </div>
            <div class="total-metrics-sep">│</div>
            <div style="text-align:right;">
              <div class="metric-label">同比</div>
              <div class="total-yoy-value${yoyClass}">${yoy}</div>
            </div>
          </div>
          <div class="total-progress-track">
            <div class="total-progress-fill" style="--progress-width: ${total.progress.progressWidth};"></div>
          </div>
        </div>
      </article>
    </div>
  `;
}

function updateBeijingClock() {
  const timeEl = $("beijingTimeValue");
  if (!timeEl) return;
  timeEl.textContent = formatBeijingNow();
}

function setupDashboardClock() {
  updateBeijingClock();
  if (_beijingClockTimer) return;
  _beijingClockTimer = window.setInterval(updateBeijingClock, 1000);
}

function renderPlatformCard(p, yoyText) {
  const yoy = yoyText || "--";
  const yoyClass = yoy.startsWith("-") ? " is-down" : (yoy !== "--" ? " is-up" : "");
  return `
    <article class="platform-summary-card ${p.className}${p.changed ? ' is-flashing' : ''}">
      <div class="platform-summary-header">
        <span class="platform-summary-icon">${p.icon}</span>
        <span class="platform-summary-name">${escapeHtml(p.platform)}</span>
      </div>
      <div class="platform-current-label">当前GMV</div>
      <div class="platform-gmv">${formatCurrency(p.gmv)}</div>
      <div class="platform-card-bottom">
      <div class="platform-target-row">
        <span class="platform-target-label">目标</span>
        <span class="platform-target-value">${formatTarget(p.target)}</span>
      </div>
      <div class="platform-progress-row">
        <span class="platform-progress-label">达成进度</span>
        <span class="platform-progress-value${p.progress.hasTarget && p.progress.progress < 100 ? ' is-below-target' : ''}">${p.progress.progressText}</span>
      </div>
      <div class="platform-yoy-row">
        <span class="platform-yoy-label">同比</span>
        <span class="platform-yoy-value${yoyClass}">${yoy}</span>
      </div>
      <div class="platform-progress-track">
        <div class="platform-progress-fill ${p.progress.hasTarget ? "" : "is-empty"}" style="width: ${p.progress.progressWidth};"></div>
      </div>
      </div>
    </article>
  `;
}

function updateSummaryCardLayout() {
  const row = document.querySelector(".summary-card-row");
  if (!row) return;

  const gap = 14;
  const minPlatformWidth = 214;
  const minSingleLineWidth = 188;
  const platformCount = row.querySelectorAll(".platform-summary-card").length;
  const singleLineColumns = Math.max(2, platformCount + 1);
  const width = row.getBoundingClientRect().width;
  const canSingleLine = width >= (singleLineColumns * minSingleLineWidth) + ((singleLineColumns - 1) * gap);

  if (canSingleLine) {
    row.dataset.layout = "single-line";
    row.style.setProperty("--summary-columns", String(singleLineColumns));
    row.style.setProperty("--total-span", "1");
    return;
  }

  const rawColumns = Math.floor((width + gap) / (minPlatformWidth + gap));
  const columns = Math.max(2, Math.min(5, rawColumns || 2));

  row.dataset.layout = "stacked";
  row.style.setProperty("--summary-columns", String(columns));
  row.style.setProperty("--total-span", String(columns));
}

function bindSummaryCardLayoutObserver() {
  const row = document.querySelector(".summary-card-row");
  if (!row) return;
  updateSummaryCardLayout();

  if (typeof ResizeObserver === "undefined") return;
  if (_summaryGridResizeObserver) _summaryGridResizeObserver.disconnect();
  _summaryGridResizeObserver = new ResizeObserver(updateSummaryCardLayout);
  _summaryGridResizeObserver.observe(row);
}

function renderSummaryGrid(model, platformYoy, dateRange) {
  const yoy = model.total.yoy || "--";
  const pyoy = platformYoy || {};
  const cardsHtml = model.platforms.map(p => renderPlatformCard(p, pyoy[p.platform] || yoy)).join("");
  $("summaryGrid").innerHTML = `
    ${renderSummaryTimeRow(dateRange)}
    <div class="summary-card-row">
      ${renderTotalCard(model.total)}
      <div class="platform-summary-grid">
        ${cardsHtml}
      </div>
    </div>
  `;
  bindSummaryCardLayoutObserver();
}

function renderStoreCard(store, yoyText) {
  const isAlert = store.status && !["ok", "pending_confirm"].includes(store.status);
  const alertClass = isAlert ? " is-alert" : "";
  const badge = STATUS_BADGE_MAP[store.status] || "";
  const yoy = yoyText || "--";
  const yoyClass = yoy.startsWith("-") ? " is-down" : (yoy !== "--" ? " is-up" : "");

  return `
    <article class="store-card ${store.className}${alertClass}${store.changed ? ' is-flashing' : ''}">
      <div class="top-bloom"></div>
      <div class="store-card-header">
        <div class="store-title-wrap">
          <span class="platform-badge ${store.className}">${escapeHtml(store.platformLabel)}</span>
          <span class="store-name" title="${escapeHtml(store.shopName)}">${escapeHtml(store.shopName)}</span>
          <span class="store-status-tags">
            <span class="store-chip">${escapeHtml(store.valueSourceShortLabel)}</span>
            ${badge}
          </span>
        </div>
      </div>
      <div class="store-gmv">${formatCurrency(store.gmv)}</div>
      <div class="store-card-bottom">
        <div class="store-metrics">
          <div>
            <div class="store-metric-label">目标</div>
            <div class="store-metric-value">${formatTarget(store.target)}</div>
          </div>
          <div style="text-align:right;">
            <div class="store-metric-label">达成进度</div>
            <div class="store-metric-value${store.progress.hasTarget && store.progress.progress < 100 ? ' is-below-target' : ''}">${store.progress.progressText}</div>
          </div>
          <div class="store-metrics-sep">│</div>
          <div style="text-align:right;">
            <div class="store-metric-label">同比</div>
            <div class="store-metric-value${yoyClass}">${yoy}</div>
          </div>
        </div>
        <div class="progress-track">
          <div class="progress-fill ${store.progress.hasTarget ? "" : "is-empty"}" style="width: ${store.progress.progressWidth};"></div>
        </div>
      </div>
    </article>
  `;
}

function renderBrandPanel(brand, stores, yoy, resolveYoy) {
  const panelClass = brand === BRAND_PANEL_RIGHT ? "brand-panel-sub" : "brand-panel-main";
  const iconClass = brand === BRAND_PANEL_RIGHT ? "brand-panel-icon-sub" : "brand-panel-icon-main";
  const iconText = brand === BRAND_PANEL_RIGHT ? "◆" : "▣";
  const resolve = resolveYoy || ((s) => yoy || "--");
  const storesHtml = stores.map(s => renderStoreCard(s, resolve(s))).join("");

  return `
    <section class="brand-panel ${panelClass}">
      <div class="brand-panel-header">
        <div class="brand-panel-title-wrap">
          <span class="brand-panel-icon ${iconClass}">${iconText}</span>
          <h2 class="brand-panel-title">${escapeHtml(brand)}</h2>
        </div>
      </div>
      <div class="brand-store-grid">
        ${storesHtml || '<div class="brand-panel-empty">当前分组暂无店铺</div>'}
      </div>
    </section>
  `;
}

function renderStoreGrid(stores, yoy, shopYoy) {
  const groups = buildBrandGroups(stores);
  const syoy = shopYoy || {};
  const resolveYoy = (store) => syoy[store.companyshopName] || yoy || "--";
  $("storeGrid").innerHTML = `
    <div class="brand-area-layout">
      ${renderBrandPanel(BRAND_PANEL_LEFT, groups[BRAND_PANEL_LEFT], yoy, resolveYoy)}
      ${renderBrandPanel(BRAND_PANEL_RIGHT, groups[BRAND_PANEL_RIGHT], yoy, resolveYoy)}
    </div>
  `;
}

function liveTasks() {
  return Array.isArray(state.snapshot?.tasks) ? state.snapshot.tasks : [];
}

function tasksFromPublicDashboardPayload(payload) {
  const dashboard = payload?.data || payload || {};
  const shops = Array.isArray(dashboard.shops) ? dashboard.shops : [];
  return shops.map((shop, index) => ({
    id: shop.task_id || index + 1,
    enabled: true,
    platform: shop.platform || "其他平台",
    brand: shop.brand || "",
    shop_name: shop.shop_name || "未命名店铺",
    companyshop_name: shop.companyshop_name || shop.shop_name || "未命名店铺",
    last_trusted_value: Number(shop.gmv || 0),
    target: Number(shop.target || 0),
    last_success_at: shop.updated_at || dashboard.generated_at || "",
    last_sample_at: shop.updated_at || dashboard.generated_at || "",
    status: shop.status || "ok",
    value_source: shop.value_source || "ocr",
    last_value_source: shop.value_source || "ocr",
  }));
}

function normalizePublicDashboardSnapshot(payload) {
  const dashboard = payload?.data || payload || {};
  return {
    type: "snapshot",
    updated_at: dashboard.generated_at || new Date().toISOString(),
    summary: dashboard.summary || {},
    tasks: tasksFromPublicDashboardPayload(payload),
    public_dashboard: dashboard,
  };
}

function renderSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    state.snapshot = { tasks: [], summary: {} };
  } else {
    state.snapshot = {
      ...snapshot,
      tasks: Array.isArray(snapshot.tasks) ? snapshot.tasks : [],
      summary: snapshot.summary && typeof snapshot.summary === "object" ? snapshot.summary : {},
    };
  }
  renderDashboard();
}
