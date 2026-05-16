# 任务管理去除平台与真实Edge重复文案计划

## Summary
- 目标：移除 `任务管理` 卡片中重复展示的 `平台名 · 真实Edge` 文案，只保留店铺名、链接/页面标识、状态、金额和操作按钮。
- 期望结果：平台信息继续只出现在平台分组标题中，例如 `天猫`；卡片内部不再重复出现 `天猫 · 真实Edge` 这类次标题。
- 约束：这是纯前端展示优化，不改任务数据结构、不改平台分组逻辑、不改 Edge 控制按钮行为。

## Current State Analysis
- `任务管理` 的卡片渲染入口在 `frontend/app.js` 的 `renderManager()`。
- 当前每张卡片头部结构为：
  - `task-title`：显示店铺名，例如 `官方旗舰店`
  - `task-meta`：显示 `${task.platform} · ${mode}`，其中 `mode` 来自 `modeLabelMap[task.capture_mode]`
  - `task-identity`：显示页面 URL / 页面标题 / page_id
- 平台分组标题已在同一视图中显示一次，来自 `renderManager()` 内的 `manager-platform-section`，例如 `天猫`、`京东`。
- `真实Edge` 文案来源于 `frontend/core.js` 的 `modeLabelMap.remote_edge = "真实Edge"`，但当前用户需求只针对 `任务管理` 视图内的重复展示，不要求全局删除该映射。
- 样式相关结构在 `frontend/styles.css`：
  - `.task-head`
  - `.task-head-main`
  - `.task-title`
  - `.task-meta`
- 从现有实现看，最小改动点是只调整 `frontend/app.js` 中任务管理卡片模板；是否需要补样式，取决于移除次标题后卡片头部间距是否出现明显空洞。

## Proposed Changes

### 1. 调整任务管理卡片模板
- 文件：`frontend/app.js`
- 改动：
  - 在 `renderManager()` 中移除卡片头部的 `${task.platform} · ${mode}` 这一行。
  - 保留以下信息不变：
    - 店铺名 `task.shop_name`
    - 页面身份信息 `task-identity`
    - 状态 badge
    - 金额、调试信息、任务按钮、Edge 控制按钮
- 原因：
  - 平台已由外层分组标题表达，卡片内再次显示平台名重复。
  - 当前工作流统一走真实 Edge，卡片内继续显示 `真实Edge` 没有额外信息价值。
- 实施方式：
  - 删除卡片模板中的对应 `task-meta` 节点。
  - 不改 `modeLabelMap`，避免影响 `采集配置`、会话下拉、状态提示等其他仍需要模式名称的地方。

### 2. 视情况微调卡片头部样式
- 文件：`frontend/styles.css`
- 改动：
  - 先按“不改样式”处理。
  - 若移除 `task-meta` 后卡片头部出现明显垂直留白或标题与 `task-identity` 贴合不自然，再对 `.task-head-main`、`.task-title`、`.task-meta` 附近样式做最小微调。
- 原因：
  - 当前样式可能在删除一行文本后依然成立，没必要预先扩大修改面。
  - 若视觉确有空隙，再以最小范围补齐。
- 实施方式：
  - 仅做局部 spacing 调整，不重构卡片布局。

## Assumptions & Decisions
- 决策：本次只处理 `任务管理` 视图，不改 `采集配置`、会话选择器、错误提示中的 `真实 Edge` 文案。
- 决策：保留平台分组标题，例如 `天猫`，只删除卡片内部重复平台文案。
- 决策：保留 Edge 控制按钮文案 `启动Edge / 显示Edge / 隐藏Edge / 关闭Edge`，因为它们仍然是明确操作入口，不属于重复标签。
- 假设：用户所说的“天猫 · 真实Edge这块内容”对应任务卡片头部次标题，而不是平台分组头或 Edge 按钮区。
- 假设：当前所有核心任务仍以 `remote_edge` 为主，但代码层仍需保留模式字段以兼容已有逻辑。

## Verification Steps
- 打开 `任务管理` 页面，确认平台分组标题仍显示，例如 `天猫`。
- 确认每张店铺卡片头部只显示店铺名，不再显示 `平台名 · 真实Edge`。
- 确认卡片中的页面链接/身份信息仍保留，未误删。
- 确认 `启动Edge / 显示Edge / 隐藏Edge / 关闭Edge` 以及 `采一次 / 编辑 / 启用 / 历史 / 重绑页面 / 删除` 按钮不受影响。
- 检查卡片头部布局是否自然；若标题与链接间距异常，再做最小样式修正。
- 对修改文件运行诊断，至少覆盖：
  - `frontend/app.js`
  - 若有样式调整，则再检查 `frontend/styles.css`

