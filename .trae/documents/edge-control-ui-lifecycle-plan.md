# 任务管理 Edge 控制改造计划

## Summary

- 目标：重构 `任务管理` 页的 Edge 控制交互，把平台级与店铺级按钮统一为 `启动Edge / 显示Edge / 隐藏Edge / 关闭Edge` 四类动作。
- 核心行为：
  - `启动Edge`：默认启动并显示对应 Edge，会尝试恢复、置前、移回可见区并最大化。
  - `显示Edge`：仅对已启动会话执行显示与最大化，不重复强调“后台启动”语义。
  - `隐藏Edge`：将对应 Edge 窗口移出可见区，保持调试端口和会话可继续采集。
  - `关闭Edge`：彻底终止对应会话的 Edge 进程树，后台不保留残留进程。
- 平台级按钮从当前平台标题行右侧移动到 `“平台名 + N 个任务”` 同一行中，UI 由实现时统一规划；店铺卡片按钮区同步扩展为四个动作。

## Current State Analysis

### 前端现状

- `frontend/app.js`
  - `renderManager()` 当前在平台头部 `manager-platform-actions` 里只渲染一个平台级按钮：`后台启动全部Edge`。
  - 每个店铺卡片当前只渲染一个 Edge 按钮：`显示Edge`。
  - `handleTaskAction()` 目前仅处理两类 Edge 动作：
    - 平台级 `start-platform-edge` -> `POST /api/platforms/{platform}/start-edge`
    - 店铺级 `start-edge` -> `showEdgeSession(sessionId)` -> `POST /api/edge-sessions/{session_id}/show`
  - `showEdgeSession()` 已存在旧接口兜底逻辑：若 `/show` 返回 `404`，会退回旧 `/start`。

### 后端现状

- `backend/main.py`
  - 已有会话级接口：
    - `POST /api/edge-sessions/{session_id}/start`
    - `POST /api/edge-sessions/{session_id}/show`
  - 已有平台级接口：
    - `POST /api/platforms/{platform}/start-edge`
  - 目前没有：
    - 会话级 `hide`
    - 会话级 `close`
    - 平台级 `show/hide/close`
- `backend/collectors/remote_edge.py`
  - `start_edge()` 当前多会话模式默认加 `--window-position=32000,0`，语义是“后台启动到屏外”。
  - `show_edge()` 已具备“若未启动则先启动，再将目标窗口显示并最大化”的能力。
  - 目前没有 `hide_edge()` 与 `close_edge()`。
- `backend/collectors/window_control.py`
  - 已有按 `debug_port / user_data_dir / pid` 精确定位 Edge 主窗口的基础。
  - 已有 `show_edge_window()`，但没有与之对称的 `hide_edge_window()`。
  - 已有 `_edge_processes()`，可枚举 `msedge.exe` 的 `ProcessId + CommandLine`，可作为“按会话终止进程”的基础。

### 样式现状

- `frontend/styles.css`
  - 平台头部使用 `.manager-platform-head / .manager-platform-title / .manager-platform-actions`。
  - 店铺按钮区统一使用 `.task-actions`，Edge 按钮仅有 `.edge-launch-button` 一类样式。
  - 当前样式足够扩展为“平台内联操作条 + 店铺多按钮操作组”，无需大改整体布局结构。

## 可落地性判断

- 该需求可直接在现有架构上实现，不需要新增表结构或任务模型字段。
- 原因：
  - 会话与店铺已有稳定映射：任务数据里已有 `edge_session_id`，后端也可通过 `store.get_edge_session()` 取得 `debug_port` 和 `user_data_dir`。
  - 窗口显示能力已存在，只需补齐“隐藏窗口”和“终止进程树”。
  - 平台级操作可以复用当前 `start-platform-edge` 的批量遍历模式，扩展出 `show/hide/close` 三类聚合接口。
- 唯一需要明确的实现边界：
  - `关闭Edge` 应限定为“关闭该会话对应的 Edge 进程树”，不能误杀其他非本会话 Edge。
  - 对 `default_real_edge` 这类共享真实 Profile 会话，关闭策略要更保守；但本需求范围聚焦任务管理里的店铺会话，优先覆盖带独立 `user_data_dir` 的 `remote_edge` 店铺任务。

## Proposed Changes

### 1. 前端任务管理区重排与动作扩展

#### 文件

- `frontend/app.js`
- `frontend/styles.css`

#### 改动内容

- 平台头部按钮布局调整：
  - 将当前平台级 `后台启动全部Edge` 从右侧孤立按钮，改为紧贴 `“N 个任务”` 的内联操作组。
  - 标题行结构调整为：平台名 -> 任务数 -> 平台 Edge 操作组。
- 平台级按钮改为四个动作：
  - `启动Edge`
  - `显示Edge`
  - `隐藏Edge`
  - `关闭Edge`
- 店铺卡片按钮区同步扩展为四个动作：
  - `启动Edge`
  - `显示Edge`
  - `隐藏Edge`
  - `关闭Edge`
- 行为映射：
  - `启动Edge` 默认走“启动并显示”链路。
  - `显示Edge` 只做显示/恢复/最大化。
  - `隐藏Edge` 只做隐藏，不关闭调试端口。
  - `关闭Edge` 调用后端彻底杀死该会话进程。
- 消息文案同步调整：
  - 不再出现“后台启动全部Edge”提示。
  - 平台级动作返回聚合结果：成功数量、失败数量、失败店铺摘要。
  - 店铺级动作返回明确状态：已启动并显示、已显示、已隐藏、已关闭。

#### 实现方式

- 在 `renderManager()` 中：
  - 平台头部新增平台操作按钮组的 HTML。
  - 店铺卡片新增三类新按钮，并把当前 `显示Edge` 文案改为 `启动Edge`，另补 `显示Edge / 隐藏Edge / 关闭Edge`。
- 在 `handleTaskAction()` 中：
  - 拆分出平台级动作分支：`start-platform-edge / show-platform-edge / hide-platform-edge / close-platform-edge`。
  - 拆分出店铺级动作分支：`start-edge / show-edge / hide-edge / close-edge`。
- 在前端 API 辅助函数中：
  - 保留 `showEdgeSession(sessionId)`，新增 `startAndShowEdgeSession()`、`hideEdgeSession()`、`closeEdgeSession()` 或统一封装会话动作调用。

### 2. 后端补齐会话级 hide / close 接口

#### 文件

- `backend/main.py`
- `backend/collectors/remote_edge.py`
- `backend/collectors/window_control.py`

#### 改动内容

- 新增会话级接口：
  - `POST /api/edge-sessions/{session_id}/hide`
  - `POST /api/edge-sessions/{session_id}/close`
- 调整 `POST /api/edge-sessions/{session_id}/start` 语义边界：
  - 保留兼容性，继续表示“仅启动调试会话”。
  - 新前端默认不再把它作为任务管理主入口。
- 新增 `RemoteEdge.hide_edge()`：
  - 基于当前会话定位窗口后，将窗口移出屏幕外或隐藏到不可见状态。
  - 返回结构与 `show_edge()` 类似，便于前端统一处理。
- 新增 `RemoteEdge.close_edge()`：
  - 基于当前会话的 `pid/debug_port/user_data_dir` 精确定位进程。
  - 优先按根进程执行 `taskkill /PID <pid> /T /F`。
  - 若根 `pid` 不可用，则按命令行包含 `--remote-debugging-port=...` 或 `--user-data-dir=...` 的进程集执行强制终止。
  - 关闭后重新检查健康状态，确保调试端口不可用，必要时返回残留错误。

#### 实现方式

- `window_control.py`
  - 抽取公共的“定位目标窗口”逻辑继续复用。
  - 新增 `hide_edge_window(...)`：
    - 定位窗口。
    - 若最小化/可见均可接受，统一移动到屏幕外并保持窗口存在，避免影响渲染策略。
    - 返回 `EdgeWindowActionResult`，`action` 标记为 `move_offscreen` 或同类语义。
  - 新增按会话筛选进程的辅助函数，如：
    - `find_edge_process_ids(debug_port, user_data_dir, pid)`
    - `kill_edge_process_tree(...)`
- `remote_edge.py`
  - 增加 `hide_edge()` / `_hide_edge()`
  - 增加 `close_edge()` / `_close_edge()`
  - 关闭后清理 `_last_pid` 与错误状态，保证后续再次 `启动Edge` 能按冷启动路径执行。
- `main.py`
  - 新增 `hide_edge_session()` / `close_edge_session()` 路由。
  - 返回统一 JSON 结构，至少包含：
    - `session_id`
    - `debug_available`
    - `window_found` 或 `closed`
    - `window_pid`
    - `last_error`
    - `health`

### 3. 后端补齐平台级 show / hide / close 聚合接口

#### 文件

- `backend/main.py`

#### 改动内容

- 在现有 `POST /api/platforms/{platform}/start-edge` 之外新增：
  - `POST /api/platforms/{platform}/show-edge`
  - `POST /api/platforms/{platform}/hide-edge`
  - `POST /api/platforms/{platform}/close-edge`
- 平台级 `启动Edge` 需要默认“启动并显示”，因此建议新增：
  - `POST /api/platforms/{platform}/launch-edge`
  - 或直接把现有 `start-edge` 调整为“启动并显示”，但此举会改变旧接口语义。

#### 实现方式

- 推荐保持兼容并新增接口，而不是直接修改旧 `start-edge` 语义：
  - `start-edge` 继续表示“后台启动”，兼容旧调用与其他潜在脚本。
  - 新增 `launch-edge` 作为“启动并显示”的平台级主入口。
  - 前端新的 `启动Edge` 按钮改调 `launch-edge`。
- 各平台级接口内部沿用当前 `asyncio.gather(*(one(config) ...))` 聚合模式。
- 每个结果项统一返回：
  - `shop_name`
  - `edge_session_id`
  - `ok`
  - `last_error`
  - `health`
  - 若是窗口动作则补 `window_found / maximized / window_action`
  - 若是关闭动作则补 `closed`

### 4. 样式与交互状态优化

#### 文件

- `frontend/styles.css`

#### 改动内容

- 平台头部采用内联布局，让 `4 个任务` 右侧紧接平台操作按钮组。
- 为四类 Edge 操作建立更清晰的按钮视觉分层：
  - `启动Edge`：主强调色
  - `显示Edge`：次强调色
  - `隐藏Edge`：中性色
  - `关闭Edge`：危险色
- 店铺卡片按钮区按两行自适应换行设计，避免卡片被单行按钮撑坏。

#### 实现方式

- 复用现有 `.task-actions` 的 `flex-wrap`，补充如 `.edge-action-group`、`.edge-button-show`、`.edge-button-hide`、`.edge-button-close` 等样式类。
- 平台头部使用新的小型按钮组样式，避免挤压标题文本。

## Assumptions & Decisions

- 决策：任务管理页的 `启动Edge` 默认语义为“启动并显示”，不再默认后台隐藏。
- 决策：保留现有旧接口 `POST /api/edge-sessions/{session_id}/start` 与 `POST /api/platforms/{platform}/start-edge`，以兼容历史调用；新 UI 改走新语义接口。
- 决策：`隐藏Edge` 采用“移到屏幕外”方案，保持 CDP 可用与截图稳定性，不做真正 `ShowWindow(SW_HIDE)` 的强隐藏。
- 决策：`关闭Edge` 以“会话级彻底结束进程树”为目标，优先通过根 `pid` 杀树，辅以 `debug_port/user_data_dir` 兜底筛选，避免误伤其他 Edge。
- 假设：任务管理中的 `remote_edge` 店铺均绑定独立 `edge_session_id`，且对应 `store` 中存在可用 `debug_port` 与 `user_data_dir`。
- 假设：平台级批量 `启动Edge` 同时拉起多个窗口是用户期望行为；若多个窗口争抢前台，执行上允许“全部显示并尽量最大化”，最终焦点落在最后处理的窗口上。

## Verification Steps

- 前端验证
  - 打开 `任务管理` 页面，确认平台标题行内展示 `平台名 + N 个任务 + 四个平台按钮`。
  - 确认店铺卡片按钮区存在 `启动Edge / 显示Edge / 隐藏Edge / 关闭Edge`。
  - 确认按钮文案已无 `后台启动全部Edge`。
- 单店铺行为验证
  - 点 `启动Edge`：若未运行，Edge 启动并显示到前台且尽量最大化。
  - 点 `显示Edge`：已运行但隐藏/屏外时可恢复到前台。
  - 点 `隐藏Edge`：窗口移出可见区，但 `/health` 仍可见调试端口正常。
  - 点 `关闭Edge`：窗口消失，端口关闭，再次 `health` 返回未连接。
- 平台级行为验证
  - 点平台 `启动Edge`：该平台所有远程 Edge 任务批量启动并尝试显示，前端展示聚合结果。
  - 点平台 `显示Edge`：已启动会话全部尝试恢复显示。
  - 点平台 `隐藏Edge`：已显示会话全部移出可见区。
  - 点平台 `关闭Edge`：平台下所有会话对应进程均被彻底结束。
- 后端验证
  - 检查新增接口返回结构统一，无 404/500 语义混乱。
  - 对已关闭会话执行进程检查，确认对应 `msedge.exe` 进程树不再存在。
- 质量验证
  - 运行最近编辑文件的诊断检查，确保前端无语法错误、后端无类型或导入错误。
  - 对 `backend/main.py`、`backend/collectors/remote_edge.py`、`backend/collectors/window_control.py` 做基础语法校验。
