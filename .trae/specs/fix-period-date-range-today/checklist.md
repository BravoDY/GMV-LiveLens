# Checklist

- [x] `date_range.end` 截断到今天（`2026-05-16`，非 `2026-06-21`）
- [x] `to_date_range.end` 截断到今天对应 to_date（`2025-05-16`，非 `2025-06-21`）
- [x] `to_date_range` 格式统一 `%Y-%m-%d`（`2025-05-06`，非 `2025/5/6`）
- [x] 同期 `ly_map` 仅累计 ≤ 当天 to_date 的 GMV（YOY 值显著变化证明）
- [x] 本期 `current_map` 不变（未来无数据已正确）
- [x] 店铺 YOY、平台 YOY、Summary YOY 均基于截断后的同期计算
- [x] 前端时间行不换行、两端对齐（`total-card-time-left` + `space-between`）
- [x] `/api/dashboard-test?dataset_id=product:集团全周期` 返回截断后 date_range/to_date_range
- [x] 边界：筛选行为空时 `--`
