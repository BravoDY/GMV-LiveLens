# Edge 会话就绪判断与显示窗口修复计划

## 一、Summary
- 目标：完美修复两个问题：
  - 问题 1：Edge 明明可以正常启动、历史也登录过很多次，却仍被判定为 `edge_session_not_ready`。
  - 问题 2：点击“显示Edge”后，原本隐藏在后台/屏幕外的 Edge 没有真正回到主屏幕前台。
- 交付原则：
  - 不接受“先改一版看看”的补丁式交付。
  - 必须按“修复 -> 重启服务 -> 真实点击验证 -> 读日志 -> 再修复”的闭环反复自测，直到这两个问题都被真实打通。
  - 只有在任务管理页、采集配置页、后端状态和窗口行为一致时，才算完成。

## 二、Current State Analysis

### 1. 已确认的代码现状
- `edge_session_not_ready` 当前主要依赖 `debug_available` 判断：
  - [main.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/main.py#L838-L874)
  - [main.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/main.py#L633-L720)
- `health()` 里对会话状态的定义是：
  - `debug_available = 调试端口能否访问`
  - `connected = Playwright browser 是否已连上`
  - 见 [remote_edge.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/remote_edge.py#L903-L941)
- 当前 `show_edge` 后端接口是异步 fire-and-forget：
  - [main.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/main.py#L497-L510)
  - 它立刻返回 `{"status":"accepted"}`，前端不会等待“窗口真的被显示成功”。
- 当前 `show_edge` 的核心逻辑在：
  - [remote_edge.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/remote_edge.py#L378-L467)
- 当前 Win32 显示窗口逻辑在：
  - [window_control.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/window_control.py#L520-L565)
  - 实际操作是 `ShowWindow -> Restore -> move_into_view -> activate -> maximize`
- 当前多会话模式启动 Edge 时会故意把窗口移到屏幕外：
  - [remote_edge.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/remote_edge.py#L326-L347)
  - 也就是说，“显示Edge”本来就必须承担“把屏幕外窗口拉回可见区”的职责。

### 2. 这两个问题的根因判断

#### 问题 1：为什么会被判成 `edge_session_not_ready`
- 当前实现把“调试端口不可达”直接等价为“Edge 会话未就绪”，但这并不等价于“没有登录态 / 没有历史 session”。
- 用户说“历史通过这个任务启动过很多次并且也登录过很多次”，这更像是：
  - **登录态是存在的**
  - 但 **当前调试端口没有恢复/建立成功**
  - 或 **启动后窗口存在、Profile 也存在，但 CDP 端口瞬时不可用**
- 当前产品文案把这几种情况混成一个 `edge_session_not_ready`，会误导用户以为“session 丢了”，这是不对的。
- 需要拆开：
  - “登录态存在但调试端口未接通”
  - “调试端口已通但 Playwright 未重连”
  - “调试端口已通但找不到业务页”

#### 问题 2：为什么点击“显示Edge”却没有真正显示
- 当前单店铺 `show-edge` 接口在 [main.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/main.py#L497-L510) 中异步返回 `accepted`，前端当成“显示动作成功发起”处理，但并不知道最终窗口是否真的拉到前台。
- 这就导致：
  - 用户点击按钮后 UI 很快认为动作发起了
  - 但 Win32 恢复窗口可能失败、没有找到正确窗口、窗口仍在屏幕外、或者被系统焦点规则拦截
  - 最终用户看到的结果就是“按钮点了，但没显示”
- 当前平台级显示接口 `show-platform-edge` 是同步聚合执行的，而单店铺 `show-edge` 不是，这里存在行为不一致。

### 3. 当前最关键的产品/架构问题
- `edge_session_not_ready` 这个状态名目前表达不准确，容易被理解成“会话/登录态丢失”，但代码实际判断的是“调试端口未接通”。
- “显示Edge” 是一个必须有明确成败结果的动作，但现在单店铺 API 被设计成异步 accepted，这与用户心智不匹配。
- 只要这两个点不改，即使底层窗口控制偶尔能成功，产品层仍然会反复制造“明明有会话却提示未就绪”“点了显示却感觉没反应”的错觉。

## 三、Proposed Changes

### A. `backend/collectors/remote_edge.py`

#### 1. 重构会话就绪判断
- 调整 `health()` 与相关调用方对“就绪”的定义：
  - 不再把 `edge_session_not_ready` 直接表述成“没有 session”
  - 区分以下状态：
    - `debug_port_unavailable`：调试端口未起来
    - `edge_debug_disconnected`：调试端口存在，但 Playwright/browser 尚未连上
    - `page_not_bound_or_missing`：会话可用，但目标页签不可用
- 保留用户登录态与 profile 诊断信息，强调“profile 仍在、登录态可能还在，只是当前会话控制链路未接通”。
- 为什么这样改：
  - 这能直接修正你第一个问题中的误导性文案。

#### 2. 强化 `show_edge()` 的最终结果语义
- 保持 [remote_edge.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/remote_edge.py#L385-L458) 为真正的“显示动作执行器”。
- 要求 `show_edge()` 的返回结果必须明确区分：
  - 调试端口是否就绪
  - 是否找到了目标窗口
  - 是否从屏幕外移回可见区域
  - 是否已恢复 / 激活 / 最大化
- 如果窗口仍未显示成功，必须给出可诊断原因：
  - `window_not_found`
  - `no_startup_window`
  - `show_window_failed`
  - `window_still_offscreen`

### B. `backend/collectors/window_control.py`

#### 1. 加强显示窗口后的结果校验
- 对 [show_edge_window](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/window_control.py#L520-L565) 做真正的“显示后验收”：
  - 执行 `ShowWindow / Restore / move_into_view / activate / maximize` 后
  - 再次枚举窗口
  - 校验窗口是否满足以下条件：
    - 仍然存在
    - 不在屏幕外
    - 非最小化
    - 最好处于可见且最大化状态
- 如果动作执行了但窗口仍在屏幕外，不能返回 `ok=True`，要显式失败。

#### 2. 评估焦点与前置失败的兼容修复
- `_activate_window()` 已有 `AllowSetForegroundWindow / SetForegroundWindow` 路径，但需要检查是否存在：
  - 窗口被恢复了但没被置前
  - 被最大化后又重新偏移到屏幕外
- 修复策略：
  - 以“窗口最终可见并回到主屏”为验收，而不是只要函数没异常就算成功。

### C. `backend/main.py`

#### 1. 把单店铺 `show-edge` 从异步 accepted 改成同步结果
- 当前 [show_edge_session](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/main.py#L497-L510) 异步返回 `accepted`，这是问题 2 的核心原因之一。
- 调整为：
  - 直接 `await asyncio.to_thread(client.show_edge, resolved_launch_url)`
  - 将真实返回的 `RemoteEdgeWindowState` 返回给前端
  - 如果失败，返回结构化错误而不是“后台已受理”
- 为什么这样改：
  - 用户点击“显示Edge”时，期望得到的是“已经显示成功 / 显示失败及原因”，而不是“我帮你异步丢后台了”。

#### 2. 调整 `edge_session_not_ready` 的错误语义
- 对以下接口统一改文案和分级：
  - `GET /api/tasks/{task_id}/page-candidates`
  - `POST /api/edge-sessions/{session_id}/pages/{page_id}/preview`
  - `POST /api/test-ocr`
- 原则：
  - 不再让用户误以为“session 没了”
  - 返回内容必须明确告诉用户：
    - profile / 登录态是否还在
    - 当前问题是调试端口、窗口显示，还是页签绑定

### D. `frontend/core.js` 与 `frontend/app.js`

#### 1. 单店铺 `显示Edge` 前端必须等待真实结果
- 当前 [core.js](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/core.js#L169-L183) 已按同步请求方式调用，但后端实际上返回的是 `accepted`。
- 后端改成同步后，前端需要：
  - 根据真实返回的 `window_found / maximized / reason_code / last_error` 决定展示成功或失败提示
  - 不再把“accepted”误认为已显示成功

#### 2. 调整错误文案
- 当前 [app.js](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/app.js#L327-L350) 对 `debug_port_unavailable / no_startup_window / window_not_found` 已有部分提示。
- 需要补充：
  - “当前不是没有历史 session，而是调试控制链路未接通”
  - “显示Edge失败不是页面没启动，而是窗口没有被拉回可见区”

### E. `frontend/config.js` 与 `frontend/edge.js`

#### 1. 修正 `edge_session_not_ready` 的用户提示
- 当前扫描页签和生成预览会把 `edge_session_not_ready` 统一理解为“当前店铺 Edge 会话未就绪”。
- 需要改为更精确的话术：
  - “该店铺 Edge 登录态/profile 可能仍在，但当前调试控制未接通”
  - “请先点击显示Edge或启动Edge，确认调试端口与窗口都恢复”

#### 2. 与任务管理页的显示动作形成闭环
- 用户在任务管理页点“显示Edge”成功后，采集配置页再次扫描时应当能明显改善状态。
- 如果没有改善，必须给出具体失败原因，不再只给笼统“未就绪”。

## 四、Assumptions & Decisions
- 决策：把“登录态/profile 是否存在”和“当前控制链路是否可用”严格区分，不再混用 `session_not_ready`。
- 决策：单店铺 `show-edge` 必须改成同步结果接口，这是问题 2 的核心修复，不做这个改动就无法满足“点了就真的显示”。
- 决策：显示动作的成功标准不是“调用过 Win32 API”，而是“窗口最终回到主屏并可见”。
- 决策：不增加新的复杂前端交互，只修正当前按钮行为、状态定义和提示文案。
- 假设当前项目允许把单店铺 `show-edge` 的返回行为从 `accepted` 改为“等待结果后返回”，前端已有足够超时预算支持这一改动。

## 五、是否改用 Chrome

### 1. 基于外部公开信息的判断
- 结论：**改成 Chrome 不能从根上避免这类问题，最多只是把“Edge 专有问题”换成“Chromium/CDP 通用问题 + Chrome 自己的限制”。**
- 原因一：`connect_over_cdp` 卡死、页签不同步、本地页签对象不出现等问题，并不是 Edge 独有，公开 issue 中在 Chromium/Edge/CDP 路线下都存在类似现象，例如：
  - Playwright 的 `connect_over_cdp` 卡住问题：[Bug: connect_over_cdp getting stuck](https://github.com/microsoft/playwright/issues/35928)
  - 页签对象与真实浏览器状态不同步、`page.url` 为空、超时的问题：[Bug: Page objects fail to sync after navigating from about:blank](https://github.com/microsoft/playwright/issues/39483)
- 原因二：Chrome 近版本还出现了“默认 Profile 远程调试受限”的额外限制，公开资料显示 Chrome 147+ 对默认数据目录的 remote debugging 有额外拦截逻辑，这意味着换 Chrome 不但不能保证更稳，某些场景还可能更麻烦：[Fix Chrome 147+ blocking remote debugging on default profile](https://github.com/browser-use/browser-harness/pull/142)
- 原因三：你现在的“显示Edge没回前台”问题本质上是 **Windows 窗口恢复 / 前置 / 屏幕外窗口拉回** 问题，这部分与 Edge/Chrome 品牌关系不大，换 Chrome 仍然会遇到同类 Win32 焦点和窗口恢复问题。

### 2. 基于当前项目代码的判断
- 当前项目并不是抽象成“任意 Chromium 浏览器”，而是明确写成 **Microsoft Edge 专用实现**：
  - `remote_edge.py` 内部直接查找 `msedge.exe`，并且启动参数、错误文案、行为语义都围绕 Edge 写死：[remote_edge.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/remote_edge.py#L676-L700)
  - `window_control.py` 的进程与窗口匹配逻辑也围绕 Edge 进程构建：[window_control.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/window_control.py#L177-L255)
  - README 也明确说明当前仅支持 Microsoft Edge：[README.md](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/README.md#L424-L424)
- 如果现在切到 Chrome，不是简单改一个可执行文件路径，而是要同步改：
  - 浏览器进程发现
  - 启动参数和 profile 路径策略
  - 窗口匹配逻辑
  - 文案和 API 语义
  - 测试与运维说明

### 3. 对你当前问题的直接结论
- **问题 1：`edge_session_not_ready`**
  - 这不是 Edge 品牌导致的核心问题，而是当前代码把“调试端口未接通”和“历史登录态不存在”混为一谈。
  - 换成 Chrome 后，如果调试端口/Playwright/CDP 没接通，依然会出现同类误判，除非我们先修复状态语义。
- **问题 2：点击“显示Edge”没显示**
  - 这更不是 Edge 独有问题，而是当前接口设计与 Win32 窗口恢复逻辑的问题。
  - 换成 Chrome，若仍采用“异步 accepted + Win32 显示后不验收”的方案，同样会出现“点击显示但窗口没回来”的体验。

### 4. 最终决策
- 当前阶段**不建议把本轮问题的主解决方案改成“切 Chrome”**。
- 更稳妥的顺序是：
  1. 先把当前 Edge 路线的状态判断、显示窗口、前后端闭环修好。
  2. 等控制链路稳定后，再评估是否值得抽象成“Chromium 浏览器适配层”。
  3. 如果未来真要支持 Chrome，应作为单独专题重构，而不是把它当成这两个问题的快捷修复手段。

## 六、Verification Steps

### 0. 交付门槛
- 只有以下条件同时满足，才允许宣告完成：
  - 点击单店铺“显示Edge”后，目标窗口真实回到主屏前台或明确报出具体失败原因。
  - 采集配置里的 `edge_session_not_ready` 不再被误解为“session 丢失”。
  - 在至少一条真实店铺链路上，完成“显示Edge -> 扫描页签 -> 生成预览”的闭环回归。

### 1. 单店铺显示动作回归
- 在任务管理页对目标店铺点击“显示Edge”。
- 预期：
  - 后端接口不再返回 `accepted`
  - 前端能拿到真实显示结果
  - Edge 窗口要么真实出现在主屏，要么返回明确失败原因

### 2. 就绪状态语义回归
- 在“调试端口未通”“调试端口已通但 browser 未连”“调试端口已通但无目标页签”三种状态下分别验证。
- 预期：
  - 三者提示不同
  - 不再把所有问题都显示成“没有 session / edge_session_not_ready”

### 3. 配置闭环回归
- 执行以下链路：
  - 任务管理点击“显示Edge”
  - 返回采集配置点击“扫描当前会话页签”
  - 选页签后点击“生成预览”
- 预期：
  - 如果窗口显示成功且调试端口可用，则扫描和预览能继续推进
  - 如果推进失败，日志和前端提示必须指出是“窗口问题”“调试端口问题”还是“页签问题”

### 4. 日志与前端一致性验证
- 检查后端日志、任务卡片状态、弹窗提示、配置页恢复提示是否一致。
- 预期：
  - 不会出现“任务管理显示成功，但配置页仍然毫无依据地报 edge_session_not_ready”

### 5. 自测循环要求
- 实施时必须至少完成以下循环：
  1. 修一轮代码
  2. 重启服务
  3. 实际点击“显示Edge”
  4. 观察窗口是否真的出现
  5. 实际点击“扫描页签”和“生成预览”
  6. 读日志确认
  7. 如果任一环节不符合预期，继续修复，直到闭环打通
