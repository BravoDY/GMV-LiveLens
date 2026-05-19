# QA_任务管理与采集配置递归测试报告

## 1. 测试结论

最终状态：`CONDITIONAL_PASS`。

本轮已完成计划文件要求的阶段报告读取、前置检查、按钮/API 映射穷举、受控 API/功能测试、多轮测试、异常边界测试、回归验证、副作用检查和报告产出。未发现新的 P0 阻塞问题；发现 1 个 P1 安全缺口并已做最小修复复测，另发现 3 个 P2 前端交互/反馈类问题，建议后续 BUILD 收敛。

通过条件：不把真实平台登录态、真实大屏采集成功作为通过标准。本轮真实 Edge 控制接口在受控环境中实际执行过平台级和任务级启动/显示/隐藏/关闭，并在测试后关闭或恢复服务；大屏读取在无目标真实大屏/CDP 断开时返回明确受控错误，服务未崩溃。

## 2. 测试边界与环境

- 目标仓库：`C:/Users/yjd22/Desktop/python项目/GMV-LiveLens`。
- 已读取背景报告：
  - `.trae/documents/SHIP_最终交付与发布说明.md`
  - `.trae/documents/VERIFY_测试验证与Debug报告.md`
  - `.trae/documents/BUILD_修复执行与代码变更报告.md`
- 测试前检查：
  - `git status --short`：存在既有 BUILD/VERIFY/REVIEW/SHIP、后端、前端、测试、`data/shops_default.json` 等改动。
  - 端口 `8100`：测试前已有本项目 uvicorn 监听，PID `39128`，命令为 `.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8100`。
  - 现有服务状态：`/api/config/public` 显示 `require_api_token=false`，`/api/health` 显示 scheduler 正在运行。
  - Python：系统 `Python 3.13.9`；虚拟环境 `Python 3.14.3`。
  - 依赖文件：`requirements.txt`、`pyproject.toml`、`package.json` 均存在。
- 受控服务设置：
  - 暂停并停止原有服务后，使用 `GMV_SCHEDULER_AUTOSTART=false`、`GMV_REQUIRE_API_TOKEN=true`、`GMV_API_TOKEN=qa-local-token`、`MYSQL_HOST=127.0.0.1`、`MYSQL_PORT=1` 启动临时 uvicorn。
  - 测试结束后已停止临时服务，并按测试前入口恢复原 uvicorn 服务；恢复后 `/api/config/public` 为 `require_api_token=false`，`/api/health` 显示 scheduler 已恢复运行。
- 禁止事项遵守情况：
  - 未删除任务。
  - 未清空配置。
  - 未修改 `data/shops.csv`。
  - 未伪造真实大屏采集结果。

## 3. 按钮与功能映射矩阵

| 区域 | 按钮/控件 | 前端绑定 | 后端 API | 测试方式 | 结果 | 风险 |
|---|---|---|---|---|---|---|
| 顶部导航 | 实时看板 / 采集配置 / 任务管理 | `bindInternalDashboardNav()` / `switchView()` | 无直接 API | 静态绑定 + 页面 200 | 通过 | 无 |
| 顶部操作 | 采集全部 | `captureAllTasks()` | `POST /api/tasks/{id}/capture-once` | 静态 + 单任务 API 验证 | 条件通过 | P2：单任务失败时仍可能显示“均已发送” |
| 顶部操作 | OCR 引擎下拉 | 未发现 `globalOcrEngine` 事件绑定 | 预期应关联 `/api/settings` | 静态搜索 | 未绑定 | P2：选择无效 |
| 顶部操作 | 正式采集频率 | `currentGlobalIntervalSeconds()` / `saveTask()` | `POST /api/tasks` | 静态 + 保存同 payload | 通过 | 无 |
| 顶部操作 | 启动采集 | `toggleScheduler()` | `GET /api/scheduler`、`POST /api/scheduler/start|pause` | 2 轮 start/pause | 通过 | 无 |
| 顶部操作 | 调试 | `setupDebugPanel()` | `/api/config/public`、`/api/health` | 静态 + API | 通过 | 无 |
| 顶部操作 | 刷新数据 | `bindSharedRefreshButton()` | `POST /api/dashboard-cache/refresh` | 无 Token 401 + Token 2 轮 | 通过 | MySQL 不可用时返回业务 `status=failed`，HTTP 仍 200 |
| 顶部操作 | 全屏看板 | `fullscreenToggle` 隐藏，未绑定 | 无 | 静态 | 不作为可见按钮 | 无 |
| 调试面板 | 保存 Token | `setApiToken()` | 浏览器本地存储 | 静态 | 通过 | 需真实浏览器确认 localStorage |
| 调试面板 | 清空 Token | `setApiToken("")` | 浏览器本地存储 | 静态 | 通过 | 需真实浏览器确认 |
| 调试面板 | 刷新状态 | `refreshDebugPanelStatus()` | `/api/config/public`、`/api/health` | 静态 + API | 通过 | 无 |
| 任务管理 | 状态筛选 全部/正常/告警/暂停 | `bindManagerFilters()` | 无直接 API | 静态 + 渲染逻辑 | 通过 | 无 |
| 任务管理 | 任务卡片跳转配置 | `bindManagerCardClicks()` | 依赖已有任务快照 | 静态 + `/api/tasks` | 通过 | 需真实浏览器点击确认 |
| 任务管理 | 平台启动 Edge | `callPlatformEdgeAction(platform, "launch")` | `POST /api/platforms/{platform}/launch-edge` | 真实受控调用 | 通过 | 失败只 `console.error`，见 P2 |
| 任务管理 | 平台显示 | `callPlatformEdgeAction(platform, "show")` | `POST /api/platforms/{platform}/show-edge` | 真实受控调用 | 通过 | 失败只 `console.error`，见 P2 |
| 任务管理 | 平台隐藏 | `callPlatformEdgeAction(platform, "hide")` | `POST /api/platforms/{platform}/hide-edge` | 真实受控调用 | 通过 | 失败只 `console.error`，见 P2 |
| 任务管理 | 平台关闭 | `callPlatformEdgeAction(platform, "close")` | `POST /api/platforms/{platform}/close-edge` | 真实受控调用 | 通过 | 失败只 `console.error`，见 P2 |
| 任务管理 | 任务启动 Edge | `startAndShowEdgeSession()` | `POST /api/edge-sessions/{session_id}/show` | 真实受控调用 | 通过 | 无 |
| 任务管理 | 任务显示 | `showEdgeSession()` | `POST /api/edge-sessions/{session_id}/show` | 真实受控调用 | 通过 | 无 |
| 任务管理 | 任务隐藏 | `hideEdgeSession()` | `POST /api/edge-sessions/{session_id}/hide` | 真实受控调用 | 通过 | 无 |
| 任务管理 | 任务关闭 | `closeEdgeSession()` | `POST /api/edge-sessions/{session_id}/close` | 真实受控调用 | 通过 | 无 |
| 采集配置 | 进入下一家 | `focusNextPendingTask()` | 依赖 `/api/tasks`、`/api/shops` | 静态 + API | 通过 | 需真实浏览器确认焦点 |
| 采集配置 | 重新扫描 | `scanBind()` | `GET /api/tasks/{id}/page-candidates` | 无 Edge/CDP 错误路径 | 通过 | 无 |
| 采集配置 | 会话下拉 | `bindSessionSelect change` | `/api/edge-sessions` | 静态 + API | 通过 | 无 |
| 采集配置 | 扫描当前会话页签 | `scanBind()` | `/api/tasks/{id}/page-candidates` | 409 受控错误 | 通过 | 无 |
| 采集配置 | 已登录，打开业务页并自动继续 | `resumeAfterLogin()` | `POST /api/tasks/{id}/resume-after-login` | 静态映射 | 条件通过 | 需真实登录态确认 |
| 采集配置 | 使用此页面 | `confirmBind()` | `POST /api/tasks/{id}/rebind-page` | 无 Token 401 覆盖同类 `/api/tasks` 前缀 | 条件通过 | 避免实际改绑，未用 Token 调真实改绑 |
| 采集配置 | 当前采集方式 | `valueSourceSelect change` | `POST /api/tasks` 保存时生效 | 静态 + 保存同 payload | 通过 | 无 |
| 采集配置 | 清空当前标定并重来 | `resetCurrentSetup()` | `POST /api/tasks/{id}/reset-calibration` | 静态映射 | 未执行 | 用户禁止清空配置，本轮不触发 |
| 采集配置 | 生成预览 | `previewRemotePage()` | `POST /api/edge-sessions/{session_id}/pages/{page_id}/preview` | 无效 page + CDP 断开 | 通过 | 无 |
| 采集配置 | 测试识别 | `testOcr()` | `POST /api/test-ocr` | 无 Token / Token 复测 | 已修复后通过 | P1 已修复 |
| 采集配置 | 保存并进入下一家 | `saveTask()` | `POST /api/tasks` | 同 task payload 保存 | 通过 | 有运行态写入，见副作用记录 |
| 大屏只读 | 开启只读 | `startScreenReadonly()` | `GET /api/edge-sessions/{session_id}/pages/{page_id}/screen-readonly` | 无效 page/CDP 断开 | 通过 | 需真实大屏确认成功路径 |
| 大屏只读 | 刷新只读结果 | `refreshScreenReadonly()` | 同上 | 无效 page/CDP 断开 | 通过 | 需真实大屏确认成功路径 |
| 大屏只读 | 清空测试记录 | `clearScreenReadonly()` | 前端内存清空 | 静态 | 通过 | 不触发后端 |
| 公共看板 | 数据集导航按钮 | `createPublicDatasetButton()` | `GET /api/dashboard?dataset_id=...` | 2 轮读接口 | 通过 | 需真实浏览器确认切换 UI |

## 4. 任务管理递归测试结果

- `/api/tasks`：2 轮读接口均 HTTP 200，返回 9 个启用任务。
- 任务卡片跳转：静态确认 `bindManagerCardClicks()` 会调用 `loadTaskIntoConfig(task)` 并切换到 `config`。
- 平台级 Edge：
  - `POST /api/platforms/天猫/launch-edge`：HTTP 200，4 个天猫任务均受控启动/显示成功。
  - `POST /api/platforms/天猫/show-edge`：HTTP 200，4 个任务显示成功。
  - `POST /api/platforms/天猫/hide-edge`：HTTP 200，4 个任务隐藏成功。
  - `POST /api/platforms/天猫/close-edge`：HTTP 200，4 个任务关闭成功。
- 任务级 Edge：
  - `POST /api/edge-sessions/天猫_天猫官旗店/start`：HTTP 200，调试端口连接成功并打开目标页。
  - `POST /api/edge-sessions/天猫_天猫官旗店/show`：HTTP 200，窗口找到并最大化。
  - `POST /api/edge-sessions/天猫_天猫官旗店/hide`：HTTP 200，窗口移动到屏外隐藏。
  - `POST /api/edge-sessions/天猫_天猫官旗店/close`：HTTP 200，`close:closed`，未使用 force kill。
- 无 Token 写接口：
  - `/api/scheduler/start`、`/api/dashboard-cache/refresh`、`/api/tasks`、`/api/platforms/{platform}/show-edge`、`/api/edge-sessions/{session_id}/show` 均返回 401。
- 发现问题：
  - 平台级 Edge 按钮失败只写 `console.error`，没有 `showMessage()` 或明显 UI 反馈，见 P2-1。

## 5. 采集配置链路测试结果

- `/api/shops`：HTTP 200，返回 9 家店铺。
- `/api/shops/match?session_id=天猫_天猫官旗店`：在会话关闭后返回 HTTP 409，错误信息明确为 Edge 调试端口未连接，服务未崩溃。
- `/api/edge-sessions`：HTTP 200，返回会话列表，包含 `default_real_edge`。
- `/api/edge-sessions/{session_id}/pages`：会话关闭后 HTTP 200，返回空数组。
- `/api/tasks/{id}/page-candidates?session_id=...`：会话关闭后 HTTP 409，错误码 `EDGE_DEBUG_UNAVAILABLE`，包含 recovery hint。
- `/api/edge-sessions/{session_id}/pages/qa-invalid-page/preview`：HTTP 409，错误码 `EDGE_DEBUG_UNAVAILABLE`，未 500。
- `/api/test-ocr`：
  - 修复前：强制 Token 环境下无 Token 返回 HTTP 200。
  - 修复后：无 Token 返回 401；带 Token 但缺参数返回 422，证明已通过 Token 中间件后进入参数校验。
- `/api/tasks` 保存：使用任务 62 原始 payload 做同值保存，HTTP 200。
- 未执行真实 `rebind-page` 成功写入：避免改变真实任务绑定。
- 未执行 `reset-calibration`：用户明确禁止清空配置，本轮只做静态映射。

## 6. 大屏只读与正式采集链路测试结果

- `/api/tasks/{id}/screen-readonly`：任务 62 在 Edge 调试端口关闭状态返回 HTTP 409，错误码 `EDGE_DEBUG_UNAVAILABLE`，未 500。
- `/api/edge-sessions/{session_id}/pages/qa-invalid-page/screen-readonly`：HTTP 409，错误码 `EDGE_DEBUG_UNAVAILABLE`。
- `/api/tasks/{id}/capture-once`：HTTP 200，业务结果 `status=edge_debug_unavailable`，不把真实大屏成功作为通过标准；接口没有崩溃，错误原因清晰。
- `/api/tasks/999999/capture-once`：HTTP 200，业务结果 `status=task_not_found`。建议后续可评估是否应改为 HTTP 404，但本轮不判 P0/P1。
- `/api/scheduler/start|pause`：强制 Token 环境下 2 轮重复调用均 HTTP 200，最终已 pause；恢复原服务后 scheduler 回到运行态。
- `/api/dashboard-cache/refresh`：强制 Token 环境下 2 轮 HTTP 200；由于 MySQL 指向不可用端口，业务数据返回 `status=failed` 并保留旧缓存，服务不崩溃。
- `/api/dashboard`、`/api/dashboard-datasets`、`/api/realtime`、`/ws/live`：2 轮读接口和 WebSocket 均通过。

## 7. 异常与边界测试结果

| 场景 | 结果 | 结论 |
|---|---|---|
| 无 Token 调敏感写接口 | `/api/scheduler/start`、`/api/dashboard-cache/refresh`、`/api/tasks`、平台/任务 Edge 写接口均 401 | 通过 |
| 无 Token 调 `/api/test-ocr` | 修复前 200，修复后 401 | P1 已修复 |
| 无 Token 调 `/api/window-preview` | 修复前 404，修复后 401 | P1 已修复 |
| 无效任务 ID page-candidates | HTTP 404 `TASK_NOT_FOUND` | 通过 |
| 无效任务 ID screen-readonly | HTTP 404 `TASK_NOT_FOUND` | 通过 |
| 无效 history limit | HTTP 422 `VALIDATION_ERROR` | 通过 |
| 无效 session pages | HTTP 404 `EDGE_SESSION_NOT_FOUND` | 通过 |
| Edge 调试端口不在线 | page-candidates、preview、screen-readonly 返回 409 或业务状态，不崩溃 | 通过 |
| MySQL 不可用 | dashboard HTTP 200；缓存刷新 HTTP 200 但业务 `status=failed` | 条件通过 |
| 重复 start/pause | 2 轮稳定 | 通过 |
| 重复缓存刷新 | 2 轮稳定 | 通过 |

## 8. 多轮/回归测试结果

- 受控 API 矩阵：
  - 主矩阵：69 项，读接口 2 轮、WebSocket 2 轮、Token 错误、调度器、缓存、任务保存、采集、异常 ID、Edge 平台控制均覆盖。
  - 补充矩阵：14 项，修正 HTML 页面解析和 URL 编码后，页面 3/3 HTTP 200，任务级 Edge 4/4 HTTP 200，关闭后健康/页面/预览/只读错误路径稳定。
- 自动化回归：
  - `python -m pytest tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py`：修复前后均通过；最终为 `24 passed, 5 warnings`。
  - `.venv\Scripts\ruff.exe check backend/core/security.py backend/main.py backend/routers/system.py backend/version.py backend/tools/full_test.py backend/collectors/edge/_session.py scripts/ci_check.py tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py`：`All checks passed!`。
  - `python scripts/ci_check.py --with-api`：
    - 第一次在受控服务仍占用 8100 时失败，原因是 CI 内部 uvicorn 无法绑定端口，随后 smoke 打到强制 Token 服务，T14 `/api/settings` 写入被 401 拦截。
    - 清理端口并移除 Token 环境变量后重跑通过，包含 Ruff、pytest、full_test `55/55 PASS`、`smoke_edge ok`、API smoke `14/14 PASS`。
- IDE lint：
  - `backend/core/security.py` 无 linter errors。

## 9. 发现的 P0/P1/P2 问题

### P0

无。

### P1

1. 已修复：`/api/test-ocr` 与 `/api/window-preview` 未纳入强制 Token 写保护。
   - 影响：公网/生产误放行时，攻击者可在无 Token 情况下触发 OCR 计算或窗口预览探测，存在资源消耗和本机信息探测风险。
   - 证据：修复前强制 `GMV_REQUIRE_API_TOKEN=true` 时，`POST /api/test-ocr` 无 Token 返回 HTTP 200；`POST /api/window-preview` 无 Token 进入业务校验并返回 404，而不是 401。
   - 修复：在 `backend/core/security.py` 的 `SENSITIVE_WRITE_PATH_PREFIXES` 增加 `/api/window-preview`、`/api/test-ocr`。
   - 复测：无 Token 均返回 401；带 Token 进入后续 422/404 业务校验。

### P2

1. 平台级 Edge 操作失败缺少用户可见提示。
   - 位置：`frontend/dashboard.js` 的 `bindManagerActionButtons()`。
   - 现象：catch 中仅 `console.error`，未调用 `showMessage()`，用户点击平台启动/显示/隐藏/关闭失败时可能只看到按钮复原，不知道失败原因。

2. “采集全部”可能给出误导性成功提示。
   - 位置：`frontend/core.js` 的 `captureAllTasks()`。
   - 现象：每个任务的 `capture-once` 只要 HTTP 200 就被视为已发送，即使业务结果是 `edge_debug_unavailable` / `task_not_found` 也会显示“所有启用任务均已发送采集指令”。

3. 顶部 `OCR引擎` 下拉未发现事件绑定。
   - 位置：`frontend/index.html` 的 `globalOcrEngine`。
   - 现象：静态搜索未找到 `globalOcrEngine` 的事件监听或与 `/api/settings` 的联动；用户更改下拉可能不会影响正式 OCR 引擎。

## 10. 测试副作用与回滚记录

| 操作 | 影响 | 回滚/处理 |
|---|---|---|
| 暂停并停止测试前已有 uvicorn PID `39128` | 原本 scheduler 运行的本地服务被临时停止 | 测试结束后按原入口恢复 uvicorn；恢复后 `/api/health` 显示 scheduler running=true |
| 启动受控临时 uvicorn | 端口 8100 临时由 Token 强制服务占用 | 测试后停止临时服务 |
| 平台级 Edge launch/show/hide/close | 实际启动/显示/隐藏/关闭 4 个天猫 Edge 会话 | 已执行平台 close；任务级会话也执行 close |
| 任务级 Edge start/show/hide/close | 实际启动并关闭 `天猫_天猫官旗店` 会话 | 已 close，健康检查显示 debug disconnected |
| `POST /api/tasks` 同值保存任务 62 | 可能刷新 SQLite 中任务记录 | 使用原始任务 payload 同值保存，未新增/删除任务；未回滚用户运行态数据库 |
| `POST /api/tasks/62/capture-once` | 写入任务运行态失败状态的可能性 | 这是受控写接口测试副作用，报告记录；未伪造成功结果 |
| `POST /api/dashboard-cache/refresh` | MySQL 不可用下返回旧缓存/失败状态 | 无文件副作用需撤回 |
| 临时测试脚本 | 新增 `scripts/qa_task_config_api_smoke_tmp.py`、`scripts/qa_task_config_api_supplement_tmp.py` | 已删除 |
| OCR 测试文件 | 检查 `data/ocr_datasets/*.png` | 未发现遗留 PNG |
| `data/shops_default.json` | 测试前已存在本机路径差异 | 非本轮新增，未回退用户/历史改动 |
| 端口 8100 | 最终恢复为本项目 uvicorn 监听 | `/api/config/public` 为开发模式不强制 Token，匹配测试前状态 |

最终 `git status --short` 新增/修改中与本轮直接相关的是：

- `backend/core/security.py`：P1 Token 保护修复。
- `.trae/documents/QA_任务管理与采集配置递归测试报告.md`：本报告。

其他已有改动为本轮测试前存在或前序阶段产物，未回退。

## 11. 后续建议

- 优先处理 3 个 P2 前端体验问题：平台级 Edge 错误提示、采集全部结果汇总、OCR 引擎下拉绑定。
- 为 `/api/test-ocr`、`/api/window-preview` 增加自动化回归，防止未来从 Token 前缀中遗漏。
- 若要把当前状态从 `CONDITIONAL_PASS` 推到无条件 PASS，需要人工完成真实浏览器 Console/Network、真实 Edge 登录态、真实平台大屏只读成功路径、公网 Nginx allowlist 验证。
- 建议后续将 `scripts/ci_check.py --with-api` 的 API smoke 支持 Token 环境，避免强制 Token 场景下只能靠额外脚本验证写接口。
