# Edge 四功能生命周期异常排查与二次启动修复 Spec

## Why
当前 Edge 窗口控制功能存在严重的二次启动失效问题：首次启动 Edge 并关闭后，再次点击"启动Edge"按钮完全无响应（无启动动作、无错误提示）。用户必须手动重启整个 GMV-LiveLens 服务才能恢复，严重影响任务管理模块的可用性。本 Spec 对该问题进行根因定位，并对启动、显示、隐藏、关闭四项核心功能进行全链路排查与健壮性加固。

## What Changes
- 定位"关闭后二次启动完全失效"的核心根因并修复
- 对 Edge **启动(Start)**、**显示(Show)**、**隐藏(Hide)**、**关闭(Close)** 四项功能进行全链路代码审查与异常分支加固
- 修复会话状态锁未正确重置、进程残留检测不完善、并发请求阻塞等问题
- 增加四项功能的冒烟测试与冲突测试方案
- 输出完整的 Bug 修复报告

## Impact
- Affected specs: 无（新增独立 spec）
- Affected code:
  - `backend/collectors/edge/_session.py` — RemoteEdgeSessionMixin: worker 线程、`_call()` 超时与会话陈旧标记
  - `backend/collectors/edge/_actions.py` — RemoteEdgeActionsMixin: `_start_edge()` 启动逻辑
  - `backend/collectors/edge/_window.py` — RemoteEdgeWindowMixin: `_show_edge()`, `_hide_edge()`, `_close_edge()`
  - `backend/collectors/window_control.py` — Win32 窗口操作与进程诊断
  - `backend/routers/edge_sessions.py` — API 路由层错误处理
  - `backend/routers/common.py` — `edge_client_for()`, `RemoteEdgeManager.get_client()` 会话复用逻辑
  - `frontend/core.js` — `startAndShowEdgeSession()`, `callEdgeAction()` 超时处理
  - `frontend/dashboard.js` — `bindTaskEdgeButtons()` 事件绑定与状态反馈

## ADDED Requirements

### Requirement: 二次启动可靠性
系统 SHALL 确保 Edge 会话在关闭后能够被再次成功启动，且不依赖外部服务重启。

#### Scenario: 启动→关闭→再次启动成功
- **WHEN** 用户对某店铺执行"启动Edge" → Edge 正常启动并显示 → 用户执行"关闭Edge" → Edge 完全关闭
- **THEN** 用户再次点击同一店铺的"启动Edge"时，系统应正常启动新的 Edge 进程并完成调试端口连接
- **AND** 前端按钮应在操作完成后恢复正常可点击状态，不会永久 disabled

#### Scenario: 关闭中途再次启动被正确拦截
- **WHEN** 用户执行"关闭Edge"操作过程中（关闭尚未完成），再次点击"启动Edge"
- **THEN** 系统应检测到前一个操作仍在执行中，返回合理的冲突提示或排队等待
- **AND** 不会导致两个操作的 worker 线程互相阻塞

### Requirement: 会话状态锁正确重置
系统 SHALL 在每次窗口操作（启动/显示/隐藏/关闭）完成后，无论成功或失败，均正确重置所有内部状态锁。

#### Scenario: 关闭操作异常中断后状态恢复
- **WHEN** 关闭 Edge 过程中发生异常（如 WM_CLOSE 超时）
- **THEN** `_window_op_running` 标志必须被重置为 `False`
- **AND** `_stale` 标记仅在 `_call()` 超时时才设置为 `True`，不应因普通异常而错误标记

#### Scenario: 超时后会话重置可恢复
- **WHEN** 某次 Edge 操作因 `EdgeActionTimeoutError` 超时，`RemoteEdgeManager.reset_client()` 被调用
- **THEN** 后续对该 session_id 的 `get_client()` 调用应创建全新的 `RemoteEdge` 实例
- **AND** 新实例的 `_window_op_running`、`_stale` 等状态位均为初始值

### Requirement: 进程残留检测与端口释放验证
系统 SHALL 在关闭 Edge 后执行进程残留检测，并在启动前验证目标端口是否完全释放。

#### Scenario: 关闭后确认无残留进程
- **WHEN** `close_edge()` 完成优雅关闭流程
- **THEN** 系统应通过 `edge_window_diagnostics()` 确认无残留进程（candidate_pids 为空）
- **AND** 通过 `_debug_available()` 确认调试端口已完全释放

#### Scenario: 检测到残留进程时的启动保护
- **WHEN** 用户执行"启动Edge"，但 `_start_edge()` 检测到同一 `user_data_dir` 有残留进程且未携带调试端口参数
- **THEN** 系统应返回清晰错误提示「当前店铺 Profile 已被一个未开启调试端口的 Edge 进程占用」
- **AND** 不应尝试强行启动新进程（已实现此逻辑，需验证完整性）

### Requirement: 四项功能全链路代码健壮性
系统 SHALL 对四项功能的代码进行异常分支覆盖检查，确保以下维度均有合理处理：

- **异常分支处理**：每个 `try/except` 块有明确的异常分类与恢复策略
- **资源释放逻辑**：Playwright browser、subprocess 句柄、Win32 窗口操作在异常路径中也正确释放
- **进程状态检测**：`tasklist` / WMI 查询使用缓存（1s TTL），避免高开销
- **并发请求拦截**：`_window_op_running` 标志在操作期间阻止冲突请求
- **跨模块状态同步**：`RemoteEdgeManager` 与 `RemoteEdge` 实例之间的状态一致性

### Requirement: 前端超时与状态反馈
系统 SHALL 为前端 Edge 操作按钮提供超时控制与准确的状态反馈。

#### Scenario: 后端操作超时前端有明确提示
- **WHEN** 前端发起 `callEdgeAction()` 在后端执行超过 20 秒
- **THEN** 前端应通过 `AbortController` 超时中断请求
- **AND** 显示用户可理解的操作超时提示，而非静默失败

#### Scenario: 操作完成后按钮恢复正常
- **WHEN** 任何 Edge 操作（启动/显示/隐藏/关闭）完成（无论成功或失败）
- **THEN** 前端触发按钮应恢复为可点击状态，显示正确的标签文字
- **AND** 任务列表应在 1.5 秒后刷新以反映最新的 Edge 会话状态

## MODIFIED Requirements

### Requirement: `_call()` 方法增加超时与陈旧标记
原有 `_call()` 方法在 `result_queue.get()` 无超时时会永久阻塞。修改为：
- 所有动作必须有超时（通过 `ACTION_TIMEOUTS` 或调用方传入）
- 超时后设置 `_stale = True`，并抛出 `EdgeActionTimeoutError`
- `RemoteEdgeManager.get_client()` 在发现 `is_stale` 时自动创建新实例（已实现，需验证）

## REMOVED Requirements
无移除项。
