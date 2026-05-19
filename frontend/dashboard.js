// ===== 任务管理面板 — 正式环境专属 =====
// 看板渲染函数在 dashboard-shared.js 中（三个页面共享）
// 此处仅包含 / 页面的独有功能

function renderManagerGrid(tasks) {
  const allTasks = Array.isArray(tasks) ? tasks : [];
  const activeFilter = managerState.filter || "all";

  const filtered = activeFilter === "all"
    ? allTasks
    : activeFilter === "ok"
      ? allTasks.filter((t) => t.status === "ok")
      : activeFilter === "paused"
        ? allTasks.filter((t) => t.status === "paused")
        : allTasks.filter((t) => t.status !== "ok" && t.status !== "paused");

  const byPlatform = new Map();
  filtered.forEach((task) => {
    const platform = task.platform || "未分类";
    if (!byPlatform.has(platform)) {
      byPlatform.set(platform, []);
    }
    byPlatform.get(platform).push(task);
  });

  const sortedPlatforms = [...byPlatform.keys()];

  const statusLabelMap = {
    ok: "正常",
    suspect: "异常",
    parse_failed: "识别失败",
    needs_recalibration: "需重标定",
    paused: "已暂停",
    readonly_failed: "只读失败",
    edge_debug_unavailable: "未连接",
    edge_debug_disconnected: "已断开",
    edge_login_page_bound: "等待登录",
    edge_session_not_found: "会话缺失",
    remote_page_not_found: "页签失效",
    pending_confirm: "待确认",
    window_not_found: "窗口未找到",
    page_not_found: "页签未找到",
  };

  function statusTone(status) {
    const s = String(status || "").replace(/-/g, "_");
    if (s === "ok") return "tone-ok";
    if (s === "readonly_no_new_data") return "tone-neutral";
    if (s === "paused") return "tone-neutral";
    if (s === "pending_confirm") return "tone-pending";
    if (s === "ok" || s === "paused") return "tone-neutral";
    return "tone-bad";
  }

  function cardStatusClass(status) {
    const s = String(status || "").replace(/-/g, "_");
    if (s === "ok") return "status-ok";
    if (s === "readonly_no_new_data") return "status-ok";
    if (s === "paused") return "is-paused";
    return "status-suspect";
  }

  let html = "";

  sortedPlatforms.forEach((platform) => {
    const tasksInPlatform = byPlatform.get(platform) || [];
    html += `<section class="manager-platform-section">
      <div class="manager-platform-head">
        <div class="manager-platform-title">
          <h3>${escapeHtml(platform)}</h3>
          <span class="manager-platform-count">${tasksInPlatform.length} 个任务</span>
        </div>
        <div class="manager-platform-actions">
          <button class="manager-action-btn" type="button" data-platform-action="launch" data-platform="${escapeHtml(platform)}">启动 Edge</button>
          <button class="manager-action-btn" type="button" data-platform-action="show" data-platform="${escapeHtml(platform)}">显示</button>
          <button class="manager-action-btn" type="button" data-platform-action="hide" data-platform="${escapeHtml(platform)}">隐藏</button>
          <button class="manager-action-btn manager-action-btn-danger" type="button" data-platform-action="close" data-platform="${escapeHtml(platform)}">关闭</button>
        </div>
      </div>
      <div class="manager-platform-row">`;

    tasksInPlatform.forEach((task) => {
      const gmv = Number(task.last_trusted_value || 0);
      const target = Number(task.target || 0);
      const progress = calcProgress(gmv, target);
      const time = task.last_sample_at || task.last_success_at || "";
      const timeStr = time ? new Date(time).toLocaleTimeString("zh-CN", { hour12: false }) : "--";
      const sessionId = task.edge_session_id || "";
      const statusKey = String(task.status || "").replace(/-/g, "_");
      const hiddenStatusLabels = new Set(["readonly_waiting", "readonly_no_new_data"]);
      const label = hiddenStatusLabels.has(statusKey) ? "" : (statusLabelMap[statusKey] || task.status || "未知");
      const statusHtml = label
        ? `<span class="status ${statusTone(task.status)}">${escapeHtml(label)}</span>`
        : "";

      html += `
      <div class="manager-card card-bg ${cardStatusClass(task.status)}" data-task-id="${task.id || ""}" data-editable="true">
        <div class="task-title">${escapeHtml(task.shop_name || "未命名")}</div>
        <div class="manager-value">${formatCurrency(gmv)}</div>
        ${progress.hasTarget ? `<div style="color:var(--muted);font-size:12px;margin:4px 0 0;">目标 ${formatCurrency(target)} · ${progress.progressText}</div>` : ""}
        <div class="task-badges" style="margin-top:10px;align-items:flex-start;">
          ${statusHtml}
          <span style="color:var(--muted);font-size:11px;">${escapeHtml(task.platform || "")} · ${escapeHtml(task.brand || "")} · ${timeStr}</span>
        </div>`;

      if (sessionId) {
        html += `
        <div class="task-actions">
          <button class="edge-button-start" type="button" data-task-edge="start" data-session="${escapeHtml(sessionId)}">启动 Edge</button>
          <button class="edge-button-show" type="button" data-task-edge="show" data-session="${escapeHtml(sessionId)}">显示</button>
          <button class="edge-button-hide" type="button" data-task-edge="hide" data-session="${escapeHtml(sessionId)}">隐藏</button>
          <button class="edge-button-close" type="button" data-task-edge="close" data-session="${escapeHtml(sessionId)}">关闭</button>
        </div>`;
      }

      html += `
      </div>`;
    });

    html += `</div></section>`;
  });

  if (!filtered.length) {
    html = '<div class="brand-panel-empty">暂无匹配的任务</div>';
  }

  return html;
}

const managerState = {
  filter: "all",
};

function bindManagerFilters() {
  const container = $("statusFilters");
  if (!container || container.dataset.bound === "1") return;
  container.dataset.bound = "1";
  container.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      container.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      managerState.filter = chip.dataset.status || "all";
      if ($("managerGrid")) {
        $("managerGrid").innerHTML = renderManagerGrid(liveTasks());
        bindManagerCardClicks();
        bindManagerActionButtons();
        bindTaskEdgeButtons();
      }
    });
  });
}

function bindManagerActionButtons() {
  const el = $("managerGrid");
  if (!el || el.dataset.actionBound === "1") return;
  el.dataset.actionBound = "1";
  el.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-platform-action]");
    if (!btn) return;
    const platform = btn.dataset.platform;
    const action = btn.dataset.platformAction;
    if (!platform || !action) return;

    const actionLabels = { launch: "启动 Edge", show: "显示", hide: "隐藏", close: "关闭" };
    const label = actionLabels[action] || action;
    btn.disabled = true;
    btn.textContent = "处理中...";
    try {
      await callPlatformEdgeAction(platform, action);
      setTimeout(() => {
        if ($("managerGrid")) {
          $("managerGrid").innerHTML = renderManagerGrid(liveTasks());
          bindManagerCardClicks();
          bindManagerActionButtons();
          bindTaskEdgeButtons();
        }
      }, 1500);
    } catch (err) {
      // #region agent log
      fetch('http://127.0.0.1:7322/ingest/74902c04-2c86-447b-b11e-113b7ea87782',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'4e09f7'},body:JSON.stringify({sessionId:'4e09f7',runId:'pre-fix',hypothesisId:'H1,H4',location:'frontend/dashboard.js:bindManagerActionButtons:catch',message:'platform edge action failed before user-visible feedback',data:{platform,action,label,errorMessage:String(err?.message||''),hasShowMessage:typeof showMessage==='function',activeView:document.querySelector('.view.active')?.id||'',configMessageVisible:Boolean(document.getElementById('configMessage')?.offsetParent)},timestamp:Date.now()})}).catch(()=>{});
      // #endregion
      const detail = parseApiErrorPayload(err);
      const errorMsg = detail?.error || detail?.detail?.error || parseApiError(err) || `平台操作失败: ${label}`;
      showMessage(errorMsg, true);
      console.error(`平台操作失败: ${label}`, err);
    } finally {
      btn.disabled = false;
      btn.textContent = label;
    }
  });
}

function bindTaskEdgeButtons() {
  const el = $("managerGrid");
  if (!el || el.dataset.taskEdgeBound === "1") return;
  el.dataset.taskEdgeBound = "1";
  el.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-task-edge]");
    if (!btn) return;
    const action = btn.dataset.taskEdge;
    const sessionId = btn.dataset.session;
    if (!sessionId) return;

    const actionLabels = { start: "启动 Edge", show: "显示", hide: "隐藏", close: "关闭" };
    const progressLabels = { start: "启动中...", show: "显示中...", hide: "隐藏中...", close: "关闭中..." };
    const label = actionLabels[action] || action;
    const progressLabel = progressLabels[action] || "处理中...";
    btn.disabled = true;
    btn.textContent = progressLabel;
    try {
      if (action === "start") {
        await startAndShowEdgeSession(sessionId);
      } else if (action === "show") {
        await showEdgeSession(sessionId);
      } else if (action === "hide") {
        await hideEdgeSession(sessionId);
      } else if (action === "close") {
        await closeEdgeSession(sessionId);
      }
      setTimeout(() => {
        if ($("managerGrid")) {
          $("managerGrid").innerHTML = renderManagerGrid(liveTasks());
          bindManagerCardClicks();
          bindManagerActionButtons();
          bindTaskEdgeButtons();
        }
      }, 1500);
    } catch (err) {
      const detail = parseApiErrorPayload(err);
      const errorMsg = detail?.error || `Edge操作失败: ${label}`;
      showMessage(errorMsg, true);
      console.error(`Edge操作失败: ${label}`, err);
    } finally {
      btn.disabled = false;
      btn.textContent = label;
    }
  });
}

function renderDashboard() {
  const rawTasks = liveTasks();
  const tasks = (state.shopConfigs && state.shopConfigs.length) ? sortByConfiguredOrder(rawTasks) : rawTasks;
  const model = buildDashboardViewModel(tasks);
  const summary = state.snapshot?.summary || {};
  if (summary && typeof summary === "object") {
    if (summary.total_gmv !== undefined) model.total.gmv = Number(summary.total_gmv || model.total.gmv);
    if (summary.total_target !== undefined) model.total.target = Number(summary.total_target || model.total.target);
    if (summary.yoy !== undefined) model.total.yoy = String(summary.yoy || "--");
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
  if ($("managerGrid")) {
    $("managerGrid").innerHTML = renderManagerGrid(liveTasks());
    bindManagerCardClicks();
    bindManagerActionButtons();
    bindTaskEdgeButtons();
  }
  bindManagerFilters();
}

function bindManagerCardClicks() {
  const el = $("managerGrid");
  if (!el || el.dataset.cardClicksBound === "1") return;
  el.dataset.cardClicksBound = "1";
  el.addEventListener("click", (e) => {
    if (e.target.closest("[data-task-edge]")) return;
    if (e.target.closest("[data-platform-action]")) return;
    if (e.target.closest("button")) return;
    const card = e.target.closest("[data-editable]");
    if (!card) return;
    const taskId = parseInt(card.dataset.taskId, 10);
    if (!taskId) return;
    const task = liveTasks().find((t) => t.id === taskId);
    if (task && typeof loadTaskIntoConfig === "function") {
      loadTaskIntoConfig(task);
      if (typeof switchView === "function") {
        switchView("config");
      }
    }
  });
}
