## Summary

- 目标 1：将 `任务管理` 中所有任务卡片右上角状态徽章统一为“上下形式”展示，不再追求首张任务卡片与其他卡片做成左右并排。
- 目标 2：让任务卡片中的登录/页面链接默认继续使用 `...` 省略显示，但支持鼠标双击后展开完整链接，再次双击可收起。
- 目标 3：深度修复 `启动Edge / 显示Edge` 仍然报 `操作失败：未找到对应的 Edge 主窗口` 的问题，不再停留在“仅扩大 PID 匹配范围”的层面。
- 约束：
  - 保持任务管理整体 UI 风格稳定，不再做平台头部、卡片结构的大范围重排。
  - 链接交互必须简单直观，默认紧凑，展开后不影响其他任务卡片基本操作。
  - 方案必须兼顾多会话 Edge、独立 `user_data_dir`、长时间运行和后续排障可解释性。

## Current State Analysis

### 1. 任务管理卡片 UI 与链接显示的当前实现

- 文件：`frontend/app.js`
- 现状：
  - 任务卡片头部结构为：
    - 左侧一个匿名 `<div>`，包含店铺名、模式、URL
    - 右侧 `.task-badges`，包含 `暂停中` 和状态标签
  - 平台级按钮仍在 `.manager-platform-title` 内部渲染，这是当前界面原始结构的一部分。
- 文件：`frontend/styles.css`
- 现状：
  - `.task-head` 继承通用 flex 头部规则，只定义了 `display:flex; align-items:center; justify-content:space-between; gap:14px;`
  - `.task-badges` 使用 `display:flex; flex-wrap:wrap; justify-content:flex-end;`
  - 当前没有对任务头部左侧内容做 `min-width: 0 / flex-shrink` 的明确约束
  - 当前也没有强制状态徽章 `nowrap`
- 结论：
  - 当前首张卡片之所以呈现“上下形式”，本质上是因为该卡片同时存在两个状态徽章：`暂停中` + `待确认`
  - 你现在已经明确接受这种上下形式，并希望所有任务统一采用这个展示方式
  - 当前链接显示则只有“单行省略”这一种状态，没有“展开完整链接”的交互能力

### 2. Edge 主窗口问题的当前实现

- 文件：`backend/collectors/remote_edge.py`
- 现状：
  - `_start_edge()` 通过：
    - `--remote-debugging-port`
    - `--new-window`
    - `edge://newtab/`
    - 独立 `--user-data-dir`
    启动 Edge 会话
  - `_show_edge()` 当前流程：
    - 先 `_start_edge()`
    - 如果调试端口可用，则调用 `show_edge_window(...)`
    - 如果失败，再调用 `_ensure_window_page()` 用 CDP 补页面后重试一次
- 文件：`backend/collectors/window_control.py`
- 现状：
  - `list_edge_windows()` 只收集：
    - 真正顶层窗口
    - 有标题
    - 宽高大于阈值
  - `find_edge_window()` 已经从“单 PID”放宽为“候选 PID 集合”，候选来源是：
    - `_last_pid`
    - 命令行里带相同 `--remote-debugging-port`
    - 命令行里带相同 `user_data_dir`
- 文件：`backend/main.py`
- 现状：
  - `/api/edge-sessions/{session_id}/show` 在 `window_found=False` 时直接抛 500，并返回 `未找到对应的 Edge 主窗口`
- 结论：
  - 当前问题已经不是“只按一个 PID 找窗”那么简单，因为候选 PID 扩大后仍可能找不到窗口
  - 根因更可能是：**该 Edge 会话此刻只有调试端口，没有本地可显示顶层窗口**

### 3. 当前根因的深度判断

- 从代码行为看，存在以下高概率场景：
  - 场景 A：Edge 进程和调试端口已存在，但主窗口没有创建成功或已被关闭
  - 场景 B：Edge 会话进入 Chromium/Edge 的 `no startup window` 运行状态，进程活着、CDP 可连，但本地没有顶层窗口
  - 场景 C：CDP 的 `new_page()` 只是在已有浏览器上下文内补标签页，不一定能在 Windows 桌面层补出一个新的原生顶层窗口
- 当前 `_ensure_window_page()` 的问题：
  - 它依赖 Playwright/CDP 创建或恢复页面
  - 但“页面存在”不等于“Windows 层存在可见主窗口”
- 因此当前失败的真正症结是：
  - **项目把“CDP 可用”误当成“本地可显示主窗口可用”**
  - 但这两个状态在 Edge 多会话运行中并不等价

## Proposed Changes

### 1. 统一所有任务卡片的状态徽章为上下形式

- 文件：`frontend/styles.css`
- 计划：
  - 不再尝试把状态徽章压回一行
  - 直接将 `.task-badges` 规范为纵向排列：
    - `flex-direction: column`
    - `align-items: flex-end`
    - `flex-wrap: nowrap`
  - 同时将 `.task-head` 调整为更适合“左侧信息 + 右侧纵向状态”的顶部对齐布局
  - 保持按钮、卡片、平台头部的原有视觉层次不变
- 为什么：
  - 用户最新意图已经改变：不再要求“左右呈现”，而是要求“全部任务统一上下形式”
  - 与其让首张卡片例外，不如将这种状态展示明确制度化，保持整体一致性

### 2. 为链接增加“双击展开/收起完整内容”的交互

- 文件：`frontend/app.js`
- 计划：
  - 给当前显示登录/页面链接的元素增加明确标识，例如：
    - `task-meta line-clamp task-identity`
    - 附带 `title` 或 `data-full-text`
  - 在任务管理区域增加双击事件委托：
    - 双击链接行时切换展开/收起状态
    - 再次双击恢复省略显示
- 文件：`frontend/styles.css`
- 计划：
  - 保留默认 `.line-clamp` 单行省略
  - 新增展开态样式，例如：
    - 允许换行
    - 取消省略号
    - 支持长链接断行显示
  - 给可双击展开的链接一个轻量提示性光标或 hover 状态，但不做高调视觉改造
- 为什么：
  - 用户希望平时保持紧凑，不要让长链接撑开卡片
  - 但需要在需要时快速查看完整链接内容
  - 双击展开/收起是最轻量、最不破坏现有界面的实现方式

### 3. 为 Edge 主窗口问题建立“诊断状态”，先把失败原因说清楚

- 文件：`backend/collectors/window_control.py`
- 文件：`backend/collectors/remote_edge.py`
- 计划：
  - 增加会话级窗口诊断信息，至少包含：
    - 当前匹配到的候选 Edge 进程 PID 列表
    - 当前枚举到的候选顶层窗口标题/句柄
    - 是否检测到“调试端口可用但无顶层窗口”
    - 是否检测到进程命令行带 `--no-startup-window`
  - 让 `_show_edge()` 失败时保留这些上下文，供接口层和前端展示
- 为什么：
  - 现在用户只能看到统一的 `未找到对应的 Edge 主窗口`
  - 这不利于判断到底是“窗口被关了”“会话在后台无窗运行”“还是匹配逻辑仍有遗漏”

### 4. 将“补页面”升级为“补原生窗口”

- 文件：`backend/collectors/remote_edge.py`
- 计划：
  - 新增一个专门的“补可见窗口”步骤，不再只依赖 `_ensure_window_page()`
  - 具体策略按顺序执行：
    1. 先尝试显示已存在顶层窗口
    2. 若失败且调试端口已开，记录诊断状态
    3. 尝试通过系统方式为该 profile 会话补一个原生新窗口
       - 对独立店铺模式：调用 `msedge.exe --user-data-dir=<当前会话目录> --new-window edge://newtab/`
       - 对真实个人环境：调用 `msedge.exe --profile-directory=<Profile> --new-window edge://newtab/`
       - 这里不再追加新的调试端口参数，因为现有浏览器进程已经接管该 profile
    4. 等待窗口创建后再次 `show_edge_window(...)`
    5. 若仍失败，再进入受控重启兜底
- 为什么：
  - 当前 `_ensure_window_page()` 只能补“浏览器页”，不能保证补出“Windows 桌面主窗口”
  - 原生窗口问题必须通过原生窗口创建路径解决

### 5. 增加“受控重启兜底”，处理 `--no-startup-window` 等无窗运行状态

- 文件：`backend/collectors/remote_edge.py`
- 文件：`backend/collectors/window_control.py`
- 计划：
  - 在以下条件同时满足时，允许自动执行一次“会话级受控重启”：
    - 调试端口可用
    - 当前 session 对应进程存在
    - 仍找不到任何可显示顶层窗口
    - 已尝试过“补原生窗口”但失败
  - 重启方式：
    - 只关闭当前 session 对应的 Edge 进程树
    - 保留 `user_data_dir` 不变
    - 再用当前 `_start_edge()` 方式重启
    - 重启后重试 `show_edge_window(...)`
  - 需要限制为一次兜底，避免无限循环
- 为什么：
  - 对这类会话来说，profile 数据比进程本身更重要
  - 受控重启不会丢登录态，但可以把“只有端口、没有窗口”的异常状态拉回正常窗口态

### 6. 调整接口和前端错误展示，使错误更可解释

- 文件：`backend/main.py`
- 文件：`frontend/core.js`
- 文件：`frontend/app.js`
- 计划：
  - 后端在 `window_found=False` 时返回结构化 detail，例如：
    - `error`
    - `reason_code`
    - `debug_available`
    - `candidate_pids`
    - `window_titles`
    - `has_no_startup_window`
    - `recovery_attempted`
  - 前端仍保持简洁提示，但对几个关键场景输出更明确文案：
    - `会话正在后台无窗运行，系统已尝试补窗口`
    - `当前会话无本地主窗口，建议重建该会话窗口`
    - `当前会话重建窗口失败，请执行关闭后重启`
- 为什么：
  - 这次问题暴露出：后端只给统一报错，前端也只能统一弹窗
  - 如果不补可解释性，后续仍会反复遇到“同一句报错但根因不同”

## Assumptions & Decisions

- 已确认的产品约束：
  - 不再大改任务管理整体 UI
  - 所有任务卡片统一采用“上下形式”的状态徽章展示
  - 链接默认省略，双击时再展开完整内容
- 本次技术判断：
  - 当前任务卡片的状态差异不是数据异常，而是局部布局规则与状态数量叠加后的结果
  - 链接完整显示需求适合做前端局部交互，不需要改后端数据结构
  - 当前 Edge 报错的深层根因是“调试端口存在”和“本地主窗口存在”被错误等同
- 本次实现决策：
  - UI 修复改为“统一纵向状态徽章 + 双击展开链接”
  - Edge 修复采用“三层恢复策略”：
    - 找已有窗口
    - 补原生窗口
    - 受控重启兜底
  - 不采用继续单纯扩大 PID/等待时间的方案，因为那只能缓解，不足以解决“无窗运行”

## Verification steps

### 1. UI 验证

- 打开 `任务管理`
- 找到同时带 `暂停中` 与 `待确认` 状态的任务卡片
- 验证：
  - 所有任务卡片的状态徽章统一采用上下排列
  - 首张任务卡片与其他同类卡片展示规则一致
  - 平台头部按钮排布保持原有整体风格
  - 链接默认仍以 `...` 截断显示
  - 双击链接后能展开完整内容
  - 再次双击后恢复省略显示

### 2. Edge 会话恢复验证

- 场景 A：会话未启动
  - 点击 `启动Edge`
  - 验证能正常打开本地 Edge 主窗口
- 场景 B：会话已隐藏到屏幕外
  - 点击 `显示Edge`
  - 验证能恢复并前置现有窗口
- 场景 C：调试端口存在，但当前没有本地主窗口
  - 点击 `显示Edge / 启动Edge`
  - 验证系统先尝试补原生窗口，再恢复显示
- 场景 D：会话进入无窗异常态
  - 验证受控重启只针对当前会话，不影响其他店铺会话
  - 验证重启后仍保留原登录态与 profile 数据

### 3. 回归验证

- `隐藏Edge` 仍能把当前会话移动到屏幕外
- `关闭Edge` 仍只关闭当前 session 对应进程树
- `采集配置` 页面通过 `显示Edge` / `启动Edge` 的工作流不被破坏
- 前端错误提示从统一失败文案变为可解释的场景化提示
