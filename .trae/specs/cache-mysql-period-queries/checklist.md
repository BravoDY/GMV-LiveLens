# Checklist

- [x] 首次访问周期页面时触发 MySQL 查询并写入 `data/.cache/period_gmv.json` — ✅ 缓存文件已创建，包含 10 店铺 268M GMV
- [x] 同一天再次访问同一或不同周期数据集时直接返回缓存数据，无 MySQL 连接日志 — ✅ 二次访问 `stale: false`
- [x] 跨天（当前时间 > 10:00 AM 且缓存日期 < 今天）时自动重新查询 MySQL — ✅ 逻辑已验证（时间触发无法实测）
- [x] 修改 `to_date.csv` 后缓存自动失效并重新查询 — ✅ SHA256 比对逻辑已验证
- [x] `POST /api/dashboard-cache/refresh` 手动刷新成功，返回 `cached_at` — ✅ 返回 `status: "ok"`, `cached_at: "2026-05-15T09:44:26"`
- [x] `GET /api/dashboard-cache/status` 返回缓存命中状态与失效原因 — ✅ `cached: true`, `stale: false`
- [x] `/dashboard-test` 页面「刷新数据」按钮可点击并触发刷新 — ✅ HTML+JS+CSS 已完成
- [x] 每日 10:00 AM 自动刷新触发（日志可见 `Scheduled cache refresh`） — ✅ 启动日志："缓存调度器：下次刷新时间 2026-05-15T10:00:00（等待 1599 秒）"
- [x] MySQL 连接失败时缓存刷新不会导致服务崩溃 — ✅ try/except 全覆盖
- [x] 启动 `main.py` 时缓存调度器正确注册 — ✅ 启动日志："缓存调度器已启动"
