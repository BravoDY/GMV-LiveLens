// ===== Edge 会话 UI 管理 =====

function selectedEdgeSessionId() {
  return $("bindSessionSelect")?.value || currentSetupTask()?.edge_session_id || state.lastBindSessionId || "default_real_edge";
}

function selectedEdgeSession() {
  const sessionId = selectedEdgeSessionId();
  return state.edgeSessions.find((item) => item.session_id === sessionId) || null;
}

function edgeSessionModeMeta(session) {
  const mode = session?.session_mode === "real_profile" ? "real_profile" : "isolated";
  if (mode === "real_profile") {
    return {
      mode,
      label: "真实个人环境",
      short: "真实",
      hint: "尽量贴近日常 Edge 登录态，但不适合多账号并行；启动前需要关闭普通 Edge。",
    };
  }
  return {
    mode,
    label: "独立店铺环境",
    short: "独立",
    hint: "每个店铺/账号固定一个会话，首次手动登录一次，后续长期复用；不要混用账号。",
  };
}

function edgeBindingSourceMeta(session = {}) {
  const source = String(session?.binding_source || "").trim();
  const detail = String(session?.binding_source_detail || "").trim();
  const labels = {
    default_real_profile: "默认真实 Profile",
    shop_config_session: "店铺配置直绑",
    shop_config_identity: "店铺身份命中",
    manual: "手动/历史会话",
  };
  return {
    code: source || "manual",
    label: labels[source] || "手动/历史会话",
    detail: detail || "当前会话未命中店铺配置，按手动创建或历史保留会话处理。",
  };
}

function edgeSessionHealthSnapshot(session = {}) {
  return session?.health && typeof session.health === "object" ? session.health : {};
}

function formatEdgePath(value, fallback = "-") {
  const text = String(value || "").trim();
  return text || fallback;
}

function extractEdgeProfileArgs(command = "") {
  const text = String(command || "").trim();
  const pick = (pattern) => {
    const match = text.match(pattern);
    return String(match?.[1] || match?.[2] || "").trim();
  };
  return {
    command: text,
    userDataDir: pick(/--user-data-dir=(?:"([^"]+)"|([^\s"]+))/i),
    profileDirectory: pick(/--profile-directory=(?:"([^"]+)"|([^\s"]+))/i),
    debugPort: pick(/--remote-debugging-port=(\d+)/i),
  };
}

function formatProfileLastModified(value) {
  const timestamp = Number(value);
  if (!Number.isFinite(timestamp) || timestamp <= 0) return "-";
  return new Date(timestamp * 1000).toLocaleString("zh-CN", { hour12: false });
}

function formatProfileDiagnostics(diagnostics = {}) {
  if (diagnostics.session_mode === "real_profile") {
    return "系统默认真实 Profile（不扫描项目独立资料目录）";
  }
  const exists = diagnostics.exists ? "存在" : "不存在";
  const entryCount = diagnostics.entry_count ?? 0;
  const cookieCount = Array.isArray(diagnostics.cookie_files) ? diagnostics.cookie_files.length : 0;
  const lastModified = formatProfileLastModified(diagnostics.last_modified);
  return `目录${exists} / 条目${entryCount} / Cookie相关文件${cookieCount} / 最近写入${lastModified}`;
}

function formatRuntimeDiagnostics(health = {}) {
  const windowFound = health.window_diagnostics?.window_found ? "有窗口" : "无窗口";
  const running = health.is_window_op_running ? "窗口动作执行中" : "窗口空闲";
  const stale = health.is_stale ? `会话陈旧(${health.stale_reason || "unknown"})` : "会话正常";
  return `${windowFound} / ${running} / ${stale}`;
}

function edgeDirDiffMeta(session = {}, health = edgeSessionHealthSnapshot(session)) {
  const expected = String(session?.expected_user_data_dir || "").trim();
  const actual = String(health?.user_data_dir || session?.user_data_dir || "").trim();
  const differs = Boolean(session?.user_data_dir_differs);
  const detail = String(session?.user_data_dir_diff_detail || "").trim()
    || (differs ? "当前资料目录与诊断期望目录不一致。" : "当前资料目录与诊断期望目录一致。");
  return {
    differs,
    label: differs ? "不一致" : "一致",
    detail,
    expected,
    actual,
  };
}

function edgeActualProfileMeta(session = {}, health = edgeSessionHealthSnapshot(session)) {
  const windowDiagnostics = health?.window_diagnostics || {};
  const runtimeCommand = Array.isArray(windowDiagnostics.candidate_commands) && windowDiagnostics.candidate_commands.length
    ? String(windowDiagnostics.candidate_commands[0] || "")
    : String(health?.edge_command || "");
  const runtimeArgs = extractEdgeProfileArgs(runtimeCommand);
  const profileDiagnostics = health?.profile_diagnostics || {};
  const sessionMode = String(health?.session_mode || session?.session_mode || "").trim() === "real_profile"
    ? "real_profile"
    : "isolated";
  const actualPath = String(profileDiagnostics.profile_path || health?.user_data_dir || session?.user_data_dir || "").trim();
  const pidCount = Array.isArray(windowDiagnostics.candidate_pids) ? windowDiagnostics.candidate_pids.length : 0;
  const windowCount = Array.isArray(windowDiagnostics.candidate_windows) ? windowDiagnostics.candidate_windows.length : 0;
  if (sessionMode === "real_profile") {
    const profileDirectory = runtimeArgs.profileDirectory || "Default";
    return {
      label: "系统默认真实 Profile",
      path: "系统默认个人 Edge Profile（非项目目录）",
      detail: `当前按 --profile-directory=${profileDirectory} 运行；检测到 ${pidCount} 个相关进程 / ${windowCount} 个窗口。`,
      command: runtimeCommand,
    };
  }
  const runtimePath = runtimeArgs.userDataDir || actualPath || session?.expected_user_data_dir || "";
  return {
    label: runtimePath ? "独立资料目录 Profile" : "独立资料目录待初始化",
    path: formatEdgePath(runtimePath, "独立资料目录尚未落地"),
    detail: `当前按独立 Profile 运行；检测到 ${pidCount} 个相关进程 / ${windowCount} 个窗口。`,
    command: runtimeCommand,
  };
}

function renderEdgeSessionMeta() {
  const session = selectedEdgeSession();
  const modeSelect = $("edgeSessionMode");
  const pathInput = $("edgeSessionPath");
  const metaEl = $("edgeSessionMeta");
  if (!modeSelect || !pathInput || !metaEl) return;
  const mode = modeSelect.value === "real_profile" ? "real_profile" : "isolated";
  const meta = edgeSessionModeMeta({ session_mode: mode });
  const binding = edgeBindingSourceMeta(session);
  const dirDiff = edgeDirDiffMeta(session);
  const actualProfile = edgeActualProfileMeta(session);
  const defaultPath = session?.session_id && session.session_id !== "default_real_edge"
    ? `data/edge_profiles/${session.session_id}`
    : "真实个人环境不使用项目独立资料目录";
  pathInput.value = mode === "real_profile"
    ? (session?.user_data_dir || "真实个人环境不使用项目独立资料目录")
    : (session?.user_data_dir || defaultPath);
  metaEl.innerHTML = `
    <div><b>${meta.label}</b></div>
    <div>${escapeHtml(meta.hint)}</div>
    <div>绑定来源：${escapeHtml(binding.label)}</div>
    <div>目录校验：${escapeHtml(dirDiff.label)}${dirDiff.expected ? ` · 期望 ${escapeHtml(dirDiff.expected)}` : ""}</div>
    <div>当前实际 Profile：${escapeHtml(actualProfile.label)} · ${escapeHtml(actualProfile.path)}</div>
  `;
}

async function refreshEdgeSessions(preferredSessionId = "") {
  const sessions = await api("/api/edge-sessions");
  state.edgeSessions = sessions;
  renderBindSessionOptions(preferredSessionId || state.lastBindSessionId || currentSetupTask()?.edge_session_id || "");
  await refreshRemoteHealth().catch(() => {});
  renderSetupWorkbench();
}

function renderBindSessionOptions(preferredSessionId = "") {
  const select = $("bindSessionSelect");
  if (!select) return;
  const task = currentSetupTask();
  const resolution = bindSessionResolution(task, preferredSessionId);
  const sessions = resolution.candidates;
  select.innerHTML =
    sessions
      .map((session) => {
        return `<option value="${escapeHtml(session.session_id)}">${escapeHtml(session.optionLabel || edgeSessionOptionLabel(session))}</option>`;
      })
      .join("") || `<option value="">暂无店铺 Edge 会话</option>`;
  const latestSessionId = resolution.latestSessionId;
  const fallbackTaskSessionId = resolution.taskSessionId;
  const preserveBoundSessionId = task?.page_id && fallbackTaskSessionId && sessions.some((item) => item.session_id === fallbackTaskSessionId)
    ? fallbackTaskSessionId
    : "";
  const nextSessionId = preferredSessionId && sessions.some((item) => item.session_id === preferredSessionId)
    ? preferredSessionId
    : preserveBoundSessionId
      ? preserveBoundSessionId
      : latestSessionId && sessions.some((item) => item.session_id === latestSessionId)
        ? latestSessionId
      : fallbackTaskSessionId && sessions.some((item) => item.session_id === fallbackTaskSessionId)
        ? fallbackTaskSessionId
        : select.value;
  if (nextSessionId) {
    select.value = nextSessionId;
    state.lastBindSessionId = nextSessionId;
  }
  renderBindContext();
}

function fillEdgeSessionForm() {
  const metaEl = $("edgeSessionMeta");
  if (metaEl) renderEdgeSessionMeta();
}

async function createEdgeSession() {
  const sessionId = selectedEdgeSessionId() === "default_real_edge" ? "" : selectedEdgeSessionId();
  const sessionMode = $("edgeSessionMode")?.value === "real_profile" ? "real_profile" : "isolated";
  const payload = {
    session_id: sessionId,
    name: $("edgeSessionName")?.value.trim() || "",
    platform: $("edgeSessionPlatform")?.value.trim() || "",
    shop_name: $("edgeSessionShop")?.value.trim() || "",
    debug_port: $("edgeSessionPort")?.value ? Number($("edgeSessionPort").value) : null,
    session_mode: sessionMode,
  };
  const saved = await api("/api/edge-sessions", { method: "POST", body: JSON.stringify(payload) });
  await refreshEdgeSessions(saved.session_id);
  const meta = edgeSessionModeMeta(saved);
  showMessage(`Edge 会话已保存：${saved.name}，端口 ${saved.debug_port}，模式 ${meta.label}`);
}

async function refreshRemoteHealth() {
  const health = await api(`/api/edge-sessions/${encodeURIComponent(selectedEdgeSessionId())}/health`);
  const sessionId = selectedEdgeSessionId();
  const sessionIndex = state.edgeSessions.findIndex((item) => item.session_id === sessionId);
  if (sessionIndex >= 0) {
    state.edgeSessions[sessionIndex] = { ...state.edgeSessions[sessionIndex], health };
  }
  const el = $("remoteHealth");
  if (!el) return health;
  const session = selectedEdgeSession();
  const binding = edgeBindingSourceMeta(session);
  const dirDiff = edgeDirDiffMeta(session, health);
  const actualProfile = edgeActualProfileMeta(session, health);
  el.innerHTML = `
    <div>模式：${escapeHtml(health.mode_label || "-")} · 调试端口：${health.debug_available ? "已开启" : "未开启"} · 连接：${health.connected ? "已连接" : "未连接"}</div>
    <div>页面：${health.visible_pages}/${health.total_pages}</div>
    <div>运行态：${escapeHtml(formatRuntimeDiagnostics(health))}</div>
    <div>绑定来源：${escapeHtml(binding.label)} · ${escapeHtml(binding.detail)}</div>
    <div>资料目录校验：${escapeHtml(dirDiff.label)} · ${escapeHtml(dirDiff.detail)}</div>
    <div>期望资料目录：${escapeHtml(formatEdgePath(dirDiff.expected, "真实个人环境 / 系统默认 Profile"))}</div>
    <div>当前资料目录：${escapeHtml(formatEdgePath(dirDiff.actual, "真实个人环境 / 系统默认 Profile"))}</div>
    <div>当前实际 Profile：${escapeHtml(actualProfile.label)} · ${escapeHtml(actualProfile.path)}</div>
    <div>实际 Profile 说明：${escapeHtml(actualProfile.detail)}</div>
    <div>Profile 状态：${health.profile_initialized ? "已初始化" : "待初始化 / 可能尚未登录"}</div>
    <div>Profile 诊断：${escapeHtml(formatProfileDiagnostics(health.profile_diagnostics || {}))}</div>
    <div>提示：${escapeHtml(health.mode_hint || "-")}</div>
    <div>命令：${escapeHtml(health.edge_command || "-")}</div>
    <div>错误：${escapeHtml(health.last_error || "-")}</div>
  `;
  renderBindContext();
  return health;
}

async function startRemoteEdge() {
  const button = $("startRemoteEdge");
  const session = selectedEdgeSession();
  const meta = edgeSessionModeMeta(session);
  button.disabled = true;
  button.textContent = "显示中...";
  showMessage(`正在启动并显示当前 ${meta.label}；若失败，请按该模式提示排查冲突。`);
  try {
    const result = await showEdgeSession(selectedEdgeSessionId());
    await refreshRemoteHealth();
    if (!result.window_found) {
      showMessage(result.last_error || "当前 Edge 会话窗口没有成功显示出来。", true);
      return;
    }
    if ($("remoteUrl")?.value.trim()) {
      await openRemotePage();
      return;
    }
    await refreshRemotePages();
    showMessage(`当前 ${meta.label}已显示${result.maximized ? "并最大化" : ""}。请在该窗口中进入目标页面，然后刷新页面列表。`);
  } finally {
    button.disabled = false;
    button.textContent = "启动并显示当前 Edge";
  }
}

async function openRemotePage() {
  const button = $("openRemotePage");
  const input = $("remoteUrl");
  const url = input?.value.trim();
  const session = selectedEdgeSession();
  const meta = edgeSessionModeMeta(session);
  if (!url) {
    showMessage("请先输入要打开的真实 Edge 页面 URL", true);
    return;
  }
  button.disabled = true;
  button.textContent = "打开中...";
  showMessage(`正在连接当前 ${meta.label}；如果端口未打开，会先尝试启动当前会话。`);
  try {
    const page = await api(`/api/edge-sessions/${encodeURIComponent(selectedEdgeSessionId())}/open`, { method: "POST", body: JSON.stringify({ url }) });
    await refreshRemotePages(page.page_id);
    showMessage(`页面已在当前 ${meta.label} 中打开并加入页面列表。每个店铺可以重复打开一次，再分别标定保存任务。`);
  } catch (err) {
    await refreshRemoteHealth().catch(() => {});
    showMessage(`打开真实 Edge 页面失败：${parseApiError(err)}`, true);
  } finally {
    button.disabled = false;
    button.textContent = "打开真实 Edge 页面";
  }
}

async function refreshRemotePages(preferredPageId = "") {
  const pages = await api(`/api/edge-sessions/${encodeURIComponent(selectedEdgeSessionId())}/pages`);
  await refreshRemoteHealth();
  renderSetupWorkbench();
  if (preferredPageId && !pages.some((page) => page.page_id === preferredPageId)) {
    showMessage(`当前任务所属会话已刷新，共 ${pages.length} 个页签，原绑定页签暂未找到。`, true);
    return pages;
  }
  showMessage(`当前任务所属会话共有 ${pages.length} 个可见页签。`);
  return pages;
}

async function previewRemotePage(options = {}) {
  const { allowRecovery = true } = options;
  const task = currentSetupTask();
  const binding = currentRemoteBindingContext(task);
  const pageId = binding.page_id || "";
  if (!pageId) {
    showMessage("请先在步骤 1 为当前店铺绑定页面。", true);
    return;
  }
  const sessionId = binding.edge_session_id || selectedEdgeSessionId() || task?.edge_session_id;
  try {
    const preview = await api(`/api/edge-sessions/${encodeURIComponent(sessionId)}/pages/${pageId}/preview`, { method: "POST" });
    clearSetupRecovery(task?.id);
    state.preview = preview;
    state.selection = null;
    state.currentPreviewSource = { capture_mode: "remote_edge", edge_session_id: sessionId, page_id: pageId, page_url: preview.page.url, page_title: preview.page.title };
    $("captureMode").value = "remote_edge";
    renderPreviewImage(preview);
    renderSetupWorkbench();
    showMessage(`真实 Edge 页面预览已生成：${preview.width}x${preview.height}`);
    return preview;
  } catch (err) {
    const code = apiErrorCode(err);
    const payload = parseApiErrorPayload(err);
    const detailPayload = payload?.detail || {};
    if (code === "remote_page_not_found" && allowRecovery && task?.id && sessionId) {
      clearPreview();
      state.selection = null;
      setSetupRecovery(
        task,
        "binding_recovering",
        detailPayload.recovery_hint || "当前记录的是旧 page_id，系统正在根据当前会话候选页尝试恢复绑定。",
        "恢复完成前不会直接判定为“绑定页签已失效”。"
      );
      renderSetupWorkbench();
      renderBindContext(task);
      try {
        const result = await api(`/api/tasks/${encodeURIComponent(task.id)}/page-candidates?session_id=${encodeURIComponent(sessionId)}`);
        const applied = applyBindCandidatesResult(result, task, { silent: true, scanned: false });
        const resolution = result.binding_resolution || {};
        const latestBinding = currentRemoteBindingContext(currentSetupTask());
        const recoveredPageId = latestBinding.page_id || "";
        if (["recovered", "bound"].includes(resolution.state) && recoveredPageId && recoveredPageId !== pageId) {
          showMessage("旧 page_id 已失效，系统已按候选页恢复到最新绑定，正在重新生成预览。");
          return await previewRemotePage({ allowRecovery: false });
        }
        if (resolution.state === "ambiguous") {
          showMessage(resolution.summary || "检测到多个相似候选页，请人工确认后重新绑定。", true);
          return null;
        }
        if (resolution.state === "invalidated" || applied?.status === "rebind_required") {
          showMessage(resolution.summary || "当前会话里未找到可恢复的业务页，请重新选择页面。", true);
          return null;
        }
        showMessage("系统已刷新候选页，请确认当前绑定状态后再重新生成预览。", true);
        return null;
      } catch (recoveryErr) {
        const recoveryCode = apiErrorCode(recoveryErr);
        const recoveryPayload = parseApiErrorPayload(recoveryErr);
        const recoveryDetail = recoveryPayload?.detail || {};
        if (["edge_session_not_found", "edge_session_not_ready", "edge_debug_unavailable", "edge_debug_disconnected"].includes(recoveryCode)) {
          const detail = recoveryDetail.recovery_hint
            || "当前店铺登录态/Profile 可能仍在，但调试控制链路还未恢复。请去任务管理启动或显示 Edge，确认后台页打开后再回来。";
          setSetupRecovery(
            task,
            "session_unavailable",
            detail,
            "当前不是历史 page_id 误判，而是调试控制链路尚未恢复。"
          );
          renderSetupWorkbench();
          renderBindContext(task);
          showMessage(detail, true);
          return null;
        }
        throw recoveryErr;
      }
    }
    if (code === "remote_page_not_found") {
      clearPreview();
      state.selection = null;
      resetBindCandidates(task?.id);
      setSetupRecovery(
        task,
        "page_missing",
        detailPayload.recovery_hint || "当前任务记录的是旧页签句柄。虽然 Edge 已启动，但这次会话里找不到原绑定页，因此不能直接生成预览。",
        "请去任务管理确认正确后台页签仍打开，再回来重新扫描并重新选择。"
      );
      renderSetupWorkbench();
      renderBindContext(task);
      $("bindTable").innerHTML = renderBindRecoveryNotice({
        title: `当前店铺 ${task?.shop_name || ""} 的绑定页签已真实失效`,
        detail: "系统完成候选页校验后，仍未找到可恢复的业务页。请确认页面是否已关闭或已离开目标业务页，然后重新绑定。",
      });
      showMessage("系统完成候选页校验后，确认原绑定页已真实失效，请重新选择页面。", true);
      return null;
    }
    if (["edge_session_not_found", "edge_session_not_ready", "edge_debug_unavailable", "edge_debug_disconnected"].includes(code)) {
      const detail = detailPayload.recovery_hint
        || "当前店铺登录态/Profile 可能仍在，但调试控制链路还未恢复。请去任务管理启动或显示 Edge，确认后台页打开后再回来。";
      setSetupRecovery(
        task,
        "session_unavailable",
        detail,
        "当前不是历史 session 丢失，而是调试控制链路未恢复。"
      );
      renderSetupWorkbench();
      showMessage(detail, true);
      return null;
    }
    if (code === "edge_action_timeout" || code === "edge_preview_failed") {
      clearPreview();
      state.selection = null;
      const stageText = detailPayload.stage ? `当前阶段：${detailPayload.stage}。` : "";
      const detail = detailPayload.recovery_hint
        || `当前页签截图过程超时或卡住。${stageText}请先去任务管理关闭并重新显示该店铺 Edge，再回来重新扫描和重新预览。`;
      setSetupRecovery(
        task,
        "preview_timeout",
        detail,
        "当前不是单纯的页签不存在，而是截图链路发生阻塞。"
      );
      renderSetupWorkbench();
      renderBindContext(task);
      $("bindTable").innerHTML = renderBindRecoveryNotice({
        title: `当前店铺 ${task?.shop_name || ""} 的预览截图超时`,
        detail,
      });
      showMessage(detail, true);
      return null;
    }
    throw err;
  }
}

async function reloadRemotePage() {
  const task = currentSetupTask();
  const binding = currentRemoteBindingContext(task);
  const pageId = binding.page_id || "";
  if (!pageId) {
    showMessage("请先为当前店铺绑定页面。", true);
    return;
  }
  const sessionId = binding.edge_session_id || selectedEdgeSessionId() || task?.edge_session_id;
  await api(`/api/edge-sessions/${encodeURIComponent(sessionId)}/pages/${pageId}/reload`, { method: "POST" });
  await refreshRemotePages(pageId);
  showMessage("真实 Edge 页面已重载");
}

function currentScreenReadonlyBinding() {
  const task = currentSetupTask();
  const binding = currentRemoteBindingContext(task);
  const pageId = binding.page_id || "";
  const sessionId = binding.edge_session_id || selectedEdgeSessionId() || task?.edge_session_id || "";
  return { task, binding, pageId, sessionId };
}

function stopScreenReadonlyPolling() {
  if (state.screenReadonly?.timerId) {
    window.clearTimeout(state.screenReadonly.timerId);
    state.screenReadonly.timerId = null;
  }
  if (state.screenReadonly) {
    state.screenReadonly.running = false;
  }
}

function formatReadonlyRatio(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "-";
  return `${(numeric * 100).toFixed(2)}%`;
}

function renderScreenReadonlyPanel() {
  const summaryEl = $("screenReadonlySummary");
  const latestEl = $("screenReadonlyLatest");
  const recordsEl = $("screenReadonlyRecords");
  if (!summaryEl || !latestEl || !recordsEl) return;
  const latest = state.screenReadonly?.latest || null;
  const records = Array.isArray(state.screenReadonly?.records) ? state.screenReadonly.records : [];
  const running = Boolean(state.screenReadonly?.running);
  const lastError = state.screenReadonly?.lastError || "";
  if (!latest) {
    summaryEl.textContent = running ? "状态：只读中，等待首条大屏结果..." : "状态：未开启";
    latestEl.textContent = lastError || "还没有读取到大屏 payAmt。请先在真实页面进入大屏，再点击“开启只读”。";
    recordsEl.textContent = "暂无测试记录。";
    return;
  }
  const screen = latest.screen || {};
  const metricLabel = screen.metric_label || "payAmt";
  summaryEl.textContent = [
    `状态：${running ? "只读中" : "已停止"}`,
    `页面：${screen.ready ? "大屏已就绪" : "未就绪"}`,
    `轮询间隔：${screen.interval_seconds || 0}s`,
    `最近读取：${screen.captured_at || "-"}`,
  ].join(" | ");
  latestEl.textContent = screen.ready
    ? [
      `最新${metricLabel}：${fmtMoney(screen.pay_amt)}`,
      `更新时间：${screen.update_time || "-"}`,
      `无线支付金额：${screen.pay_amt_wl != null ? fmtMoney(screen.pay_amt_wl) : "-"}`,
      `支付笔数：${screen.pay_cnt ?? "-"}`,
      `无线支付占比：${formatReadonlyRatio(screen.pay_amt_wl_ratio)}`,
    ].join("\n")
    : `读取失败：${screen.message || lastError || "当前还没有可用的大屏值。"}`;
  recordsEl.textContent = records.length
    ? records.map((item) => {
      const screenValue = item.screen || {};
      if (!screenValue.ready) {
        return `[${screenValue.captured_at || "-"}] 失败: ${screenValue.message || screenValue.reason_code || "unknown"}`;
      }
      return `[${screenValue.captured_at || "-"}] ${(screenValue.metric_label || "payAmt")}=${screenValue.pay_amt} update=${screenValue.update_time || "-"} source=${screenValue.source_url || "-"}`;
    }).join("\n")
    : "暂无测试记录。";
}

function pushScreenReadonlyRecord(payload) {
  const records = Array.isArray(state.screenReadonly?.records) ? state.screenReadonly.records : [];
  records.unshift(payload);
  state.screenReadonly.records = records.slice(0, 10);
  state.screenReadonly.latest = payload;
}

async function fetchScreenReadonlyValue({ silent = false } = {}) {
  const { pageId, sessionId } = currentScreenReadonlyBinding();
  if (!pageId || !sessionId) {
    throw new Error(JSON.stringify({ detail: { reason_code: "binding_required", error: "请先绑定当前店铺页面，再读取大屏只读值。" } }));
  }
  const result = await api(`/api/edge-sessions/${encodeURIComponent(sessionId)}/pages/${pageId}/screen-readonly`);
  pushScreenReadonlyRecord(result);
  state.screenReadonly.lastError = result?.screen?.message || "";
  renderScreenReadonlyPanel();
  if (!silent) {
    if (result?.screen?.ready) {
      showMessage(`大屏只读值已更新：${result?.screen?.metric_label || "payAmt"}=${fmtMoney(result.screen.pay_amt)}`);
    } else {
      showMessage(result?.screen?.message || "当前还没有可用的大屏只读值。", true);
    }
  }
  return result;
}

function scheduleNextScreenReadonlyPoll(intervalSeconds = 5) {
  if (!state.screenReadonly?.running) return;
  const seconds = Math.min(Math.max(Number(intervalSeconds || 5), 1), 30);
  if (state.screenReadonly.timerId) {
    window.clearTimeout(state.screenReadonly.timerId);
  }
  state.screenReadonly.timerId = window.setTimeout(async () => {
    try {
      const latest = await fetchScreenReadonlyValue({ silent: true });
      scheduleNextScreenReadonlyPoll(latest?.screen?.interval_seconds || seconds);
    } catch (error) {
      state.screenReadonly.lastError = parseApiError(error);
      renderScreenReadonlyPanel();
      scheduleNextScreenReadonlyPoll(seconds);
    }
  }, seconds * 1000);
}

async function startScreenReadonly() {
  stopScreenReadonlyPolling();
  state.screenReadonly.records = [];
  state.screenReadonly.latest = null;
  state.screenReadonly.lastError = "";
  state.screenReadonly.running = true;
  renderScreenReadonlyPanel();
  try {
    const first = await fetchScreenReadonlyValue();
    scheduleNextScreenReadonlyPoll(first?.screen?.interval_seconds || 5);
    return first;
  } catch (error) {
    stopScreenReadonlyPolling();
    state.screenReadonly.lastError = parseApiError(error);
    renderScreenReadonlyPanel();
    throw error;
  }
}

async function refreshScreenReadonly() {
  return await fetchScreenReadonlyValue();
}

async function clearScreenReadonly() {
  stopScreenReadonlyPolling();
  state.screenReadonly.records = [];
  state.screenReadonly.latest = null;
  state.screenReadonly.lastError = "";
  renderScreenReadonlyPanel();
  showMessage("大屏只读测试记录已清空。");
}

function setupRemoteEdgeUi() {
  return null;
}
