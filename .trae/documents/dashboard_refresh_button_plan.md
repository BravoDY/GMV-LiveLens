# 看板「刷新数据」按钮恢复 + 每日刷新时间确认

## 一、现状分析

### 1.1 按钮当前状态

**按钮已经存在于 HTML 中**，位置正确：

- [frontend/index.html](file:///d:/User_Project/GMV-LiveLens/frontend/index.html#L51)：
  ```html
  <button id="refreshCacheBtn" class="test-dataset-refresh-btn" type="button" title="强制刷新周期数据缓存">刷新数据</button>
  ```

- [frontend/test-dashboard/index.html](file:///d:/User_Project/GMV-LiveLens/frontend/test-dashboard/index.html#L47)：同样存在

**Click 事件也已绑定**：在 [dashboard-public.js:L222-L244](file:///d:/User_Project/GMV-LiveLens/frontend/dashboard-public.js#L222) 中 `bindSharedRefreshButton()` 已实现完整的点击→ POST `/api/dashboard-cache/refresh` → 刷新看板逻辑。

### 1.2 按钮为什么看不见？

问题出在 [dashboard-public.js:L207-L214](file:///d:/User_Project/GMV-LiveLens/frontend/dashboard-public.js#L207) 的 `applyPublicDashboardMode()` 函数中：

```javascript
function applyPublicDashboardMode() {
  document.body.classList.add("public-dashboard-mode");
  // ... 隐藏导航等
  document.querySelectorAll("#captureAllButton, #schedulerToggle, #debugPanelToggle, #debugStatusPanel, #refreshCacheBtn").forEach((el) => {
    if (el) el.style.display = "none";   // ← 这里把按钮隐藏了
  });
}
```

同时在 [dashboard-public.js:L250](file:///d:/User_Project/GMV-LiveLens/frontend/dashboard-public.js#L250) 中，`bindSharedRefreshButton()` 只在非 publicMode 下才会被调用：

```javascript
if (!publicMode) bindSharedRefreshButton({ preserveLocalSnapshot });
```

**结论**：在 public-dashboard 模式下，按钮被隐藏且事件未绑定。

### 1.3 每日自动刷新时间确认

**已经是 AM 10:00**，无需修改：

| 位置 | 代码 | 说明 |
|------|------|------|
| [dashboard_query.py:L699-L706](file:///d:/User_Project/GMV-LiveLens/backend/services/dashboard_query.py#L699) | `next_run = now.replace(hour=10, minute=0, ...)` | 定时调度器，每天 10:00 刷新 |
| [dashboard_query.py:L95](file:///d:/User_Project/GMV-LiveLens/backend/services/dashboard_query.py#L95) | `refresh_deadline = today_start.replace(hour=10, minute=0)` | 缓存过期判定也用 10:00 |

---

## 二、修改方案

### 修改 1：`frontend/dashboard-public.js` — 在 public 模式下显示并绑定刷新按钮

**位置**：第 212-214 行，`applyPublicDashboardMode()`

**修改前**：
```javascript
document.querySelectorAll("#captureAllButton, #schedulerToggle, #debugPanelToggle, #debugStatusPanel, #refreshCacheBtn").forEach((el) => {
    if (el) el.style.display = "none";
});
```

**修改后**：把 `#refreshCacheBtn` 从隐藏列表中移除（保留其他按钮的隐藏）：
```javascript
document.querySelectorAll("#captureAllButton, #schedulerToggle, #debugPanelToggle, #debugStatusPanel").forEach((el) => {
    if (el) el.style.display = "none";
});
// 刷新数据按钮在 public 模式下也显示，允许手动触发 MYSQL 数据刷新
```

### 修改 2：`frontend/dashboard-public.js` — 始终绑定刷新按钮事件

**位置**：第 250 行，`startSharedPublicDashboard()`

**修改前**：
```javascript
if (!publicMode) bindSharedRefreshButton({ preserveLocalSnapshot });
```

**修改后**：
```javascript
bindSharedRefreshButton({ preserveLocalSnapshot });
```

无论是否 public 模式，都绑定按钮点击事件。

### 不需要修改：每日刷新时间

`_cache_refresh_loop()` 和 `_is_cache_stale()` 中均已使用 `hour=10`，即每天 **AM 10:00** 自动刷新。当前配置已满足需求，无需修改。

---

## 三、验证步骤

1. 启动服务，访问看板页面
2. 确认右上角「刷新数据」按钮可见
3. 点击按钮，确认按钮变为「刷新中...」并成功调用 `/api/dashboard-cache/refresh`
4. 确认刷新完成后看板数据更新，状态提示显示「周期数据缓存刷新完成」
5. 模拟 VPN 断开 → 重新连接 → 手动点击按钮 → 确认数据正常获取

---

## 四、改动范围

| 文件 | 改动行数 | 说明 |
|------|----------|------|
| `frontend/dashboard-public.js` | ~2 行 | 移除按钮隐藏 + 无条件绑定事件 |
| 后端 | 0 行 | 10:00 已是期望值，无需修改 |
