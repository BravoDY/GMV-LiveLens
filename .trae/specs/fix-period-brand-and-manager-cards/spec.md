# 修复：周期看板品牌分类 + 任务管理卡片 + 数字格式化

## Why

三个联动的质量修复需求：
1. 测试环境周期看板（to_date.csv 的数据集导航）中，所有店铺卡片都归入「大货独立店」，子品牌独立店面板永远为空。
2. 正式环境任务管理视图为空—— `managerGrid` 占位符从未被 JavaScript 填充。
3. GMV / Target 数字需统一去掉小数位并带千分符。

## What Changes

- **Bugfix** — 周期看板缺失 `brand` 字段，导致店铺卡片全堆到「大货独立店」
- **Feature** — 新增任务管理卡片渲染，复用现有 `.manager-card` CSS 样式
- **Style** — `formatCurrency()` 取整后再千分位格式化

## Impact

- Affected specs: 无（现有功能缺陷修复）
- Affected code:
  - `backend/services/dashboard_query.py` — `_build_period_payload()` 新增 `brand` 字段
  - `frontend/dashboard.js` — 新增 `renderManagerGrid()` + 修改 `formatCurrency` 取整
  - `frontend/config.js` — `loadTasks()` / `renderSnapshot()` 触发任务管理卡片渲染
  - `frontend/test-dashboard/dashboard.js` — `formatCurrency` 取整同步

---

## ADDED Requirements

### Requirement: 周期看板携带 brand 字段

`_build_period_payload()` 返回的 `shops[*]` 中 SHALL 包含 `brand` 字段，从 task 的 `brand` 属性获取。

#### Scenario: 周期看板品牌分组正确
- **WHEN** 用户切换到「集团全周期」或「第一波抢先购」导航
- **THEN** 品牌为「子品牌独立店」的店铺卡片显示在「子品牌独立店」面板
- **AND** 品牌为空或「大货独立店」的店铺卡片显示在「大货独立店」面板

### Requirement: 任务管理视图渲染卡片

正式环境任务管理视图 SHALL 渲染所有任务卡片，展示：店铺名、平台、品牌、状态、最新采集值、目标值、达成进度、最后采集时间。

#### Scenario: 任务管理视图正常显示卡片
- **WHEN** 用户点击「任务管理」导航栏
- **THEN** `#managerGrid` 中按平台分组渲染任务卡片
- **AND** 卡片状态通过 CSS class（如 `status-ok`、`status-suspect`）显示颜色标识
- **AND** 点击卡片可通过已有 `loadTaskIntoConfig()` 进入编辑

### Requirement: 数字格式化去掉小数位

`formatCurrency()` SHALL 对数值取整（`Math.round`）后再调用 `toLocaleString("zh-CN")`，不保留小数位。

#### Scenario: 周期看板金额无小数
- **WHEN** 周期 API 返回 `gmv: 108289841.08`
- **THEN** 前端显示 `¥108,289,841`（千分符，无小数）

---

## MODIFIED Requirements

N/A（均为新增功能，无边改）
