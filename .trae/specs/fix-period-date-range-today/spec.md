# 修复周期日期范围 + 同期 GMV 截断 + 时间行换行 Spec

## Why
1. 周期日期范围显示 `to_date.csv` 完整范围（含未来日期），而非"最早 → 今天"。同期（ly_periods）GMV 取了全部 to_dates（47 天），未截断到今天对应的 to_date，导致 本期 11 天 vs 同期 47 天的不对称比较。
2. 时间行外层 `<span>` 包裹导致 flex 中换行。

## What Changes
- 后端 `_build_period_payload()`：`date_range.end` → 今天；`to_date_range` → 当天对应 to_date；`ly_map` 从 `to_index` 按截断后 to_dates 重新计算
- `to_date_range` 值统一 `%Y-%m-%d` 格式
- 前端 `renderTotalCard()`：去掉多余 `<span>` 包裹 → `.total-card-time-left`
- CSS：新增 `.total-card-time-left`

## Impact
- **BREAKING**: 所有周期导航的 YOY 百分比值会变化（同期 GMV 范围缩小）
- Affected code:
  - `backend/services/dashboard_query.py` — `_build_period_payload()`（ly_map 重算 + 日期范围截断）
  - `frontend/dashboard-shared.js` — `renderTotalCard()`
  - `frontend/styles.css` — 新增 `.total-card-time-left`

## MODIFIED Requirements

### Requirement: 本期 date_range.end 截断到今天
系统 SHALL 对周期模式的 `date_range.end` 使用当天日期。

#### Scenario: 集团全周期 date_range 截断
- **WHEN** 今天为 2026/5/16，集团全周期 date 范围为 2026/5/6 ~ 2026/6/21
- **THEN** `date_range.end` = `"2026-05-16"`

### Requirement: 同期 to_date_range 截断到今天对应 to_date
系统 SHALL 找到当天 date 对应的 to_date 行作为 `to_date_range.end`。

#### Scenario: 集团全周期 to_date_range 截断
- **WHEN** 今天 2026/5/16，对应行 to_date=2025/5/16
- **THEN** `to_date_range.end` = `"2025-05-16"`

### Requirement: 同期 ly GMV 截断到今天对应 to_date
系统 SHALL 仅累计 `to_date ≤ 当天对应的 to_date` 的同期 GMV，保证本期与同期天数对称。

#### Scenario: 同期 GMV 对称截断
- **WHEN** 集团全周期 date=2026/5/6~2026/6/21，to_date=2025/5/6~2025/6/21，今天 2026/5/16
- **THEN** 同期 GMV 仅计算 to_date ∈ [2025/5/6, 2025/5/16]（11 天，与本期对齐）

### Requirement: to_date_range 统一 %Y-%m-%d 格式
系统 SHALL 将 `to_date_range` 值通过 `_parse_date` → `strftime("%Y-%m-%d")` 格式化。

### Requirement: 时间行不换行
前端 SHALL 保证北京时间区域不换行。
