# 同比（YOY）各维度聚合逻辑修复 Spec

## Why
目前同比数据在全渠道（total）、平台（platform）、店铺（store）三个维度显示的数值完全一样，原因是后端平台 YOY 和 Summary YOY 没有按维度独立聚合计算，而是直接取了第一个店铺的 YOY 百分比值；同时前端 `/dashboard-test` 页面的 shopYoy 索引键错误（用 `platform` 而非唯一键），导致同平台店铺 YOY 互相覆盖。

## What Changes
- **后端 `_build_realtime_payload()`**：平台 YOY 改为 `sum(平台本期GMV) / sum(平台同期GMV) - 1`，Summary YOY 改为 `sum(全渠道本期GMV) / sum(全渠道同期GMV) - 1`
- **后端 `_build_period_payload()`**：同上，平台 YOY 和 Summary YOY 改为按维度聚合计算，不再取第一个店铺值
- **前端 `test-dashboard/dashboard.js`**：`snapshotShopYoy` 索引键从 `s.platform` 改为唯一键（`companyshop_name` 或兼容 `shop_name`）
- **前端 `dashboard-shared.js`**：`renderStoreGrid()` 中 `resolveYoy` 的查找键从 `store.platform` 改为与前端一致的唯一键

## Impact
- Affected specs: YOY 同比逻辑完整链路
- Affected code:
  - `backend/services/dashboard_query.py` — `_build_realtime_payload()` + `_build_period_payload()`
  - `frontend/test-dashboard/dashboard.js` — `renderDashboard()`
  - `frontend/dashboard-shared.js` — `renderStoreGrid()`

## MODIFIED Requirements

### Requirement: 平台级 YOY 按聚合 GMV 计算
系统 SHALL 对每个平台独立计算 YOY：`(平台本期GMV合计 / 平台同期GMV合计 - 1) × 100%`，而非取该平台下任意一个店铺的 YOY 值。

#### Scenario: 实时模式平台 YOY 正确聚合
- **WHEN** 前端请求 `/api/dashboard-view?dataset=realtime`
- **THEN** `platforms[].yoy` = 该平台所有 enabled 店铺的 `last_trusted_value` 合计 / 该平台同期 MySQL GMV 合计 - 1

#### Scenario: 周期模式平台 YOY 正确聚合
- **WHEN** 前端请求 `/api/dashboard-view?dataset=product:集团全周期`
- **THEN** `platforms[].yoy` = 该平台所有 enabled 店铺的 `(periods[csn] + today_gmv[csn])` 合计 / 该平台 `ly_periods[csn]` 合计 - 1

### Requirement: 全渠道 Summary YOY 按聚合 GMV 计算
系统 SHALL 对全渠道 Summary YOY 独立计算：`(全渠道本期GMV合计 / 全渠道同期GMV合计 - 1) × 100%`，而非取任意单个店铺的 YOY 值。

#### Scenario: Summary YOY 基于全量聚合
- **WHEN** 计算 summary.yoy
- **THEN** summary.yoy = 所有 enabled 店铺本期GMV合计 / 所有 enabled 店铺同期GMV合计 - 1

### Requirement: 前端店铺 YOY 按唯一键传递
前端 SHALL 使用店铺唯一标识（`companyshop_name`）作为 YOY 映射的键，确保每个店铺卡片显示自己独立的 YOY 值。

#### Scenario: /dashboard-test 页面店铺 YOY 独立显示
- **WHEN** 渲染 `/dashboard-test` 页面的店铺卡片
- **THEN** 每个店铺卡片显示自身 `companyshop_name` 对应后端返回的 `shops[].yoy`，不同店铺可有不同 YOY 值
