# Tasks

- [ ] Task 1: 复现并量化问题
  - [ ] 使用浏览器 DevTools Performance 面板录制从点击导航 tab 到页面完全渲染的全流程，记录卡顿持续时间
  - [ ] 使用 Network 面板筛选慢请求（>1s），定位具体是哪个 API 调用阻塞了 UI
  - [ ] 分别在以下场景录制：首次加载、加载完成后切换"采集配置"→"实时看板"、加载完成后切换"实时看板"→"任务管理"
  - [ ] 输出量化报告：卡顿时长（ms）、阻塞 API、触发条件

- [ ] Task 2: 修复 `GET /api/edge-sessions` 健康检查阻塞
  - [ ] 在 [common.py](file:///d:/User_Project/GMV-LiveLens/backend/routers/common.py) 的 `build_edge_session_item()` 中为每个会话的 `edge_health_payload()` 增加 `asyncio.wait_for(..., timeout=5.0)` 超时
  - [ ] 超时后返回降级健康数据（`debug_available: false, connected: false`），不阻塞其他会话
  - [ ] 验证 `asyncio.gather()` 正确地并行执行（当前已并行，确认无退化）
  - [ ] 重启服务后验证 `GET /api/edge-sessions` 响应时间从 2-20s 降至 3s 以内

- [ ] Task 3: 优化 `renderDashboard()` 按视图激活渲染
  - [ ] 在 [dashboard.js](file:///d:/User_Project/GMV-LiveLens/frontend/dashboard.js) 的 `renderDashboard()` 函数开头增加视图检测：若当前激活视图不是 `dashboard`，仅更新 `state.snapshot` 数据，跳过 DOM 渲染
  - [ ] 在 `switchView()` 函数中增加逻辑：当切换到 `dashboard` 视图时，若 `state.snapshot` 有缓存数据则立即调用 `renderDashboard()`
  - [ ] 移除 `renderDashboard()` 中对 `managerGrid` 的无条件渲染（[dashboard.js L260-L265](file:///d:/User_Project/GMV-LiveLens/frontend/dashboard.js#L260-L265)），改为仅在 `managerGrid` 可见时渲染
  - [ ] 验证：切换至"采集配置"视图后，1.2s 轮询不再触发 `renderDashboard()` 的 DOM 操作

- [ ] Task 4: MySQL 连接配置优化
  - [ ] 在 [dashboard_query.py](file:///d:/User_Project/GMV-LiveLens/backend/services/dashboard_query.py) 中将 `connect_timeout` 从 10s 改为 5s，`read_timeout` 从 30s 改为 15s
  - [ ] 为 `_query_all_periods_mysql()` 和 `_query_target_goal_mysql()` 增加 `pymysql.err.OperationalError` 捕获，返回空结果或文件缓存数据
  - [ ] 实现 MySQL 连接池：检查项目是否已安装 `DBUtils`，如有则使用 `PooledDB`；如无，使用 `queue.Queue` + 预建连接方式（最多 5 个连接）
  - [ ] 验证：MySQL 不可达时，周期看板 API 返回降级数据且不超 5 秒

- [ ] Task 5: 前端性能监控埋点
  - [ ] 在 [core.js](file:///d:/User_Project/GMV-LiveLens/frontend/core.js) 的 `switchView()` 函数中增加 `performance.now()` 计时，console 输出 `[Perf] switchView: Xms`
  - [ ] 在 [core.js](file:///d:/User_Project/GMV-LiveLens/frontend/core.js) 的 `api()` 和 `callEdgeAction()` 函数中增加请求耗时记录，console 输出 `[Perf] GET/POST /api/xxx: Xms`
  - [ ] 慢请求告警：当 API 请求耗时超过 2s 时，console 输出 `[Perf] SLOW` 前缀日志
  - [ ] 在 [dashboard-public.js](file:///d:/User_Project/GMV-LiveLens/frontend/dashboard-public.js) 的数据集切换函数中增加计时

- [ ] Task 6: 回归验证
  - [ ] 重启服务，在浏览器中打开内部管理页面，验证首次加载时间 ≤ 5s
  - [ ] 反复切换"实时看板"↔"采集配置"↔"任务管理"各 10 次，验证每次切换 ≤ 100ms
  - [ ] 切换到周期看板数据集，验证 MySQL 不可达时降级行为正常（不卡死）
  - [ ] 在浏览器 console 中确认 `[Perf]` 日志正常输出
  - [ ] 运行 `backend/tools/smoke_api.py` 确认所有 API 端点正常响应

# Task Dependencies
- Task 2、3、4 依赖 Task 1（先量化问题再精准修复）
- Task 5 可与 Task 2、3、4 并行
- Task 6 依赖 Task 2、3、4、5（所有修复完成后回归验证）
