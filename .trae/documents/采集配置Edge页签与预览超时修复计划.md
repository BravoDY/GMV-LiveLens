# 采集配置 Edge 页签与预览超时修复计划

## 一、Summary
- 目标：解决采集配置过程中 `GET /api/edge-sessions/{session_id}/pages` 返回 500、`POST /api/edge-sessions/{session_id}/pages/{page_id}/preview` 返回 500，以及 `Edge 动作超时: screenshot_page @ screenshot_page:capturing (25.0s)` 的问题。
- 交付原则：
  - 不按“先打一版补丁再说”的方式交付。
  - 必须执行“修复 -> 自检 -> 复现 -> 回归 -> 再修复”的闭环，直到关键验收场景通过后再交付。
  - 在实施前不能诚实承诺“绝对完美”，但实施阶段会以商业级稳定性交付为目标，持续 debug 到核心场景通过。
- 预期结果：
  - 页签扫描接口在 Edge 已连接时稳定返回，不因为某个异常页签导致整批失败。
  - 预览截图接口在单个页签卡死时能给出明确可恢复错误，不把整个会话拖死。
  - 一旦 `list_pages` 或 `screenshot_page` 超时，系统能够自动淘汰僵死的 `RemoteEdge` 客户端并恢复下一次调用，而不是持续进入“后续请求全超时”的坏状态。
  - 前端对超时、页签冻结、会话失活能给出明确操作指引，而不是只显示泛化的 500。

## 二、Current State Analysis

### 1. 已确认的现状
- `GET /api/edge-sessions/{session_id}/health` 返回 200，说明调试端口并非完全不可用。
- `GET /api/tasks/{task_id}/page-candidates` 有时返回 200，说明同一会话并非完全无法列页签，而是存在“部分操作成功、部分操作卡死”的状态。
- `GET /api/edge-sessions/{session_id}/pages` 在 [main.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/main.py#L553-L564) 中直接调用 `client.list_pages()`。
- `POST /api/edge-sessions/{session_id}/pages/{page_id}/preview` 在 [main.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/main.py#L584-L614) 中直接调用 `client.screenshot_page(page_id)`。
- `client.list_pages()` 和 `client.screenshot_page()` 都走 [remote_edge.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/remote_edge.py) 中的 `_call()` 单线程 worker 队列。

### 2. 当前根因判断
- **根因 A：单线程 worker 超时后没有自恢复机制**
  - [remote_edge.py:_call](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/remote_edge.py#L222-L233) 在 `queue.Empty` 时仅抛出 `EdgeActionTimeoutError`，但不会重置浏览器连接、不会废弃当前 client、不会中止已卡住的后台 job。
  - 结果是：某次 `page.screenshot()` 或 `page.title()` 一旦卡住，worker 线程仍然被这个 job 占住，后续请求继续排队，导致同一会话持续报错。

- **根因 B：页签列表扫描对单个坏页签过于脆弱**
  - [remote_edge.py:_list_pages](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/remote_edge.py#L792-L801) 会对所有页签调用 `_page_info()`。
  - [remote_edge.py:_page_info](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/remote_edge.py#L1049-L1055) 直接调用 `page.title()`。
  - 在直播后台、复杂控制台页、冻结页签、跨进程异常页签场景下，`page.title()` 可能阻塞或非常慢，导致“一个坏页签拖死整次页签扫描”。

- **根因 C：截图失败时错误信息不够完整，前端无法给出正确恢复动作**
  - `/pages` 和 `/preview` 的 500 响应目前缺少足够的 `stage / health / reason_code` 细节。
  - 前端 [edge.js](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/edge.js#L189-L241) 与 [config.js](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/config.js#L624-L686) 对 `edge_action_timeout`、`edge_preview_failed` 的恢复提示不完整。

- **根因 D：调度器与配置页共用同一 RemoteEdge 客户端，坏状态会相互污染**
  - [scheduler.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/services/scheduler.py#L85-L149) 也会调用 `find_page()` / `screenshot_page()`。
  - 如果配置页预览先把 client 卡死，调度器随后也可能进入同样的超时链路；反过来也成立。

### 3. 当前实现上的关键结论
- 这不是单纯“Edge 没启动”的问题，而是“Edge 会话已可访问，但 Playwright/CDP 某个动作卡住后，RemoteEdge client 没有恢复机制”。
- 这不是简单把超时从 25 秒调大就能解决的问题；单纯延长超时只会把卡死时间拉长，不能解决僵死 client 和坏页签拖垮全会话的问题。

## 三、Proposed Changes

### A. `backend/collectors/remote_edge.py`

#### 1. 引入 client 失效与重建机制
- 为 `RemoteEdge` 增加“超时后标记失效”的状态，例如 `self._stale = True` 或同等字段。
- 当 `_call()` 捕获 `queue.Empty` 并抛出 `EdgeActionTimeoutError` 时：
  - 记录 `reason_code = edge_action_timeout`
  - 标记当前 client 已失效
  - 保存超时时的 `action/stage`
- 为 `RemoteEdgeManager` 增加显式重置能力，例如 `reset_client(session_id)` 或同等级接口。
- 设计决策：
  - **不尝试在原 worker 上强行恢复**，因为卡住的 Playwright 调用不可可靠中断。
  - **直接废弃旧 client，创建新 client**，让下一次请求重新 `connect_over_cdp`。

#### 2. 硬化页签扫描逻辑，避免单个坏页签拖垮整个列表
- 重构 `_list_pages()`，要求：
  - 先清理 `self._pages` 中已经关闭的页签。
  - 对单页信息提取使用“逐页容错”策略，单个页签失败时只跳过该页签，不让整个 `list_pages` 失败。
- 重构 `_page_info()`，要求：
  - **移除直接 `page.title()` 的强依赖**，改成“拿不到标题也允许返回空标题”。
  - 第一优先级是保证 `page_id + url + alive` 稳定返回，标题允许降级为空字符串。
- 设计决策：
  - 这里优先追求稳定性，不把“标题准确性”放在“页签列表可用性”之前。
  - 前端已有 `title || url || page_id` 的降级展示逻辑，可以承受标题为空。

#### 3. 硬化截图逻辑与失败分级
- 重构 `_screenshot_page()`，要求：
  - 在真正截图前再次校验页签是否仍存活。
  - 对 `wait_for_load_state` 保持宽容，但对 `page.screenshot()` 超时要清晰标记。
  - 截图失败时保留失败阶段，例如 `screenshot_page:wait_load`、`screenshot_page:capturing`。
- 设计决策：
  - 不新增“自动换页截图”或“偷偷新开页”行为，避免误采。
  - 只允许“明确报错 + 让用户重新扫描/重绑”，与现有产品原则一致。

### B. `backend/main.py`

#### 1. 统一超时错误响应结构
- 修改以下接口的异常处理：
  - [GET /api/edge-sessions/{session_id}/pages](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/main.py#L553-L564)
  - [POST /api/edge-sessions/{session_id}/pages/{page_id}/preview](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/main.py#L584-L614)
  - [GET /api/tasks/{task_id}/page-candidates](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/main.py#L746-L793)
  - [POST /api/test-ocr](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/main.py#L649-L684)
- 对 `EdgeActionTimeoutError` 单独捕获，统一返回：
  - `reason_code`
  - `action`
  - `stage`
  - `session_id`
  - `page_id`（若有）
  - `health`
  - `recovery_hint`

#### 2. 在超时后自动丢弃僵死 client
- 在捕获 `EdgeActionTimeoutError` 后调用 `remote_edge_manager.reset_client(session_id)`。
- 对 `/pages` 与 `/preview` 采取“超时后重建 client，再决定是否重试一次”的策略。
- 设计决策：
  - `/pages` 可以考虑重建后重试一次，因为它是只读且无副作用。
  - `/preview` 也可以允许一次重试，但只限同一 `page_id`，若仍失败则返回明确错误，不无限重试。

### C. `backend/services/scheduler.py`

#### 1. 为正式采集链路补齐超时分类与恢复
- 在 [capture_once](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/services/scheduler.py#L85-L149) 中单独处理 `EdgeActionTimeoutError`。
- 超时时：
  - 记录任务状态为 `edge_action_timeout`
  - `last_reason` 写入具体 `action/stage`
  - 调用 `remote_edge_manager.reset_client(session.session_id)`，避免下一轮采集继续用僵死 client
- 设计决策：
  - 不把超时吞掉，也不伪装成 `remote_page_not_found`。
  - 让任务管理页能区分“页面没了”和“页面还在但截图线程卡死”。

### D. `frontend/config.js` 与 `frontend/edge.js`

#### 1. 给扫描和预览补充可执行恢复提示
- 在 [scanBind](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/config.js#L624-L686) 中新增对以下错误码的处理：
  - `edge_action_timeout`
  - `list_pages_failed`
- 在 [previewRemotePage](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/edge.js#L189-L241) 中新增对以下错误码的处理：
  - `edge_action_timeout`
  - `edge_preview_failed`
- UI 提示策略：
  - 明确告诉用户“不是 Edge 没启动，而是当前页签响应异常或截图线程卡住”
  - 给出下一步动作：“关闭当前会话 Edge -> 重新显示 -> 回来重新扫描 -> 重新预览”
  - 若后端返回 `stage`，在提示中展示具体阶段

#### 2. 保持现有产品约束
- 不新增自动重绑。
- 不在前端偷偷切换到其它页签。
- 只做更精准的提示与恢复引导。

## 四、Assumptions & Decisions
- 假设当前项目允许对 `RemoteEdgeManager` 增加 client 重建能力，这是本次修复的核心。
- 决策：优先修复稳定性，不优先保留页签标题的完美展示。
- 决策：不通过“把超时改大”来掩盖卡死；根本目标是“超时后能恢复”。
- 决策：不引入新的浏览器自动恢复策略，不帮用户自动打开或猜测正确页签，避免错误采集。
- 当前仓库未发现现成自动化测试目录或测试文件，本次验证以手工回归和日志验证为主。

## 五、Verification Steps

### 0. 交付门槛
- 以下任一条件未满足，都不视为完成：
  - 我无法稳定复现并回归验证你的原始报错链路。
  - 页签扫描、预览截图、单次采集三条链路里仍有一条会持续进入僵死状态。
  - 后端虽然不报 500，但前端仍然只能看到模糊错误而无法恢复操作。

### 0.5. 实施期 debug 原则
- 实施时按以下顺序循环，直到通过：
  1. 精确复现你的报错。
  2. 修改一个最小闭环。
  3. 立即重跑后端并重新测试扫描、预览、采一次。
  4. 读取新日志，确认是否从“原错误”变成了“新错误”。
  5. 若仍失败，继续定位直到核心验收场景通过，不以“代码写完了”作为结束条件。

### 1. 回归采集配置主流程
- 启动后端与前端，进入 `采集配置`。
- 选择问题店铺会话，执行“扫描当前会话页签”。
- 预期：
  - `/api/edge-sessions/{session_id}/pages` 或 `/api/tasks/{task_id}/page-candidates` 不再因为单个坏页签整体 500。
  - 页签标题即使为空，也能看到 URL 或页签 ID 供手动选择。

### 2. 回归预览截图
- 绑定一个已知正常页签，点击“生成预览”。
- 预期：
  - 正常页签能稳定返回预览。
  - 异常页签返回可恢复错误，包含 `reason_code / stage / recovery_hint`。

### 3. 验证超时后的恢复能力
- 人为制造一个会让截图卡住的页签后触发预览。
- 首次预期：
  - 后端返回 `edge_action_timeout`
  - 日志中能看到具体阶段，例如 `screenshot_page:capturing`
- 再次操作预期：
  - 因为 client 已被重建，不会一直沿用坏掉的旧 worker
  - 重新显示 Edge 或重新扫描后，后续请求可恢复

### 4. 验证正式采集链路
- 对同一会话执行一次 `capture_once`。
- 预期：
  - 超时被记录为明确状态，而不是泛化成其它错误
  - 下一次采集不会持续卡在同一个僵死 client 上

### 5. 前端交互验证
- 在扫描失败、预览失败、超时三种场景下分别验证提示文案。
- 预期：
  - 用户能看懂“当前发生了什么”
  - 用户知道“下一步去任务管理做什么”
  - 不会只看到笼统的 “500 Internal Server Error”

## 六、最终验收标准
- 只有在以下条件同时满足时，才向用户宣告修复完成：
  - 你的原始报错链路已无法稳定复现，或已被明确降级为可恢复错误。
  - 触发一次超时后，不会把同一会话永久拖死，后续操作可恢复。
  - 扫描页签、生成预览、采一次三条链路都实际跑通过。
  - 关键改动已完成自检，未引入新的明显诊断错误。
  - 交付说明会明确写出：改了什么、为什么这样改、如何验证、剩余风险是什么。
