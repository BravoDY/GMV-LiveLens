# 全项目系统审查与修复路线图

生成时间：2026-05-06

## 0. 当前结论

GMV-LiveLens 的基础服务可以运行：FastAPI 后端、静态前端、核心 GET API、WebSocket 均已验证可访问。

但项目尚不能判定为“业务采集稳定可交付”。当前风险集中在真实 Edge 会话、任务运行态、OCR 真实截图链路、启动期数据写入行为、以及缺少 Git 仓库导致的回滚/审计能力不足。

本路线图以后续真实代码和命令结果为准，不以 README 或历史审计文档为依据。

## 1. 已确认项目画像

### 技术栈

- 后端：Python、FastAPI、Pydantic v2、SQLite、Uvicorn
- 前端：原生 HTML/CSS/JavaScript，无 npm 构建链
- 采集：Playwright CDP 控制 Edge、pywin32 窗口枚举、mss/Pillow/OpenCV 截图处理
- OCR：rapidocr、ddddocr、onnxruntime
- 数据：`data/gmv_livelens.sqlite3`、`data/shops.csv`、`data/shops_default.json`

### 包管理器

- 主包管理器：`pip`
- 依赖文件：`requirements.txt`
- 未发现：`package.json`、`pyproject.toml`、`poetry.lock`、`pom.xml`、`build.gradle`、`go.mod`

### 入口

- 后端入口：`backend/main.py`
- 启动脚本：`第1步_启动GMV服务.bat`
- 静态前端入口：`frontend/index.html`
- 主要验证脚本：
  - `backend/tools/full_test.py`
  - `backend/tools/smoke_api.py`
  - `backend/tools/smoke_edge_buttons.py`
  - `backend/tools/start_shop_edges.py`

## 2. 已执行验证结果

### 依赖与语法

- `.venv\Scripts\python.exe --version`
  - 结果：Python 3.14.3
- `.venv\Scripts\python.exe -m pip check`
  - 结果：`No broken requirements found.`
- 后端 AST 解析 `backend/**/*.py`
  - 结果：全部通过
- `node --check frontend\core.js`
- `node --check frontend\dashboard.js`
- `node --check frontend\edge.js`
- `node --check frontend\config.js`
- `node --check frontend\app.js`
  - 结果：全部通过
- `import backend.main`
  - 结果：导入成功，FastAPI routes = 61

### 真实服务

当前 `127.0.0.1:8100` 已有 Uvicorn 服务运行，PID 为 `44100`。

已验证通过：

- `GET /api/health`：200
- `GET /api/scheduler`：200
- `GET /api/settings`：200
- `GET /api/tasks`：200
- `GET /api/realtime`：200
- `GET /api/shops`：200
- `GET /api/ocr/engines`：200
- `GET /api/windows`：200
- `GET /`：200
- `GET /static/core.js`：200
- `GET /static/app.js`：200
- `GET /favicon.ico`：200
- `WS /ws/live`：101，成功收到 snapshot

关键运行态：

- `/api/tasks` 显示 `tasks=5`
- `summary.active_tasks=5`
- `summary.ok_tasks=0`
- `summary.alert_tasks=5`

Edge 结果：

- `default_real_edge`：
  - `debug_available=False`
  - `connected=False`
  - `reason=edge_debug_unavailable`
- `天猫_官方旗舰店`：
  - `debug_available=True`
  - `connected=True`
  - `window_found=True`

## 3. 已修复项

### FIX-001：验证脚本与当前模型签名不一致

- 优先级：P1
- 文件：`backend/tools/full_test.py`
- 问题：
  - `CaptureTask` fixture 缺少必填字段 `value_source`
  - `CaptureScheduler._judge()` 当前返回 7 个值，但测试仍按旧的 5 个值解包
- 修复：
  - 给测试 fixture 补充 `value_source="ocr"`
  - 更新 B4 测试解包为 7 返回值
  - 对齐当前同日 GMV 下降规则：忽略下降值，不更新可信值
- 验证：
  - `.venv\Scripts\python.exe backend\tools\full_test.py --skip-api`
  - 结果：`47/47 PASS`

### FIX-002：OCR 合成图测试假失败

- 优先级：P2
- 文件：`backend/tools/full_test.py`
- 问题：
  - 原测试使用 PIL 默认小字号 bitmap 字体，OCR 返回空文本，造成测试假失败
- 修复：
  - 改为 Windows TrueType 字体
  - 使用大字号、高对比、清晰文本 `RMB 474487`
  - 输出 OCR engine source 细节
- 验证：
  - D2 结果：`OCR文本='RMB474487'，候选=[474487]`

### FIX-003：启动/同步阶段重复任务处理风险已开始收敛

- 优先级：P1
- 文件：`backend/services/store.py`
- 当前状态：
  - 已把 `_dedupe_capture_tasks()` 改为支持 `delete_duplicates=False`
  - 已让同步阶段报告 `duplicate_tasks / duplicate_shops`
  - 已避免同步阶段默认静默删除重复任务和样本
- 注意：
  - 此项是在上一轮中断前开始修改的，当前已通过后端 AST 和 `full_test.py --skip-api`
  - 仍需专门补一个“重复任务不会被启动同步删除”的回归测试

## 4. 未修高风险项

### RISK-001：真实采集链路当前不健康

- 优先级：P0
- 涉及：
  - `backend/services/scheduler.py`
  - `backend/collectors/remote_edge.py`
  - `data/gmv_livelens.sqlite3`
- 证据：
  - `/api/tasks` 中 `active_tasks=5`
  - `ok_tasks=0`
  - `alert_tasks=5`
- 判断：
  - 项目基础服务可以运行，但业务采集不能判定稳定
- 下一步：
  - 先验证单店铺 `天猫_官方旗舰店`
  - 再扩展到其余店铺

### RISK-002：`default_real_edge` 不可用但仍暴露在健康检查中

- 优先级：P1
- 证据：
  - `GET /api/edge-sessions/default_real_edge/health`
  - `debug_available=False`
  - `reason=edge_debug_unavailable`
- 判断：
  - 默认 Edge 会话不可用不代表店铺专属会话不可用
  - 但它会干扰健康判断和用户预期
- 下一步：
  - 判断 `default_real_edge` 是否仍是必要运行模式
  - 若不是核心路径，应降低其告警权重或隐藏默认入口

### RISK-003：启动阶段仍会写业务 SQLite

- 优先级：P1
- 涉及：
  - `backend/main.py::startup`
  - `backend/services/store.py::init_db`
  - `backend/services/store.py::sync_tasks_with_shop_configs`
- 证据：
  - 服务启动会执行 `store.init_db()`
  - 服务启动会执行 `store.sync_tasks_with_shop_configs()`
- 当前缓解：
  - 重复任务默认删除风险已开始收敛
- 下一步：
  - 补启动期行为说明和测试
  - 明确哪些字段允许启动同步覆盖
  - 对业务库启动前备份形成脚本化流程

### RISK-004：无 Git 仓库，审计和回滚能力弱

- 优先级：P1
- 证据：
  - `git status --short` 返回 `fatal: not a git repository`
- 影响：
  - 无法可靠输出 git diff
  - 无法区分用户改动、自动生成文件和修复改动
  - 回滚只能靠手工备份
- 下一步：
  - 建议初始化 Git 或复制到受控仓库
  - 在此之前，每次动业务库和业务代码前必须备份

### RISK-005：测试脚本中仍存在会写业务状态的 API 段

- 优先级：P2
- 涉及：
  - `backend/tools/full_test.py`
  - `backend/tools/smoke_api.py`
- 证据：
  - API 段包含 `/api/settings POST`
  - API 段包含 `/api/shops/init`
  - API 段包含 `/api/scheduler/start` / `/api/scheduler/pause`
- 下一步：
  - 拆分只读 smoke 与写入 smoke
  - 写入类测试必须显式标注 destructive 或 live

### RISK-006：真实 Edge live 操作尚未验证

- 优先级：P2
- 涉及：
  - `backend/tools/smoke_edge_buttons.py --live`
- 未执行原因：
  - 会真实 start/show/hide/close Edge
- 下一步：
  - 先确认测试店铺
  - 再执行单店铺 live 验证
  - 不应直接批量跑平台级 live 操作

## 5. 下一轮验证命令

### 只读验证

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe -m pip check
```

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe -c "import backend.main as m; print(len(m.app.routes))"
```

```powershell
node --check frontend\core.js
node --check frontend\dashboard.js
node --check frontend\edge.js
node --check frontend\config.js
node --check frontend\app.js
```

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe backend\tools\full_test.py --skip-api
```

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe backend\tools\smoke_edge_buttons.py --base-url http://127.0.0.1:8100
```

### 真实服务只读 smoke

验证目标：

- `/api/health`
- `/api/tasks`
- `/api/realtime`
- `/api/shops`
- `/api/ocr/engines`
- `/api/windows`
- `/`
- `/static/core.js`
- `/static/app.js`
- `/ws/live`
- 店铺专属 Edge health

### 需确认后执行

以下命令会写入状态或控制真实 Edge，执行前必须确认：

```powershell
.venv\Scripts\python.exe backend\tools\full_test.py
```

风险：

- API 段会写 settings
- 会调用 `/api/shops/init`
- 会 start/pause scheduler

```powershell
.venv\Scripts\python.exe backend\tools\smoke_edge_buttons.py --base-url http://127.0.0.1:8100 --live --session-id "天猫_官方旗舰店"
```

风险：

- 会真实 start/show/hide/close Edge

```powershell
Invoke-WebRequest -Method POST http://127.0.0.1:8100/api/tasks/62/capture-once
```

风险：

- 会写采样结果和任务运行态

## 6. 修复顺序

### 第一优先级：建立可回滚和可审计基础

1. 初始化 Git 或复制到受控仓库
2. 备份业务库 `data/gmv_livelens.sqlite3`
3. 记录当前服务 PID、端口、任务状态

### 第二优先级：完成启动期数据安全修复

1. 给重复任务检测补测试
2. 验证启动同步不会删除重复任务
3. 明确 `sync_tasks_with_shop_configs()` 的字段覆盖边界

### 第三优先级：验证单店铺真实采集链路

1. 选择 `天猫_官方旗舰店`
2. 验证 Edge health
3. 验证 page id 是否仍有效
4. 执行单次 capture-once
5. 检查 task status、sample、screenshot

### 第四优先级：修复 `default_real_edge` 健康判断

1. 判断默认会话是否业务必需
2. 如果不是核心路径，调整健康展示逻辑
3. 如果仍必需，修复默认 Edge 启动/连接流程

### 第五优先级：拆分测试脚本风险等级

1. 只读 smoke：默认可运行
2. 写入 smoke：必须显式参数开启
3. Edge live smoke：必须指定 session id
4. 平台批量 live：最后执行

## 7. 当前交付判断

### 可以交付的部分

- 后端基础服务启动能力
- 静态前端加载能力
- 核心只读 API
- WebSocket snapshot 推送
- 纯函数和临时库验证脚本
- OCR 合成图基础识别验证

### 不能直接交付的部分

- 真实 GMV 持续采集
- 多店铺 Edge 稳定控制
- 默认 Edge 会话健康状态
- 启动期业务数据安全边界
- 完整回滚审计流程

## 8. 下一步建议

下一步应先处理 `RISK-001`：单店铺真实采集链路验证。

推荐目标任务：

- `task_id=62`
- `platform=天猫`
- `shop_name=官方旗舰店`
- `edge_session_id=天猫_官方旗舰店`

推荐先执行只读检查，再确认是否执行 `capture-once`。

