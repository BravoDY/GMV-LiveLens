// ===== 全局状态 =====

const state = {
  mode: window.location.pathname === "/dashboard" ? "public_dashboard" : "internal",
  snapshot: { tasks: [], summary: {} },
  preview: null,
  selection: null,
  editingTaskId: null,
  currentPreviewSource: null,
  platformFilter: "all",
  statusFilter: "all",
  edgeSessions: [],
  shopConfigs: [],
  setupQueue: [],
  currentSetupTaskId: null,
  setupSummary: { total: 0, pendingBind: 0, pendingCalibrate: 0, completed: 0 },
  lastBindSessionId: "",
  setupRecovery: null,
  bindCandidates: null,
  selectedBindPageId: "",
  expandedTaskIdentities: {},
  screenReadonly: {
    running: false,
    timerId: null,
    records: [],
    latest: null,
    lastError: "",
  },
};

state.publicDashboardMode = state.mode === "public_dashboard";

const MIN_CONTEXT_STORAGE_KEY = "gmv-live-lens:min-context:v1";
const API_TOKEN_STORAGE_KEY = "gmv-live-lens:api-token:v1";
const IS_PUBLIC_DASHBOARD = window.location.pathname === "/dashboard";
state.publicDashboardMode = IS_PUBLIC_DASHBOARD;

function currentApiToken() {
  try {
    return window.localStorage.getItem(API_TOKEN_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

function setApiToken(token) {
  try {
    const value = String(token || "").trim();
    if (value) window.localStorage.setItem(API_TOKEN_STORAGE_KEY, value);
    else window.localStorage.removeItem(API_TOKEN_STORAGE_KEY);
  } catch (error) {
    console.warn("API Token 保存失败", error);
  }
}

function normalizeStoredTaskId(value) {
  const id = Number(value);
  return Number.isFinite(id) && id > 0 ? id : null;
}

function normalizeStoredSessionId(value) {
  return String(value || "").trim();
}

function persistMinimalContext() {
  try {
    const payload = {
      currentSetupTaskId: normalizeStoredTaskId(state.currentSetupTaskId),
      lastBindSessionId: normalizeStoredSessionId(state.lastBindSessionId),
      savedAt: new Date().toISOString(),
    };
    if (!payload.currentSetupTaskId && !payload.lastBindSessionId) {
      window.localStorage.removeItem(MIN_CONTEXT_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(MIN_CONTEXT_STORAGE_KEY, JSON.stringify(payload));
  } catch (error) {
    console.warn("最小上下文持久化失败", error);
  }
}

function restoreMinimalContext() {
  const result = {
    attempted: false,
    restoredTaskId: null,
    restoredSessionId: "",
    failed: false,
    reason: "",
  };
  try {
    const raw = window.localStorage.getItem(MIN_CONTEXT_STORAGE_KEY);
    if (!raw) return result;
    result.attempted = true;
    const parsed = JSON.parse(raw);
    const restoredTaskId = normalizeStoredTaskId(parsed?.currentSetupTaskId);
    const restoredSessionId = normalizeStoredSessionId(parsed?.lastBindSessionId);
    if (restoredTaskId) {
      state.currentSetupTaskId = restoredTaskId;
      state.editingTaskId = restoredTaskId;
      result.restoredTaskId = restoredTaskId;
    }
    if (restoredSessionId) {
      state.lastBindSessionId = restoredSessionId;
      result.restoredSessionId = restoredSessionId;
    }
    if (!restoredTaskId && !restoredSessionId) {
      window.localStorage.removeItem(MIN_CONTEXT_STORAGE_KEY);
    }
    return result;
  } catch (error) {
    result.attempted = true;
    result.failed = true;
    result.reason = String(error?.message || "未知错误");
    console.warn("最小上下文恢复失败", error);
    return result;
  }
}

state.minimalContextRestore = restoreMinimalContext();

// ===== 基础工具 =====

const $ = (id) => document.getElementById(id);
const fmtMoney = (value) => `¥${Number(value || 0).toLocaleString("zh-CN")}`;
const fmtTime = (value) => value || "-";
const escapeHtml = (text) =>
  String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

// ===== 常量映射 =====

const modeLabelMap = {
  managed_browser: "托管页面",
  remote_edge: "真实Edge",
  window_capture: "窗口截图",
  screen_region: "整屏区域",
};

const taskStatusMeta = {
  ok: { label: "正常", tone: "ok" },
  pending_confirm: { label: "待确认", tone: "pending" },
  suspect: { label: "疑似异常", tone: "bad" },
  parse_failed: { label: "识别失败", tone: "bad" },
  readonly_waiting: { label: "等待大屏", tone: "pending" },
  readonly_failed: { label: "只读失败", tone: "bad" },
  window_not_found: { label: "窗口未找到", tone: "bad" },
  needs_recalibration: { label: "需要重标", tone: "bad" },
  page_not_found: { label: "页面未找到", tone: "bad" },
  remote_page_not_found: { label: "真实 Edge 页面已失效", tone: "bad" },
  edge_session_not_found: { label: "Edge 会话未找到", tone: "bad" },
  edge_session_not_ready: { label: "调试链路未恢复", tone: "bad" },
  edge_debug_unavailable: { label: "调试端口未接通", tone: "bad" },
  edge_debug_disconnected: { label: "自动连接未恢复", tone: "bad" },
  edge_recovered: { label: "会话已恢复", tone: "pending" },
  edge_login_page_bound: { label: "已恢复到登录页", tone: "bad" },
  edge_page_bound: { label: "已恢复到其它页", tone: "pending" },
  edge_target_page_ready: { label: "已恢复到业务页", tone: "ok" },
};

const platformMeta = {
  天猫: { label: "天猫", icon: "猫", color: "var(--color-taobao)", glow: "rgba(255, 59, 79, 0.22)" },
  京东: { label: "京东", icon: "京", color: "var(--color-jd)", glow: "rgba(255, 107, 24, 0.22)" },
  得物: { label: "得物", icon: "得", color: "var(--color-dewu)", glow: "rgba(53, 212, 127, 0.22)" },
  抖音: { label: "抖音", icon: "抖", color: "var(--color-douyin)", glow: "rgba(24, 199, 243, 0.22)" },
  唯品会: { label: "唯品会", icon: "唯", color: "var(--color-vip)", glow: "rgba(196, 92, 255, 0.22)" },
  其他平台: { label: "其他平台", icon: "其", color: "var(--color-other)", glow: "rgba(142, 160, 184, 0.22)" },
};

// ===== 辅助函数 =====

function normalizePlatform(platform) {
  return String(platform || "未知平台").trim();
}

function taskStatusInfo(status) {
  const key = String(status || "").trim();
  const meta = taskStatusMeta[key];
  if (meta) return { key, ...meta };
  return { key, label: key || "未知状态", tone: "neutral" };
}

function normalizeValueSourceKey(value) {
  const text = String(value || "").trim().toLowerCase();
  if (["screen_readonly", "page_readonly", "readonly"].includes(text)) return "screen_readonly";
  if (text === "manual") return "manual";
  return "ocr";
}

function valueSourceLabel(value) {
  const key = normalizeValueSourceKey(value);
  if (key === "screen_readonly") return "大屏只读";
  if (key === "manual") return "人工修正";
  return "OCR识别";
}

function taskRuntimeValueSource(task) {
  return normalizeValueSourceKey(task?.value_source || task?.last_value_source || "ocr");
}

function statusClassSuffix(value) {
  return String(value || "unknown").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-") || "unknown";
}

function showMessage(text, isError = false) {
  const el = $("configMessage");
  el.textContent = text;
  el.classList.toggle("bad-text", isError);
}

function parseApiError(error) {
  try {
    const parsed = JSON.parse(error.message);
    if (parsed?.success === false) {
      const requestId = parsed.request_id ? `（请求编号：${parsed.request_id}）` : "";
      return `${parsed.message || parsed.code || "接口请求失败"}${requestId}`;
    }
    if (typeof parsed.detail === "string") return parsed.detail;
    if (parsed.detail?.error) return parsed.detail.error;
    if (parsed.detail?.message) return parsed.detail.message;
    return JSON.stringify(parsed.detail || parsed);
  } catch {
    return error.message;
  }
}

function parseApiErrorPayload(error) {
  try {
    return JSON.parse(error?.message || "");
  } catch {
    return null;
  }
}

function apiErrorCode(error) {
  const payload = parseApiErrorPayload(error);
  if (typeof payload?.code === "string") return payload.code;
  const detail = payload?.detail;
  if (typeof detail?.reason_code === "string") return detail.reason_code;
  if (typeof detail?.code === "string") return detail.code;
  if (typeof detail?.error === "string") return detail.error;
  if (typeof payload?.error === "string") return payload.error;
  return "";
}

function apiRequestId(error) {
  const payload = parseApiErrorPayload(error);
  return String(payload?.request_id || payload?.detail?.request_id || "");
}

async function api(path, options = {}) {
  const { timeoutMs = 0, actionName = "", ...fetchOptions } = options;
  const controller = timeoutMs > 0 ? new AbortController() : null;
  const timeoutId = controller
    ? window.setTimeout(() => controller.abort(`timeout:${actionName || path}`), timeoutMs)
    : 0;
  try {
    const token = currentApiToken();
    const headers = {
      "Content-Type": "application/json",
      ...(token ? { "X-API-Token": token } : {}),
      ...(fetchOptions.headers || {}),
    };
    const response = await fetch(path, {
      ...fetchOptions,
      headers,
      signal: controller ? controller.signal : fetchOptions.signal,
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.json();
  } catch (error) {
    if (controller && controller.signal.aborted) {
      const detail = {
        error: `${actionName || path} 请求超时`,
        reason_code: "edge_action_timeout",
        action: actionName || path,
        timeout_ms: timeoutMs,
      };
      throw new Error(JSON.stringify({ detail }));
    }
    throw error;
  } finally {
    if (timeoutId) window.clearTimeout(timeoutId);
  }
}

function switchView(view) {
  document.querySelectorAll(".view").forEach((el) => el.classList.toggle("active", el.id === view));
  document.querySelectorAll(".tab, .nav-item").forEach((el) => el.classList.toggle("active", el.dataset.view === view));
}

// ===== Edge 会话 API 封装 =====

async function callEdgeAction(path, { actionName, timeoutMs } = {}) {
  const ms = timeoutMs || 20_000;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), ms);
  try {
    const token = currentApiToken();
    const headers = { "Content-Type": "application/json" };
    if (token) headers["X-API-Token"] = token;
    const response = await fetch(path, {
      method: "POST",
      signal: controller.signal,
      headers,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const detail = { status: response.status, ...body };
      throw new Error(JSON.stringify({ detail }));
    }
    return await response.json();
  } catch (error) {
    if (error.name === "AbortError") {
      const detail = {
        error: `操作超时 (${ms / 1000}秒)`,
        reason_code: "edge_action_timeout",
        action: actionName || path,
        timeout_ms: ms,
      };
      throw new Error(JSON.stringify({ detail }));
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function startEdgeSession(sessionId, launchUrl = "") {
  const suffix = launchUrl ? `?launch_url=${encodeURIComponent(launchUrl)}` : "";
  return callEdgeAction(`/api/edge-sessions/${encodeURIComponent(sessionId)}/start${suffix}`, {
    actionName: "start_edge",
    timeoutMs: 18_000,
  });
}

async function showEdgeSession(sessionId, launchUrl = "") {
  const suffix = launchUrl ? `?launch_url=${encodeURIComponent(launchUrl)}` : "";
  try {
    return await callEdgeAction(`/api/edge-sessions/${encodeURIComponent(sessionId)}/show${suffix}`, {
      actionName: "show_edge",
      timeoutMs: 35_000,
    });
  } catch (error) {
    const message = String(error?.message || "");
    if (!message.includes("404")) throw error;
    const legacy = await startEdgeSession(sessionId, launchUrl);
    const detail = '当前后端还是旧版本，已退回后台启动。请重启 GMV-LiveLens 服务后再使用“显示Edge”。';
    throw new Error(JSON.stringify({ detail, legacy }));
  }
}

async function startAndShowEdgeSession(sessionId, launchUrl = "") {
  // “启动Edge”在产品语义上是启动并显示；后端 show 单入口会在未运行时可见启动，
  // 避免前端先 /start 再 /show 造成双窗口和重复标签。
  return showEdgeSession(sessionId, launchUrl);
}

async function hideEdgeSession(sessionId) {
  return callEdgeAction(`/api/edge-sessions/${encodeURIComponent(sessionId)}/hide`, {
    actionName: "hide_edge",
    timeoutMs: 22_000,
  });
}

async function closeEdgeSession(sessionId) {
  return callEdgeAction(`/api/edge-sessions/${encodeURIComponent(sessionId)}/close`, {
    actionName: "close_edge",
    timeoutMs: 35_000,
  });
}

async function callPlatformEdgeAction(platform, action) {
  const encoded = encodeURIComponent(platform);
  const pathMap = {
    launch: `/api/platforms/${encoded}/launch-edge`,
    show: `/api/platforms/${encoded}/show-edge`,
    hide: `/api/platforms/${encoded}/hide-edge`,
    close: `/api/platforms/${encoded}/close-edge`,
  };
  const path = pathMap[action];
  if (!path) throw new Error(`unknown_platform_edge_action:${action}`);
  return callEdgeAction(path, { actionName: `platform_${action}_edge`, timeoutMs: 45_000 });
}

// ===== 数据聚合与排序 =====

function liveTasks() {
  return (state.snapshot.tasks || [])
    .filter((task) => task.enabled)
    .map((task) => {
      const config = shopConfigForTask(task);
      if (!config) return null;
      return {
        ...task,
        platform: config.platform,
        brand: config.brand || task.brand || "",
        shop_name: config.shop_name,
        sort_order: Number(config.sort_order ?? task.sort_order ?? 0),
        edge_session_id: config.edge_session_id || task.edge_session_id,
      };
    })
    .filter(Boolean);
}

function aggregatePlatforms(tasks) {
  const groups = new Map();
  for (const task of tasks) {
    const key = normalizePlatform(task.platform);
    if (!groups.has(key)) {
      groups.set(key, { key, total: 0, tasks: [], meta: platformMeta[key] || platformMeta["其他平台"], sort_order: task.sort_order || 0 });
    }
    const group = groups.get(key);
    group.total += Number(task.last_trusted_value || 0);
    group.tasks.push(task);
  }
  return Array.from(groups.values()).sort((a, b) => a.sort_order - b.sort_order);
}

function platformOrder() {
  const order = [];
  for (const shop of state.shopConfigs || []) {
    if (shop.platform && !order.includes(shop.platform)) order.push(shop.platform);
  }
  return order;
}

function shopSortIndex(task) {
  const index = (state.shopConfigs || []).findIndex((shop) => shop.platform === task.platform && shop.shop_name === task.shop_name);
  return index >= 0 ? index : Number.MAX_SAFE_INTEGER;
}

function sortByConfiguredOrder(tasks) {
  const platforms = platformOrder();
  return [...tasks].sort((a, b) => {
    const pa = platforms.includes(a.platform) ? platforms.indexOf(a.platform) : Number.MAX_SAFE_INTEGER;
    const pb = platforms.includes(b.platform) ? platforms.indexOf(b.platform) : Number.MAX_SAFE_INTEGER;
    if (pa !== pb) return pa - pb;
    const sa = shopSortIndex(a);
    const sb = shopSortIndex(b);
    if (sa !== sb) return sa - sb;
    return String(a.shop_name || "").localeCompare(String(b.shop_name || ""), "zh-CN");
  });
}

// ===== 任务/店铺查找 =====

function findTaskById(taskId) {
  return (state.snapshot.tasks || []).find((task) => task.id === taskId) || null;
}

function normalizeIdentityText(value) {
  return String(value || "").trim();
}

function findTaskForShopConfig(config) {
  if (!config) return null;
  const resolvedPlatform = normalizeIdentityText(config.platform);
  const resolvedShopName = normalizeIdentityText(config.shop_name);
  const exactTask = (state.snapshot.tasks || []).find((task) => (
    normalizeIdentityText(task.platform) === resolvedPlatform
    && normalizeIdentityText(task.shop_name) === resolvedShopName
  ));
  if (exactTask) return exactTask;
  const resolvedSessionId = normalizeIdentityText(config.edge_session_id);
  if (!resolvedSessionId) return null;
  return (state.snapshot.tasks || []).find((task) => (
    normalizeIdentityText(task.edge_session_id) === resolvedSessionId
  )) || null;
}

function findTaskByIdentity(platform, shopName) {
  const resolvedPlatform = normalizeIdentityText(platform);
  const resolvedShopName = normalizeIdentityText(shopName);
  const exactTask = (state.snapshot.tasks || []).find((task) => (
    normalizeIdentityText(task.platform) === resolvedPlatform
    && normalizeIdentityText(task.shop_name) === resolvedShopName
  ));
  if (exactTask) return exactTask;
  const config = (state.shopConfigs || []).find((item) => (
    normalizeIdentityText(item.platform) === resolvedPlatform
    && normalizeIdentityText(item.shop_name) === resolvedShopName
  ));
  return findTaskForShopConfig(config);
}

function upsertTaskIntoSnapshot(taskLike) {
  if (!taskLike || typeof taskLike !== "object") return null;
  const snapshot = state.snapshot || { tasks: [] };
  const tasks = [...(snapshot.tasks || [])];
  const taskId = Number(taskLike.id || 0);
  let index = taskId ? tasks.findIndex((item) => Number(item.id || 0) === taskId) : -1;
  if (index < 0) {
    index = tasks.findIndex((item) => (
      String(item.platform || "").trim() === String(taskLike.platform || "").trim()
      && String(item.shop_name || "").trim() === String(taskLike.shop_name || "").trim()
    ));
  }
  if (index >= 0) {
    tasks[index] = { ...tasks[index], ...taskLike };
  } else {
    tasks.push(taskLike);
    index = tasks.length - 1;
  }
  state.snapshot = { ...snapshot, tasks };
  return tasks[index] || null;
}

function currentSetupTask() {
  return findTaskById(state.currentSetupTaskId);
}

function shopConfigForTask(task) {
  if (!task) return null;
  const resolvedPlatform = normalizeIdentityText(task.platform);
  const resolvedShopName = normalizeIdentityText(task.shop_name);
  const exactConfig = (state.shopConfigs || []).find((item) => (
    normalizeIdentityText(item.platform) === resolvedPlatform
    && normalizeIdentityText(item.shop_name) === resolvedShopName
  ));
  if (exactConfig) return exactConfig;
  const resolvedSessionId = normalizeIdentityText(task.edge_session_id);
  if (!resolvedSessionId) return null;
  return (state.shopConfigs || []).find((item) => (
    normalizeIdentityText(item.edge_session_id) === resolvedSessionId
  )) || null;
}

function edgeSessionById(sessionId) {
  const resolved = String(sessionId || "").trim();
  if (!resolved) return null;
  return (state.edgeSessions || []).find((item) => item.session_id === resolved) || null;
}

function latestConfiguredSessionIdForTask(task) {
  return String(shopConfigForTask(task)?.edge_session_id || "").trim();
}

function edgeSessionOptionLabel(session, suffix = "") {
  if (!session) return suffix || "未知会话";
  const base = `${session.platform || "其他平台"} / ${session.shop_name || session.name || session.session_id}（端口 ${session.debug_port}）`;
  return suffix ? `${base} · ${suffix}` : base;
}

function bindSessionCandidatesForTask(task = currentSetupTask()) {
  const sessions = (state.edgeSessions || []).filter((session) => session.session_id !== "default_real_edge");
  if (!task) {
    return sessions.map((session) => ({
      ...session,
      optionLabel: edgeSessionOptionLabel(session),
      optionSource: "all_sessions",
      sourceText: "全部店铺会话",
    }));
  }
  const latestSessionId = latestConfiguredSessionIdForTask(task);
  const taskSessionId = String(task.edge_session_id || "").trim();
  const candidateIds = [];
  const pushCandidate = (sessionId) => {
    const resolved = String(sessionId || "").trim();
    if (!resolved || candidateIds.includes(resolved)) return;
    candidateIds.push(resolved);
  };
  pushCandidate(latestSessionId);
  pushCandidate(taskSessionId);
  const candidates = candidateIds
    .map((sessionId) => edgeSessionById(sessionId))
    .filter(Boolean)
    .map((session) => {
      const isLatestConfigured = session.session_id === latestSessionId;
      const isTaskBound = session.session_id === taskSessionId;
      const isHistorical = isTaskBound && latestSessionId && taskSessionId && latestSessionId !== taskSessionId;
      return {
        ...session,
        optionLabel: edgeSessionOptionLabel(session, isHistorical ? "历史绑定" : (isLatestConfigured ? "当前店铺配置" : "")),
        optionSource: isHistorical ? "task_bound_historical" : (isLatestConfigured ? "latest_config" : "task_bound"),
        sourceText: isHistorical ? "当前任务历史绑定会话" : (isLatestConfigured ? "当前店铺最新配置会话" : "当前任务绑定会话"),
      };
    });
  if (candidates.length) {
    return candidates;
  }
  return sessions.map((session) => ({
    ...session,
    optionLabel: edgeSessionOptionLabel(session),
    optionSource: "fallback_all",
    sourceText: "未匹配到当前店铺专属会话，回退到全部会话",
  }));
}

function bindSessionResolution(task = currentSetupTask(), sessionId = "") {
  const currentTask = task || null;
  const latestSessionId = latestConfiguredSessionIdForTask(currentTask);
  const taskSessionId = String(currentTask?.edge_session_id || "").trim();
  const selectValue = String($("bindSessionSelect")?.value || "").trim();
  const lastSessionId = String(state.lastBindSessionId || "").trim();
  const selectedSessionId = String(
    sessionId
    || taskSessionId
    || latestSessionId
    || selectValue
    || lastSessionId
    || ""
  ).trim();
  const selectedSession = edgeSessionById(selectedSessionId);
  const latestSession = edgeSessionById(latestSessionId);
  const taskSession = edgeSessionById(taskSessionId);
  const candidates = bindSessionCandidatesForTask(currentTask);
  const fallbackAll = candidates.some((item) => item.optionSource === "fallback_all");
  const selectedCandidate = candidates.find((item) => item.session_id === selectedSessionId) || null;
  const latestMatchesTask = Boolean(latestSessionId && taskSessionId && latestSessionId === taskSessionId);
  return {
    candidates,
    fallbackAll,
    selectedSessionId,
    selectedSession,
    selectedCandidate,
    latestSessionId,
    latestSession,
    taskSessionId,
    taskSession,
    latestMatchesTask,
    usesHistoricalTaskSession: Boolean(taskSessionId && latestSessionId && taskSessionId !== latestSessionId),
  };
}

function configuredSetupTasks() {
  const tasks = (state.snapshot.tasks || []).filter((task) => shopConfigForTask(task));
  return sortByConfiguredOrder(tasks);
}

function setupShopEntries() {
  return (state.shopConfigs || []).map((config) => {
    const task = findTaskForShopConfig(config);
    return { config, task };
  });
}

function currentRemoteBindingContext(task = currentSetupTask()) {
  const bindPayload = state.bindCandidates?.task?.id === task?.id ? state.bindCandidates : null;
  const bindTask = bindPayload?.task && bindPayload.task.id === task?.id ? bindPayload.task : null;
  const latestTask = bindTask || task || null;
  const currentBinding = bindPayload?.current_binding || null;
  const boundPage = bindPayload?.pages?.find((item) => item.is_current_bound) || null;
  return {
    task: latestTask,
    page_id: String(
      currentBinding?.page_id
      || boundPage?.page_id
      || latestTask?.page_id
      || state.currentPreviewSource?.page_id
      || ""
    ).trim(),
    page_url: String(
      currentBinding?.page_url
      || boundPage?.url
      || latestTask?.page_url
      || state.currentPreviewSource?.page_url
      || ""
    ).trim(),
    page_title: String(
      currentBinding?.page_title
      || boundPage?.title
      || latestTask?.page_title
      || state.currentPreviewSource?.page_title
      || ""
    ).trim(),
    edge_session_id: String(
      currentBinding?.edge_session_id
      || latestTask?.edge_session_id
      || state.currentPreviewSource?.edge_session_id
      || ""
    ).trim(),
  };
}

// ===== 配置进度计算 =====

function isApproximatelyEqual(a, b, epsilon = 0.0001) {
  return Math.abs(Number(a || 0) - Number(b || 0)) <= epsilon;
}

function isTaskUsingDefaultCalibration(task) {
  const config = shopConfigForTask(task);
  if (!task || !config) return false;
  return isApproximatelyEqual(task.x_ratio, config.x_ratio)
    && isApproximatelyEqual(task.y_ratio, config.y_ratio)
    && isApproximatelyEqual(task.width_ratio, config.width_ratio)
    && isApproximatelyEqual(task.height_ratio, config.height_ratio)
    && Number(task.x || 0) === Number(config.x || 0)
    && Number(task.y || 0) === Number(config.y || 0)
    && Number(task.width || 0) === Number(config.width || 0)
    && Number(task.height || 0) === Number(config.height || 0);
}

function setupStageMeta(task) {
  if (!task) return { key: "idle", label: "未开始", tone: "neutral" };
  if (task.capture_mode !== "remote_edge") return { key: "other", label: "兼容模式", tone: "neutral" };
  if (!task.page_id) return { key: "pending_bind", label: "待绑定", tone: "pending" };
  if (task.status === "edge_login_page_bound") return { key: "pending_login", label: "待登录", tone: "bad" };
  if (task.status === "edge_page_bound") return { key: "pending_target_page", label: "待切业务页", tone: "pending" };
  if (task.status === "edge_target_page_ready") {
    return isTaskUsingDefaultCalibration(task)
      ? { key: "pending_calibrate", label: "待标定", tone: "pending" }
      : { key: "completed", label: "已完成", tone: "ok" };
  }
  if (["remote_page_not_found", "edge_session_not_ready", "edge_debug_unavailable", "edge_debug_disconnected", "edge_session_not_found", "window_not_found"].includes(task.status)) {
    return { key: "pending_bind", label: "待绑定", tone: "pending" };
  }
  if (isTaskUsingDefaultCalibration(task)) return { key: "pending_calibrate", label: "待标定", tone: "pending" };
  return { key: "completed", label: "已完成", tone: "ok" };
}

function buildSetupSummary() {
  const entries = setupShopEntries();
  const summary = {
    total: (state.shopConfigs || []).length,
    pendingBind: 0,
    pendingCalibrate: 0,
    completed: 0,
  };
  const queueBuckets = {
    pending_bind: [],
    pending_login: [],
    pending_target_page: [],
    pending_calibrate: [],
  };
  for (const { task } of entries) {
    if (!task || task.capture_mode !== "remote_edge") continue;
    const stage = setupStageMeta(task);
    if (["pending_bind", "pending_login", "pending_target_page"].includes(stage.key)) {
      summary.pendingBind += 1;
      queueBuckets[stage.key].push(task.id);
    } else if (stage.key === "pending_calibrate") {
      summary.pendingCalibrate += 1;
      queueBuckets.pending_calibrate.push(task.id);
    } else if (stage.key === "completed") {
      summary.completed += 1;
    }
  }
  const queue = [
    ...queueBuckets.pending_bind,
    ...queueBuckets.pending_login,
    ...queueBuckets.pending_target_page,
    ...queueBuckets.pending_calibrate,
  ];
  state.setupSummary = summary;
  state.setupQueue = queue;
  return summary;
}

function updateSetupSummaryView() {
  const summary = state.setupSummary || { total: 0, pendingBind: 0, pendingCalibrate: 0, completed: 0 };
  if ($("setupTotal")) $("setupTotal").textContent = String(summary.total || 0);
  if ($("setupPendingBind")) $("setupPendingBind").textContent = String(summary.pendingBind || 0);
  if ($("setupPendingCalibrate")) $("setupPendingCalibrate").textContent = String(summary.pendingCalibrate || 0);
  if ($("setupCompleted")) $("setupCompleted").textContent = String(summary.completed || 0);
}

// ===== 批量任务控制 =====

async function toggleScheduler() {
  const btn = $("schedulerToggle");
  if (!btn) return;
  btn.disabled = true;
  try {
    const status = await api("/api/scheduler");
    if (status.running) {
      await api("/api/scheduler/pause", { method: "POST" });
      btn.textContent = "启动采集";
      btn.classList.remove("active");
    } else {
      await api("/api/scheduler/start", { method: "POST" });
      btn.textContent = "停止采集";
      btn.classList.add("active");
    }
  } finally {
    btn.disabled = false;
  }
}

async function syncSchedulerButton() {
  const btn = $("schedulerToggle");
  if (!btn) return;
  try {
    const status = await api("/api/scheduler");
    if (status.running) {
      btn.textContent = "停止采集";
      btn.classList.add("active");
    } else {
      btn.textContent = "启动采集";
      btn.classList.remove("active");
    }
  } catch {
  }
}

async function captureAllTasks() {
  const button = $("captureAllButton");
  if (button) button.disabled = true;
  try {
    showMessage("正在向所有启用的任务发送采集指令...");
    const tasks = liveTasks();
    const promises = tasks.map(task => api(`/api/tasks/${task.id}/capture-once`, { method: "POST" }).catch(e => console.error(`Task ${task.id} capture failed`, e)));
    await Promise.all(promises);
    showMessage("所有启用任务均已发送采集指令。");
    await loadTasks();
  } catch (error) {
    showMessage(parseApiError(error) || "采集全部失败", true);
  } finally {
    if (button) button.disabled = false;
  }
}

// ===== 全局事件绑定 =====

$("testOcr")?.addEventListener("click", () => testOcr().catch((err) => showMessage(parseApiError(err), true)));
  $("saveTask")?.addEventListener("click", () => saveTask().catch((err) => showMessage(parseApiError(err), true)));
  $("captureAllButton")?.addEventListener("click", () => captureAllTasks());
  $("schedulerToggle")?.addEventListener("click", () => toggleScheduler().catch((err) => showMessage(parseApiError(err), true)));
  $("previewRemotePage")?.addEventListener("click", () => previewRemotePage().catch((err) => showMessage(parseApiError(err), true)));
  $("resumeAfterLogin")?.addEventListener("click", () => resumeAfterLogin().catch((err) => showMessage(parseApiError(err), true)));
  $("startScreenReadonly")?.addEventListener("click", () => startScreenReadonly().catch((err) => showMessage(parseApiError(err), true)));
  $("refreshScreenReadonly")?.addEventListener("click", () => refreshScreenReadonly().catch((err) => showMessage(parseApiError(err), true)));
  $("clearScreenReadonly")?.addEventListener("click", () => clearScreenReadonly().catch((err) => showMessage(parseApiError(err), true)));

  $("scanBind")?.addEventListener("click", () => scanBind().catch((err) => showMessage(parseApiError(err), true)));
  $("confirmBind")?.addEventListener("click", () => confirmBind().catch((err) => showMessage(parseApiError(err), true)));
  $("rescanCurrentSetup")?.addEventListener("click", () => scanBind().catch((err) => showMessage(parseApiError(err), true)));
  $("focusNextSetup")?.addEventListener("click", () => focusNextPendingTask().catch((err) => showMessage(parseApiError(err), true)));
  $("resetCurrentSetup")?.addEventListener("click", () => resetCurrentSetup().catch((err) => showMessage(parseApiError(err), true)));

  $("setupShopJumper")?.addEventListener("change", function () {
    const val = this.value;
    if (val.startsWith("task:")) {
      const taskId = parseInt(val.slice(5), 10);
      if (taskId) focusSetupTask(taskId).catch((err) => showMessage(parseApiError(err), true));
    } else if (val.startsWith("config:")) {
      const parts = val.slice(7).split("::");
      if (parts.length === 2) focusSetupShopByIdentity(parts[0], parts[1]).catch((err) => showMessage(parseApiError(err), true));
    }
  });

  $("bindSessionSelect")?.addEventListener("change", function () {
    const task = typeof currentSetupTask === "function" ? currentSetupTask() : null;
    if (task && typeof renderBindContext === "function") renderBindContext(task);
  });

  $("valueSourceSelect")?.addEventListener("change", function () {
    if (typeof markValueSourceSelectionManual === "function") markValueSourceSelectionManual();
    if (typeof renderSetupWorkbench === "function") renderSetupWorkbench();
  });

  $("setupStepBind")?.addEventListener("click", function (e) {
    const actionBtn = e.target.closest("[data-setup-action]");
    if (!actionBtn) return;
    const action = actionBtn.dataset.setupAction;
    if (action === "select-bind-page") {
      const pageId = actionBtn.dataset.pageId;
      if (pageId && typeof selectBindPage === "function") selectBindPage(pageId);
    } else if (action === "open-manager") {
      if (typeof switchView === "function") switchView("manager");
    } else if (action === "rescan-bind") {
      if (typeof switchView === "function") switchView("config");
      setTimeout(() => {
        if (typeof scanBind === "function") scanBind().catch((err) => showMessage(parseApiError(err), true));
      }, 200);
    }
  });

// ===== WebSocket 实时推送 =====

let _liveWsReconnectTimer = null;

function connectLiveWebSocket(options = {}) {
  const { renderDashboardOnMessage = true } = options;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/live`;
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    if (typeof setWsStatus === "function") setWsStatus("实时连接");
    if (_liveWsReconnectTimer) { clearTimeout(_liveWsReconnectTimer); _liveWsReconnectTimer = null; }
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (renderDashboardOnMessage && data && data.tasks && typeof renderSnapshot === "function") {
        renderSnapshot(data);
      }
    } catch {}
  };

  ws.onclose = () => {
    if (typeof setWsStatus === "function") setWsStatus("实时断开", "bad");
    _liveWsReconnectTimer = setTimeout(() => connectLiveWebSocket(options), 3000);
  };

  ws.onerror = () => { ws.close(); };
}
