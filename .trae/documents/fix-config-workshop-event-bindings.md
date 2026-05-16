# 采集配置工作台 — 页面选择与已选页签按钮不显示修复计划

## 症状

在采集配置工作台中，进入某个店铺后：
1. 下方不会出现可选的页面列表（候选页签）
2. "使用此页面"（confirmBind）按钮不显示
3. 所有采集配置操作按钮（扫描页签、重新扫描、清空标定、进入下一家等）点击均无反应

## 根因分析

经过深度代码审查，问题的根因在 `frontend/core.js` 第 787-797 行的全局事件绑定区。

### 当前已绑定的事件（9 个）
```javascript
$("testOcr")                  → testOcr()
$("saveTask")                 → saveTask()
$("captureAllButton")         → captureAllTasks()
$("schedulerToggle")          → toggleScheduler()
$("previewRemotePage")        → previewRemotePage()
$("resumeAfterLogin")         → resumeAfterLogin()
$("startScreenReadonly")      → startScreenReadonly()
$("refreshScreenReadonly")    → refreshScreenReadonly()
$("clearScreenReadonly")      → clearScreenReadonly()
```

### 缺失的事件绑定（共 6 个直接按钮 + 3 个动态事件）

| DOM ID / 属性 | 应绑定的函数 | 用途 |
|---|---|---|
| `#scanBind` | `scanBind()` | 扫描当前会话页签 |
| `#confirmBind` | `confirmBind()` | 使用此页面（确认绑定） |
| `#rescanCurrentSetup` | `scanBind()` | 重新扫描 |
| `#focusNextSetup` | `focusNextPendingTask()` | 进入下一家 |
| `#resetCurrentSetup` | 需新建 `resetCurrentSetup()` | 清空当前标定并重来 |
| `#setupShopJumper` (change) | 需新建处理函数 | 切换店铺下拉 |
| `#bindSessionSelect` (change) | 需新建处理函数 | 切换 Edge 会话 |
| `#valueSourceSelect` (change) | 需新建处理函数 | 切换采集方式 |
| `[data-setup-action]` (click) | 委托事件 | 动态按钮（"选择此页"/"去任务管理"/"回来重新扫描"） |

### 影响链路

1. 用户从任务管理点击卡片 → `loadTaskIntoConfig(task)` → `syncTaskContext(task)` → `preloadTaskBindCandidates(task)` 会调 `/api/tasks/{id}/page-candidates` 获取页签列表
2. 后端返回的页签数据通过 `applyBindCandidatesResult()` 渲染到 `#bindTable`
3. `renderBindPageCandidates()` 会为每个页签生成"选择此页"按钮，带 `data-setup-action="select-bind-page"`
4. **但由于没有任何事件监听器绑定到这些按钮和委托事件，用户无法进行任何操作**

---

## 修复计划

### Task 1: 补全 `core.js` 全局事件绑定（高优先级）

在 `core.js` 第 797 行后增加以下事件绑定：

```javascript
// 采集配置工作台按钮
$("scanBind")?.addEventListener("click", () => scanBind().catch((err) => showMessage(parseApiError(err), true)));
$("confirmBind")?.addEventListener("click", () => confirmBind().catch((err) => showMessage(parseApiError(err), true)));
$("rescanCurrentSetup")?.addEventListener("click", () => scanBind().catch((err) => showMessage(parseApiError(err), true)));
$("focusNextSetup")?.addEventListener("click", () => focusNextPendingTask().catch((err) => showMessage(parseApiError(err), true)));

// 切换店铺下拉
$("setupShopJumper")?.addEventListener("change", function() {
  const val = this.value;
  if (val.startsWith("task:")) {
    const taskId = parseInt(val.slice(5), 10);
    if (taskId) focusSetupTask(taskId).catch((err) => showMessage(parseApiError(err), true));
  } else if (val.startsWith("config:")) {
    const parts = val.slice(7).split("::");
    if (parts.length === 2) focusSetupShopByIdentity(parts[0], parts[1]).catch((err) => showMessage(parseApiError(err), true));
  }
});

// 切换 Edge 会话下拉
$("bindSessionSelect")?.addEventListener("change", function() {
  const task = typeof currentSetupTask === "function" ? currentSetupTask() : null;
  if (task) {
    renderBindContext(task);
  }
});

// 切换采集方式下拉
$("valueSourceSelect")?.addEventListener("change", function() {
  if (typeof markValueSourceSelectionManual === "function") markValueSourceSelectionManual();
  if (typeof renderSetupWorkbench === "function") renderSetupWorkbench();
});

// 动态按钮事件委托（data-setup-action 系列）
$("setupStepBind")?.addEventListener("click", function(e) {
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
```

### Task 2: 新建 `resetCurrentSetup()` 函数（config.js）

在 `config.js` 中新增清空当前标定函数：

```javascript
async function resetCurrentSetup() {
  const task = currentSetupTask();
  if (!task) {
    showMessage("当前没有待处理店铺。", true);
    return;
  }
  try {
    await api(`/api/tasks/${encodeURIComponent(task.id)}/reset-calibration`, { method: "POST" });
  } catch {
    // 即使后端没有此接口，也清空前端状态
  }
  clearPreview();
  resetBindCandidates(task.id);
  state.selectedBindPageId = "";
  renderBindContext(task);
  renderSetupWorkbench();
  showMessage(`已清空 ${task.shop_name} 的标定数据。`);
}
```

并在 `core.js` 中绑定：
```javascript
$("resetCurrentSetup")?.addEventListener("click", () => resetCurrentSetup().catch((err) => showMessage(parseApiError(err), true)));
```

### Task 3: 更新前端版本号

在 `frontend/index.html` 中将 `core.js` 和 `config.js` 的版本号更新为新值。

---

## 冒烟测试计划

### 前置条件
- Edge 浏览器已打开且至少一个店铺已登录
- 后端服务 `http://127.0.0.1:8100` 正常运行
- 任务管理中有可见的任务卡片

### 测试用例

| # | 测试项 | 操作步骤 | 预期结果 |
|---|--------|---------|---------|
| 1 | 进入采集配置 | 点击任务管理卡片 | 切换到采集配置视图，显示当前店铺信息 |
| 2 | 扫描页签 | 点击"扫描当前会话页签" | 弹出页签列表，显示候选页面卡片 |
| 3 | 选择页面 | 点击页签卡片上的"选择此页" | 按钮变为"已选中"，高亮当前选中页签 |
| 4 | 确认绑定 | 点击"使用此页面" | 显示绑定成功，自动生成预览（如果页面截图成功） |
| 5 | 进入下一家 | 点击"进入下一家" | 自动切换到下一个待配置店铺 |
| 6 | 重新扫描 | 点击"重新扫描" | 重新扫描当前会话页签 |
| 7 | 清空标定 | 点击"清空当前标定并重来" | 清空预览、框选、绑定状态 |
| 8 | 切换店铺下拉 | 在切换店铺下拉中选择另一个店铺 | 自动加载该店铺配置 |
| 9 | 切换会话 | 在 Edge 会话下拉中切换 | 更新上下文信息 |
| 10 | 切换采集方式 | 在采集方式下拉中切换 OCR/大屏只读 | 工作台步骤和提示文字变化 |
| 11 | 动态恢复按钮 | 模拟页签失效场景，确认"去任务管理显示 Edge"按钮 | 点击后跳转到任务管理视图 |
| 12 | 生成预览 | 完成绑定后点击"生成预览" | 右侧显示页面截图 |
| 13 | 测试识别 | 框选区域后点击"测试识别" | 显示 OCR 识别结果 |
| 14 | 保存任务 | 点击"保存并进入下一家" | 任务保存成功，自动切换到下一家 |

---

## 涉及文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `frontend/core.js` | 修改 | 新增 10+ 行事件绑定 |
| `frontend/config.js` | 修改 | 新增 `resetCurrentSetup()` 函数 |
| `frontend/index.html` | 修改 | JS 版本号更新 |

---

## 风险评估

- **风险等级：L2（标准任务）**
- 不涉及后端逻辑变更
- 不涉及数据结构和数据库变更
- 仅恢复前端事件绑定链路
- 修改文件均为前端 JS，不影响采集核心链路
