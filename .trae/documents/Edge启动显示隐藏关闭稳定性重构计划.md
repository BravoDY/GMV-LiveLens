## Summary

- 目标：彻底重构当前 Edge 会话控制链路，解决“点击启动Edge后长时间无响应、无错误提示、不启动”的问题，并确保 `启动 / 显示 / 隐藏 / 关闭` 四类动作都具备稳定执行、明确状态反馈、完善超时控制和结构化异常处理。
- 覆盖范围：
  - 单任务按钮：`启动Edge / 显示Edge / 隐藏Edge / 关闭Edge`
  - 平台批量按钮：平台级 `启动 / 显示 / 隐藏 / 关闭`
  - 后端会话控制器：`RemoteEdge`
  - Windows 主窗口控制：`window_control`
  - 前端 API 调用、超时、提示文案
- 约束：
  - 保持现有任务管理 UI 基本结构不变
  - 不能只修“启动”一个动作，要把四个动作统一为同一套稳定状态机
  - 必须有清晰的 `try/except`、超时、兜底和可观测错误码

## Current State Analysis

### 1. 前端当前启动机制的真实行为

- 文件：`frontend/app.js`
- 当前事实：
  - 任务管理里的 `启动Edge` 并不是调用单独的“start”接口，而是直接调用 `startAndShowEdgeSession(task.edge_session_id)`。
  - `startAndShowEdgeSession()` 实际只是 `return showEdgeSession(sessionId)`，见 `frontend/core.js`。
- 文件：`frontend/core.js`
- 当前事实：
  - `showEdgeSession()` 直接请求 `/api/edge-sessions/{session_id}/show`
  - `api()` 封装是裸 `fetch()`，没有 `AbortController`，没有请求超时，没有统一的 pending/timeout/error 分类
- 结论：
  - 当前前端一旦遇到后端长时间不返回，请求会一直 pending，用户看到的就是“点了按钮，等很久，不报错，也没启动”
  - 这不是纯粹的 UI 问题，而是**前端没有超时与中断机制**

### 2. 后端当前 show/start 链路的真实行为

- 文件：`backend/main.py`
- 当前事实：
  - `/api/edge-sessions/{session_id}/show` 调用 `await asyncio.to_thread(client.show_edge)`
  - `/api/edge-sessions/{session_id}/hide` 调用 `await asyncio.to_thread(client.hide_edge)`
  - `/api/edge-sessions/{session_id}/close` 调用 `await asyncio.to_thread(client.close_edge)`
  - 平台批量动作 `run_platform_edge_action()` 也复用同一套 client runner
- 文件：`backend/collectors/remote_edge.py`
- 当前事实：
  - `show_edge()` 会进入 `_call(self._show_edge)`
  - `_call()` 内部 `result_queue.get()` 没有 timeout
  - worker 线程 `_worker_loop()` 是单队列串行执行
  - `_show_edge()` 当前内部包含：
    1. `_start_edge()`
    2. `show_edge_window()`
    3. 失败后补原生窗口
    4. 失败后会话级受控重启
  - `_start_edge()` 自己就会循环等调试端口最多约 10 秒
  - `show_edge_window()` 自己也有等待窗口轮询
- 结论：
  - 当前 show 链路本身是“复合长流程”
  - 一旦其中任何一步卡住，`_call()` 无 timeout，API 线程就会一直等
  - **这是当前“前端一直转圈、不报错”的核心后端原因**

### 3. 当前阻塞点和不可控点

- 文件：`backend/collectors/remote_edge.py`
- 已确认的高风险阻塞点：
  - `_call()` 的 `result_queue.get()` 无超时
  - `_ensure_browser()` 依赖 Playwright `connect_over_cdp()`，出错时有异常，但没有统一动作级超时封顶
  - `_show_edge()` 把“启动 + 显示 + 补窗口 + 重启”混在一个同步请求里完成，导致单次请求时间过长
- 文件：`backend/collectors/window_control.py`
- 已确认的高风险点：
  - `show_edge_window()` / `hide_edge_window()` 本身有窗口轮询等待
  - 当前有诊断能力，但动作层还没有统一的 `reason_code / timeout_code / recovery_stage`
- 结论：
  - 当前不是单点 bug，而是**动作执行模型缺少统一超时与状态机**

### 4. 当前 hide/close 机制也不够稳

- 文件：`backend/collectors/remote_edge.py`
- 当前事实：
  - `hide_edge()` 和 `close_edge()` 虽然已有基本错误返回，但没有统一动作级恢复与阶段性错误码
  - `hide` 依赖找到现有窗口，如果找不到，错误仍较粗糙
  - `close` 成功与否主要看 kill 后端口是否还可访问，但缺乏更细的过程状态
- 文件：`backend/main.py`
- 当前事实：
  - `show` 接口已有 `reason_code` 雏形
  - `hide / close` 还没有同步的结构化错误返回规范
- 结论：
  - 你要求“显示、隐藏、关闭都是正确执行的”，就必须把四个动作统一成一个动作框架，而不是只加强 show

### 5. 当前 try/catch 机制不完整

- 文件：`frontend/app.js`
- 当前事实：
  - 单任务 `start-edge / show-edge` 已有局部 `try/catch`
  - `hide-edge / close-edge` 仍主要依赖外围统一异常处理
- 文件：`backend/main.py`
- 当前事实：
  - API 层主要靠 `HTTPException` 抛错
  - 没有“动作级 timeout 捕获 + 统一 reason_code + 统一 recovery_attempted + 统一动作阶段 stage”
- 结论：
  - 当前异常处理是不一致的，用户体验和排障信息会断层

## Proposed Changes

### 1. 重构前端 API 调用层，为 Edge 动作加入超时、中断和标准错误包装

- 文件：`frontend/core.js`
- 计划：
  - 为 `api()` 增加可选超时支持，基于 `AbortController`
  - 为 Edge 动作单独封装统一请求函数，例如：
    - `callEdgeAction(path, { timeoutMs, actionName })`
  - 超时后返回标准化前端错误，而不是无限 pending
- 具体策略：
  - `show / hide / close / platform edge action` 全部接入统一超时层
  - 不再让裸 `fetch()` 无限制等待
- 为什么：
  - 这是解决“点了没反应也没报错”的第一道防线

### 2. 将前端“启动Edge”从语义上拆清楚

- 文件：`frontend/core.js`
- 文件：`frontend/app.js`
- 计划：
  - 明确区分：
    - `startEdgeSession()`：只负责启动/确保调试端口可用
    - `showEdgeSession()`：只负责确保有可显示窗口并前置显示
    - `startAndShowEdgeSession()`：显式串联两步，且分阶段处理错误
  - 前端提示文案区分：
    - 启动失败
    - 端口已起但无窗口
    - 已尝试恢复窗口
    - 操作超时
- 为什么：
  - 当前“启动”实质等于“show”，语义混乱，不利于诊断和恢复

### 3. 为 `RemoteEdge` 引入统一动作执行器，彻底解决 worker 无限等待

- 文件：`backend/collectors/remote_edge.py`
- 计划：
  - 将 `_call()` 升级为带超时和动作名的执行入口，例如：
    - `self._call("show_edge", self._show_edge, timeout_seconds=...)`
  - `result_queue.get()` 必须带超时
  - 超时后返回明确异常，如：
    - `edge_action_timeout:show_edge`
    - `edge_action_timeout:start_edge`
  - 若 worker 长时间卡死，记录动作阶段并允许后续请求得到明确错误，而不是一起永久挂起
- 为什么：
  - 当前最大问题不是“报错不够好”，而是**可能永远不返回**

### 4. 将四类动作统一为状态机式执行模型

- 文件：`backend/collectors/remote_edge.py`
- 计划：
  - 为四类动作统一输出：
    - `action`
    - `stage`
    - `ok / debug_available / window_found / closed`
    - `reason_code`
    - `recovery_attempted`
    - `window_diagnostics`
    - `last_error`
  - 建议动作阶段示例：
    - `start: locating_edge`
    - `start: launching_process`
    - `start: waiting_debug_port`
    - `show: finding_window`
    - `show: spawn_native_window`
    - `show: controlled_restart`
    - `hide: finding_window`
    - `close: killing_process_tree`
    - `close: verifying_shutdown`
- 为什么：
  - 这样才能把 `启动 / 显示 / 隐藏 / 关闭` 真正做成一套可观测系统，而不是零散函数

### 5. 重构 start 机制，避免“show 里顺带 start”导致超长同步阻塞

- 文件：`backend/collectors/remote_edge.py`
- 计划：
  - 拆分 `_start_edge()` 和 `_show_edge()` 的职责
  - `show_edge()` 中如果检测到调试端口未开启：
    - 先走受控 `start`
    - `start` 成功后再进入 `show`
  - 两步各自有独立超时和错误码
- 为什么：
  - 当前单个 show 请求串了太多步骤，用户感觉就是“点了后系统没反应”

### 6. 把窗口恢复从“黑盒重试”改成“阶段化恢复”

- 文件：`backend/collectors/remote_edge.py`
- 文件：`backend/collectors/window_control.py`
- 计划：
  - `show` 动作按顺序执行：
    1. 查找现有窗口
    2. 如果端口在但无窗口，补原生窗口
    3. 如果仍失败，判断是否进入 `--no-startup-window`
    4. 满足条件时只重启当前 session
    5. 最终返回阶段信息和诊断结果
  - 所有恢复步骤单独包 `try/except`
  - 每一步失败都保留错误上下文
- 为什么：
  - 你要“完美解决启动问题”，核心就是让恢复链路变成可控、可解释、可终止

### 7. hide / close 同步纳入统一超时与错误码

- 文件：`backend/collectors/remote_edge.py`
- 文件：`backend/main.py`
- 计划：
  - `hide`：
    - 加动作级 timeout
    - 如果找不到窗口，返回结构化 `reason_code`
    - 明确区分“会话没起”“有端口但无窗”“隐藏成功”
  - `close`：
    - 加动作级 timeout
    - 明确区分“已杀进程但端口未释放”“部分进程残留”“完全关闭成功”
  - API 层将 `show / hide / close / start` 的 detail 结构对齐
- 为什么：
  - 如果只修 start/show，hide/close 仍会保留不一致行为

### 8. API 层统一错误包装与 try/except

- 文件：`backend/main.py`
- 计划：
  - 为单会话和平台批量接口统一封装动作执行器
  - 捕获：
    - 动作超时
    - 会话不存在
    - 端口未打开
    - 窗口未找到
    - 受控重启失败
  - 统一输出：
    - `error`
    - `reason_code`
    - `action`
    - `stage`
    - `recovery_attempted`
    - `health`
- 为什么：
  - 当前 API 结构不完全统一，前端无法稳定展示

### 9. 前端交互补齐 loading、禁用态和阶段提示

- 文件：`frontend/app.js`
- 计划：
  - 点击 `启动Edge / 显示Edge / 隐藏Edge / 关闭Edge` 时：
    - 禁用当前按钮或当前任务卡片内相关 Edge 按钮
    - 显示阶段性提示，如“正在启动调试端口”“正在恢复窗口”“正在关闭进程”
  - 请求结束后恢复按钮状态
  - 如果超时，明确提示“操作超时，而不是无响应”
- 为什么：
  - 用户现在最痛的体验是“完全不知道系统在做什么”

## Assumptions & Decisions

- 已确认的目标：
  - 优先解决“启动Edge无响应”
  - 同时把 `显示 / 隐藏 / 关闭` 一起做成稳定方案
  - 必须有完善 `try/catch` 和动作级错误处理
- 已确认的代码事实：
  - 当前前端 `启动Edge` 实际调用 `/show`
  - 当前前端 `fetch` 没有超时控制
  - 当前后端 worker `_call()` 无 timeout，存在无限等待风险
  - 平台批量动作复用同一套 client action，因此也必须同步重构
- 本次设计决策：
  - 不做“小修补等几秒再试”
  - 直接重构为“动作分层 + 超时控制 + 状态机 + 统一错误结构”
  - 优先保证“不会无限挂起”，其次再优化恢复成功率

## Verification Steps

### 1. 单任务动作验证

- 在 `任务管理` 中对同一任务分别测试：
  - `启动Edge`
  - `显示Edge`
  - `隐藏Edge`
  - `关闭Edge`
- 验证：
  - 每个动作点击后都有明确 loading/pending 提示
  - 每个动作都不会无限等待
  - 超时时会返回明确错误
  - 成功时能返回明确成功提示

### 2. 启动问题专项验证

- 场景 A：Edge 未启动
  - 点击 `启动Edge`
  - 验证：
    - 能先启动调试端口
    - 再显示主窗口
    - 若失败，能指出失败阶段
- 场景 B：端口已开但窗口不存在
  - 点击 `启动Edge` 或 `显示Edge`
  - 验证：
    - 会尝试补原生窗口
    - 必要时只重启当前 session
    - 不影响其他 session
- 场景 C：worker 内部动作卡死
  - 验证：
    - 前端不会无限 pending
    - 后端会返回 timeout 类错误

### 3. hide / close 验证

- `隐藏Edge`
  - 验证窗口确实被移到屏幕外
  - 若无窗口，返回结构化错误
- `关闭Edge`
  - 验证只关闭当前 session 相关进程
  - 验证关闭后调试端口不可访问
  - 验证残留进程时有明确错误信息

### 4. 平台批量动作验证

- 对平台级按钮分别测试：
  - `启动Edge`
  - `显示Edge`
  - `隐藏Edge`
  - `关闭Edge`
- 验证：
  - 单个任务失败不会导致整个平台结果不可见
  - 每个失败项都包含结构化错误信息
  - 平台级总结果能看出成功数、失败数和失败原因摘要

### 5. 回归验证

- `采集配置` 页签中的 Edge 会话能力不被破坏
- `open / pages / preview` 相关真实 Edge 页面能力不被破坏
- 现有多会话 `user_data_dir` 隔离能力不被破坏

