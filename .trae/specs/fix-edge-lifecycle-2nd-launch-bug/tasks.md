# Tasks

- [x] Task 1: 二次启动失效根因定位
  - [x] 在 [_actions.py](file:///d:/User_Project/GMV-LiveLens/backend/collectors/edge/_actions.py) `_start_edge()` 方法中追踪关闭后再次启动的完整代码路径，确认每一步的状态变化
  - [x] 检查 [_session.py](file:///d:/User_Project/GMV-LiveLens/backend/collectors/edge/_session.py) 中 `RemoteEdgeManager.get_client()` 在关闭后是否正确复用或重建 `RemoteEdge` 实例
  - [x] 确认 `_close_edge()` 完成后 `_reset_browser()` 是否正确释放了 Playwright 连接，`_last_pid` 和 `_cached_hwnd` 是否重置为 0
  - [x] 验证 `_worker_loop()` 单线程队列是否会因前一个操作残留导致后续操作永久阻塞
  - [x] 对照已有文档（`Edge启动显示隐藏关闭稳定性重构计划.md`）中标记的阻塞点逐一验证当前代码状态
  - [x] 输出根因分析报告，明确列出导致二次启动失效的具体代码缺陷

- [x] Task 2: 四项功能代码健壮性审查与加固
  - [x] 审查 [_window.py](file:///d:/User_Project/GMVV-LiveLens/backend/collectors/edge/_window.py) 中 `__show_edge()`、`__hide_edge()`、`__close_edge()` 的异常分支覆盖
  - [x] 审查 [window_control.py](file:///d:/User_Project/GMV-LiveLens/backend/collectors/window_control.py) 中 `show_edge_window()`、`hide_edge_window()`、`close_edge_window_native()` 对 `user32 is None` 及 Win32 API 调用失败的兜底
  - [x] 检查所有 `try/except` 块：确认每个异常分支都有明确的 `_last_reason_code` 赋值和错误信息
  - [x] 验证 `_window_op_running` 标志在所有代码路径（包括异常路径）中均通过 `finally` 块重置
  - [x] 检查 `_stale` 标志的设置时机：仅 `_call()` 超时、`mark_stale()` 显式调用、及 `RemoteEdgeManager.reset_client()` 时设置
  - [x] 修复发现的缺陷：补充缺失的异常处理、添加资源释放 `finally` 块、修正错误的状态位设置（双重 `_reset_browser()` 修复）

- [x] Task 3: 会话状态锁与并发控制修复
  - [x] 在 `_call()` 方法中增加前置的 `_window_op_running` 检查：当已有窗口操作在执行时，新的窗口操作应返回冲突错误而非排队阻塞
  - [x] 确保 `RemoteEdgeManager.get_client()` 在检测到 `is_stale` 时正确创建新实例，且旧实例的 worker 线程不会残留影响新实例
  - [x] 在 API 层 (`edge_sessions.py`) 增加 `_window_op_running` 检查，返回 HTTP 409

- [x] Task 4: 进程残留检测与端口释放验证增强
  - [x] 在 `__close_edge()` 的 `_try_graceful_shutdown()` 失败路径中，增加进程残留的显式诊断日志（已有 `profile_process_still_running` reason_code）
  - [x] 在 `_start_edge()` 启动新进程前，增加端口释放等待逻辑：close 后轮询最多 3 秒
  - [x] 增强 `close_edge_window_native()` 的进程检测准确性：每次轮询前强制刷新 `_EDGE_PROC_CACHE`
  - [x] 在 `_close_edge()` 后增加 `_stale` 标记的显式重置：关闭成功后设置 `_stale=False`
  - [x] 在 `_start_edge()` 中增加 close→start 宽限：`_prev_action == "safe_close_edge"` 时跳过 `profile_locked_without_debug`

- [x] Task 5: 前端超时控制与按钮状态修复
  - [x] 在 [core.js](file:///d:/User_Project/GMV-LiveLens/frontend/core.js) 的 `callEdgeAction()` 中增加 `AbortController` 超时中断机制
  - [x] 在 [dashboard.js](file:///d:/User_Project/GMV-LiveLens/frontend/dashboard.js) 的 `bindTaskEdgeButtons()` 中确保按钮在 `catch` 块中也能正确恢复（增加 `showMessage` 错误提示）
  - [x] 增加操作进行中的视觉反馈（按钮显示具体操作如"启动中..."）
  - [x] 修复按钮事件重复绑定：`bindTaskEdgeButtons()` 使用 `data-task-edge-bound` 防止重复（已确认无冲突）

- [ ] Task 6: 冒烟测试执行
  - [ ] 对修复后的**启动**功能进行单店铺冒烟：点击"启动Edge" → 验证 Edge 进程启动、调试端口就绪、窗口显示
  - [ ] 对修复后的**显示**功能进行单店铺冒烟：Edge 在后台/屏幕外时 → 点击"显示Edge" → 验证窗口回到主屏前台
  - [ ] 对修复后的**隐藏**功能进行单店铺冒烟：Edge 可见时 → 点击"隐藏Edge" → 验证窗口移出屏幕外或最小化
  - [ ] 对修复后的**关闭**功能进行单店铺冒烟：Edge 运行中 → 点击"关闭Edge" → 验证进程退出、端口释放、无残留
  - [ ] **关键冒烟**：执行"启动→关闭→再启动"完整循环至少 3 次，确认每次都能成功

- [ ] Task 7: 冲突测试执行
  - [ ] 重复点击测试：快速连续点击"启动Edge"按钮 3 次，验证不启动多个 Edge 进程
  - [ ] 跨店铺同时操作：对店铺A点击"启动Edge"的同时对店铺B点击"启动Edge"，验证两个独立会话互不干扰
  - [ ] 进程异常退出后重试：手动在任务管理器中强杀 Edge 进程，然后点击"启动Edge"，验证系统能正确恢复
  - [ ] 关闭中途再启动：快速点击"关闭Edge"后立即点击"启动Edge"，验证冲突正确处理
  - [ ] 网络波动模拟（可选）：在 Edge 启动过程中短暂断开 localhost 连接，验证超时恢复机制

- [ ] Task 8: 输出 Bug 修复报告
  - [ ] 整理根因分析结果，含复现路径、代码缺陷定位、修复前后对比
  - [ ] 汇总所有代码变更（文件路径 + 行级 diff 说明）
  - [ ] 汇总冒烟测试与冲突测试的用例执行结果
  - [ ] 给出最终结论：二次启动失效问题是否已彻底解决，剩余风险说明

# Task Dependencies
- Task 2 依赖 Task 1（先定位根因，再审查加固）
- Task 3 依赖 Task 1（先理解状态流转缺陷，再修复锁机制）
- Task 4 可与 Task 2、3 并行
- Task 5 可与 Task 2、3、4 并行
- Task 6 依赖 Task 2、3、4、5（所有修复完成后执行冒烟测试）
- Task 7 依赖 Task 6（冒烟通过后执行冲突测试）
- Task 8 依赖 Task 6、7（所有测试完成后输出报告）
