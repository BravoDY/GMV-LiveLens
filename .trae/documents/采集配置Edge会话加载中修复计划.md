# 采集配置「Edge会话加载中」修复计划

## 一、现象

正式环境主页 `/`，点击导航栏「采集配置」后，`bindSessionSelect` 下拉框始终显示「加载中...」，不出现 Edge 会话列表。

## 二、根因分析

### 数据流追踪

```
startInternalDashboard()                     [app.js:L82-L108]
  ├─ loadShopConfigs()  → state.shopConfigs ✅
  ├─ loadTasks()        → state.snapshot     ✅
  └─ renderSetupWorkbench()                  ✅
       └─ renderBindSessionOptions()          ❌ 此时 state.edgeSessions 仍为空数组 []
            └─ bindSessionResolution(task) → candidates=[]
                └─ select.innerHTML = "" → 但初始 HTML 是 `<option>加载中...</option>`
```

### 关键证据

1. **`state.edgeSessions` 的唯一赋值入口** 是 `refreshEdgeSessions()` — [edge.js:L165-L171](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/edge.js#L165-L171)：
   ```javascript
   async function refreshEdgeSessions(preferredSessionId = "") {
     const sessions = await api("/api/edge-sessions");
     state.edgeSessions = sessions;
     renderBindSessionOptions(...);
     await refreshRemoteHealth().catch(() => {});
     renderSetupWorkbench();
   }
   ```

2. **`startInternalDashboard()` 从未调用 `refreshEdgeSessions()`** — [app.js:L82-L108](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/app.js#L82-L108)，仅调用了 `loadShopConfigs()`、`loadTasks()`、`buildSetupSummary()`、`renderSetupWorkbench()`。

3. `refreshEdgeSessions()` 仅在以下场景被调用：
   - 创建新 Edge 会话后 — [edge.js:L223](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/edge.js#L223)
   - 任务预加载候选页时 (syncTaskContext) — [config.js:L705](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/config.js#L705)

4. **用户的操作路径**：直接点导航栏「采集配置」→ 没有任何任务被加载 → 不触发 `syncTaskContext` → `state.edgeSessions` 保持空数组 → 下拉框保持初始 HTML「加载中...」

### 根因结论

**`startInternalDashboard()` 缺少 `refreshEdgeSessions()` 调用**，导致页面首次加载时 `state.edgeSessions` 为空数组，`renderBindSessionOptions()` 生成的候选列表为空，且无法覆盖 HTML 中硬编码的 `<option>加载中...</option>` 占位符。

## 三、修复方案

在 `frontend/app.js` 的 `startInternalDashboard()` 中，`renderSetupWorkbench()` 之前添加：

```javascript
await refreshEdgeSessions();
```

### 文件变更

| 文件 | 变更 |
|------|------|
| `frontend/app.js` | `startInternalDashboard()` 中新增 `await refreshEdgeSessions();` |
| `frontend/index.html` | JS 版本号更新 |

### 修复后数据流

```
startInternalDashboard()
  ├─ loadShopConfigs()    → state.shopConfigs      ✅
  ├─ loadTasks()          → state.snapshot          ✅
  ├─ refreshEdgeSessions() → state.edgeSessions     ✅ ← NEW
  │    └─ renderBindSessionOptions() → 14 个会话选项
  │    └─ renderSetupWorkbench()
  ├─ buildSetupSummary()
  └─ renderSetupWorkbench()
```

## 四、验证方案

1. 刷新浏览器 `/` 页面
2. 点击导航栏「采集配置」
3. **验证**：`bindSessionSelect` 下拉框不再显示「加载中...」，而是列出 14 个 Edge 会话选项
