# Tasks

- [x] Task 1: 修复后端 `_build_period_payload()` 日期范围 + 同期 GMV 截断
  - 用 `load_to_date_rows()` 加载 to_date 映射，筛选 `date ≤ today` 的行
  - `date_range.end` = today（`2026-05-16`），不再取 `to_date.csv` 最晚日期
  - `to_date_range`：从筛选行取 min/max to_date，`_parse_date` → `strftime("%Y-%m-%d")`（统一格式）
  - **同期 `ly_map`**：从 `to_index` 累加筛选行的 to_date 对应 GMV（不再用 ly_periods 全量预聚合值）
  - 本期 `current_map` 不变（MySQL 无未来数据，已正确）
  - 边界：筛选行为空时 `ly_map = {}`，`to_date_range` 为 `{"start":"","end":""}`

- [x] Task 2: 修复前端 `renderTotalCard()` 时间行不换行
  - HTML: `total-card-time-label` + `total-card-time-value` 归入 `<span class="total-card-time-left">`
  - CSS: 新增 `.total-card-time-left { display: inline-flex; flex-shrink: 0; white-space: nowrap; }`

- [x] Task 3: 版本号 + 重启验证
  - 验证 `date_range: 2026-05-06 - 2026-05-16` ✅（截断到今天）
  - 验证 `to_date_range: 2025-05-06 - 2025-05-16` ✅（截断到今天对应 to_date，格式 %Y-%m-%d）
  - 验证 GMV 同期范围已截断：YOY 值从 ~60% 变为 ~100%（天猫 88%，京东 163%，唯品 141%）✅
  - 前端 `total-card-time-left` 已生效 ✅

# Task Dependencies
- Task 1-2 可并行
- Task 3 依赖 Task 1-2
