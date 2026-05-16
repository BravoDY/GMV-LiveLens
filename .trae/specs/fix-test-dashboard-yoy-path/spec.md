# test-dashboard YOY 前端读取路径修复 Spec

## Why
上一轮 `fix-yoy-aggregation-per-dimension` 修复了后端 YOY 按维度独立聚合计算（已验证通过），也修复了前端 shopYoy 的索引键。但 **test-dashboard 的 `renderDashboard()` 从错误的路径读取 platforms/shops**：它读 `state.snapshot.platforms`，但数据实际在 `state.snapshot.public_dashboard.platforms`。导致 `snapshotPlatformYoy` 和 `snapshotShopYoy` 始终为空 `{}`，所有卡片降级使用同一个 `model.total.yoy`，用户看到的三个卡片模块仍是相同数字。

## What Changes
- `frontend/test-dashboard/dashboard.js`：`renderDashboard()` 中 `state.snapshot?.platforms` → `state.snapshot?.public_dashboard?.platforms`，`state.snapshot?.shops` → `state.snapshot?.public_dashboard?.shops`

## Impact
- Affected specs: `fix-yoy-aggregation-per-dimension`（补充遗漏修复）
- Affected code: `frontend/test-dashboard/dashboard.js` `renderDashboard()`

## MODIFIED Requirements

### Requirement: test-dashboard 从 public_dashboard 读取 YOY 数据
前端 `/dashboard-test` 页面 SHALL 从 `state.snapshot.public_dashboard` 而非 `state.snapshot` 直接读取 `platforms` 和 `shops` 数组的 YOY 值。

#### Scenario: 平台卡片 YOY 各自不同
- **WHEN** 刷新 `/dashboard-test` 页面
- **THEN** 每个平台卡片显示该平台聚合 YOY（如天猫=-18.29%，京东=29.22%），不再全部相同

#### Scenario: 店铺卡片 YOY 各自不同
- **WHEN** 渲染 test-dashboard 店铺卡片
- **THEN** 每个店铺卡片通过 `companyshop_name` 匹配自身独立的 YOY 值
