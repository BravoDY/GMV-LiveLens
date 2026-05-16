# Checklist

- [x] 后端 `_build_period_payload()` 平台 YOY = 该平台本期GMV合计 / 同期GMV合计 - 1（不再取首店值）
- [x] 后端 `_build_period_payload()` Summary YOY = 全渠道本期GMV合计 / 同期GMV合计 - 1（不再取首店值）
- [x] 后端 `_build_realtime_payload()` 平台 YOY = 该平台本期GMV合计 / 同期GMV合计 - 1
- [x] 后端 `_build_realtime_payload()` Summary YOY = 全渠道本期GMV合计 / 同期GMV合计 - 1
- [x] 店铺级 YOY 仍正确：每个 `shops[].yoy` = 自身 gmv / 自身 ly_val - 1
- [x] 前端 `test-dashboard/dashboard.js` 中 `snapshotShopYoy` 键改为 `companyshop_name`
- [x] 前端 `dashboard-shared.js` 中 `resolveYoy` 查找键与前端 shopYoy 键一致
- [x] `/api/dashboard-test?dataset_id=realtime` 返回的 `summary.yoy`、`platforms[].yoy`、`shops[].yoy` 三个维度各自独立计算，不完全相同
- [x] `/api/dashboard-test?dataset_id=product:集团全周期` 同上
- [x] 前端 `${item.gmv}` 已更新版本号（`v=20260516-yoy-agg-0013`）
- [x] ruff 静态检查无新增错误（2个预存问题 I001/UP037 非本次引入）
- [x] 边界情况：ly_val=0 时返回 `--`（DSTGOLF抖店 无同期数据正确显示 `--`）
