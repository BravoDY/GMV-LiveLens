# 前端导航切换卡顿排查与优化 Spec

## Why
用户在 GMV-LiveLens 内部管理页面切换导航（实时看板 ↔ 采集配置 ↔ 任务管理）时出现长时间卡顿，表现为点击导航按钮后页面冻结 2-20 秒无响应。经代码调研确认：`switchView()` 本身是纯 CSS 类切换（零开销），卡顿根因在导航切换前后关联的初始化加载链、轮询渲染覆盖、以及后端 API 阻塞。

## What Changes
- 排查并修复页面初始化时 `GET /api/edge-sessions` 因逐会话串行健康检查导致的长时间阻塞
- 优化 `renderDashboard()` 仅在"实时看板"视图激活时渲染，避免非活跃视图的无效 DOM 操作
- 为周期看板 MySQL 查询增加超时兜底与连接池配置
- 前端增加导航切换性能埋点与后端 API 耗时监控
- 修复 `connect_timeout=10s` 级联阻塞：MySQL 不可达时前端应快速降级而非卡死

## Impact
- Affected specs: 无（新增独立 spec）
- Affected code:
  - `backend/routers/common.py` — `build_edge_session_item()` 逐会话健康检查串行化
  - `backend/services/dashboard_query.py` — MySQL `connect_timeout=10s` 无连接池
  - `frontend/dashboard.js` — `renderDashboard()` 全视图渲染
  - `frontend/app.js` — `startInternalDashboard()` 初始化加载链
  - `frontend/core.js` — `connectLiveWebSocket()` 配置
  - `frontend/dashboard-public.js` — 数据集切换加载

## ADDED Requirements

### Requirement: 页面初始化 API 加载链不阻塞 UI
系统 SHALL 确保内部管理页面首次加载时，所有 API 请求的串行链路不会导致超过 3 秒的 UI 阻塞。

#### Scenario: 首次加载页面导航可立即响应
- **WHEN** 用户打开 `/` 路由（内部管理模式）
- **THEN** `startInternalDashboard()` 中的 `refreshEdgeSessions()` 调用 SHALL 在 3 秒内返回初始渲染数据
- **AND** 导航 tab 按钮在初始化完成前即可点击切换视图
- **AND** 若 `GET /api/edge-sessions` 超时，不影响看板渲染和任务列表展示

#### Scenario: Edge 会话健康检查不阻塞页面加载
- **WHEN** 后端 `GET /api/edge-sessions` 遍历多个 Edge 会话并逐一调用 `health()`
- **THEN** 每个会话的健康检查超时不得超过 5 秒
- **AND** 健康检查失败的会话不应阻塞其他会话的健康检查
- **AND** 前端在收到部分健康数据后即可渲染，缺失的会话显示"加载中"状态

### Requirement: 导航切换无无效渲染
系统 SHALL 确保 `renderDashboard()` 仅在"实时看板"视图激活时执行完整渲染，避免在"采集配置"或"任务管理"视图下进行不必要的 DOM 重建。

#### Scenario: 采集配置视图中跳过看板渲染
- **WHEN** 用户当前在"采集配置"视图，且 1.2 秒轮询返回新的 `/api/dashboard` 数据
- **THEN** `renderDashboard()` SHALL 检测当前激活视图：若非 `dashboard` 视图，仅更新 `state.snapshot` 数据，跳过 DOM 渲染
- **AND** 当用户切换回"实时看板"视图时，立即用最新缓存数据渲染

#### Scenario: 任务管理视图中跳过 managerGrid 重建
- **WHEN** 用户当前在"实时看板"视图，且 1.2 秒轮刷新渲染
- **THEN** `renderDashboard()` 中的 `managerGrid` 渲染 SHALL 仅在被激活时才刷新内容
- **AND** 不活跃的 `managerGrid` 保留上次渲染的快照，避免无效的重建和事件重绑定

### Requirement: MySQL 周期查询超时与降级
系统 SHALL 确保周期看板数据集的 MySQL 查询在连接超时时快速降级，不阻塞前端。

#### Scenario: MySQL 不可达时前端不卡死
- **WHEN** 用户切换到周期看板数据集，后端需要查询 MySQL，但 MySQL 服务不可达
- **THEN** MySQL 连接超时不得超过 5 秒（当前为 10 秒）
- **AND** 后端返回降级数据（使用文件缓存或空数据），而非等待超时后抛 500
- **AND** 前端显示"周期数据暂不可用，已使用缓存数据"提示

#### Scenario: MySQL 连接池避免频繁建连
- **WHEN** 周期看板需要多次查询 MySQL（如多个数据集连续切换）
- **THEN** 系统 SHALL 使用连接池复用连接，而非每次 `pymysql.connect()`
- **AND** 连接池最小空闲连接数 ≥ 1，最大连接数 ≤ 5

### Requirement: 前端性能监控埋点
系统 SHALL 在前端关键导航路径上增加性能埋点，便于后续实时监控卡顿复现。

#### Scenario: 导航切换耗时记录
- **WHEN** 用户点击导航按钮触发 `switchView()`
- **THEN** 前端 SHALL 记录切换前后的 `performance.now()` 时间戳
- **AND** 在浏览器 console 中输出 `[Perf] switchView: Xms` 格式日志
- **AND** 若单次切换耗时超过 100ms，输出 `[Perf] SLOW switchView: Xms` 警告日志

#### Scenario: API 请求耗时跟踪
- **WHEN** 前端发起任何 `fetch()` 请求
- **THEN** `api()` 和 `callEdgeAction()` 函数 SHALL 记录请求的 start/end 时间戳
- **AND** 在 console 中输出 `[Perf] GET /api/xxx: Xms (status=N)` 格式日志

## MODIFIED Requirements

### Requirement: `build_edge_session_item()` 健康检查超时
当前 [common.py](file:///d:/User_Project/GMV-LiveLens/backend/routers/common.py) 中 `build_edge_session_item()` 通过 `asyncio.gather()` 并行调用，但每个 `edge_health_payload()` 内部可能因 `health()` 方法阻塞。修改为：
- 每个会话的健康检查增加 **5 秒超时**
- 超时后返回 `debug_available: false` 的降级健康数据
- 不阻塞 `GET /api/edge-sessions` 的整体响应

### Requirement: MySQL 查询超时收紧
当前 [dashboard_query.py](file:///d:/User_Project/GMV-LiveLens/backend/services/dashboard_query.py) 中 `connect_timeout=10s, read_timeout=30s`。修改为：
- `connect_timeout=5s`
- `read_timeout=15s`
- 新增 `pymysql.err.OperationalError` 捕获，返回空缓存数据而非抛异常
- 新增连接池（`DBUtils.PooledDB` 或 `queue` 实现），最大 5 连接

## REMOVED Requirements
无移除项。
