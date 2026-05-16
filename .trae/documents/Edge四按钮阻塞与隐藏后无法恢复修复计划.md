## Summary
- 本次计划目标：
  - 梳理 `启动Edge / 显示Edge / 隐藏Edge / 关闭Edge` 四个按钮的完整运行链路。
  - 明确“按钮会黑很久”和“隐藏后再显示不出来网页”的真实根因。
  - 给出一份按风险递进、可验证、可回退的修复计划。
- 当前问题结论：
  - `显示Edge` 并不是单纯的窗口显示动作，而是“会话启动/重连 + 调试端口检查 + 窗口恢复 + 原生补窗 + 受控重启”的复合动作，因此天然阻塞重。
  - `隐藏Edge` 当前优先尝试 `SW_HIDE`，而不是优先“移出屏幕外”；这会让后续 `显示Edge` 的窗口恢复路径更不稳定。
  - 前端会把同一作用域内四个 Edge 按钮统一置为 busy/disabled，导致用户体感是“四个按钮一起黑很久”。

## Current State Analysis
### 1. 前端按钮层
- 文件：`frontend/app.js`
- 事实：
  - `setEdgeActionBusy()` 会把当前作用域内全部 `.edge-launch-button` 一起禁用。
  - 无论点击的是启动、显示、隐藏还是关闭，视觉上都是整组按钮一起变黑。
  - 平台旁边的四个按钮和店铺旁边的四个按钮共享同一套 busy 处理思路，但平台按钮触发的是“批量动作”，复杂度更高。
- 影响：
  - 用户无法知道到底是哪一个动作在执行，也无法区分当前是“真正卡住”还是“后台仍在恢复”。
  - 由于整组按钮一起黑，用户会误以为四个动作共享同一个黑盒状态，而看不到实际是哪个动作在阻塞。

### 2. 前端 API 超时层
- 文件：`frontend/core.js`
- 事实：
  - `startEdgeSession()` 超时为 18 秒
  - `showEdgeSession()` 超时为 35 秒
  - `hideEdgeSession()` 超时为 22 秒
  - `closeEdgeSession()` 超时为 35 秒
  - 平台级操作统一超时为 45 秒
- 影响：
  - 当前前端设计本身已经接受这些动作是“长耗时同步动作”。
  - 因此前端黑很久不一定是异常，也可能是后端动作设计本身过重。
  - 当前前端只在失败后通过 `edgeWindowErrorMessage()` 展示 `stage`，但在“正常等待中”不会持续展示阶段，因此用户看到的仍然只是黑按钮。
  - 平台级按钮超时统一是 45 秒，但其内部实际是多个店铺动作的聚合，这个超时和单店铺动作的语义并不匹配。

### 3. 后端 `start_edge` 链路
- 文件：`backend/collectors/remote_edge.py`
- 实际执行阶段：
  1. `start:locating_edge`
  2. 发现已存在调试端口则直接进入 `start:debug_port_ready`
  3. 否则检查是否存在“同 profile 但非调试模式”的 Edge 进程
  4. 必要时受控关闭并重启该 profile
  5. `start:launching_process`
  6. `start:waiting_debug_port`
  7. `start:connecting_browser`
  8. `_ensure_launch_page(target_url)`
- 关键阻塞点：
  - 等调试端口时固定轮询 20 次，每次 0.5 秒，理论上最多 10 秒。
  - 如果检测到 profile 已运行但非调试模式，还会先关闭再重启。
  - `_ensure_launch_page(target_url)` 在 `start` 阶段内同步执行，也会继续拉长启动动作。

### 4. 后端 `show_edge` 链路
- 文件：`backend/collectors/remote_edge.py`
- 实际执行阶段：
  1. `show:starting_session`
  2. 若已存在窗口但调试端口未接通，则先尝试只显示窗口
  3. 否则直接调用 `_start_edge(..., reset_context=False)`
  4. `show:finding_window`
  5. 找不到则 `_spawn_native_window()`
  6. 仍失败则 `_restart_edge_for_window()`
  7. 成功后进入 `show:window_ready`
- 关键结论：
  - `显示Edge` 并不是“只做显示”，而是一个复合恢复入口。
  - 因此它会继承 `start_edge` 的阻塞，再叠加窗口恢复阻塞。
  - 当前 `show_edge` 实际承担了“显示窗口控制器 + 会话修复器 + 会话重启器”三种职责，耦合过重。

### 5. 后端 `hide_edge` 链路
- 文件：`backend/collectors/remote_edge.py`、`backend/collectors/window_control.py`
- 实际执行阶段：
  1. `hide:checking_debug_port`
  2. `hide:finding_window`
  3. 调用 `hide_edge_window()`
- 当前隐藏策略顺序：
  1. `hide_window` -> `SW_HIDE`
  2. `minimize_window` -> `SW_MINIMIZE`
  3. `move_offscreen` -> 移出屏幕外
- 风险点：
  - 当前优先 `SW_HIDE`，恢复难度最大。
  - 隐藏成功验收标准 `_window_is_hidden_like()` 只要满足“不显示 / 最小化 / 屏幕外”任一条件就算成功。
  - 这意味着“成功隐藏”与“可稳定恢复显示”不是同一个标准。

### 6. `RemoteEdgeClient` 单线程 worker 模型
- 文件：`backend/collectors/remote_edge.py`
- 事实：
  - 每个 session 的 `RemoteEdge` 只有一个后台 worker 线程，通过 `_jobs` 队列串行执行所有动作。
  - `_call()` 超时后，只是把 client 标记为 `stale` 并向上抛 `EdgeActionTimeoutError`。
  - 但已超时的那个 worker 任务不会被真正中断，仍可能继续在后台执行。
- 影响：
  - 一旦某次 `show/hide/start/close` 超时，前端以为动作失败，但老 worker 可能仍在继续跑。
  - 用户随后再次点击按钮，体感就会变成“后续所有按钮都更慢、更乱、更黑”。
  - 这不是纯窗口问题，而是动作执行模型与超时语义不一致的问题。

### 7. 后端 `show_edge_window()` 恢复链
- 文件：`backend/collectors/window_control.py`
- 实际行为：
  - 先按 `cached_hwnd` 找窗口
  - 找不到再按 `debug_port + user_data_dir + pid` 过滤进程窗口
  - 再对目标窗口做：
    - `SW_SHOW`
    - `SW_RESTORE`
    - `_move_window_into_view()`
    - `_activate_window()`
    - `SW_MAXIMIZE`
  - 共重试 3 轮
- 风险点：
  - 若窗口已经被 `SW_HIDE` 后系统状态变得不稳定，虽然仍能找到 hwnd，也不一定能回到 `presentable` 状态。
  - `show_edge_window()` 当前只负责“恢复既有窗口”，不能区分“恢复不稳”与“窗口对象本身已不适合恢复”。
  - 当前 `_find_edge_window_for_action()` 依赖 `debug_port + user_data_dir + pid` 过滤到候选进程，再找窗口；如果 pid 缓存、窗口句柄缓存或候选进程识别出现偏差，恢复链会继续误判。

### 8. 后端 `close_edge` 链路
- 文件：`backend/collectors/remote_edge.py`
- 当前行为：
  - 已经是“优雅关闭优先，强杀兜底”
  - 这条链相对之前更健康
- 但仍存在：
  - 如果用户频繁在 `hide/show` 之间切换失败，可能最终被迫走 `close/start` 才恢复

### 9. 任务状态层与窗口控制层是两套状态机
- 文件：`frontend/core.js`、`frontend/config.js`、`backend/main.py`
- 事实：
  - 任务配置工作台的 `setupStageMeta(task)` 关注的是：
    - 待绑定
    - 待登录
    - 待切业务页
    - 待标定
    - 已完成
  - Edge 窗口控制链关注的是：
    - 调试端口
    - 窗口句柄
    - 恢复阶段
    - 会话是否 stale
- 影响：
  - 用户当前在 UI 上能看到的多是任务状态，而不是 Edge 控制状态。
  - 这会造成“任务看起来没问题，但窗口动作黑很久”的认知割裂。

### 10. 平台级四按钮是“批量聚合动作”，不是单动作
- 文件：`frontend/app.js`、`frontend/core.js`、`backend/main.py`
- 事实：
  - 平台区按钮：
    - `启动Edge`
    - `显示Edge`
    - `隐藏Edge`
    - `关闭Edge`
  - 实际走的是 `/api/platforms/{platform}/*-edge`
  - 后端 `run_platform_edge_action()` 通过 `asyncio.gather()` 并发执行平台下所有任务的动作。
- 影响：
  - 当前平台级动作不是“按顺序逐个吊起 N 个会话”，而是“同平台下多个会话并发发起动作”。
  - 这会把单店铺已有的窗口恢复、调试端口、超时、stale client 问题放大成平台级问题。
  - 用户体感会是“平台按钮更黑、更久、更不可解释”。

### 11. 平台级“启动Edge”和店铺级“启动Edge”语义不一致
- 文件：`backend/main.py`、`frontend/app.js`
- 事实：
  - 店铺级 `启动Edge` 走的是 `startAndShowEdgeSession()`，先 `start` 再 `show`
  - 平台级 `启动Edge` 的 UI 实际映射到 `launch-platform-edge`
  - 后端 `launch-edge` 当前调用的是 `client.show_edge(...)`，不是显式 `client.start_edge(...) + client.show_edge(...)`
- 影响：
  - 同样叫“启动Edge”，平台按钮和店铺按钮却不是同一条动作链。
  - 这会导致排查时“单店逻辑”和“平台逻辑”对不上，也会让批量恢复行为更不可预测。

## Complete Logic Chain
### 启动Edge
- 前端点击任务按钮
- `frontend/app.js` 调 `startAndShowEdgeSession()`
- `frontend/core.js` 先调 `/api/edge-sessions/{id}/start`
- 若调试端口接通，再继续调 `/api/edge-sessions/{id}/show`
- 后端 `start_edge` 负责进程与调试端口
- 后端 `show_edge` 负责窗口恢复与必要的补救

### 显示Edge
- 前端点击任务按钮
- `frontend/app.js` 直接调 `showEdgeSession()`
- `frontend/core.js` 调 `/api/edge-sessions/{id}/show`
- 后端 `show_edge` 先可能隐式执行 `_start_edge()`
- 再走窗口恢复逻辑
- 若失败，还会补建窗口，甚至整会话受控重启

### 隐藏Edge
- 前端点击任务按钮
- `frontend/app.js` 调 `hideEdgeSession()`
- `frontend/core.js` 调 `/api/edge-sessions/{id}/hide`
- 后端 `hide_edge` 只负责窗口层动作，不重建会话
- 但当前隐藏策略优先 `SW_HIDE`，给后续恢复埋下不稳定性

### 关闭Edge
- 前端点击任务按钮
- `frontend/app.js` 调 `closeEdgeSession()`
- `frontend/core.js` 调 `/api/edge-sessions/{id}/close`
- 后端 `close_edge` 优先优雅关闭，失败后强杀

### 平台级四按钮
- 前端点击平台卡片旁的四个按钮
- `frontend/app.js` 调 `callPlatformEdgeAction(platform, action)`
- `frontend/core.js` 调 `/api/platforms/{platform}/{action}-edge`
- 后端 `run_platform_edge_action()` 会先拿到该平台下所有 `edge_tasks_for_platform(platform)`
- 然后对这些任务执行 `asyncio.gather(*(run_one(task) for task in tasks))`
- 这意味着当前平台级按钮本质上是“并发批量动作聚合器”

## Root Cause
### 根因 1：`show_edge` 职责过重
- 现在 `show_edge` 同时承担：
  - 启动/重连调试会话
  - 窗口恢复
  - 补建原生窗口
  - 受控重启整个会话
- 结果：
  - 一个“显示”按钮背后变成多阶段同步阻塞动作
  - 用户感知就是“点击显示后黑很久”

### 根因 2：隐藏策略优先级不合理
- 当前隐藏顺序是 `SW_HIDE -> SW_MINIMIZE -> move_offscreen`
- 从恢复稳定性看，应该相反：
  - 最稳的是 `move_offscreen`
  - 次稳是 `minimize`
  - 最不稳才是 `SW_HIDE`
- 结果：
  - 当前“隐藏成功”并不意味着“下次显示容易恢复”

### 根因 3：动作超时语义与执行模型不一致
- 当前 `_call()` 超时只会让调用方返回失败，并标记 client stale
- 但 worker 中的实际动作不会被真正取消
- 结果：
  - 老动作可能继续执行
  - 新动作可能排队或撞上旧状态
  - 用户感知是“一次卡住后，后面越来越乱”

### 根因 4：前端 busy 粒度过粗
- 当前同组四个按钮统一 disabled
- 结果：
  - 用户不知道到底是哪一层在执行
  - 无法区分“系统正在正常恢复”与“系统已经卡住”

### 根因 5：后端阶段信息只在失败后透出，没有形成“处理中可见”
- `remote_edge.py` 内部已经维护了大量 `stage`
- 前端现在主要在失败消息里拼接 `stage`
- 但在成功前的等待过程中，并不会实时看到阶段
- 结果：
  - 用户只看到黑按钮
  - 看不到卡在“等待调试端口 / 找窗 / 补窗 / 重启”哪一步

### 根因 6：窗口控制状态与任务业务状态耦合松散
- 当前任务状态机并不能代表窗口控制状态健康
- 结果：
  - 即使任务层仍显示“已绑定/已完成”，窗口层可能已经 stale 或仍在处理上一轮动作
  - 用户缺少统一的 Edge 会话健康视图

### 根因 7：平台级批量动作采用并发模型，缺少顺序控制
- 当前 `run_platform_edge_action()` 使用 `asyncio.gather()` 并发执行同平台下所有店铺动作
- 结果：
  - 如果一个平台下有多个店铺，会同时触发多个 `show/start/hide/close`
  - 多个 Edge 进程会同时争用：
    - Windows 前台窗口切换
    - 调试端口建立
    - 窗口枚举与恢复
    - 前端等待时间
  - 这和你要求的“按顺序分别吊起 N 个平台 / N 个会话”是冲突的

### 根因 8：平台级与店铺级启动语义不一致
- 店铺级 `启动Edge` 是显式 `start + show`
- 平台级 `启动Edge` 当前通过 `launch-edge -> show_edge` 间接触发启动
- 结果：
  - 排查逻辑难以统一
  - 平台级“启动”行为更像“显示并尝试修复”
  - 会进一步放大 `show_edge` 职责过重的问题

## Best Implementation
### 总体原则
- 优先修最小风险、最大收益的点：
  1. 先修执行模型与隐藏策略里最致命的问题
  2. 再补会话级可观测性
  3. 再拆分 `show_edge` 职责
- 不做一步到位的大重构，避免把窗口控制链彻底打乱。

### 修复优先级判断
- 第一优先：解决“隐藏后再显示出不来”
- 第二优先：解决“超时后老动作仍在后台继续跑”
- 第三优先：解决“按钮黑很久但用户不知道卡在哪”
- 第四优先：降低 `show_edge` 的复合阻塞程度
- 第五优先：统一平台级与店铺级四按钮语义，并把平台级动作改成顺序执行

## Proposed Changes
### 1. 先补会话级动作占用与 stale 可视化
- 文件：`backend/collectors/remote_edge.py`、`backend/main.py`、`frontend/app.js`
- 变更：
  - 在 health / show / hide / start / close 返回里稳定透出：
    - `is_window_op_running`
    - `is_stale`
    - `stale_reason`
    - 当前 `stage`
  - 前端在按钮 busy 和失败消息中都展示这些信息
- 为什么这样改：
  - 先把“旧动作还在跑”这件事看见
  - 避免继续把所有问题都误归因到窗口句柄

### 2. 调整隐藏策略顺序
- 文件：`backend/collectors/window_control.py`
- 变更：
  - 将 `hide_edge_window()` 的动作顺序改为：
    1. `move_offscreen`
    2. `minimize_window`
    3. `hide_window`
  - 默认优先使用“移出屏幕外”作为隐藏成功策略
- 为什么这样改：
  - 项目本来就在启动时用 `--window-position=32000,0` 的思路保留渲染能力
  - 与现有多会话设计更一致
  - 恢复显示的成功率也更高

### 3. 收紧隐藏成功验收与恢复语义
- 文件：`backend/collectors/window_control.py`、`backend/collectors/remote_edge.py`
- 变更：
  - 在隐藏结果里明确区分：
    - `move_offscreen`
    - `minimize_window`
    - `hide_window`
  - 在 `hide_edge` 的返回中保留该动作供前端展示
- 为什么这样改：
  - 让“隐藏成功”的语义更可解释
  - 方便后续判断哪种隐藏方式最容易恢复

### 4. 修正动作超时后的 client 回收策略
- 文件：`backend/main.py`、`backend/collectors/remote_edge.py`
- 变更：
  - 对 `start/show/hide/close` 超时场景，统一在 API 层立即 `reset_client(session_id)`
  - 避免超时后继续复用一个已被标记 stale、且可能仍有旧 worker 动作未结束的 client 实例
- 为什么这样改：
  - 这是当前结构里最小风险、最直接的收口手段
  - 不需要先重写 worker 模型，就能先降低“超时后后续动作越来越乱”的概率

### 5. 拆分 `show_edge` 的恢复路径优先级
- 文件：`backend/collectors/remote_edge.py`
- 变更：
  - `show_edge` 优先做“仅显示既有窗口”
  - 只有在明确不存在可恢复窗口时，才进入：
    - `_spawn_native_window()`
    - `_restart_edge_for_window()`
  - 对每个恢复阶段记录更明确的 `stage`
- 为什么这样改：
  - 降低“显示”按钮被过度设计成“万金油修复入口”的副作用
  - 优先走轻路径，减少长时间阻塞

### 6. 统一平台级与店铺级按钮语义
- 文件：`frontend/app.js`、`frontend/core.js`、`backend/main.py`
- 变更：
  - 明确四类动作统一语义：
    - `启动Edge` = 建立/恢复调试会话，再显示窗口
    - `显示Edge` = 只做窗口恢复，必要时有限补救
    - `隐藏Edge` = 只做窗口隐藏
    - `关闭Edge` = 关闭会话
  - 平台级与店铺级按钮走相同语义模型，不再一套显式 `start+show`，另一套隐式 `show -> start`
- 为什么这样改：
  - 避免同名动作却不是同一逻辑链
  - 让平台级和店铺级排查口径统一

### 7. 平台级四按钮改为顺序执行模型
- 文件：`backend/main.py`
- 变更：
  - 将 `run_platform_edge_action()` 从 `asyncio.gather()` 并发执行，改为按配置顺序逐个执行
  - 每执行完一个会话，记录阶段结果，再继续下一个
  - 为平台级动作补充：
    - 当前序号
    - 当前店铺
    - 累计成功/失败
- 为什么这样改：
  - 平台按钮本身就是“批量控制器”，更适合顺序、可观测、可中断的执行方式
  - 尤其是 `显示Edge` 和 `启动Edge`，并发恢复多个窗口本身就和桌面窗口控制天然冲突

### 8. 前端显示当前 Edge 动作阶段
- 文件：`frontend/app.js`、`frontend/core.js`
- 变更：
  - 在按钮 busy 期间，把后端返回或异常中的 `stage` / `reason_code` 展示给用户
  - 至少能提示：
    - 正在等待调试端口
    - 正在查找窗口
    - 正在补建原生窗口
    - 正在执行受控重启
- 为什么这样改：
  - 让“黑很久”变成“用户知道系统正在做什么”

### 9. 细化前端按钮禁用范围
- 文件：`frontend/app.js`
- 变更：
  - 优先只禁用当前点击按钮
  - 其它按钮在必要时禁用，避免整组全部发黑
  - 或者保留整组禁用，但增加明显的“处理中阶段说明”
- 为什么这样改：
  - 改善体感
  - 降低“系统卡死”的误判

### 10. 为 `show/hide/start/close` 增加链路诊断输出
- 文件：`backend/main.py`、`backend/collectors/remote_edge.py`
- 变更：
  - 在 API 返回结果中稳定带出：
    - `stage`
    - `reason_code`
    - `window_action`
    - `recovery_attempted`
    - `window_diagnostics`
- 为什么这样改：
  - 方便前端展示
  - 也方便后续定位“到底卡在窗口层还是调试层”

### 11. 补一个统一的 Edge 会话健康视图
- 文件：`frontend/app.js`、`frontend/edge.js`
- 变更：
  - 在任务管理或会话状态区增加会话级摘要：
    - 调试端口是否在线
    - 当前是否有窗口
    - 当前是否 stale
    - 当前是否仍有窗口动作在执行
    - 最近阶段 / 最近错误
- 为什么这样改：
  - 统一“任务状态”和“窗口控制状态”的认知差异
  - 用户后续排查不会再只盯着任务标签看

### 12. 仅在最终阶段再优化产品文案
- 文件：`frontend/app.js`
- 变更：
  - 将“显示Edge / 隐藏Edge / 启动Edge / 关闭Edge”提示语，从一句笼统提示，升级为带阶段和建议的提示
- 为什么这样改：
  - 先把底层行为修稳，再同步文案，避免文案先承诺、行为后跟不上

## Assumptions & Decisions
- 已确认事实：
  - 当前按钮发黑时间长，不是纯前端问题，而是后端同步阻塞链导致的真实结果。
  - 当前“隐藏后再显示不出来”最可疑的是隐藏策略顺序不合理，而不是单纯某个按钮偶发失灵。
  - 当前还存在更深的结构问题：单线程 worker 超时后，老动作可能继续运行，导致同会话后续动作越来越不稳定。
- 本次方案选择：
  - 不优先大改浏览器/CDP 主链
  - 先修会话执行模型的收口策略、窗口控制策略与前端可观测性
  - 再逐步收敛 `show_edge` 的职责
  - 平台级动作必须纳入同一套修复计划，不能只修店铺级按钮

## Risk Assessment
- 低风险改动：
  - 超时后立即 reset stale client
  - 调整隐藏顺序
  - 增加阶段展示
  - 增加诊断字段展示
- 中风险改动：
  - 拆分 `show_edge` 的恢复优先级
  - 改动窗口恢复条件
  - 调整 busy 粒度
- 中高风险改动：
  - 平台级动作从并发改为顺序执行
  - 平台级与店铺级按钮统一语义
- 暂不建议一步到位做的动作：
  - 彻底重写 `show_edge` 全链
  - 彻底重写 `RemoteEdge` worker 模型
  - 删除补建窗口或受控重启逻辑
  - 把所有动作改成完全异步但不提供阶段回传

## Execution Order
1. 先补 `is_stale / stale_reason / is_window_op_running / stage` 的统一透传。
2. 对 `start/show/hide/close` 超时场景统一立即 `reset_client(session_id)`。
3. 再修改 `hide_edge_window()` 顺序为 `move_offscreen -> minimize -> hide`。
4. 统一平台级与店铺级四按钮语义，先消除“同名不同链路”。
5. 将平台级动作从并发改为顺序执行，并补充逐个会话的进度结果。
6. 前端增加动作阶段展示和会话健康摘要。
7. 然后再收紧 `show_edge` 的恢复优先级，优先轻路径。
8. 最后根据验证结果，再决定是否进一步拆分 `show_edge` 或重构 worker 模型。

## Verification Steps
### 场景 1：启动后首次显示
- 操作：
  - 点击 `启动Edge`
- 期望：
  - 能看到当前卡在的阶段
  - 若成功，窗口应正常恢复到前台最大化

### 场景 2：显示已在屏幕外的窗口
- 操作：
  - 启动后点击 `隐藏Edge`
  - 再点击 `显示Edge`
- 期望：
  - 以“恢复屏幕外窗口”为主路径成功
  - 不应频繁进入补建窗口或受控重启

### 场景 3：连续隐藏 -> 显示 -> 隐藏 -> 显示
- 操作：
  - 对同一店铺连续反复执行
- 期望：
  - 不再出现“一次隐藏后，下次显示长时间黑住且恢复不出来”的高概率问题

### 场景 4：某次 show/hide 超时后再次点击按钮
- 操作：
  - 故意制造一次 `show_edge` 或 `hide_edge` 超时
  - 立即再次点击同店铺按钮
- 期望：
  - 新动作不会继续复用旧的 stale client
  - 会话状态能明确显示“已重置旧 client，重新建立控制链”

### 场景 5：调试端口未接通但窗口还在
- 操作：
  - 制造“窗口在，但调试连接断”的状态
- 期望：
  - 前端能明确显示“窗口已恢复，但调试端口未接通”
  - 用户可区分“窗口问题”和“调试链路问题”

### 场景 6：平台级批量操作
- 操作：
  - 使用平台维度的 `显示Edge / 隐藏Edge`
- 期望：
  - 不再采用并发一把梭，而是按顺序逐个执行
  - 返回结果中能标明每个会话卡在哪一阶段
  - 单个会话失败不应直接让整个平台动作黑成不可解释状态

### 场景 7：平台级“启动Edge”与店铺级“启动Edge”一致性
- 操作：
  - 对同一店铺分别使用店铺级启动按钮、平台级启动按钮
- 期望：
  - 两者使用同一套动作语义
  - 日志、阶段、恢复路径应保持一致，不再出现“一个是 start+show，一个是 show 兼修复”的分裂行为
