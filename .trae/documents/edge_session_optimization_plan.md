# Edge Session 工作线程与日志流控优化方案

## 一、根因分析

### 1.1 日志持续滚动打印的根因

问题链路如下：

```
_run_loop() [scheduler.py:99]
  → capture_once() [scheduler.py:215]
    → client.find_page(task.page_id) [_page.py:285]
      → _call("find_page", ...) [_session.py:249]
        → _jobs.put(job)  [提交任务给 worker 线程]
        → result_queue.get(timeout=10.0)  [等待结果]
          → _worker_loop [_session.py:239]
            → func() = _find_page() → _list_pages() → _ensure_browser()
              → 抛出 RuntimeError("真实 Edge 调试端口未连接...")
          → result_queue.put((False, exc))  [worker 返回异常]
        → raise value  [重新抛出异常]  [_session.py:270]
      → 异常向上传播
    → except Exception [scheduler.py:357]
      → logger.error(f"Capture error: {exc}\n{traceback.format_exc()}")  ⬅ 每次打印完整堆栈
  → 调度器按 task_interval (默认1s) 周期性重新调度同一任务
  → 错误重复触发，日志持续滚动
```

**核心根因**：
- `scheduler.py` 第 357-359 行的 `except Exception` 分支每次都用 `traceback.format_exc()` 输出完整堆栈
- 调度器会按间隔周期性重试同一任务，而底层问题（如调试端口未连接）短时间内不会自愈
- 每次重试都触发完整错误日志，导致日志快速滚动刷屏

### 1.2 后台资源占用过高的根因

| 问题 | 代码位置 | 根因 |
|------|----------|------|
| 工作队列无限容量 | `_session.py:215` | `self._jobs = queue.Queue()` — 无 maxsize，任务可无限堆积 |
| 线程无空闲回收 | `_session.py:235` | `_worker_loop` 是 `daemon=True` 的无限循环，空闲时不退出 |
| 废弃 client 线程泄漏 | `_init__.py:37` → `_session.py:571-613` | `RemoteEdgeManager.get_client()` 替换旧 client 时仅 dereference，不停止其工作线程 |
| 超时后 worker 空转 | `_session.py:244,261` | `_call()` 超时后调用者放弃等待，但 worker 仍执行 `func()` 并将结果放入无人读取的 `result_queue` |

---

## 二、优化方案

### 2.1 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `backend/collectors/edge/_session.py` | 核心：worker 循环优化、队列容量限制、空闲回收、异常处理增强 |
| `backend/services/scheduler.py` | 日志限流、减少冗余 traceback 输出 |
| `backend/utils/log_throttle.py` | **新建**：通用日志限流工具类 |

---

### 2.2 修改详情

#### 修改 1：`_session.py` — Worker 线程池优化

**位置**：`RemoteEdgeSessionMixin.__init__()` 和 `_worker_loop()`

**当前代码** (`_session.py` L197-L247)：
```python
class RemoteEdgeSessionMixin:
    def __init__(self, session_id="default_real_edge", name="Real Edge Default",
                 debug_port=DEBUG_PORT, user_data_dir="", session_mode="isolated",
                 profile_directory="Default"):
        ...
        self._jobs: queue.Queue = queue.Queue()
        self._ready = threading.Event()
        ...
        self._thread = threading.Thread(target=self._worker_loop, name="gmv-remote-edge", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10)

    def _worker_loop(self) -> None:
        self._ready.set()
        while True:
            action_name, func, result_queue = self._jobs.get()
            try:
                result_queue.put((True, func()))
            except Exception as exc:
                self._last_error = str(exc)
                result_queue.put((False, exc))
```

**优化后代码**：

```python
import os
import logging

logger = logging.getLogger(__name__)

# 环境变量可配置参数
_WORKER_IDLE_TIMEOUT = float(os.environ.get("GMV_EDGE_WORKER_IDLE_TIMEOUT", "300"))   # 5分钟空闲退出
_JOBS_QUEUE_MAXSIZE = int(os.environ.get("GMV_EDGE_JOBS_QUEUE_MAXSIZE", "10"))        # 队列最大容量
_WORKER_JOIN_TIMEOUT = float(os.environ.get("GMV_EDGE_WORKER_JOIN_TIMEOUT", "5.0"))   # 停止等待超时

class RemoteEdgeSessionMixin:
    def __init__(self, session_id="default_real_edge", name="Real Edge Default",
                 debug_port=DEBUG_PORT, user_data_dir="", session_mode="isolated",
                 profile_directory="Default"):
        ...
        self._jobs: queue.Queue = queue.Queue(maxsize=_JOBS_QUEUE_MAXSIZE)
        self._ready = threading.Event()
        self._worker_stop = threading.Event()         # 新增：停止信号
        self._worker_exited = threading.Event()        # 新增：退出确认
        self._active_job_count = 0                     # 新增：活跃任务计数（用于结果废弃判断）
        ...
        self._thread = threading.Thread(target=self._worker_loop, name="gmv-remote-edge", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10)

    def _worker_loop(self) -> None:
        self._ready.set()
        while not self._worker_stop.is_set():
            try:
                job = self._jobs.get(timeout=5.0)      # 每5秒检查一次停止信号
            except queue.Empty:
                continue                               # 空闲时周期性检查停止信号
            action_name, func, result_queue, job_id = job
            try:
                result = func()
                if not self._worker_stop.is_set():     # 仅在未停止时写入结果
                    try:
                        result_queue.put((True, result), timeout=1.0)
                    except queue.Full:
                        logger.warning("worker result_queue full, discarding result for action=%s job_id=%s",
                                       action_name, job_id)
            except Exception as exc:
                self._last_error = str(exc)
                if not self._worker_stop.is_set():
                    try:
                        result_queue.put((False, exc), timeout=1.0)
                    except queue.Full:
                        logger.warning("worker result_queue full, discarding exception for action=%s job_id=%s: %s",
                                       action_name, job_id, exc)
        self._worker_exited.set()
        logger.info("worker thread exiting gracefully, session_id=%s", self.session_id)

    def _shutdown_worker(self) -> None:
        """优雅关闭工作线程"""
        if not self._thread.is_alive():
            return
        self._worker_stop.set()
        try:
            # 放入哨兵任务唤醒可能阻塞在 _jobs.get() 的线程
            self._jobs.put(("__shutdown__", lambda: None, queue.Queue(maxsize=1), -1),
                           timeout=1.0)
        except queue.Full:
            pass
        self._thread.join(timeout=_WORKER_JOIN_TIMEOUT)
        if self._thread.is_alive():
            logger.warning("worker thread did not exit in time for session_id=%s", self.session_id)
```

#### 修改 2：`_session.py` — `_call()` 超时与队列保护

**位置**：`_session.py` L249-L270

**优化后代码**：

```python
    def _call(self, action_name: str, func: Callable[[], T], timeout_seconds: float | None = None) -> T:
        if self._worker_stop.is_set() or not self._thread.is_alive():
            exc = RuntimeError(f"Edge worker 已停止，无法执行 {action_name}")
            self._stale = True
            self._stale_reason = f"worker_stopped:{action_name}"
            raise exc
        if self._window_op_running and action_name in ("show_edge", "hide_edge", "close_edge"):
            exc = RuntimeError(f"窗口操作正在进行中，当前无法执行 {action_name}")
            exc.reason_code = "window_op_in_progress"
            self._last_reason_code = "window_op_in_progress"
            self._last_error = str(exc)
            raise exc

        result_queue: queue.Queue = queue.Queue(maxsize=1)
        self._current_action = action_name
        self._action_stage = f"{action_name}:queued"

        job_id = id(result_queue)  # 用于关联任务和结果
        effective_timeout = float(timeout_seconds or ACTION_TIMEOUTS.get(action_name, 20.0))
        try:
            self._jobs.put((action_name, func, result_queue, job_id), timeout=effective_timeout * 0.5)
        except queue.Full:
            self._stale = True
            self._stale_reason = f"job_queue_full:{action_name}"
            raise EdgeActionTimeoutError(action_name, "queue_full", effective_timeout)

        self._action_stage = f"{action_name}:waiting"
        try:
            ok, value = result_queue.get(timeout=effective_timeout)
        except queue.Empty as exc:
            self._stale = True
            self._stale_reason = f"{action_name}@{self._action_stage}"
            self._last_reason_code = "edge_action_timeout"
            self._last_error = f"Edge 动作超时: {action_name} @ {self._action_stage} ({effective_timeout:.1f}s)"
            raise EdgeActionTimeoutError(action_name, self._action_stage, effective_timeout) from exc

        if ok:
            self._last_error = ""
            self._last_reason_code = ""
            return value
        raise value
```

#### 修改 3：`_session.py` — `RemoteEdgeManager` 资源回收

**位置**：`_session.py` L571-L623

**优化点**：在替换或重置旧 client 时调用 `_shutdown_worker()`

```python
class RemoteEdgeManager:
    def __init__(self) -> None:
        self._clients: dict[str, RemoteEdge] = {}
        self._lock = threading.Lock()

    def _dispose_client(self, client: RemoteEdge) -> None:
        """安全释放 client 资源"""
        try:
            client.mark_stale("manager_dispose")
            client._shutdown_worker()
        except Exception:
            pass

    def get_client(self, ...) -> RemoteEdge:
        ...
        with self._lock:
            client = self._clients.get(session_id)
            if client is not None:
                should_replace = (...)
                if should_replace:
                    self._dispose_client(client)       # ← 新增：释放旧 client
                    del self._clients[session_id]
                    client = None
            ...

    def reset_client(self, session_id: str) -> None:
        session_id = (session_id or "default_real_edge").strip()
        with self._lock:
            client = self._clients.pop(session_id, None)
        if client is not None:
            self._dispose_client(client)               # ← 新增：释放旧 client
```

#### 修改 4：新建 `backend/utils/log_throttle.py` — 日志限流工具

```python
"""日志限流工具：防止相同错误日志在短时间内重复打印"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional


class LogThrottle:
    """按消息指纹限流，相同消息在 interval 秒内只打印一次"""

    def __init__(self, interval_seconds: float = 60.0, max_entries: int = 100):
        self._interval = interval_seconds
        self._max_entries = max_entries
        self._last_logged: dict[int, float] = {}

    def should_log(self, fingerprint: str) -> bool:
        """返回 True 表示应该打印日志，False 表示应跳过"""
        key = hash(fingerprint)
        now = time.time()
        last = self._last_logged.get(key, 0)
        if now - last >= self._interval:
            self._last_logged[key] = now
            self._trim_if_needed()
            return True
        return False

    def _trim_if_needed(self) -> None:
        if len(self._last_logged) > self._max_entries:
            cutoff = time.time() - self._interval * 2
            stale = [k for k, v in self._last_logged.items() if v < cutoff]
            for k in stale:
                del self._last_logged[k]

    def reset(self) -> None:
        self._last_logged.clear()


# 全局实例：60秒内相同指纹只打印一次
global_throttle = LogThrottle(interval_seconds=60.0)
```

#### 修改 5：`scheduler.py` — 异常日志限流

**位置**：`scheduler.py` L357-L388

**优化前**：
```python
        except Exception as exc:
            import traceback
            logger.error(f"Capture error: {exc}\n{traceback.format_exc()}")
            ...
```

**优化后**：
```python
        except Exception as exc:
            from backend.utils.log_throttle import global_throttle

            # 构造指纹：任务ID + 异常类型 + 异常消息摘要
            fp = f"capture:task_{task.id}:{type(exc).__name__}:{str(exc)[:120]}"
            if global_throttle.should_log(fp):
                import traceback
                logger.error(
                    "Capture error task_id=%s platform=%s type=%s: %s\n%s",
                    task.id, task.platform, type(exc).__name__, exc,
                    traceback.format_exc(),
                )
            else:
                logger.warning(
                    "Capture error (suppressed repeat) task_id=%s platform=%s type=%s: %s",
                    task.id, task.platform, type(exc).__name__, exc,
                )
            ...
```

**同样对 `_run_loop` 的 `except Exception`** (L150-L152) 应用限流：

```python
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                from backend.utils.log_throttle import global_throttle
                fp = f"run_loop:{type(exc).__name__}:{str(exc)[:120]}"
                if global_throttle.should_log(fp):
                    logger.error("调度循环发生未预期异常，1s 后继续：%s", exc, exc_info=True)
                else:
                    logger.warning("调度循环异常（已限流）: %s", exc)
                await asyncio.sleep(1.0)
```

#### 修改 6：`_session.py` — worker 异常日志限流

**位置**：`_worker_loop` 的 `except` 分支

给 worker 内部的异常记录也加上限流：

```python
            except Exception as exc:
                self._last_error = str(exc)
                from backend.utils.log_throttle import global_throttle
                fp = f"worker:{action_name}:{type(exc).__name__}:{str(exc)[:120]}"
                if global_throttle.should_log(fp):
                    logger.error("worker action=%s failed: %s", action_name, exc, exc_info=True)
                if not self._worker_stop.is_set():
                    try:
                        result_queue.put((False, exc), timeout=1.0)
                    except queue.Full:
                        pass
```

---

### 2.3 资源配置参数推荐值

| 参数 | 环境变量 | 推荐值 | 说明 |
|------|----------|--------|------|
| 工作队列容量 | `GMV_EDGE_JOBS_QUEUE_MAXSIZE` | `10` | 队列满时 `_call()` 快速失败，避免内存堆积 |
| Worker 空闲超时 | `GMV_EDGE_WORKER_IDLE_TIMEOUT` | `300` | 5分钟无任务自动退出（暂不启用自退出，仅预留） |
| Worker 停止等待 | `GMV_EDGE_WORKER_JOIN_TIMEOUT` | `5.0` | 等待线程优雅退出的秒数 |
| 日志限流间隔 | (hardcoded) | `60.0` | 相同错误指纹 60s 内仅输出一次完整 traceback |
| 限流缓存上限 | (hardcoded) | `100` | 最多缓存 100 个指纹，超过则清理过期条目 |

---

## 三、效果验证步骤

### 3.1 启动前准备

```bash
# 1. 确保 Edge 调试端口未启动（故意制造异常场景）
# 2. 清理旧日志便于观察
```

### 3.2 验证项 1：日志不再持续滚动

1. 启动服务：双击 `第1步_启动GMV服务.bat`
2. 观察控制台输出，确认：
   - 相同错误消息在 60s 内只出现一次完整 traceback
   - 后续相同错误仅输出 `(suppressed repeat)` 的 warning 级别精简日志
   - 不同错误（不同异常类型或不同消息）仍正常独立限流

### 3.3 验证项 2：CPU/内存占用降低

1. 启动服务后打开任务管理器
2. 观察 `python.exe` (uvicorn) 进程：
   - **优化前**：持续高 CPU（频繁写日志 + traceback 序列化）
   - **优化后**：CPU 空闲时接近 0%，内存稳定不增长
3. 检查是否有僵尸线程残留：
   - 使用 `任务管理器 → 详细信息` 查看 Python 进程线程数
   - 主动触发 session 重建（修改 session 配置），确认旧线程被回收

### 3.4 验证项 3：异常正常捕获

1. 在 Edge 调试端口未连接的情况下启动采集任务
2. 确认 `capture_once` 返回合理的失败状态（`remote_page_not_found` / `edge_debug_unavailable` 等）
3. 确认 API 前端能看到任务状态更新，而非超时或无响应
4. 启动 Edge 调试端口后，确认采集自动恢复正常

### 3.5 验证项 4：队列保护生效

1. 快速连续触发大量 `_call()` 请求（可通过 API 压力测试）
2. 确认队列满时 `_call()` 快速返回 `EdgeActionTimeoutError("queue_full")`
3. 确认不会出现内存持续增长或线程阻塞

### 3.6 回归验证

1. `find_page` 正常流程（Edge 在线、页面存在）：确认返回 `RemotePageInfo`
2. `find_page` 页面不存在：确认返回 `None`（不抛异常）
3. `capture_once` 完整采集流程：截图 → OCR → 数据入库全部正常
4. `refresh_page_preview_once` 页面巡检正常

---

## 四、改动风险与回滚

- **低风险**：所有改动为防御性优化，不修改核心业务逻辑
- **回滚方式**：Git revert 对应 commit 即可
- **环境变量兼容**：新增环境变量均有合理默认值，不设置也能正常运行
- **日志限流**：仅影响日志输出频率，不影响任何功能行为
