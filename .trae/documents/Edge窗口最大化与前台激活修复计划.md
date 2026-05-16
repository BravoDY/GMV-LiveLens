## Summary

- 目标：彻底解决“任务里能吊起 Edge，但无法通过任务栏点击把对应 Edge 稳定恢复到前台并最大化”的问题。
- 根因判断：
  - `backend/collectors/remote_edge.py` 在多会话模式下会为店铺 Edge 追加 `--window-position=32000,0`，故意把窗口移到屏幕外。
  - 当前前端“吊起Edge”按钮只调用 `POST /api/edge-sessions/{session_id}/start`，后端只保证调试端口可用，不保证窗口可见、可激活、可最大化。
  - 当会话已经运行时，`start_edge()` 会在 `debug_available=True` 时直接返回健康状态，不会再尝试把现有窗口拉回前台。
- 成功标准：
  - 单店铺“吊起 Edge”后，目标 Edge 会话能被稳定恢复到当前桌面、置前并最大化。
  - 已在后台运行的 Edge 会话，不需要依赖任务栏点击，也能从 GMV-LiveLens 内一键显示出来。
  - 原有后台采集链路不被破坏：自动采集仍可继续使用隐藏/屏外窗口，不强制所有会话都常驻前台。

## Current State Analysis

- 启动逻辑：
  - 文件：`backend/collectors/remote_edge.py`
  - 关键位置：`RemoteEdge._start_edge()`
  - 现状：
    - 对带 `user_data_dir` 的店铺会话，使用 `--window-position=32000,0 --window-size=1280,800` 启动。
    - 只检查调试端口是否可用，不跟踪顶层窗口句柄，也不执行 `ShowWindow/SetForegroundWindow`。
    - 如果调试端口已可用，则直接返回，不处理已有窗口的前台激活。

- UI 触发链路：
  - 文件：`frontend/app.js`
  - 关键位置：
    - `handleTaskAction()` 中 `data-action="start-edge"`
    - `startRemoteEdge()`
    - `handleTaskAction()` 中 `data-action="start-platform-edge"`
  - 现状：
    - 单任务按钮、配置页启动按钮都只调用 `/start`。
    - 前端收到的只是健康状态，无法区分“已启动但仍在屏幕外”与“已显示到前台”。

- API 能力：
  - 文件：`backend/main.py`
  - 现状：
    - 已有 `POST /api/edge-sessions/{session_id}/start`
    - 没有“显示指定会话窗口”“恢复并最大化指定会话窗口”的专用接口

- Windows 能力基础：
  - 文件：`backend/collectors/window_capture.py`
  - 现状：
    - 已经使用 `ctypes.windll.user32` 枚举顶层窗口。
  - 依赖：
    - `requirements.txt` 已包含 `pywin32>=306`
  - 结论：
    - 项目已经具备实现 Windows 窗口查找、恢复、置前、最大化的依赖基础，不需要引入新的重量级依赖。

## Proposed Changes

### 1. 新增独立的 Windows 窗口控制模块

- 新增文件：`backend/collectors/window_control.py`
- 目标：把“按 Edge 会话找到窗口并恢复/最大化”的系统级逻辑从截图模块中拆开，避免把窗口控制和截图枚举混在一起。
- 实现内容：
  - 定义 `EdgeWindowInfo` 数据结构，至少包含：
    - `hwnd`
    - `title`
    - `pid`
    - `is_visible`
    - `is_minimized`
    - `is_offscreen`
  - 提供顶层窗口枚举能力，只保留真正的可交互 Edge 主窗口，排除子窗口、空标题窗口和过小窗口。
  - 提供按 `pid` 过滤窗口的能力。
  - 提供按 Edge 进程命令行定位目标进程的能力，优先匹配：
    - `--remote-debugging-port={debug_port}`
    - `--user-data-dir={user_data_dir}`（店铺隔离会话）
  - 提供 `focus_edge_window(...)` 能力，内部执行：
    - 如窗口最小化，先 `ShowWindow(..., SW_RESTORE)`
    - 再尝试前台激活
    - 最后 `ShowWindow(..., SW_MAXIMIZE)`，确保最终是最大化状态
  - 前台激活策略要兼容 Windows 焦点限制，必要时使用线程附着/临时前台切换方案，不能只调用一次 `SetForegroundWindow` 就结束。

- 为什么这样做：
  - 现在真正缺失的不是“启动 Edge”，而是“可确定地把特定 Edge 会话恢复出来”。
  - 单独模块便于后续复用到别的窗口场景，也便于单独排错。

### 2. 在 `RemoteEdge` 中补齐“显示会话窗口”能力

- 修改文件：`backend/collectors/remote_edge.py`
- 新增/调整内容：
  - 为 `RemoteEdge` 增加对最近一次启动进程 PID 的记录，例如 `_last_pid`。
  - `subprocess.Popen(...)` 后保存 PID，作为定位窗口的第一优先级线索。
  - 新增 `show_edge()` 或 `reveal_window()` 方法，职责是：
    - 如果调试端口尚未打开，先沿用现有 `_start_edge()` 启动会话。
    - 启动完成后，轮询目标 Edge 主窗口是否出现。
    - 找到后调用新的窗口控制模块执行恢复、置前、最大化。
  - 当调试端口已经可用时，不再直接结束，而是允许 `show_edge()` 对“已运行但屏外/最小化”的窗口执行恢复。
  - 保留现有 `start_edge()` 的“后台采集友好”语义，不把所有启动都改成前台最大化。

- 关键决策：
  - `start_edge()` 继续用于“只保证会话已启动且可调试”。
  - `show_edge()` 用于“人工交互场景，保证窗口显示出来并最大化”。
  - 这样不会破坏自动采集依赖的屏外窗口策略，也能彻底解决人工查看窗口的问题。

### 3. 增加专用后端接口：显示并最大化指定 Edge 会话

- 修改文件：`backend/main.py`
- 新增接口：
  - `POST /api/edge-sessions/{session_id}/show`
- 返回结构建议：
  - 以当前 `health` 为主体，额外补充窗口结果，例如：
    - `window_found`
    - `window_title`
    - `window_hwnd`
    - `window_action`
    - `last_error`
- 行为设计：
  - 通过 `edge_client_for(session_id)` 获取客户端。
  - 调用 `show_edge()`。
  - 若会话启动成功但窗口仍未找到，返回 409 或 500，并明确区分“调试端口可用”和“窗口恢复失败”。

- 同时保留：
  - 现有 `POST /api/edge-sessions/{session_id}/start`
  - 现有 `POST /api/platforms/{platform}/start-edge`

- 为什么不直接重载 `/start`：
  - 现在 `/start` 已被当作“启动调试会话”使用，语义稳定。
  - 新增 `/show` 后，手动交互和后台自动启动职责分离，前端和后端都更清晰。

### 4. 调整前端交互语义，手动按钮改为“显示 Edge”

- 修改文件：`frontend/app.js`
- 调整点：
  - 单任务按钮：
    - 当前：`吊起Edge`
    - 调整为更明确的文案，例如 `显示Edge`
    - 行为改为调用 `POST /api/edge-sessions/{session_id}/show`
  - 配置页中的 `启动真实 Edge 调试`：
    - 用户主动点击时，应改为“启动并显示当前会话”
    - 启动成功后提示语明确写成“已显示并最大化当前 Edge 会话”
  - 平台分组按钮：
    - 保持批量启动语义，不做“批量最大化”
    - 文案建议从 `吊起Edge` 调整为 `启动全部Edge`
    - 仍调用 `POST /api/platforms/{platform}/start-edge`

- 原因：
  - “平台批量启动”不适合定义成“最大化”，否则多个窗口只能最后一个留在前台，交互语义会混乱。
  - “单任务显示”才是真正对应你当前要解决的人工操作问题。

### 5. 补充前端反馈与状态展示

- 修改文件：`frontend/app.js`
- 具体要求：
  - 当 `/show` 成功时，提示语展示：
    - 店铺名
    - 是否已恢复
    - 是否已最大化
  - 当 `/show` 失败时，优先展示后端的窗口级错误，而不是只显示“启动失败”。
  - 配置页健康信息区如果有窗口状态字段，可同步展示“已显示/未找到窗口/已最大化”。

- 目标：
  - 让用户能直接知道是“会话没启动”“窗口找不到”“窗口已拉起但被焦点限制拦截”，便于后续排查。

### 6. 如有必要，更新静态资源缓存版本和说明文档

- 修改文件：
  - `frontend/index.html`
  - `README.md`
- 内容：
  - 如果前端 JS/CSS 改动后浏览器可能命中旧缓存，则更新 `?v=` 版本号。
  - 在 README 的“真实 Edge 调试模式”补充说明：
    - 平台批量按钮只负责启动会话
    - 单店铺按钮负责显示并最大化指定会话

## Assumptions & Decisions

- 保留“店铺会话可隐藏到屏幕外以便后台采集”的既有设计，不把所有 Edge 一律改为前台最大化。
- 本次“完全解决”的定义是：
  - 用户不再需要依赖任务栏点击来赌 Windows 是否把屏外 Edge 拉回来；
  - 系统提供稳定、按会话精确定位的“显示并最大化”能力；
  - 单店铺人工查看路径被彻底打通。
- 平台批量按钮不做批量最大化，只做批量启动；否则多个窗口的前台争夺没有稳定可用的交互结果。
- 窗口匹配优先级按以下顺序：
  - 最近启动 PID
  - Edge 进程命令行中的调试端口
  - Edge 进程命令行中的 `user_data_dir`
- 如果某些极端情况下窗口句柄暂未出现，后端采用短轮询等待，而不是一次性查找失败就立即返回。

## Verification Steps

- 后端单会话验证：
  - 调用 `POST /api/edge-sessions/{session_id}/start`，确认旧能力仍只负责启动会话，不强制拉前台。
  - 调用 `POST /api/edge-sessions/{session_id}/show`，确认：
    - 未启动时可先启动再显示
    - 已启动但屏外时可恢复并最大化
    - 已最小化时可恢复并最大化

- 前端交互验证：
  - 在 `任务管理` 点击单任务 `显示Edge`
  - 确认目标店铺 Edge 被带到前台且为最大化状态
  - 在 `采集配置` 点击当前会话的启动/显示按钮，确认同样可见
  - 平台按钮点击后仅反馈批量启动结果，不抢当前桌面焦点

- 回归验证：
  - 启动采集后，隐藏会话仍能继续通过 CDP 截图，不要求窗口前台可见
  - `open_remote_page`、`refresh_remote_pages`、`preview_remote_page` 等既有流程不回归
  - `window_capture` 兼容模式不受影响

- 失败场景验证：
  - 如果 Edge 进程存在但主窗口暂未建立，接口返回明确错误
  - 如果会话端口已被占用或窗口匹配到错误进程，返回可读错误，而不是静默成功
