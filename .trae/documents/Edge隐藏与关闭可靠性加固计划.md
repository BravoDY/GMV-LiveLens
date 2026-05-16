# Edge 隐藏与关闭可靠性加固计划

## 1. 需求理解
- 本次目标不是只修一个按钮，而是把 `启动Edge`、`显示Edge`、`隐藏Edge`、`关闭Edge` 四条链路统一提升为“可验收、可解释、可回归”的商业级可靠控制链路。
- 重点新增排查对象是 `隐藏Edge` 与 `关闭Edge`，确认它们是否像之前的 `显示Edge` 一样存在“命令发出即算成功”“前端和后端语义不一致”“窗口/进程实际状态未验收”的问题。
- 成功标准：
  - 单店铺四个动作都返回真实结果，而不是 `accepted`。
  - 前端提示与后端真实结果一致。
  - 隐藏后能确认窗口确实不可见/不可用；关闭后能确认调试端口和进程确实退出。
  - 完成多轮真实回归，覆盖成功、失败、兜底恢复三类场景。

## 2. 当前项目结构判断

### 2.1 核心模块
- `backend/main.py`
  - FastAPI 入口。
  - 负责单店铺与平台级 Edge 控制 API。
  - 当前 `show` 已改为同步验收，但 `hide`、`close` 仍是异步 `accepted`。
- `backend/collectors/remote_edge.py`
  - 真实 Edge/CDP/窗口控制核心。
  - 已具备 `start_edge()`、`show_edge()`、`hide_edge()`、`close_edge()` 底层能力。
  - `hide` 与 `close` 已有状态对象，但验收粒度不一致。
- `backend/collectors/window_control.py`
  - Win32 窗口层控制。
  - `show_edge_window()` 已有显示后验收。
  - `hide_edge_window()` 当前仅移动到屏幕外，未做隐藏后复核。
- `frontend/core.js`
  - 前端调用单店铺 Edge 控制 API 的统一入口。
- `frontend/app.js`
  - 任务卡片上 `启动 / 显示 / 隐藏 / 关闭` 四个按钮的交互与消息提示。

### 2.2 已发现的真实风险
- `backend/main.py`
  - `/api/edge-sessions/{session_id}/hide` 仍是 `asyncio.create_task(...); return {"status":"accepted"}`。
  - `/api/edge-sessions/{session_id}/close` 也仍是 `accepted`。
  - 这和之前 `showEdge` 的老问题完全同型，会导致前端误判成功。
- `frontend/app.js`
  - `hide-edge` 点击后立即按 `result.window_found` 判断成功。
  - `close-edge` 点击后立即按 `result.closed` 判断成功。
  - 但后端当前返回的是 `accepted`，说明前后端语义已经脱节。
- `backend/collectors/window_control.py`
  - `hide_edge_window()` 目前只做 `SW_SHOW + move_offscreen`，没有像 `show_edge_window()` 那样做“动作后验收”。
  - 这意味着可能出现“返回成功，但窗口还可见、还在主屏、或被系统重新拉回”的假成功。
- `backend/collectors/remote_edge.py`
  - `__hide_edge()` 当前在 `debug_available=False` 时直接回 `debug_port_unavailable`，但对“窗口仍在，只是调试端口不在”的场景缺少更细语义。
  - `__close_edge()` 已有 `graceful -> force_kill -> verify debug_port` 框架，但还需要和 API/前端统一成同步验收和结构化错误。

## 3. 最佳实现方案

### 3.1 总体设计原则
- 统一四个动作的可靠性模型：
  - 后端同步执行
  - 动作后验收
  - 失败返回结构化 `reason_code / stage / health / diagnostics`
  - 前端按真实结果提示，不再把“请求已接收”当成功
- 延续现有 `showEdge` 的修复模式，避免再走一套不同逻辑，降低维护成本。

### 3.2 计划修改文件

#### 文件 1：`backend/main.py`
- 计划修改内容：
  - 将单店铺 `/hide`、`/close` 从异步 `accepted` 改为同步等待 `client.hide_edge()`、`client.close_edge()`。
  - 对 `hide`、`close` 引入与 `show/start/preview` 同级的异常收口：
    - `EdgeActionTimeoutError` 结构化 detail。
    - 普通异常返回 `reason_code / stage / health`。
  - 成功后刷新任务快照并按需要刷新会话健康状态。
- 这样设计的原因：
  - 这是最直接复用现有修复范式的方案。
  - 能彻底消除“前端等同步结果，后端却只返回 accepted”的架构错位。
- 不推荐的更简单方案：
  - 只改前端，让前端接受 `accepted`。
  - 不推荐，因为这样仍然无法保证隐藏/关闭真的完成，只是把假成功换个文案。

#### 文件 2：`backend/collectors/window_control.py`
- 计划修改内容：
  - 为 `hide_edge_window()` 增加隐藏后验收机制，至少复核：
    - 窗口是否仍可见；
    - 是否仍在主屏范围；
    - 是否仍可被恢复为前台主窗口；
    - 是否需要使用更稳的最小化/隐藏组合而不是仅 move offscreen。
  - 抽象 `_window_is_hidden_like()` 或等价判断函数，和 `_window_is_presentable()` 对应。
- 这样设计的原因：
  - 真正的“万无一失”不能只看 API 是否调用成功，必须验证最终窗口状态。
  - `show` 已经有验收标准，`hide` 也应有对称标准。
- 不推荐的更简单方案：
  - 继续只移动到屏幕外。
  - 不推荐，因为 Windows 下 offscreen 不能等价于“已隐藏”，尤其在多屏、分辨率变化、系统窗口恢复场景下不稳。

#### 文件 3：`backend/collectors/remote_edge.py`
- 计划修改内容：
  - 统一 `hide_edge()` / `close_edge()` 的 `reason_code`、`stage`、`diagnostics` 语义。
  - `hide` 增加对以下场景的细分：
    - 窗口不存在；
    - 窗口找到但隐藏后仍可见；
    - 调试端口不在但窗口还存在；
    - 缓存 hwnd 失效后重新查找失败。
  - `close` 增加对以下场景的细分：
    - 优雅关闭失败；
    - 强杀执行失败；
    - 调试端口已断但 profile 进程仍残留；
    - 调试端口还在，说明关闭未完成。
  - 必要时为 `hide_edge` / `close_edge` 单独调优超时预算。
- 这样设计的原因：
  - 只靠 `window_not_found / close_failed` 这类粗粒度错误，不足以指导恢复操作。
  - 既然用户要求“各个环节你都考虑到并且修复了”，就必须把恢复路径也明确化。

#### 文件 4：`frontend/app.js`
- 计划修改内容：
  - 对 `hide-edge`、`close-edge` 使用和 `show-edge` 同等级的真实成功判断与提示逻辑。
  - 补充 `reason_code` 映射，避免错误提示继续笼统。
  - 成功后统一 `await loadTasks()`，保证卡片状态与后端真实结果同步。
- 这样设计的原因：
  - 当前 UI 已经是同步判断写法，只是后端结果不可靠。
  - 修完后前端只需要把成功/失败消息做细化即可。

#### 文件 5：`frontend/core.js`
- 计划修改内容：
  - 评估并调整 `hide_edge`、`close_edge` 的前端超时预算，使其与后端真实执行时间匹配。
  - 保持与 `show_edge` 一致的 API 调用模式。
- 这样设计的原因：
  - 后端改为同步后，前端超时必须配套，否则容易变成“后端成功、前端先超时”。

## 4. 风险评估
- 可能影响现有功能：
  - `hide`、`close` 从异步改同步后，按钮等待时间会更长，但这是为换取真实结果，是正确代价。
  - 平台级批量 `hide/close` 目前已经是同步聚合模式，需确认单店铺接口改动后不会造成语义不一致。
  - `hide` 如果从“移出屏幕”升级为“最小化/隐藏+复核”，需要确认不会误伤恢复登录态或下次 `show` 的窗口定位。
- 兼容性风险：
  - 多显示器、负坐标窗口、最小化窗口、系统自动恢复前台焦点等 Windows 行为可能影响隐藏验收。
  - `close` 的强杀兜底需要继续保留，但要明确提醒“登录态保留风险较高”。
- 需要重点防回归的点：
  - `show` 已修好的逻辑不能被这次改动破坏。
  - `start -> show -> hide -> show -> close -> start` 的串行动作必须连续稳定。

## 5. 执行计划

### 步骤 1：收口单店铺 hide/close API
- 把 `backend/main.py` 的 `/hide`、`/close` 改成同步返回真实结果。
- 为两条接口补齐 `timeout / reason_code / health / diagnostics` 异常 detail。

### 步骤 2：给 hide 增加“隐藏后验收”
- 改造 `backend/collectors/window_control.py` 的 `hide_edge_window()`。
- 增加动作后复核，确保窗口真的离开可见主屏或进入可接受的隐藏状态。
- 为失败场景输出更准确的错误码。

### 步骤 3：统一 remote_edge 的 hide/close 状态语义
- 在 `backend/collectors/remote_edge.py` 中细化 `hide_edge()` 与 `close_edge()` 的阶段和错误分类。
- 让返回结构足够支撑前端精确提示和后续诊断。

### 步骤 4：前端成功/失败提示与状态刷新对齐
- 在 `frontend/app.js`、`frontend/core.js` 中更新成功判断、提示语和超时预算。
- 成功后刷新任务列表，保证卡片状态与真实会话状态一致。

### 步骤 5：真实回归验证
- 必做单店铺回归：
  - `启动 -> 显示 -> 隐藏 -> 显示 -> 关闭 -> 启动 -> 显示`
  - `显示失败 -> 隐藏失败 -> 关闭失败` 的结构化错误检查
  - `关闭` 的优雅关闭与强杀兜底两类分支
- 必做采集闭环回归：
  - `启动 -> 显示 -> 扫描页签 -> 生成预览`
  - 再执行 `隐藏 -> 显示 -> 预览`
  - 再执行 `关闭 -> 启动 -> 显示 -> 预览`
- 必做结果验收：
  - 不允许再出现单店铺 `hide/close` 返回 `accepted`
  - 前端按钮提示必须与后端实际结果一致
  - 若动作失败，必须能给出明确恢复建议

## 6. 假设与决策
- 假设当前目标仍是 Windows 本地真实 Edge 会话控制，不切换 Chrome 路线。
- 假设“万无一失”的落地标准不是绝对零失败，而是：
  - 所有已知高频失败模式都有检测、分类、恢复提示和兜底；
  - 不再出现“界面显示成功，实际上没成功”的假阳性。
- 决策：
  - 优先修“单店铺接口真实验收”和“隐藏后复核”，因为这两处是当前最明确的结构性缺口。

## 7. 验证步骤
- 代码层验证：
  - 检查 `backend/main.py`、`backend/collectors/remote_edge.py`、`backend/collectors/window_control.py`、`frontend/app.js`、`frontend/core.js` 的诊断与语法。
- 真实接口验证：
  - 单店铺 `start/show/hide/close` 全部拿到真实结构化返回。
  - 平台级 `show/hide/close` 聚合结果仍然正确。
- 真实行为验证：
  - `hide` 后窗口确实不在主屏可见范围；
  - `show` 后窗口确实回到主屏并可操作；
  - `close` 后调试端口不可访问、对应进程退出；
  - 重启后仍可恢复会话控制并继续预览。
