// ===== 配置面板：工作台 / 预览 / OCR / 绑定 =====

function currentBindingResolution(task = currentSetupTask()) {
  const payload = state.bindCandidates?.task?.id === task?.id ? state.bindCandidates : null;
  return payload?.binding_resolution || null;
}

const SCREEN_READONLY_SUPPORTED_PLATFORM_KEYS = ["天猫", "京东", "唯品会", "抖音", "得物"];

function currentGlobalIntervalSeconds() {
  const value = Number($("globalInterval")?.value);
  if (!Number.isFinite(value)) return 1.0;
  return Math.max(0.5, value);
}

function syncValueSourceSelection(task = currentSetupTask(), options = {}) {
  const select = $("valueSourceSelect");
  const { force = false } = options;
  if (!select) return defaultValueSourceForTask(task);
  if (!task) {
    select.value = "ocr";
    select.dataset.boundTaskId = "";
    select.dataset.appliedDefault = "ocr";
    select.dataset.userOverride = "0";
    return "ocr";
  }
  const currentTaskId = String(task.id || "");
  const defaultKey = defaultValueSourceForTask(task);
  const lastBoundTaskId = String(select.dataset.boundTaskId || "");
  const lastAppliedDefault = normalizeValueSourceKey(select.dataset.appliedDefault || "");
  const currentValue = normalizeValueSourceKey(select.value);
  const hasManualOverride = lastBoundTaskId === currentTaskId && select.dataset.userOverride === "1";
  const shouldApplyDefault = force
    || lastBoundTaskId !== currentTaskId
    || !hasManualOverride
    || currentValue === lastAppliedDefault;
  if (shouldApplyDefault) {
    select.value = defaultKey;
    select.dataset.userOverride = "0";
  }
  select.dataset.boundTaskId = currentTaskId;
  select.dataset.appliedDefault = defaultKey;
  return normalizeValueSourceKey(select.value || defaultKey);
}

function markValueSourceSelectionManual(task = currentSetupTask()) {
  const select = $("valueSourceSelect");
  if (!select || !task?.id) return;
  if (String(select.dataset.boundTaskId || "") !== String(task.id)) return;
  select.dataset.userOverride = "1";
}

function selectedValueSource(task = currentSetupTask()) {
  const select = $("valueSourceSelect");
  if (select?.value) return normalizeValueSourceKey(select.value);
  return defaultValueSourceForTask(task);
}

function isScreenReadonlyMode(task = currentSetupTask()) {
  return selectedValueSource(task) === "screen_readonly";
}

function readonlyPlatformKey(platform = "") {
  const text = String(platform || "").trim();
  if (text.includes("天猫") || text.includes("淘宝") || text.includes("生意参谋")) return "天猫";
  if (text.includes("京东") || text.includes("商智")) return "京东";
  if (text.includes("唯品") || text.includes("唯品会") || text.toLowerCase().includes("vip")) return "唯品会";
  if (text.includes("抖音") || text.includes("巨量")) return "抖音";
  if (text.includes("得物") || text.toLowerCase().includes("dewu")) return "得物";
  return text || "其他平台";
}

function supportsScreenReadonlyPlatform(platform = "") {
  return SCREEN_READONLY_SUPPORTED_PLATFORM_KEYS.includes(readonlyPlatformKey(platform));
}

function currentTaskPlatform(task = currentSetupTask()) {
  const shopConfig = shopConfigForTask(task);
  return String(shopConfig?.platform || task?.platform || $("platform")?.value || "").trim();
}

function screenReadonlyUnsupportedMessage(platform = "") {
  const key = readonlyPlatformKey(platform);
  return `${key} 平台的大屏只读规则尚未配置。请先使用 OCR，或等待该平台单独页面分析。`;
}

function screenReadonlyMetricLabel(platform = "") {
  const key = readonlyPlatformKey(platform);
  if (key === "京东") return "“今日成交金额累计”";
  if (key === "唯品会") return "“实时GMV”";
  if (key === "抖音") return "“今日用户支付金额”";
  if (key === "得物") return "“今日成交额”";
  return "天猫专享 `payAmt.value`";
}

function screenReadonlyTargetPageHint(platform = "") {
  const key = readonlyPlatformKey(platform);
  if (key === "京东") return "京东实时看板 `realKanBans.html`";
  if (key === "唯品会") return "唯品会魔方日常直播间 `live/index.html#/daily`";
  if (key === "抖音") return "抖音单店大屏 `screen/shop/single`";
  if (key === "得物") return "得物交易看板 `main/transaction/adjustment?noLayout=1`";
  return "天猫专享生意参谋大屏";
}

function screenReadonlyPollingHint(platform = "") {
  if (!supportsScreenReadonlyPlatform(platform)) return "";
  return "正式链路跟随顶部“正式采集频率”设置。";
}

function taskHasPersistedOcrSelection(task = {}) {
  if (!task) return false;
  const xRatio = Number(task.x_ratio || 0);
  const yRatio = Number(task.y_ratio || 0);
  const widthRatio = Number(task.width_ratio || 0);
  const heightRatio = Number(task.height_ratio || 0);
  return (
    xRatio > 0
    || yRatio > 0
    || Math.abs(widthRatio - 0.1) > 0.0001
    || Math.abs(heightRatio - 0.06) > 0.0001
  );
}

function defaultValueSourceForTask(task = currentSetupTask()) {
  return "screen_readonly";
}

function screenReadonlyModeDescription(platform = "", mode = "saved") {
  const key = readonlyPlatformKey(platform);
  if (key === "京东") {
    return mode === "saved"
      ? "已选择大屏只读：保存后系统会持续等待京东实时看板，并读取“今日成交金额累计”作为正式采集值。正式链路跟随顶部“正式采集频率”设置。"
      : "测试模式：请先在真实页面进入京东实时看板 `realKanBans.html`，再点击“开启只读”。系统只在页面内读取“今日成交金额累计”，不做接口重放。";
  }
  if (key === "唯品会") {
    return mode === "saved"
      ? "已选择大屏只读：保存后系统会持续等待唯品会魔方日常直播间，并读取顶部“实时GMV”作为正式采集值。正式链路跟随顶部“正式采集频率”设置。"
      : "测试模式：请先在真实页面进入唯品会魔方日常直播间 `live/index.html#/daily`，再点击“开启只读”。系统只在页面内读取顶部“实时GMV”，不做接口重放。";
  }
  if (key === "抖音") {
    return mode === "saved"
      ? "已选择大屏只读：保存后系统会持续等待抖音单店大屏，并读取“今日用户支付金额”作为正式采集值。正式链路跟随顶部“正式采集频率”设置。"
      : "测试模式：请先在真实页面进入抖音单店大屏 `screen/shop/single`，再点击“开启只读”。系统只在页面内读取“今日用户支付金额”，不做接口重放。";
  }
  if (key === "得物") {
    return mode === "saved"
      ? "已选择大屏只读：保存后系统会持续等待得物交易看板，并读取“今日成交额”作为正式采集值。正式链路跟随顶部“正式采集频率”设置。"
      : "测试模式：请先在真实页面进入得物交易看板 `main/transaction/adjustment?noLayout=1`，再点击“开启只读”。系统只在页面内读取“今日成交额”的主数字，不做接口重放。";
  }
  return mode === "saved"
    ? "已选择天猫专享大屏只读：保存后系统会持续等待天猫大屏，并读取 `payAmt.value` 作为正式采集值。正式链路跟随顶部“正式采集频率”设置。"
    : "测试模式：请先在真实页面进入天猫专享生意参谋大屏，再点击“开启只读”。系统只在页面内读取 `payAmt.value`，不做接口重放。";
}

function renderBindContext(task = currentSetupTask()) {
  const el = $("bindContext");
  const hint = $("bindHint");
  if (!el || !hint) return;
  if (!task) {
    hint.textContent = "请从任务管理进入当前店铺。";
    el.textContent = "尚未选择店铺上下文。";
    return;
  }
  const resolution = bindSessionResolution(task);
  const session = resolution.selectedSession || resolution.taskSession || resolution.latestSession;
  const stage = setupStageMeta(task);
  const payload = state.bindCandidates?.task?.id === task.id ? state.bindCandidates : null;
  const pageCount = payload?.pages?.length || 0;
  const selectedPage = (payload?.pages || []).find((item) => item.page_id === state.selectedBindPageId) || null;
  const recovery = state.setupRecovery && state.setupRecovery.taskId === task.id ? state.setupRecovery : null;
  const bindingResolution = currentBindingResolution(task);
  const flow = setupFlowState(task);
  const latestSourceText = resolution.latestSession
    ? edgeSessionOptionLabel(resolution.latestSession, "当前店铺配置")
    : (resolution.latestSessionId ? `${resolution.latestSessionId}（当前配置未生成会话）` : "当前店铺未配置专属会话");
  const selectedSourceText = session
    ? edgeSessionOptionLabel(session, resolution.selectedCandidate?.optionSource === "task_bound_historical" ? "历史绑定" : "")
    : (resolution.selectedSessionId || task.edge_session_id || "-");
  const binding = session ? edgeBindingSourceMeta(session) : null;
  const dirDiff = session ? edgeDirDiffMeta(session, edgeSessionHealthSnapshot(session)) : null;
  const actualProfile = session ? edgeActualProfileMeta(session, edgeSessionHealthSnapshot(session)) : null;
  const mappingHint = resolution.fallbackAll
    ? "当前未匹配到该店铺的最新版专属会话，步骤 1 已回退展示全部店铺会话。"
    : (resolution.usesHistoricalTaskSession
        ? "当前任务仍绑定历史会话；下拉框已优先对齐到该店铺最新版配置会话，同时保留历史会话回退。"
        : "当前步骤 1 已对齐到该店铺最新版配置会话。");
  const bindActionText = isScreenReadonlyMode(task)
    ? "请先扫描当前会话页签，并绑定将来会进入大屏的业务页。"
    : "请先扫描当前会话页签，再手动选择需要 OCR 的页面。";
  hint.textContent = recovery?.hint || bindingResolution?.summary || payload?.next_action || `当前店铺 ${task.shop_name || "-"}，${bindActionText}`;
  el.innerHTML = `
    <div><b>${escapeHtml(task.platform || "-")} / ${escapeHtml(task.shop_name || "-")}</b></div>
    <div>当前状态：${escapeHtml(stage.label)} · 当前选择会话：${escapeHtml(selectedSourceText)}</div>
    <div>最新店铺配置会话：${escapeHtml(latestSourceText)} · ${escapeHtml(mappingHint)}</div>
    ${binding ? `<div>会话绑定来源：${escapeHtml(binding.label)} · ${escapeHtml(binding.detail)}</div>` : ""}
    ${dirDiff ? `<div>资料目录校验：${escapeHtml(dirDiff.label)} · 当前 ${escapeHtml(formatEdgePath(dirDiff.actual, "真实个人环境 / 系统默认 Profile"))} · 期望 ${escapeHtml(formatEdgePath(dirDiff.expected, "真实个人环境 / 系统默认 Profile"))}</div>` : ""}
    ${actualProfile ? `<div>当前实际 Profile：${escapeHtml(actualProfile.label)} · ${escapeHtml(actualProfile.path)}</div>` : ""}
    ${actualProfile?.detail ? `<div>${escapeHtml(actualProfile.detail)}</div>` : ""}
    <div>当前步骤：${escapeHtml(flow.label)} · 当前会话页签：${pageCount} 个</div>
    <div>已选页签：${escapeHtml(selectedPage?.title || selectedPage?.url || task.page_title || task.page_url || task.page_id || "未选择")}</div>
    ${recovery?.detail ? `<div>${escapeHtml(recovery.detail)}</div>` : ""}
    ${!recovery?.detail && bindingResolution?.detail ? `<div>${escapeHtml(bindingResolution.detail)}</div>` : ""}
  `;
}

function setSetupRecovery(task, kind, hint = "", detail = "") {
  state.setupRecovery = task ? { taskId: task.id, kind, hint, detail } : null;
}

function clearSetupRecovery(taskId = currentSetupTask()?.id) {
  if (!state.setupRecovery) return;
  if (!taskId || state.setupRecovery.taskId === taskId) {
    state.setupRecovery = null;
  }
}

function renderBindRecoveryNotice({ title, detail, showManagerAction = true, showRescanAction = true }) {
  return `
    <div class="bind-recovery-card">
      <div class="bind-recovery-title">${escapeHtml(title)}</div>
      <div class="bind-recovery-detail">${escapeHtml(detail)}</div>
      <div class="bind-recovery-actions">
        ${showManagerAction ? '<button type="button" class="secondary" data-setup-action="open-manager">去任务管理显示 Edge</button>' : ""}
        ${showRescanAction ? '<button type="button" class="secondary" data-setup-action="rescan-bind">回来重新扫描</button>' : ""}
      </div>
    </div>
  `;
}

function resetBindCandidates(taskId = currentSetupTask()?.id) {
  if (!taskId || state.bindCandidates?.task?.id === taskId) {
    state.bindCandidates = null;
    state.selectedBindPageId = "";
  }
}

function currentBindPages() {
  return state.bindCandidates?.pages || [];
}

function selectedBindPageInfo() {
  return currentBindPages().find((item) => item.page_id === state.selectedBindPageId) || null;
}

function selectBindPage(pageId) {
  state.selectedBindPageId = pageId || "";
  renderBindPageCandidates();
  renderBindContext();
  renderSetupWorkbench();
}

function renderBindPageBadge(page) {
  const badges = [];
  if (page.is_current_bound) badges.push('<span class="bind-page-badge is-bound">当前绑定</span>');
  if (page.is_target_page) badges.push('<span class="bind-page-badge is-match">目标业务页</span>');
  if (page.is_login_page) badges.push('<span class="bind-page-badge">登录页</span>');
  if (page.matches_target_url) badges.push('<span class="bind-page-badge is-match">匹配目标URL</span>');
  if (page.matches_task_page_url) badges.push('<span class="bind-page-badge is-match">匹配当前URL</span>');
  if (page.matches_task_page_title) badges.push('<span class="bind-page-badge">匹配标题</span>');
  return badges.join("");
}

function renderBindPageCandidates() {
  const table = $("bindTable");
  if (!table) return;
  const pages = currentBindPages();
  if (!pages.length) {
    table.innerHTML = "";
    return;
  }
  table.innerHTML = pages
    .map((page, index) => {
      const selected = page.page_id === state.selectedBindPageId;
      return `
        <div class="bind-page-card${selected ? " is-selected" : ""}">
          <div class="bind-page-card-main">
            <div class="bind-page-card-title">${escapeHtml(page.title || `页签 ${index + 1}`)}</div>
            <div class="bind-page-card-url">${escapeHtml(page.url || "-")}</div>
            <div class="bind-page-card-badges">${renderBindPageBadge(page)}</div>
          </div>
          <div class="bind-page-card-actions">
            <button type="button" class="${selected ? "primary" : "secondary"}" data-setup-action="select-bind-page" data-page-id="${escapeHtml(page.page_id)}">
              ${selected ? "已选中" : "选择此页"}
            </button>
          </div>
        </div>
      `;
    })
    .join("");
}

function syncSetupTaskSnapshot(taskLike, options = {}) {
  const currentTask = currentSetupTask();
  const payload = taskLike && typeof taskLike === "object" ? taskLike : null;
  if (!payload) return currentTask;
  const base = currentTask && payload.id && Number(currentTask.id) === Number(payload.id)
    ? currentTask
    : findTaskById(payload.id) || findTaskByIdentity(payload.platform, payload.shop_name) || {};
  const synced = upsertTaskIntoSnapshot({ ...base, ...payload });
  if (synced?.id && state.currentSetupTaskId && Number(state.currentSetupTaskId) === Number(synced.id)) {
    state.editingTaskId = synced.id;
  }
  if (options.render !== false) {
    buildSetupSummary();
  }
  return synced || currentTask;
}

function applyBindCandidatesResult(result, task, options = {}) {
  const { silent = false, scanned = false } = options;
  const syncedTask = syncSetupTaskSnapshot(result.task, { render: false }) || task;
  const table = $("bindTable");
  const confirmBtn = $("confirmBind");
  const bindingResolution = result.binding_resolution || {};
  state.bindCandidates = result;
  state.selectedBindPageId = result.current_binding?.page_id
    || result.pages?.find((item) => item.is_current_bound)?.page_id
    || result.pages?.[0]?.page_id
    || "";
  const pages = result.pages || [];
  if (!pages.length) {
    const title = syncedTask
      ? `当前店铺 ${syncedTask.shop_name || ""} 还没有可绑定页签`
      : "当前会话没有可绑定页签";
    const detail = syncedTask
      ? "请先去“任务管理”点击对应平台或店铺的“显示Edge”，确认正确后台页已经打开，再回到这里点击“重新扫描”。"
      : "请在任务管理里打开目标店铺后台页后再回来扫描。";
    setSetupRecovery(syncedTask, "no_candidates", detail, result.recovery_hint || "当前会话里还没有可用页面。");
    if (table) {
      table.innerHTML = syncedTask
        ? renderBindRecoveryNotice({ title, detail })
        : "<div style='color:var(--muted)'>该店铺会话没有待绑定的任务。请先配置店铺任务。</div>";
    }
    if (!silent && syncedTask) {
      showMessage("当前店铺还没有可绑定页签。请去任务管理显示正确 Edge 页面，再回到这里重新扫描。", true);
    }
    renderBindContext(syncedTask);
    renderSetupWorkbench();
    return { status: "empty", task: syncedTask, count: 0 };
  }
  if (bindingResolution.state === "ambiguous") {
    setSetupRecovery(
      syncedTask,
      "candidate_ambiguous",
      bindingResolution.summary || "检测到多个相似候选页，系统不会直接判为页签失效，请先人工确认。",
      bindingResolution.detail || result.recovery_hint || "请从当前会话现有页签中手动确认正确页面。"
    );
    renderBindPageCandidates();
    if (table) {
      const title = `当前店铺 ${syncedTask.shop_name || ""} 存在多个候选页`;
      const detail = "当前会话里识别到多个相似候选页，系统为避免误绑没有自动恢复。请人工确认后重新绑定。";
      table.innerHTML = `${renderBindRecoveryNotice({ title, detail })}${table.innerHTML}`;
    }
    if (confirmBtn) confirmBtn.style.display = state.selectedBindPageId ? "block" : "none";
    renderBindContext(syncedTask);
    renderSetupWorkbench();
    if (!silent) {
      showMessage(bindingResolution.summary || "检测到多个相似候选页，请人工确认后重新绑定。", true);
    }
    return { status: "ambiguous", task: syncedTask, count: pages.length };
  }
  if (bindingResolution.state === "invalidated" || result.flow_state === "rebind_required") {
    setSetupRecovery(
      syncedTask,
      "page_missing",
      bindingResolution.summary || "当前会话里未找到可恢复的业务页，原绑定页签已真实失效。",
      bindingResolution.detail || result.recovery_hint || "请从当前会话现有页签中重新选择要 OCR 的页面。"
    );
    renderBindPageCandidates();
    if (table) {
      const title = `当前店铺 ${syncedTask.shop_name || ""} 的绑定页签已真实失效`;
      const detail = "当前会话里没有找到可安全恢复的业务页。通常是页面已关闭，或已经离开原目标业务页。请确认后重新选择页面。";
      table.innerHTML = `${renderBindRecoveryNotice({ title, detail })}${table.innerHTML}`;
    }
    if (confirmBtn) confirmBtn.style.display = state.selectedBindPageId ? "block" : "none";
    renderBindContext(syncedTask);
    renderSetupWorkbench();
    if (!silent) {
      showMessage(bindingResolution.summary || "原绑定页签已真实失效，请重新选择页面。", true);
    }
    return { status: "rebind_required", task: syncedTask, count: pages.length };
  }
  clearSetupRecovery(syncedTask?.id);
  renderBindPageCandidates();
  if (confirmBtn) {
    confirmBtn.style.display = scanned && result.flow_state !== "page_selected" && state.selectedBindPageId ? "block" : "none";
  }
  renderBindContext(syncedTask);
  renderSetupWorkbench();
  if (!silent) {
    if (bindingResolution.state === "recovered") {
      showMessage(bindingResolution.summary || "系统已自动恢复到最新绑定页签，可直接生成预览。");
    } else if (result.flow_state === "page_selected") {
      showMessage("当前绑定页仍有效，可直接生成预览。");
    } else if (scanned) {
      showMessage(`已扫描当前会话 ${pages.length} 个页签，请手动选择一个用于 OCR 的页面。`);
    }
  }
  return {
    status: result.flow_state === "page_selected" ? "page_selected" : "matched",
    task: syncedTask,
    count: pages.length,
  };
}

async function preloadTaskBindCandidates(task, options = {}) {
  if (!task || task.capture_mode !== "remote_edge" || !task.edge_session_id) {
    resetBindCandidates(task?.id);
    return null;
  }
  const { silent = false } = options;
  try {
    const result = await api(`/api/tasks/${encodeURIComponent(task.id)}/page-candidates`);
    applyBindCandidatesResult(result, task, { silent, scanned: false });
    return result;
  } catch (err) {
    if (!silent) {
      const code = apiErrorCode(err);
      if (["edge_session_not_ready", "edge_debug_unavailable", "edge_debug_disconnected", "edge_session_not_found"].includes(code)) {
        setSetupRecovery(
          task,
          "session_unavailable",
          "当前店铺登录态/Profile 可能仍在，但调试控制链路还未恢复。请去任务管理启动或显示 Edge，确认窗口和后台页都恢复后再回来。",
          "当前不是历史 session 丢失，而是调试控制链路尚未接通。"
        );
        showMessage("当前店铺上下文已恢复，但调试控制链路未恢复。请去任务管理启动或显示 Edge 后重试。", true);
      } else {
        showMessage(`当前店铺候选页预加载失败：${parseApiError(err)}`, true);
      }
      renderBindContext(task);
      renderSetupWorkbench();
    }
    return null;
  }
}

function setupFlowState(task = currentSetupTask()) {
  if (!task) {
    return {
      key: "idle",
      label: "未开始",
      nextStep: "请在任务管理中选中一个任务，或进入当前待配置店铺。",
      previewHint: "完成页面绑定后，右侧会用于生成预览和框选 GMV 区域。",
    };
  }
  const recovery = state.setupRecovery && state.setupRecovery.taskId === task.id ? state.setupRecovery : null;
  const bindPayload = state.bindCandidates?.task?.id === task.id ? state.bindCandidates : null;
  const bindingResolution = bindPayload?.binding_resolution || null;
  const stage = setupStageMeta(task);
  if (recovery?.kind === "binding_recovering") {
    return {
      key: "recovering",
      label: "步骤 1：恢复绑定中",
      nextStep: "系统正在根据当前会话候选页校验并自愈旧绑定，请稍候。",
      previewHint: "恢复完成前不要直接判定页签失效；若恢复成功可继续生成预览。",
    };
  }
  if (bindingResolution?.state === "ambiguous" || recovery?.kind === "candidate_ambiguous") {
    return {
      key: "manual_confirm",
      label: "步骤 1：人工确认页面",
      nextStep: "当前存在多个相似候选页，请人工确认后重新绑定，系统未直接判为真实失效。",
      previewHint: "完成人工确认并重新绑定后，右侧才能生成正确预览。",
    };
  }
  if (bindingResolution?.state === "invalidated" || bindPayload?.flow_state === "rebind_required" || recovery?.kind === "page_missing") {
    return {
      key: "rebind_required",
      label: "步骤 1：重新选择页面",
      nextStep: "先在任务管理确认正确后台页仍打开；若页面已关闭或已离开业务页，请回来重新扫描并手动重新绑定。",
      previewHint: "只有确认真实失效后重新绑定，右侧才能重新生成预览。",
    };
  }
  if (!task.page_id || bindPayload?.flow_state === "waiting_page") {
    return {
      key: "bind",
      label: "步骤 1：选择页面",
      nextStep: isScreenReadonlyMode(task)
        ? "先扫描当前会话页签，手动选中将来会进入大屏的业务页，再点击“使用此页面”。"
        : "先扫描当前会话页签，手动选中一个需要 OCR 的页签，再点击“使用此页面”。",
      previewHint: isScreenReadonlyMode(task)
        ? "大屏只读模式不依赖 OCR 框选；先完成页面绑定，再保存正式配置。"
        : "绑定页面后即可在右侧生成预览。",
    };
  }
  if (isScreenReadonlyMode(task)) {
    return {
      key: "readonly_ready",
      label: "步骤 2：保存大屏只读",
      nextStep: `保存后系统会在真实页面里持续等待大屏就绪，并读取${screenReadonlyMetricLabel(currentTaskPlatform(task))}作为正式值。`,
      previewHint: "大屏只读模式无需框选 OCR 区域；可选生成预览做人工核对。",
    };
  }
  const currentPageId = state.currentPreviewSource?.page_id || "";
  const hasCurrentPreview = Boolean(state.preview && currentPageId && currentPageId === task.page_id);
  // 如果用户已经对当前绑定页成功生成了真实预览，优先信任当前预览进入框选/OCR流程，
  // 避免因为目标URL匹配过严而把真实业务页误判成“非目标页”。
  if (hasCurrentPreview) {
    if (!hasUsableSelection()) {
      return {
        key: "region_selected",
        label: "步骤 2：框选 GMV",
        nextStep: "直接在右侧截图上拖拽框住 GMV 数字区域。",
        previewHint: "当前预览已生成，请在右侧截图上拖拽框住完整的 GMV 数字。",
      };
    }
    return {
      key: "ready_to_save",
      label: "步骤 3：测试并保存",
      nextStep: "建议先测试识别，再点击“保存并进入下一家”。",
      previewHint: "当前已完成框选，可测试识别后保存进入下一家。",
    };
  }
  if (!state.preview || currentPageId !== task.page_id) {
    return {
      key: "preview",
      label: "步骤 2：生成预览",
      nextStep: "点击“生成预览”，把当前绑定页签截图到右侧。",
      previewHint: "生成预览后，在右侧拖拽框住 GMV 数字区域。",
    };
  }
  if (!hasUsableSelection()) {
    return {
      key: "region_selected",
      label: "步骤 2：框选 GMV",
      nextStep: "直接在右侧截图上拖拽框住 GMV 数字区域。",
      previewHint: "请在右侧截图上拖拽框住完整的 GMV 数字。",
    };
  }
  return {
    key: "ready_to_save",
    label: "步骤 3：测试并保存",
    nextStep: "建议先测试识别，再点击“保存并进入下一家”。",
    previewHint: "当前已完成框选，可测试识别后保存进入下一家。",
  };
}

function renderSetupWorkbench() {
  const summary = state.setupSummary || { total: 0, pendingBind: 0, pendingCalibrate: 0, completed: 0 };
  const task = currentSetupTask();
  const flow = setupFlowState(task);
  const nameEl = $("setupCurrentName");
  const metaEl = $("setupCurrentMeta");
  const statusEl = $("setupCurrentStatus");
  const nextStepEl = $("setupNextStep");
  const summaryLineEl = $("setupSummaryLine");
  const previewHintEl = $("previewStepHint");
  const nextBtn = $("focusNextSetup");
  const rescanBtn = $("rescanCurrentSetup");
  const resetBtn = $("resetCurrentSetup");
  const scanBtn = $("scanBind");
  const resumeBtn = $("resumeAfterLogin");
  const confirmBtn = $("confirmBind");
  const previewBtn = $("previewRemotePage");
  const testBtn = $("testOcr");
  const saveBtn = $("saveTask");
  const bindCard = $("setupStepBind");
  const saveCard = $("setupStepSave");
  const bindSessionLabel = bindCard?.querySelector("label");
  const bindTable = $("bindTable");
  const valueSourceSelect = $("valueSourceSelect");
  const valueSourceHint = $("valueSourceHint");
  const readonlyCard = $("screenReadonlyCard");
  const readonlyTitle = $("screenReadonlyTitle");
  const readonlyHelper = $("screenReadonlyHelper");
  if (nameEl && metaEl && statusEl) {
    if (!task) {
      nameEl.textContent = state.setupQueue.length ? "待处理店铺未加载" : "暂无待处理店铺";
      metaEl.textContent = state.setupQueue.length
        ? "已识别到待处理任务，请稍后刷新或手动进入任务编辑。"
        : "请从任务管理进入编辑。";
      statusEl.className = "status tone-neutral";
      statusEl.textContent = state.setupQueue.length ? "处理中断" : flow.label;
    } else {
      const stage = setupStageMeta(task);
      const resolution = bindSessionResolution(task);
      const session = resolution.selectedSession || resolution.latestSession || resolution.taskSession;
      const pageText = task.page_title || task.page_url || task.page_id || "未绑定页面";
      nameEl.textContent = `${task.platform || "-"} / ${task.shop_name || "未命名店铺"}`;
      metaEl.textContent = `会话：${session?.name || session?.session_id || task.edge_session_id || "-"} · 页面：${pageText}`;
      statusEl.className = `status tone-${stage.tone}`;
      statusEl.textContent = stage.label;
    }
  }
  if (nextStepEl) nextStepEl.textContent = `下一步：${flow.nextStep}`;
  if (summaryLineEl) {
    summaryLineEl.textContent = `待处理统计：总店铺 ${summary.total || 0}，待绑定（含待登录/待切业务页） ${summary.pendingBind || 0}，待标定 ${summary.pendingCalibrate || 0}，已完成 ${summary.completed || 0}。`;
  }
  renderSetupShopJumper();
  if (previewHintEl) previewHintEl.textContent = flow.previewHint;
  if (valueSourceSelect) {
    valueSourceSelect.disabled = !task;
    syncValueSourceSelection(task);
  }
  if (valueSourceHint) {
    const platform = currentTaskPlatform(task);
    const readonlyUnsupported = isScreenReadonlyMode(task) && !supportsScreenReadonlyPlatform(platform);
    valueSourceHint.textContent = isScreenReadonlyMode(task)
      ? (readonlyUnsupported
          ? screenReadonlyUnsupportedMessage(platform)
          : screenReadonlyModeDescription(platform, "saved"))
      : "已选择 OCR识别：需要先生成预览并框选 GMV 区域，再测试并保存。";
    valueSourceHint.classList.toggle("bad-text", readonlyUnsupported);
  }
  if (nextBtn) nextBtn.disabled = state.setupQueue.length === 0;
  if (rescanBtn) {
    rescanBtn.disabled = !task || task.capture_mode !== "remote_edge";
    rescanBtn.style.display = task ? "inline-flex" : "none";
  }
  if (resetBtn) resetBtn.disabled = !task;
  if (bindSessionLabel) bindSessionLabel.style.display = task ? "block" : "none";
  if (bindTable) bindTable.style.display = task ? "flex" : "none";
  if (scanBtn) scanBtn.style.display = task && ["bind", "rebind_required", "manual_confirm", "target_page_required"].includes(flow.key) ? "block" : "none";
  if (resumeBtn) {
    resumeBtn.style.display = task && flow.key === "login_required" ? "block" : "none";
    resumeBtn.disabled = !task || flow.key !== "login_required";
  }
  if (confirmBtn) {
    confirmBtn.style.display = task && ["bind", "rebind_required", "manual_confirm", "target_page_required"].includes(flow.key) && state.selectedBindPageId ? "block" : "none";
    confirmBtn.disabled = !state.selectedBindPageId;
  }
  if (previewBtn) previewBtn.style.display = task && ["preview", "region_selected", "ready_to_save", "readonly_ready"].includes(flow.key) ? "inline-flex" : "none";
  if (testBtn) testBtn.style.display = flow.key === "ready_to_save" ? "inline-flex" : "none";
  if (saveBtn) saveBtn.style.display = ["ready_to_save", "readonly_ready"].includes(flow.key) ? "inline-flex" : "none";
  if (bindCard) bindCard.classList.toggle("is-active", ["bind", "rebind_required", "manual_confirm", "recovering", "login_required", "target_page_required"].includes(flow.key));
  if (saveCard) saveCard.classList.toggle("is-active", ["preview", "region_selected", "ready_to_save", "readonly_ready"].includes(flow.key));
  if (bindCard) bindCard.classList.toggle("is-muted", !task);
  if (readonlyCard) readonlyCard.classList.toggle("is-active", Boolean(task) && isScreenReadonlyMode(task));
  if (readonlyTitle) {
    const platform = currentTaskPlatform(task);
    const key = readonlyPlatformKey(platform);
    readonlyTitle.textContent = isScreenReadonlyMode(task)
      ? (key === "天猫" ? "天猫专享大屏只读模式" : "大屏只读模式")
      : (key === "天猫" ? "天猫专享大屏只读测试" : "大屏只读测试");
  }
  if (readonlyHelper) {
    const platform = currentTaskPlatform(task);
    readonlyHelper.textContent = isScreenReadonlyMode(task)
      ? `正式模式：保存后会在真实页面上下文中持续等待${screenReadonlyTargetPageHint(platform)}，并读取${screenReadonlyMetricLabel(platform)}，写入正式任务结果。${screenReadonlyPollingHint(platform)}`
      : screenReadonlyModeDescription(platform, "testing");
  }
  renderBindContext(task);
}

function renderSetupShopJumper() {
  const row = $("setupShopJumperRow");
  const sel = $("setupShopJumper");
  if (!row || !sel) return;
  const entries = setupShopEntries();
  if (entries.length < 2) { row.style.display = "none"; return; }
  row.style.display = "";
  const currentTask = currentSetupTask();
  const currentIdentity = `${currentTask?.platform || ""}::${currentTask?.shop_name || ""}`;
  sel.innerHTML = entries.map(({ config, task }) => {
    const stageLabel = task ? setupStageMeta(task).label : "待初始化";
    const value = task?.id ? `task:${task.id}` : `config:${encodeURIComponent(config.platform || "")}::${encodeURIComponent(config.shop_name || "")}`;
    const selected = task?.id
      ? (currentTask?.id === task.id)
      : (`${config.platform || ""}::${config.shop_name || ""}` === currentIdentity);
    return `<option value="${value}"${selected ? " selected" : ""}>${escapeHtml(config.platform)} / ${escapeHtml(config.shop_name)} [${stageLabel}]</option>`;
  }).join("");
}

let _setupAutoFocusInFlight = false;
let _minimalContextRestoreInFlight = false;
let _minimalContextRestoreHandled = false;

async function ensureSetupTaskFocused(options = {}) {
  const activeView = document.querySelector(".view.active")?.id || "";
  if (activeView !== "config") return null;
  if (currentSetupTask()) return currentSetupTask();
  buildSetupSummary();
  if (!state.setupQueue.length || _setupAutoFocusInFlight) return null;
  _setupAutoFocusInFlight = true;
  try {
    return await focusNextPendingTask(options);
  } finally {
    _setupAutoFocusInFlight = false;
  }
}

async function syncTaskContext(task, options = {}) {
  if (!task) return;
  const { refreshPages = false, preloadCandidates = true } = options;
  const preferredSessionId = task.page_id
    ? (task.edge_session_id || latestConfiguredSessionIdForTask(task) || "")
    : (latestConfiguredSessionIdForTask(task) || task.edge_session_id || "");
  if (preferredSessionId && (!state.edgeSessions || !state.edgeSessions.some((item) => item.session_id === preferredSessionId))) {
    await refreshEdgeSessions(preferredSessionId);
  }
  renderBindSessionOptions(preferredSessionId);
  if ($("bindSessionSelect") && preferredSessionId) {
    $("bindSessionSelect").value = preferredSessionId;
  }
  renderBindContext(task);
  if (task.capture_mode === "remote_edge" && preferredSessionId) {
    await refreshRemoteHealth().catch(() => {});
    if (refreshPages) {
      await refreshRemotePages(task.page_id || "").catch(() => {});
    }
    if (preloadCandidates) {
      await preloadTaskBindCandidates(task, { silent: false });
    }
  }
}

async function restoreSetupContextAfterRefresh() {
  if (_minimalContextRestoreHandled || _minimalContextRestoreInFlight) return;
  const restoreMeta = state.minimalContextRestore || {};
  if (!restoreMeta.attempted) {
    _minimalContextRestoreHandled = true;
    return;
  }
  _minimalContextRestoreInFlight = true;
  try {
    if (restoreMeta.failed) {
      showMessage(`刷新后恢复上次上下文失败：${restoreMeta.reason || "未知错误"}。请手动选择店铺继续。`, true);
      _minimalContextRestoreHandled = true;
      return;
    }
    const restoredTaskId = Number(restoreMeta.restoredTaskId || state.currentSetupTaskId || 0);
    if (!restoredTaskId) {
      _minimalContextRestoreHandled = true;
      return;
    }
    const task = findTaskById(restoredTaskId);
    if (!task) {
      state.currentSetupTaskId = null;
      state.editingTaskId = null;
      persistMinimalContext();
      showMessage(`刷新后恢复失败：未找到任务 #${restoredTaskId}，请重新选择店铺。`, true);
      _minimalContextRestoreHandled = true;
      return;
    }
    state.currentSetupTaskId = task.id;
    state.editingTaskId = task.id;
    persistMinimalContext();
    if (task.capture_mode === "remote_edge" && task.page_id) {
      setSetupRecovery(
        task,
        "binding_recovering",
        "页面已刷新，系统正在根据当前会话候选页恢复并校验上次绑定，请稍候。",
        "恢复完成前不会直接判定为“绑定页签已失效”。"
      );
    }
    renderSetupWorkbench();
    await syncTaskContext(task, { refreshPages: task.capture_mode === "remote_edge", preloadCandidates: task.capture_mode === "remote_edge" });
    if (task.capture_mode === "remote_edge") {
      const recovered = state.setupRecovery && state.setupRecovery.taskId === task.id;
      if (!recovered) {
        showMessage(`已恢复上次店铺：${task.platform || "-"} / ${task.shop_name || "-"}，并自动完成候选页预加载。`);
      }
    }
    _minimalContextRestoreHandled = true;
  } finally {
    _minimalContextRestoreInFlight = false;
  }
}

async function focusSetupTask(taskId, options = {}) {
  const task = findTaskById(taskId);
  if (!task) return null;
  const { message = "", keepPreview = false } = options;
  state.lastBindSessionId = task.edge_session_id || latestConfiguredSessionIdForTask(task) || "";
  state.currentSetupTaskId = task.id;
  persistMinimalContext();
  await loadTaskIntoConfig(task, { message, keepPreview, syncContext: true });
  renderSetupWorkbench();
  return task;
}

async function focusSetupShopByIdentity(platform, shopName, options = {}) {
  const resolvedPlatform = decodeURIComponent(String(platform || "").trim());
  const resolvedShopName = decodeURIComponent(String(shopName || "").trim());
  let task = findTaskByIdentity(resolvedPlatform, resolvedShopName);
  if (!task) {
    showMessage(`当前店铺 ${resolvedPlatform} / ${resolvedShopName} 还没有初始化任务，正在自动补齐...`);
    await api("/api/shops/init", { method: "POST" });
    await loadTasks();
    task = findTaskByIdentity(resolvedPlatform, resolvedShopName);
  }
  if (!task) {
    showMessage(`当前店铺 ${resolvedPlatform} / ${resolvedShopName} 初始化后仍未找到任务，请检查 shops.csv 与任务唯一约束。`, true);
    return null;
  }
  return focusSetupTask(task.id, {
    message: options.message || `已进入当前店铺：${resolvedPlatform} / ${resolvedShopName}`,
    keepPreview: false,
  });
}

async function focusNextPendingTask(options = {}) {
  const { message = "" } = options;
  buildSetupSummary();
  const nextId = state.setupQueue[0];
  if (!nextId) {
    state.currentSetupTaskId = null;
    persistMinimalContext();
    renderSetupWorkbench();
    if (message) showMessage(message);
    return null;
  }
  return focusSetupTask(nextId, { message: message || "已切换到下一家待配置店铺。" });
}

// ===== 窗口截图 =====

async function refreshManagedPages() {}

async function refreshWindows() {
  const windows = await api("/api/windows");
  $("windowSelect").innerHTML = windows
    .map((item) => `<option value="${item.hwnd}" data-title="${escapeHtml(item.title)}">${escapeHtml(item.title)} (${item.width}x${item.height})</option>`)
    .join("");
  showMessage(`找到 ${windows.length} 个窗口`);
}

async function previewWindow() {
  const hwnd = Number($("windowSelect").value);
  if (!hwnd) {
    showMessage("请先选择窗口", true);
    return;
  }
  const preview = await api("/api/window-preview", { method: "POST", body: JSON.stringify({ hwnd }) });
  const title = $("windowSelect").selectedOptions[0]?.dataset.title || "";
  $("windowKeyword").value = title;
  state.preview = preview;
  state.selection = null;
  state.currentPreviewSource = { capture_mode: "window_capture", hwnd, window_keyword: title };
  renderPreviewImage(preview);
  showMessage(`窗口预览已生成：${preview.width}x${preview.height}`);
}

function clearPreview() {
  state.preview = null;
  state.selection = null;
  state.currentPreviewSource = null;
  $("previewImage").removeAttribute("src");
  $("previewImage").style.display = "none";
  $("selectionBox").style.display = "none";
  $("ocrResult").textContent = "";
}

function renderPreviewImage(preview) {
  const image = $("previewImage");
  image.src = preview.image;
  image.style.display = "block";
  $("selectionBox").style.display = "none";
  $("coordX").textContent = "-";
  $("coordY").textContent = "-";
  $("coordW").textContent = "-";
  $("coordH").textContent = "-";
  $("ocrResult").textContent = "";
}

function updateSelectionBox() {
  const image = $("previewImage");
  const box = $("selectionBox");
  if (!state.selection || !image.src) {
    box.style.display = "none";
    return;
  }
  const { x, y, width, height } = state.selection;
  box.style.display = "block";
  box.style.left = `${image.offsetLeft + x}px`;
  box.style.top = `${image.offsetTop + y}px`;
  box.style.width = `${width}px`;
  box.style.height = `${height}px`;
  const ratio = selectionRatios();
  $("coordX").textContent = Math.round(ratio.x_ratio * state.preview.width);
  $("coordY").textContent = Math.round(ratio.y_ratio * state.preview.height);
  $("coordW").textContent = Math.round(ratio.width_ratio * state.preview.width);
  $("coordH").textContent = Math.round(ratio.height_ratio * state.preview.height);
}

function selectionRatios() {
  const image = $("previewImage");
  const naturalW = image.naturalWidth || image.clientWidth;
  const naturalH = image.naturalHeight || image.clientHeight;
  const scaleX = naturalW / image.clientWidth;
  const scaleY = naturalH / image.clientHeight;
  const sel = state.selection;
  const x = sel.x * scaleX;
  const y = sel.y * scaleY;
  const width = sel.width * scaleX;
  const height = sel.height * scaleY;
  return {
    x_ratio: x / naturalW,
    y_ratio: y / naturalH,
    width_ratio: width / naturalW,
    height_ratio: height / naturalH,
  };
}

function savedSelectionRatios(task = {}) {
  return {
    x_ratio: Number(task.x_ratio || 0),
    y_ratio: Number(task.y_ratio || 0),
    width_ratio: Number(task.width_ratio || 0),
    height_ratio: Number(task.height_ratio || 0),
  };
}

function hasUsableSelection() {
  if (!state.preview || !state.selection) return false;
  const image = $("previewImage");
  const scaleX = (image.naturalWidth || image.clientWidth) / image.clientWidth;
  const scaleY = (image.naturalHeight || image.clientHeight) / image.clientHeight;
  return state.selection.width * scaleX >= 40 && state.selection.height * scaleY >= 24;
}

// ===== OCR 测试与任务保存 =====

async function testOcr() {
  if (!hasUsableSelection()) {
    showMessage("选区太小，请拖拽框住完整 GMV 数字区域", true);
    return;
  }
  const source = state.currentPreviewSource || {};
  const task = currentSetupTask() || findTaskById(state.editingTaskId) || {};
  const result = await api("/api/test-ocr", {
    method: "POST",
    body: JSON.stringify({
      task_id: task.id || state.editingTaskId || null,
      commit_result: Boolean(task.id || state.editingTaskId),
      capture_mode: source.capture_mode || "remote_edge",
      hwnd: source.hwnd || null,
      page_id: source.page_id || "",
      edge_session_id: source.edge_session_id || $("bindSessionSelect")?.value || currentSetupTask()?.edge_session_id || "default_real_edge",
      preview_image: state.preview?.image || "",
      ...selectionRatios(),
      safety_margin: Number($("safetyMargin").value || 0.05),
      keyword_hint: $("keywordHint").value,
    }),
  });
  const engines = result.engines ? Object.entries(result.engines).filter(([, ok]) => ok).map(([name]) => name).join(", ") : "-";
  const sources = [...new Set((result.details || []).filter((item) => item.text).map((item) => `${item.engine}/${item.variant}`))].join(", ") || "-";
  $("ocrResult").innerHTML = `
    <b>最终纯数字：</b>${result.suggested_value ? String(result.suggested_value) : "未识别"}\n
    <b>建议候选来源：</b>${result.suggested_candidate ? `${result.suggested_candidate.engine || "-"} / ${result.suggested_candidate.variant || "-"} / ${result.suggested_candidate.source_kind || "-"} / fix=${result.suggested_candidate.correction_count || 0}` : "-"}\n
    <b>已同步任务：</b>${result.committed ? "是，任务管理已更新" : "否"}\n
    <b>实际 OCR 裁剪：</b>${result.crop_rect ? `x:${result.crop_rect.x} y:${result.crop_rect.y} w:${result.crop_rect.width} h:${result.crop_rect.height}` : "-"}\n
    ${result.image ? `<img class="ocr-crop-preview" src="${result.image}" alt="实际 OCR 裁剪区域" />` : ""}
    <b>可用引擎：</b>${escapeHtml(engines)}\n
    <b>命中来源：</b>${escapeHtml(sources)}\n
    <b>OCR 原文：</b>${escapeHtml(result.ocr_text || "-")}\n
    <b>候选纯数字：</b>\n${result.candidates.map((c) => `${c.value}  score=${c.score}  ${c.reason}  [${c.engine || "-"} / ${c.variant || "-"} / ${c.source_kind || "-"} / fix=${c.correction_count || 0}]`).join("\n") || "-"}
  `;
  if (result.committed) {
    await loadTasks();
    showMessage("测试识别完成，任务管理金额已同步更新。");
  } else {
    showMessage(result.suggested_value ? "测试识别完成，但未绑定到可写入任务。" : "测试识别完成，未识别到可同步金额。", !result.suggested_value);
  }
}

async function saveTask() {
  const valueSource = selectedValueSource();
  if (valueSource !== "screen_readonly" && !hasUsableSelection()) {
    showMessage("请先截取预览并框选 GMV 区域", true);
    return;
  }
  const source = state.currentPreviewSource || {};
  const currentTask = currentSetupTask() || findTaskById(state.editingTaskId) || {};
  const binding = currentRemoteBindingContext(currentTask);
  const shopConfig = shopConfigForTask(currentTask);
  const resolvedPlatform = String(shopConfig?.platform || currentTask.platform || $("platform").value || "").trim();
  const resolvedShopName = String(shopConfig?.shop_name || currentTask.shop_name || $("shopName").value || "").trim();
  if (!resolvedPlatform || !resolvedShopName) {
    showMessage("当前任务未匹配到 shop.csv 的 platform / shop_name，禁止保存。", true);
    return;
  }
  if (valueSource === "screen_readonly" && !supportsScreenReadonlyPlatform(resolvedPlatform)) {
    showMessage(screenReadonlyUnsupportedMessage(resolvedPlatform), true);
    return;
  }
  if (!binding.page_id && valueSource === "screen_readonly") {
    showMessage(`大屏只读模式也必须先绑定真实业务页，系统之后才能持续等待${screenReadonlyTargetPageHint(resolvedPlatform)}并读取${screenReadonlyMetricLabel(resolvedPlatform)}。`, true);
    return;
  }
  const ratios = valueSource === "screen_readonly" ? savedSelectionRatios(currentTask) : selectionRatios();
  const payload = {
    id: state.editingTaskId,
    capture_mode: "remote_edge",
    value_source: valueSource,
    page_id: binding.page_id || source.page_id || "",
    page_url: binding.page_url || source.page_url || "",
    target_page_url: currentTask.target_page_url || currentTask.page_url || "",
    page_title: binding.page_title || source.page_title || "",
    browser_profile: binding.edge_session_id || source.edge_session_id || "default",
    edge_session_id: binding.edge_session_id || source.edge_session_id || $("bindSessionSelect")?.value || currentSetupTask()?.edge_session_id || "default_real_edge",
    platform: resolvedPlatform,
    shop_name: resolvedShopName,
    window_keyword: source.window_keyword || $("windowKeyword").value || "",
    keyword_hint: $("keywordHint").value || "",
    interval_seconds: currentGlobalIntervalSeconds(),
    enabled: true,
    base_width: state.preview?.width || currentTask.base_width || 0,
    base_height: state.preview?.height || currentTask.base_height || 0,
    x: state.preview ? Math.round(ratios.x_ratio * state.preview.width) : Number(currentTask.x || 0),
    y: state.preview ? Math.round(ratios.y_ratio * state.preview.height) : Number(currentTask.y || 0),
    width: state.preview ? Math.round(ratios.width_ratio * state.preview.width) : Number(currentTask.width || 0),
    height: state.preview ? Math.round(ratios.height_ratio * state.preview.height) : Number(currentTask.height || 0),
    ...ratios,
    safety_margin: Number($("safetyMargin").value || 0.05),
    confirm_count: Number($("confirmCount").value || 2),
    target: Number(currentTask.target || 0),
    sort_order: Number(currentTask.sort_order || 0),
  };
  const saved = await api("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
  await loadTasks();
  state.currentSetupTaskId = saved.id;
  persistMinimalContext();
  buildSetupSummary();
  const nextTask = await focusNextPendingTask({
    message: state.setupQueue.length
      ? `任务已保存：${saved.shop_name}，已切换到下一家待配置店铺。`
      : `任务已保存：${saved.shop_name}。当前没有待处理店铺。`,
  });
  if (!nextTask) {
    const latest = findTaskById(saved.id);
    if (latest) {
      await loadTaskIntoConfig(latest, {
        message: `任务已保存：${saved.shop_name}。当前没有待处理店铺。`,
        keepPreview: false,
        syncContext: true,
      });
    }
  }
}

async function loadTasks() {
  const snapshot = await api("/api/tasks");
  renderSnapshot(snapshot);
  return snapshot;
}

async function loadShopConfigs() {
  state.shopConfigs = await api("/api/shops");
  buildSetupSummary();
  renderSetupWorkbench();
}

async function loadTaskIntoConfig(task, options = {}) {
  if (!task) return;
  const { message = "", keepPreview = false, syncContext = false } = options;
  const shopConfig = shopConfigForTask(task);
  state.editingTaskId = task.id;
  state.currentSetupTaskId = task.id;
  persistMinimalContext();
  $("captureMode").value = "remote_edge";
  $("platform").value = shopConfig?.platform || task.platform || "";
  $("shopName").value = shopConfig?.shop_name || task.shop_name || "";
  $("keywordHint").value = task.keyword_hint || "";
  $("confirmCount").value = task.confirm_count || 2;
  $("safetyMargin").value = Math.min(Number(task.safety_margin || 0.05), 0.08);
  $("windowKeyword").value = task.window_keyword || "";
  resetBindCandidates(task.id);
  state.selectedBindPageId = task.page_id || "";
  if (!keepPreview) {
    clearPreview();
  }
  switchView("config");
  if (syncContext) {
    await syncTaskContext(task, { refreshPages: task.capture_mode === "remote_edge", preloadCandidates: task.capture_mode === "remote_edge" });
  }
  renderSetupWorkbench();
  showMessage(message || "已载入当前店铺，请继续扫描、预览并完成框选保存。");
  syncValueSourceSelection(task, { force: true });
  renderSetupWorkbench();
}

// ===== 扫描并绑定 =====

function currentBindSessionId() {
  const preferred = $("bindSessionSelect")?.value || state.lastBindSessionId || currentSetupTask()?.edge_session_id || "";
  if ($("bindSessionSelect") && preferred) $("bindSessionSelect").value = preferred;
  return preferred;
}

async function scanBind() {
  const task = currentSetupTask();
  const sessionId = currentBindSessionId();
  const table = $("bindTable");
  const confirmBtn = $("confirmBind");
  if (!sessionId) {
    table.innerHTML = "<div style='color:var(--bad)'>请为当前店铺选择一个 Edge 会话。</div>";
    return { status: "missing_session" };
  }
  if (!task) {
    table.innerHTML = "<div style='color:var(--bad)'>请从任务管理进入当前店铺。</div>";
    return { status: "no_task" };
  }
  state.lastBindSessionId = sessionId;
  persistMinimalContext();
  table.innerHTML = "<div style='color:var(--muted)'>正在扫描当前会话页签...</div>";
  confirmBtn.style.display = "none";
  resetBindCandidates(task?.id);
  try {
    const result = await api(`/api/tasks/${encodeURIComponent(task.id)}/page-candidates?session_id=${encodeURIComponent(sessionId)}`);
    return applyBindCandidatesResult(result, task, { silent: false, scanned: true });
  } catch (err) {
    const code = apiErrorCode(err);
    const payload = parseApiErrorPayload(err);
    const detailPayload = payload?.detail || {};
    if (["edge_session_not_ready", "edge_debug_unavailable", "edge_debug_disconnected", "edge_session_not_found"].includes(code)) {
      const title = task
        ? `当前店铺 ${task.shop_name} 的调试控制链路未恢复`
        : "当前 Edge 调试控制链路未恢复";
      const detail = detailPayload.recovery_hint
        || "当前店铺登录态/Profile 可能仍在，但调试端口或自动控制连接还未恢复。请先去“任务管理”点击“显示Edge”或“启动Edge”，确认正确后台页已经打开，再回来重新扫描。";
      setSetupRecovery(task, "session_unavailable", detail, "当前不是 session 丢失，而是控制链路尚未恢复，暂时无法扫描候选页面。");
      table.innerHTML = renderBindRecoveryNotice({ title, detail });
      showMessage(detail, true);
      renderBindContext(task);
      return { status: "session_unavailable", task };
    }
    if (code === "edge_action_timeout" || code === "list_pages_failed") {
      const stageText = detailPayload.stage ? `当前阶段：${detailPayload.stage}。` : "";
      const detail = detailPayload.recovery_hint
        || `当前会话页签扫描超时或卡住。${stageText}请先去“任务管理”关闭并重新显示当前店铺 Edge，再回来重新扫描。`;
      setSetupRecovery(task, "session_timeout", detail, "当前不是会话未启动，而是页签扫描过程发生阻塞。");
      table.innerHTML = renderBindRecoveryNotice({
        title: task ? `当前店铺 ${task.shop_name} 的页签扫描超时` : "当前会话页签扫描超时",
        detail,
      });
      showMessage(detail, true);
      renderBindContext(task);
      return { status: "timeout", task };
    }
    table.innerHTML = `<div style='color:var(--bad)'>${escapeHtml(parseApiError(err))}</div>`;
    return { status: "error", task };
  }
}

async function confirmBind() {
  const task = currentSetupTask();
  const sessionId = $("bindSessionSelect").value;
  const pageId = state.selectedBindPageId;
  const page = selectedBindPageInfo();
  if (!task || !pageId || !page) {
    showMessage("请先从当前会话页签列表里选择一个页面。", true);
    return;
  }
  try {
    const saved = await api(`/api/tasks/${encodeURIComponent(task.id)}/rebind-page`, {
      method: "POST",
      body: JSON.stringify({
        page_id: pageId,
        page_url: page.url || "",
        page_title: page.title || "",
        edge_session_id: sessionId,
        capture_mode: "remote_edge",
      }),
    });
    await loadTasks();
    const latest = findTaskById(saved.id || task.id);
    if (latest) {
      await focusSetupTask(latest.id, { message: `已绑定当前任务页签：${page.title || page.url || page.page_id}`, keepPreview: false });
      if (latest.page_id) {
        try {
          const preview = await previewRemotePage();
          if (preview?.image) {
            showMessage("当前页签已绑定，预览已生成。请直接框选 GMV 区域，再测试并保存。");
          } else {
            showMessage("当前页签已绑定，但预览未成功生成。请先检查步骤 1 的提示，再重新预览。", true);
          }
        } catch (err) {
          showMessage(`当前页签已绑定，但自动预览失败：${parseApiError(err)}`, true);
        }
      }
    } else {
      showMessage("当前页签已绑定，请继续完成当前店铺标定。");
    }
  } catch (err) {
    showMessage(parseApiError(err), true);
  }
}

async function resumeAfterLogin() {
  const task = currentSetupTask();
  if (!task || task.capture_mode !== "remote_edge") {
    showMessage("当前店铺不是真实 Edge 任务，不能执行登录后自动继续。", true);
    return;
  }
  if (!task.target_page_url) {
    showMessage("当前任务缺少目标业务页 URL，无法自动继续。", true);
    return;
  }
  const button = $("resumeAfterLogin");
  if (button) {
    button.disabled = true;
    button.textContent = "正在打开业务页并自动继续...";
  }
  showMessage(`正在为 ${task.shop_name} 打开目标业务页并自动继续，请稍候...`);
  try {
    const result = await api(`/api/tasks/${encodeURIComponent(task.id)}/resume-after-login`, {
      method: "POST",
    });
    await loadTasks();
    const latest = findTaskById(task.id);
    if (!latest) {
      showMessage(result.message || "自动继续已执行，但当前任务未能刷新出来。", !result.ok);
      return;
    }
    await focusSetupTask(latest.id, {
      message: result.message || latest.last_reason || "当前店铺已自动继续，请检查最新状态。",
      keepPreview: false,
    });
    if (latest.status === "edge_target_page_ready" && latest.page_id) {
      try {
        const preview = await previewRemotePage();
        if (preview?.image) {
          showMessage("目标业务页已打开并恢复绑定，预览也已生成。请直接框选 GMV 区域。");
        } else {
          showMessage("目标业务页已恢复绑定，但预览未成功生成。请先检查步骤 1 的提示，再重新预览。", true);
        }
      } catch (err) {
        showMessage(`目标业务页已恢复并绑定，但自动预览失败：${parseApiError(err)}`, true);
      }
      return;
    }
    showMessage(result.message || latest.last_reason || "系统已尝试自动继续，但当前还未进入目标业务页。", true);
  } catch (err) {
    showMessage(parseApiError(err), true);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "已登录，打开业务页并自动继续";
    }
  }
}

function resetCurrentSetup() {
  const task = currentSetupTask();
  if (!task) {
    showMessage("当前没有待处理店铺。", true);
    return;
  }
  try {
    api(`/api/tasks/${encodeURIComponent(task.id)}/reset-calibration`, { method: "POST" }).catch(() => {});
  } catch {
  }
  clearPreview();
  resetBindCandidates(task.id);
  state.selectedBindPageId = "";
  renderBindContext(task);
  renderSetupWorkbench();
  showMessage(`已清空 ${task.shop_name} 的标定数据。`);
}

// ===== EOF =====
