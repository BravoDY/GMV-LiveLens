// ===== 部署调试 / API Token 面板 =====

function setDebugText(id, value) {
  const el = $(id);
  if (el) el.textContent = value || "-";
}

function setDebugMessage(text, isError = false) {
  const el = $("debugStatusMessage");
  if (!el) return;
  el.textContent = text || "";
  el.classList.toggle("bad-text", Boolean(isError));
}

function renderStoredApiTokenState() {
  const token = currentApiToken();
  const input = $("apiTokenInput");
  if (input && token && !input.value) input.value = token;
  setDebugText("debugTokenState", token ? "本机已保存" : "本机未保存");
}

async function refreshDebugPanelStatus() {
  renderStoredApiTokenState();
  try {
    const [configPayload, healthPayload] = await Promise.all([
      api("/api/config/public"),
      api("/api/health"),
    ]);
    const config = configPayload?.data || configPayload || {};
    const health = healthPayload?.data || healthPayload || {};
    const security = config.security || {};
    setDebugText("debugHealthStatus", health.status === "ok" ? "正常" : "异常");
    setDebugText("debugAppEnv", config.app_env || security.app_env || "-");
    setDebugText("debugTokenRequired", security.require_api_token ? "已开启" : "未开启");
    setDebugText("debugLastRequestId", healthPayload?.request_id || configPayload?.request_id || "-");
    const subtitle = $("debugStatusSubtitle");
    if (subtitle) {
      subtitle.textContent = security.require_api_token
        ? "生产/公网写操作需要 X-API-Token"
        : "当前写操作未强制 Token，适合本地开发";
    }
    setDebugMessage("状态已刷新");
  } catch (error) {
    const requestId = apiRequestId(error);
    if (requestId) setDebugText("debugLastRequestId", requestId);
    setDebugText("debugHealthStatus", "异常");
    setDebugMessage(parseApiError(error) || "调试状态加载失败", true);
  }
}

function openDebugPanel() {
  const panel = $("debugStatusPanel");
  if (!panel) return;
  panel.classList.add("is-open");
  refreshDebugPanelStatus().catch((error) => setDebugMessage(parseApiError(error), true));
}

function closeDebugPanel() {
  $("debugStatusPanel")?.classList.remove("is-open");
}

function setupDebugPanel() {
  $("debugPanelToggle")?.addEventListener("click", openDebugPanel);
  $("debugPanelClose")?.addEventListener("click", closeDebugPanel);
  $("refreshDebugStatus")?.addEventListener("click", () => refreshDebugPanelStatus());
  $("saveApiToken")?.addEventListener("click", () => {
    const token = String($("apiTokenInput")?.value || "").trim();
    setApiToken(token);
    renderStoredApiTokenState();
    setDebugMessage(token ? "Token 已保存到当前浏览器" : "Token 为空，已清空本机保存值");
  });
  $("clearApiToken")?.addEventListener("click", () => {
    setApiToken("");
    const input = $("apiTokenInput");
    if (input) input.value = "";
    renderStoredApiTokenState();
    setDebugMessage("已清空当前浏览器保存的 Token");
  });
  renderStoredApiTokenState();
}
