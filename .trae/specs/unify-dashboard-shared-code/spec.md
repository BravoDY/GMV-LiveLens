# 三页面代码统一与共享机制

## Why

`frontend/dashboard.js` (627行) 和 `frontend/test-dashboard/dashboard.js` (412行) 存在 **75.7% 的逐字完全相同代码**，修改一处需要手动同步另一处，已导致多次代码漂移。需要建立统一共享机制，单点修改自动同步所有页面。

## What Changes

- **新增** `frontend/dashboard-shared.js` — 提取两文件共有的 19 个函数
- **瘦身** `frontend/dashboard.js` — 仅保留 Manager Grid 专属函数
- **瘦身** `frontend/test-dashboard/dashboard.js` — 仅保留周期横幅 + 独特 renderDashboard
- 三个 HTML 页面调整 `<script>` 加载顺序：shared.js → 页面专属 JS

## Impact

- Affected code:
  - **NEW** `frontend/dashboard-shared.js`
  - **MODIFIED** `frontend/dashboard.js`（大幅瘦身）
  - **MODIFIED** `frontend/test-dashboard/dashboard.js`（大幅瘦身）
  - **MODIFIED** `frontend/index.html`（新增 `<script>` 引用）
  - **MODIFIED** `frontend/test-dashboard/index.html`（调整 `<script>` 顺序）

## ADDED Requirements

- 系统 SHALL 提供 `frontend/dashboard-shared.js` 包含 19 个共用函数
- `/` 和 `/dashboard` 加载 core.js → dashboard-shared.js → dashboard.js
- `/dashboard-test` 加载 core.js → dashboard-shared.js → test-dashboard/dashboard.js
- 修改 shared.js 中的函数 → 三个页面自动生效
