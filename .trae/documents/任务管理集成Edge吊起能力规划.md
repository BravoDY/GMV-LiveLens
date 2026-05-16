## Summary

- 目标：将当前依赖 `.bat` 手动启动的 Edge 吊起能力，整合进 `任务管理` 页面。
- 期望效果：
  - 在每个任务卡片上提供“单任务吊起 Edge”入口。
  - 在每个平台分组标题处提供“平台统一吊起 Edge”入口。
  - 平台标题字体略微放大，强化平台分组层级。
- 成功标准：
  - 不需要离开 `GMV-LiveLens` 页面即可启动对应店铺或平台的 Edge 调试会话。
  - 单任务吊起和平台批量吊起都能给出明确反馈。
  - 启动按钮位置与视觉层级清晰，不破坏现有任务管理布局。

## Current State Analysis

- 当前“平台级批量启动”能力只存在于外部脚本：
  - 文件：`backend/tools/start_shop_edges.py`
  - 作用：按 `--platform` 读取 `shops.csv`，逐个启动该平台下所有店铺的 Edge 会话。
- 当前“单会话启动”能力后端已经具备：
  - 文件：`backend/main.py`
  - 现有接口：`POST /api/edge-sessions/{session_id}/start`
  - 内部调用：`edge_client_for(session_id).start_edge`
- 任务与 Edge 会话已经通过 `edge_session_id` 建立了稳定关联：
  - 文件：`backend/services/store.py`
  - 说明：`capture_tasks` 中保存 `edge_session_id`，且已实现 `shops.csv` 与任务的同步。
- 任务管理页已经按平台分组渲染任务卡片：
  - 文件：`frontend/app.js`
  - 关键位置：`renderManager()` 中的 `manager-platform-head` 和每张 `manager-card`
- 当前任务卡片的操作区只有采集、编辑、启停、历史、重绑、删除，没有“吊起 Edge”按钮：
  - 文件：`frontend/app.js`
- 当前平台分组标题只有平台名称和任务数，没有平台级操作按钮：
  - 文件：`frontend/app.js`
- 当前平台标题字体较小：
  - 文件：`frontend/styles.css`
  - 关键位置：`.manager-platform-head h3 { font-size: 18px; }`

## Proposed Changes

### 1. 后端：补充“平台统一吊起 Edge”接口

- 文件：`backend/main.py`
- 新增接口建议：
  - `POST /api/platforms/{platform}/start-edge`
- 行为设计：
  - 根据 `platform` 从 `shop_config.load_shop_configs()` 中找出该平台下所有店铺配置。
  - 对每个配置使用其 `edge_session_id` 对应的 `RemoteEdge` client 执行 `start_edge()`。
  - 返回结果结构中包含：
    - `platform`
    - `requested`
    - `started`
    - `results: [{shop_name, edge_session_id, debug_port, ok, health/last_error}]`
- 为什么这样做：
  - 现有 `.bat` 脚本已经证明“按平台批量启动”是有效需求。
  - Web 页面不应依赖本地脚本入口，应该调用 API 直接完成同样动作。

### 2. 前端：在任务卡片上增加“单任务吊起 Edge”按钮

- 文件：`frontend/app.js`
- 在 `renderManager()` 的 `task-actions` 区域增加按钮：
  - 文案建议：`吊起Edge`
- 触发逻辑：
  - 从当前任务读取 `edge_session_id`
  - 调用现有接口：`POST /api/edge-sessions/{session_id}/start`
  - 成功后提示：
    - `已启动 {shop_name} 的 Edge 会话`
  - 失败后提示后端错误信息
- 约束：
  - 仅对 `remote_edge` 任务显示该按钮最合理；如果任务是 `window_capture`，可以隐藏按钮或禁用按钮
- 推荐决策：
  - 本次优先仅对 `remote_edge` 模式显示，避免窗口模式出现无意义操作

### 3. 前端：在平台分组标题处增加“平台统一吊起 Edge”入口

- 文件：`frontend/app.js`
- 在 `manager-platform-head` 中新增平台操作区：
  - 平台名左侧/右侧保留原有标题
  - 新增按钮文案：`吊起Edge`
- 触发逻辑：
  - 以当前平台名调用新增接口：`POST /api/platforms/{platform}/start-edge`
  - 成功提示：
    - `已为平台 {platform} 启动 N 个 Edge 会话`
  - 若部分失败，反馈失败数量或错误摘要
- 为什么放这里：
  - 符合你截图中红字标注的交互习惯
  - 平台级动作应放在平台分组头部，而不是混进单任务卡片

### 4. 前端：增强任务管理区域的视觉层级

- 文件：`frontend/styles.css`
- 调整内容：
  - 将 `.manager-platform-head h3` 字体由 `18px` 上调到更醒目的尺寸，例如 `20px` 或 `21px`
  - 为平台级“吊起Edge”入口增加明显但不抢主按钮的样式
  - 为单任务“吊起Edge”按钮提供区分色，建议使用偏红橙或高亮描边，贴近你截图中的视觉意图
- 布局注意点：
  - 平台头部需要支持：平台名 + 平台任务数 + 平台吊起按钮
  - 卡片按钮区域要在现有 `task-actions` 内保持换行可读，不挤压已有按钮

### 5. 前端：补充事件处理与消息反馈

- 文件：`frontend/app.js`
- 新增事件分支：
  - 任务按钮：`data-action="start-edge"`
  - 平台按钮：例如 `data-action="start-platform-edge"`
- 反馈方式：
  - 复用现有 `showMessage()` 或 `alert/parseApiError` 体系
  - 平台级成功提示要返回明确数量
  - 单任务失败时应直接显示后端返回的 `last_error` 或 `detail`

## Assumptions & Decisions

- “单个任务吊起”本质上是启动该任务绑定的 `edge_session_id` 对应 Edge 会话，而不是打开页面或自动绑定标签页。
- “平台统一吊起”本质上是对该平台下所有 `ShopConfig` 对应会话逐个执行 `start_edge()`，与现有 `.bat` 脚本行为保持一致。
- 本次只规划“启动 Edge 会话”，不包含：
  - 自动打开业务 URL
  - 自动登录
  - 自动绑定页面
  - 自动截取预览
- 单任务按钮仅针对 `remote_edge` 任务展示，避免和 `window_capture` 模式语义冲突。
- 平台名使用任务分组中的实际 `platform` 文本，不新增额外平台映射层。

## Verification Steps

- 后端接口验证：
  - 调用单任务接口 `POST /api/edge-sessions/{session_id}/start`，确认已有能力仍可正常返回健康状态
  - 调用平台接口 `POST /api/platforms/{platform}/start-edge`，确认返回批量结果
- 前端页面验证：
  - 打开 `任务管理`
  - 检查平台标题字号是否比当前略大，层级更明显
  - 检查每个平台标题是否出现“吊起Edge”入口
  - 检查每个 `remote_edge` 任务卡片是否出现“吊起Edge”按钮
- 功能验证：
  - 点击单任务“吊起Edge”，确认对应会话启动且页面有成功提示
  - 点击平台“吊起Edge”，确认该平台多个店铺会话被启动且页面返回数量反馈
  - 如果某个会话启动失败，前端应能看到明确错误，而不是静默失败
- 布局验证：
  - 按钮加入后任务卡片操作区仍然整齐
  - 平台头部在多平台场景下不拥挤，移动端/窄屏下也能换行显示
