# 实时看板像素级UI复刻计划

## 1. 目标与范围
基于 `D:\MyDownloads\GMV-LiveLens_实时看板像素级UI修改说明.md` 进行实时看板的像素级 UI 重构。
**范围**：
- `frontend/index.html`（调整 Header 与 Dashboard 容器结构）
- `frontend/styles.css`（完全替换 Dashboard 相关样式，引入新的变量和布局）
- `frontend/dashboard.js`（拆分渲染函数，构建 ViewModel，渲染新版卡片）
- `frontend/core.js`（更新平台元数据和状态映射，确保切换视图的逻辑兼容新类名）

## 2. 与之前修改的冲突与解决策略 (核心)
在对比了 MD 规范和您刚刚让我完成的“Target 字段与 CSV 行顺序同步”功能后，存在以下冲突点，我将优先保留您最新的真实需求：

1. **店铺排序冲突**：
   - **MD 规范**：建议在前端写死一个 `SHOP_ORDER` 数组（第27.2条）。
   - **已有实现**：您刚刚明确要求“根据 shops.csv 的行顺序呈现”。
   - **解决策略**：**忽略 MD 中的 `SHOP_ORDER`**，继续保持直接遍历从后端传来的 `tasks` 数组（后端已按 CSV 的 `sort_order` 排好序），确保严格按 CSV 行顺序呈现。
2. **目标金额 (Target) 字段名与兜底逻辑冲突**：
   - **MD 规范**：建议使用 `gmv_target` 字段，并在前端写死一个 `SHOP_TARGETS` 兜底（第24和25条）。
   - **已有实现**：我们已经成功在数据库加入了 `target` 字段，并实现了全链路打通。
   - **解决策略**：**忽略 MD 中的前端兜底配置和 `gmv_target` 命名**，继续直接使用我们已经做好的真实的 `task.target` 数据。

## 3. 拟议的具体修改

### 3.1 frontend/index.html
- **Header 更新**：将 `<header class="topbar">` 改为 `<header class="app-header">`，内部类名匹配设计规范。
- **Dashboard 容器**：将 `<section class="hero-grid">` 替换为 `<div id="summaryGrid" class="summary-grid"></div>`，内部由 JS 渲染全渠道汇总卡和平台卡。
- **Store 容器**：将 `<div id="storeGrid" class="store-grid-uniform"></div>` 改为 `<div id="storeGrid" class="store-grid"></div>`。

### 3.2 frontend/styles.css
- **全局变量**：添加 `--color-total`, `--color-taobao`, `--color-jd`, `--color-dewu`, `--color-douyin`, `--color-vip`, `--color-other` 平台颜色变量。
- **Body & 主容器**：更新 `body` 的 `radial-gradient` 背景。
- **Header 样式**：添加 `.app-header`, `.header-brand`, `.header-logo`, `.header-title`, `.header-nav`, `.nav-item` 等。
- **Summary & Platform 区**：添加 `.summary-grid`, `.total-card`, `.platform-summary-card` 及内部样式。
- **Store 区**：添加 `.store-section-header`, `.store-grid` 及其响应式媒体查询。更新 `.store-card` 内部样式，**删除右上角的 logo，左上角采用单字 Icon**。

### 3.3 frontend/dashboard.js
- **重构与函数拆分**：
  - `renderDashboard()`：主入口。
  - `buildDashboardViewModel(tasks)`：聚合平台数据和总数据。
  - 渲染函数：`renderSummaryGrid`, `renderTotalCard`, `renderPlatformCard`, `renderStoreGrid`, `renderStoreCard`, `renderPlaceholderCard`。
  - 数据格式化辅助函数：`formatCurrency`, `formatPercent`。
- **平台排序**：按规范实现 `PLATFORM_ORDER = ["淘宝", "京东", "得物", "抖音", "唯品会"]` 对顶部的平台汇总卡进行排序。
- **去除冗余信息**：不在看板卡片上显示 URL、长报错，保持界面清爽。

### 3.4 frontend/core.js
- **平台映射与元数据**：更新 `normalizePlatform` 将 "天猫" 统一映射为 "淘宝"；更新 `platformMeta` 使用单字 Icon（如“淘”、“京”、“得”等）。
- **兼容性**：修改 `switchView` 逻辑，允许通过 `.tab` 或 `.nav-item` 进行视图切换。

## 4. 验证步骤
1. 打开本地服务看板。
2. 确认暗色背景、字号、平台单字 Icon 呈现无误，无多余的 618 或任务管理文案。
3. **重点确认**：店铺网格仍严格按照 `shops.csv` 行顺序排列，且目标金额正确读取自之前做好的 `target` 字段。