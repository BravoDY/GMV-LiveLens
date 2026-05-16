# Tasks

- [x] Task 1: 修复后端 `_build_period_payload()` 的平台和 Summary YOY 聚合计算
  - 修改平台 YOY 计算逻辑：遍历 `shop_rows` 按 platform 分组，分别累加 `gmv`（本期）和 `ly_map[csn]`（同期），再计算 `(gmv / ly - 1) * 100%`
  - 修改 Summary YOY：使用全部 `shop_rows` 的 `gmv` 合计 / `ly_map` 合计 - 1
  - 保留原有 `--` 边界处理（ly_val <= 0 或 gmv <= 0 时返回 `--`）

- [x] Task 2: 修复后端 `_build_realtime_payload()` 的平台和 Summary YOY 聚合计算
  - `_compute_realtime_platform_yoy()` 返回 per-csn 的 `(yoy_map, cur_map, ly_map)` 三元组
  - 平台 YOY = `sum(平台本期GMV) / sum(平台同期GMV) - 1`
  - Summary YOY = `sum(全渠道本期GMV) / sum(全渠道同期GMV) - 1`

- [x] Task 3: 修复前端 `test-dashboard/dashboard.js` 的 shopYoy 索引键
  - `snapshotShopYoy` 的 key 从 `s.platform` 改为 `s.companyshop_name || s.shop_name`
  - `snapshotPlatformYoy` 保留使用 `p.platform`

- [x] Task 4: 修复前端 `dashboard-shared.js` 的 YOY 查找
  - `tasksFromPublicDashboardPayload()` 新增 `companyshop_name` 字段
  - `buildDashboardViewModel()` store 对象新增 `companyshopName` 字段
  - `renderStoreGrid()` 中 `resolveYoy` 查找键从 `store.platform` 改为 `store.companyshopName`
  - `frontend/dashboard.js` `renderDashboard()` 也从 `public_dashboard` 读取 per-dimension YOY

- [x] Task 5: 静态检查 + 重启服务验证
  - ruff 检查: 2 个预存问题（I001/UP037），非本次引入
  - 验证 realtime: Summary=-23.87%, 天猫=-18.29%, 京东=29.22%, 唯品=-99.17%, 抖音=-27.07%, 得物=-56.99% — 各维度不同 ✅
  - 验证 集团全周期: Summary=-59.41%, 天猫=-62.00%, 京东=-55.81%, 唯品=-46.04%, 抖音=-52.54%, 得物=-74.80% — 各维度不同 ✅
  - 店铺级 YOY 各自独立计算 ✅

# Task Dependencies
- Task 1 和 Task 2 无依赖，可并行
- Task 3 和 Task 4 依赖 Task 2（需要后端返回正确的 shop 级 yoy）
- Task 5 依赖 Task 1-4 全部完成
