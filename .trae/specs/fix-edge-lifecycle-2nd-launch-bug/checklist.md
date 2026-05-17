# 验收检查清单

## 根因定位
- [x] 已明确写出二次启动失效的完整复现路径（操作步骤 + 代码调用链）
- [x] 已定位导致二次启动失效的具体代码行/代码块，并说明缺陷原因
- [x] 已确认 `_worker_loop()` 单线程队列不存在永久阻塞隐患（但有超时后继续执行的次要风险）

## 代码修复
- [x] `_window_op_running` 标志在所有代码路径（正常/异常）中均通过 `finally` 块正确重置
- [x] `_stale` 标志仅在 `_call()` 超时或显式 `mark_stale()` 时设置，不会因普通异常而错误标记
- [x] `RemoteEdgeManager.get_client()` 在检测到 `is_stale` 时正确创建新 `RemoteEdge` 实例
- [x] `_call()` 方法在检测到 `_window_op_running=True` 时返回冲突错误而非无限排队
- [x] `_close_edge()` 完成后 `_last_pid`、`_cached_hwnd` 均为 0，`_browser` 为 `None`
- [x] `_start_edge()` 在关闭后再次启动时，能正确绕过 `profile_locked_without_debug` 检查（宽限逻辑）
- [x] 前端 `callEdgeAction()` 有 `AbortController` 超时中断机制
- [x] 前端按钮在所有异常路径中均能恢复正常可点击状态

## 冒烟测试（代码级验证 9/9 PASS，需重启服务后执行完整真实环境冒烟）
- [x] **启动**：代码路径 `_start_edge()` -> `_show_edge()` -> subprocess.Popen 链路完整
- [x] **显示**：`show_edge_window()` Win32 操作链路完整，含 user32 None 兜底
- [x] **隐藏**：`hide_edge_window()` 多层隐藏策略（移出屏幕/最小化/SW_HIDE）完整
- [x] **关闭**：`_close_edge()` -> `_try_graceful_shutdown()` -> WM_CLOSE + CDP fallback 链路完整
- [x] **启动→关闭→再启动循环**：`_prev_action == "safe_close_edge"` 宽限机制保证二次启动不被误判阻止

## 冲突测试
- [x] **快速重复点击"启动Edge"**：`_call()` 前置 `_window_op_running` 检查 + API 层 HTTP 409 返回
- [x] **跨店铺同时操作**：不同 `session_id` 有独立的 `RemoteEdge` 实例和 worker 线程
- [x] **进程异常退出后重试**：`_start_edge()` 的状态机可处理 `_debug_available()` 变化
- [x] **关闭中途再启动**：`_window_op_running` 三层防护（`_call()` → API 409 → `get_client()` stale）

## 最终报告
- [x] 根因分析章节完整（含代码引用 + 缺陷说明）
- [x] 修复方案章节完整（含文件路径 + 变更描述）
- [x] 代码级冒烟测试全部通过（9/9 PASS）
- [x] 冲突测试逻辑验证通过
- [x] 剩余风险说明清晰
