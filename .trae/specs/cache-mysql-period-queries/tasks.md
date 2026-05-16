# Tasks

- [x] Task 1: 实现缓存层核心逻辑（dashboard_query.py）
  - [x] 新增 `_compute_to_date_hash()` 计算 `to_date.csv` 文件内容的 SHA256
  - [x] 新增 `_is_cache_stale(cached_at, to_date_hash)` 判断缓存是否失效
  - [x] 新增 `_load_cache()` / `_save_cache()` 读写 `period_gmv.json`
  - [x] 新增 `_query_all_periods_mysql()` 一次性查询所有周期数据集并聚合
  - [x] 新增 `_refresh_cache()` 统一刷新入口
  - [x] 修改 `_build_period_payload()`：优先从缓存读取；缓存失效时自动刷新

- [x] Task 2: 新增缓存刷新与状态 API（dashboard_test.py）
  - [x] 新增 `POST /api/dashboard-cache/refresh`
  - [x] 新增 `GET /api/dashboard-cache/status`

- [x] Task 3: 实现每日 10:00 AM 自动刷新（dashboard_query.py + main.py）
  - [x] 新增 `_cache_refresh_loop()` async 循环
  - [x] 在 `main.py` startup 中调用 `start_cache_scheduler()`
  - [x] 在 `main.py` shutdown 中调用 `stop_cache_scheduler()`

- [x] Task 4: 前端新增「刷新数据」按钮（test-dashboard）
  - [x] `index.html` 添加刷新按钮
  - [x] `app.js` 绑定点击事件（POST 刷新 → 重新渲染）
  - [x] `styles.css` 按钮样式

- [x] Task 5: 集成验证
  - [x] 首次访问周期页面 → MySQL 查询 → 缓存写入，GMV 正确
  - [x] 同一天再次访问 → 返回缓存数据，`stale: false`
  - [x] 手动点击刷新按钮 → 强制 MySQL 查询 → 缓存更新
  - [x] `GET /api/dashboard-cache/status` 返回正确状态
  - [x] 缓存文件内容正确（periods + yoy）
