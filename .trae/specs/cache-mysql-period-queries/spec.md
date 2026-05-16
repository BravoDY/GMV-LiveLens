# 周期数据 MySQL 查询缓存与按需刷新 规范

## Why

当前 `/dashboard-test` 页面每次切换导航标签页都会重新连接 MySQL 执行全量查询，而 `to_date.csv` 的日期配置并不会频繁变化。导致冗余 MySQL 查询耗时 20 秒以上直至超时。

核心思想：**to\_date.csv 不变 + 未跨天 → 直接使用缓存，不查 MySQL**。

## What Changes

* 新增周期 GMV 缓存层，将 MySQL 查询结果持久化到 JSON 文件

* 缓存失效条件：to\_date.csv 内容变更 或 跨天（每天 10:00 AM 自动刷新）

* 新增 `POST /api/dashboard-cache/refresh` 接口

* 新增 `GET /api/dashboard-cache/status` 接口

* 在 `/dashboard-test` 页面新增「刷新数据」按钮

## Impact

* Affected code:

  * `backend/services/dashboard_query.py` — 新增缓存读写与校验逻辑

  * `backend/routers/dashboard_test.py` — 新增刷新/状态 API

  * `backend/main.py` — 注册缓存调度器

  * `frontend/test-dashboard/index.html` — 新增刷新按钮

  * `frontend/test-dashboard/app.js` — 绑定刷新按钮事件

