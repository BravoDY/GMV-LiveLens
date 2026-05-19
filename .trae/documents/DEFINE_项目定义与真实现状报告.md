# DEFINE_项目定义与真实现状报告

本报告按当前仓库真实代码与文件状态编写，优先采信 `backend/`、`frontend/`、`data/`、`tests/`、`scripts/`、`.github/`、`deploy/` 中的现有实现。README、历史 Markdown、旧 DEFINE 只能作为背景参考，其中“无 Git”“前端 5 个 JS 模块”等结论已与当前仓库不一致，视为可能过时。

## 1. 项目一句话定位

GMV-LiveLens 是一个运行在 Windows 本机的全渠道 GMV 实时监控工具：后端用 FastAPI 控制 Microsoft Edge CDP 会话采集电商大屏数据，前端用 Vanilla JS 静态看板展示实时 GMV、目标达成和周期同比，并通过 FRP + Nginx 对公网提供只读看板。

## 2. 当前项目真实目标

- 统一监控 DESCENTE 相关店铺在天猫、京东、抖音、唯品、得物等平台的实时 GMV。
- 通过 `data/shops.csv` 定义店铺、平台、目标值、默认业务页、Edge 会话和采集策略；当前 CSV 中 9 个店铺 `enabled` 为 `TRUE`。
- 在本机服务启动时初始化 SQLite、同步店铺配置、启动采集调度器，并持续维护任务状态、采样记录和 Edge 会话状态。
- 对支持的平台优先使用 Playwright CDP 的“大屏只读”读取链路；不支持或失败时保留 OCR 识别与人工配置能力。
- 为内网/本机管理员提供采集配置、任务管理、Edge 启停与调试能力；为公网用户只开放只读看板、静态资源、只读数据接口和健康检查。
- 支持周期数据和同比展示：实时数据来自本机采集，周期/历史数据来自 CSV 与可选 MySQL 查询缓存 `data/.cache/period_gmv.json`。

## 3. 核心用户与使用场景

- **运营看板用户**：在大屏或浏览器访问 `/dashboard`，只查看 GMV 总览、平台分组、店铺明细、目标达成与同比，不参与采集配置。
- **本机管理员/运营同学**：在 Windows 机器访问 `/`，维护采集配置、绑定 Edge 页面、启动/显示/隐藏店铺 Edge、切换 OCR/只读采集方式、执行单次或批量采集。
- **开发/维护人员**：维护 FastAPI 路由、采集器、SQLite 数据结构、前端静态脚本、测试脚本、GitHub Actions、FRP/Nginx 部署配置。
- **公网访问者**：经腾讯云 Nginx + FRP 访问公网只读看板；按 `deploy/README-public-dashboard.md` 设计，不应触达管理接口、Edge 控制接口和写接口。

## 4. 技术栈识别结果

- **后端**：Python、FastAPI、Uvicorn；入口为 `backend/main.py`，FastAPI 应用版本为 `0.3.0`。
- **前端**：Vanilla JS 静态页面，无构建工具；`frontend/index.html` 当前加载 8 个主页面 JS 模块：`core.js`、`dashboard-shared.js`、`dashboard.js`、`dashboard-public.js`、`edge.js`、`config.js`、`debug.js`、`app.js`。
- **本地数据层**：SQLite 数据库 `data/gmv_livelens.sqlite3`，CSV 店铺配置 `data/shops.csv`，JSON 快照 `data/shops_default.json`、`data/shops_page_data.json`，周期缓存 `data/.cache/period_gmv.json`。
- **可选缓存/外部数据源**：MySQL，通过 `pymysql` 与 `MYSQL_*` 环境变量读取周期 GMV，失败时写入/使用本地缓存。
- **浏览器自动化**：Playwright CDP，目标浏览器为 Windows + Microsoft Edge，采集链路包括 Edge 会话管理、页面绑定、只读大屏读取和 OCR。
- **OCR/图像依赖**：`rapidocr`、`onnxruntime`、`ddddocr`、`opencv-python`、`Pillow`、`mss`、`pywin32`。
- **测试与质量**：pytest 依赖、自研 `tests/full_test.py`、`tests/smoke_edge.py`、`tests/smoke_api.py`、Ruff、GitHub Actions。
- **部署**：本机 Windows 运行 FastAPI；公网只读部署依赖 FRP + Nginx，公网入口由腾讯云转发到 Windows `127.0.0.1:8100`。
- **仓库状态**：当前目标目录是 Git 仓库，旧 DEFINE 中“无 Git”的判断已过时。

## 5. 项目目录与模块地图

- `backend/main.py`：应用入口，加载 `.env`，创建 FastAPI 实例，挂载静态目录，注册中间件、异常处理、路由、启动/关闭生命周期。
- `backend/routers/`：API 路由集合，包含系统页与健康检查、任务管理、店铺配置、Edge 会话、OCR、平台级操作、看板数据集和测试看板接口。
- `backend/core/`：配置、安全、响应、请求 ID、中间件和错误处理；`WriteTokenMiddleware` 在生产或强制 Token 时保护敏感写接口。
- `backend/services/`：SQLite 存储、调度器、店铺配置解析、看板聚合、周期数据查询和缓存。
- `backend/collectors/`：窗口截图、OCR、Edge CDP、只读大屏读取、窗口控制等采集底层能力。
- `backend/tools/`：全量测试、API 冒烟、OCR 异常排查、Edge 启动辅助等命令行工具。
- `frontend/index.html`：本机管理台与公网看板共用 HTML 入口，通过路径 `/dashboard` 切换公网只读模式。
- `frontend/core.js`：全局状态、API 包装、Token 存储、任务/店铺辅助函数、WebSocket 连接、全局事件绑定。
- `frontend/dashboard-shared.js`、`frontend/dashboard.js`、`frontend/dashboard-public.js`：看板渲染、公共看板轮询、周期数据集导航和刷新逻辑。
- `frontend/config.js`、`frontend/edge.js`、`frontend/debug.js`、`frontend/app.js`：采集配置、Edge 控制、调试面板、应用入口和页面模式分流。
- `data/`：当前运行数据和配置，含店铺 CSV、JSON 快照、SQLite、截图、Edge profiles、周期缓存。
- `tests/`：pytest 回归文件和自研 smoke/full test 入口；当前 CI 调用脚本式测试为主。
- `scripts/ci_check.py`：GitHub Actions 的主 CI 编排脚本。
- `.github/workflows/test.yml`：Windows CI，安装 Python 3.11 依赖后运行 `python scripts/ci_check.py --with-api`。
- `deploy/`：FRP、Nginx、systemd、Windows FRP 客户端安装脚本、公网只读部署说明和生产环境变量样例。
- `第1步_启动GMV服务.bat`、`第2步_启动公网隧道.bat`：Windows 本机启动服务和公网隧道的操作入口。

## 6. 核心业务链路

- **服务启动链路**：`第1步_启动GMV服务.bat` 使用 `.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8100` 启动服务；`backend/main.py` 在 startup 阶段初始化 SQLite、同步 `shops.csv` 店铺配置、注册实时快照广播回调，并按 `GMV_SCHEDULER_AUTOSTART` 启动调度器和周期缓存调度。
- **店铺配置链路**：`backend/services/shop_config.py` 优先读取 `data/shops.csv`，其次读取 `shops_page_data.json`，最后读取 `shops_default.json`；当前因 CSV 存在，CSV 是真实店铺配置来源。
- **采集配置链路**：管理员在 `/` 页面进入采集配置/任务管理，选择店铺 Edge 会话，扫描页面，绑定业务页，选择“大屏只读”或 OCR，保存任务。
- **Edge 采集链路**：后端通过 Playwright CDP 连接 Microsoft Edge，管理独立或真实 Profile 会话；支持启动、显示、隐藏、关闭、页面列表、页面绑定和健康检查。
- **只读大屏链路**：对天猫、京东、唯品会、抖音、得物识别目标大屏 URL，在页面上下文读取关键 GMV 字段或受控请求结果，减少 OCR 对截图和字体的依赖。
- **OCR 链路**：对未使用只读或只读失败的任务，通过截图区域、OCR 引擎、确认次数和安全边界提取 GMV 数值。
- **实时展示链路**：调度器更新 SQLite 任务运行态和采样记录，`build_snapshot()` 生成实时任务快照，WebSocket `/ws/live` 推送给管理台，`/api/dashboard` 为看板提供聚合模型。
- **周期展示链路**：`build_dashboard_view()` 结合实时任务、目标 CSV、周期数据集和可选 MySQL/缓存，返回实时/周期看板 payload；前端 `dashboard-public.js` 每 1.2 秒轮询刷新。
- **公网只读链路**：公网请求经腾讯云 Nginx -> Ubuntu 本地 FRP 端口 -> Windows FastAPI；Nginx 只放行 `/dashboard`、`/static/`、`/api/dashboard`、`/api/dashboard-datasets`、`/api/health`、`/favicon.ico`。

## 7. 数据流与调用关系

- `data/shops.csv` -> `shop_config.load_shop_configs()` -> `store.sync_tasks_with_shop_configs()` -> SQLite `capture_tasks` 与 `edge_sessions`。
- 管理台配置动作 -> `/api/tasks`、`/api/shops/bind`、`/api/edge-sessions/*`、`/api/platforms/*` -> `store`、`scheduler`、`remote_edge_manager` -> SQLite 与 Edge CDP。
- 调度器采集 -> Edge CDP/只读页面/OCR -> `store.update_task_runtime()`、`store.add_sample()` -> `build_snapshot()` -> `/api/realtime`、`/api/tasks`、`/ws/live`。
- 看板 API -> `build_dashboard_view(dataset_id)` -> 实时 `build_snapshot()` + 目标/周期 CSV + MySQL 查询或 `data/.cache/period_gmv.json` -> `/api/dashboard`。
- 前端管理台 -> `api()` 包装器自动带 `X-API-Token`；但 `dashboard-public.js` 中 `POST /api/dashboard-cache/refresh` 使用裸 `fetch`，不会自动携带 Token。
- 公网只读部署 -> Nginx allowlist 控制外部可访问路径；后端自身默认未对读接口和 `/ws/live` 增加统一鉴权。

## 8. 启动方式与运行依赖

- **本地服务**：在 Windows 仓库根目录运行 `第1步_启动GMV服务.bat`，要求 `.venv\Scripts\python.exe` 已存在；服务监听 `127.0.0.1:8100`。
- **直接开发启动**：可用 `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8100`，但仍依赖 Windows、Edge、Playwright、OCR 依赖和 `data/` 下运行数据。
- **环境变量**：`.env` 由 `python-dotenv` 加载；关键变量包括 `GMV_APP_ENV`、`GMV_API_TOKEN`、`GMV_REQUIRE_API_TOKEN`、`GMV_CORS_ORIGIN_REGEX`、`GMV_DEBUG_API_ENABLED`、`GMV_SCHEDULER_AUTOSTART` 和 `MYSQL_*`。
- **Python 依赖**：`requirements.txt` 固定 FastAPI、Uvicorn、pytest、websockets、Playwright、OCR、pywin32、pymysql、python-dotenv 等版本；`pyproject.toml` 声明项目版本 `0.3.0`、Python `>=3.11`、Ruff 配置。
- **前端依赖**：无 npm 构建依赖；`package.json` 当前 `npm test` 为占位失败命令，前端通过静态脚本直接由 FastAPI `/static` 服务。
- **公网部署**：按 `deploy/README-public-dashboard.md`，Windows 本机运行采集服务和 FRP 客户端，腾讯云 Ubuntu 运行 FRP server 与 Nginx；公网只读入口当前包括 `http://124.223.70.233/dashboard`，备案和证书完成后切换域名 HTTPS。

## 9. 已有测试与验证方式

- **GitHub Actions**：`.github/workflows/test.yml` 在 `windows-latest` 上安装 Python 3.11、`requirements.txt` 和 Ruff，然后运行 `python scripts/ci_check.py --with-api`。
- **CI 编排内容**：`scripts/ci_check.py` 依次运行 Ruff、`tests/full_test.py --skip-api`、`tests/smoke_edge.py`，再启动 Uvicorn 并运行 `tests/smoke_api.py`。
- **pytest 文件**：`tests/test_dashboard_regression.py` 覆盖看板 JS、HTML 静态版本、移动端样式、公共看板与测试看板 API 一致性等；`tests/test_screen_readonly_hardening.py` 覆盖只读金额边界、失败退避、抖音解析回归等。
- **当前缺口**：上述两个 `test_*.py` 文件未被 `pytest` 命令纳入 CI 执行；CI 只通过 Ruff 检查这些文件语法/风格，不运行其中断言。
- **部署验证**：`deploy/README-public-dashboard.md` 给出公网 curl 验证，预期只读接口成功、`POST /api/dashboard-cache/refresh` 和 `/api/tasks` 返回 `403`。

## 10. 当前主要风险

风险计数：P0 5 项、P1 9 项、P2 10 项。

- **P0-1：前端管理台可能因 `setWsStatus` 未定义直接中断初始化。** `app.js` 在 `startInternalDashboard()` 中直接调用 `setWsStatus()`，catch 分支也继续调用；若实际未定义，会导致管理台后续 `syncSchedulerButton()` 和 `connectLiveWebSocket()` 无法稳定执行。
- **P0-2：生产安全过度依赖部署层路径阻断。** 后端读接口和 `/ws/live` 默认未鉴权，写接口只有在 `GMV_APP_ENV=production` 或 `GMV_REQUIRE_API_TOKEN=true` 时由 `WriteTokenMiddleware` 保护；一旦 Windows 端口、FRP 或 Nginx 配置误暴露，管理/实时数据边界会变弱。
- **P0-3：公网/生产写操作链路与前端实现不一致。** `POST /api/dashboard-cache/refresh` 被列为敏感写接口，但前端用裸 `fetch` 不带 `X-API-Token`；公网 Nginx 又显式返回 `403`，按钮和接口策略容易形成用户可见失败。
- **P0-4：Fresh clone 难以独立复现业务运行态。** 核心链路依赖 Windows、Microsoft Edge 登录态、CDP 端口、Edge profile、SQLite 运行数据、`.venv` 和本机路径；仅拉仓库无法立即重建真实采集环境。
- **P0-5：运行数据、配置快照和缓存混在仓库 `data/` 内，缺少迁移/备份/恢复边界。** SQLite、Edge profiles、截图、JSON 快照、MySQL 缓存和 CSV 共同影响运行态，一旦误提交、误覆盖或环境迁移，可能直接影响采集和看板可信度。

- **P1-1：版本信息不一致。** `backend/main.py` FastAPI 版本为 `0.3.0`，`/api/health` 与 `/api/debug/status` 中版本仍显示 `0.2.0`，影响运维判断和发布追踪。
- **P1-2：`setupDebugPanel()` 未在当前入口中明确调用。** `debug.js` 定义了 Token/调试面板事件绑定，但当前入口未看到调用，调试按钮、Token 保存和生产状态提示可能不可用。
- **P1-3：管理台看板和任务管理存在数据双轨风险。** `app.js` 以 `preserveLocalSnapshot: true` 启动共享看板，可能让看板展示的聚合数据与管理任务快照不是同一条状态源。
- **P1-4：CI 未执行两个 pytest 回归文件。** `tests/test_dashboard_regression.py` 与 `tests/test_screen_readonly_hardening.py` 内容较关键，但 GitHub Actions 当前没有运行 `pytest`，回归保护不足。
- **P1-5：店铺配置来源存在优先级和状态差异。** 代码优先使用 `shops.csv`，而 `shops_page_data.json` 中可出现不同 `enabled` 状态和本机绝对路径，维护者容易误判真实生效配置。
- **P1-6：MySQL 周期数据查询失败时降级较静默。** `dashboard_query.py` 捕获 MySQL 异常后返回空结果或缓存状态，缺少面向看板/运维的强提示，可能把外部数据失败误读为业务波动。
- **P1-7：读类管理接口如果被部署层误放行会泄露运行信息。** `/api/tasks`、`/api/edge-sessions`、`/api/windows`、`/api/settings` 等 GET 接口不在 Token 中间件保护范围，可能暴露店铺、窗口、路径或运行状态。
- **P1-8：公网只读页面仍包含部分本机管理 DOM 和脚本。** `/dashboard` 通过 CSS/JS 隐藏管理区，而不是独立最小化页面；若脚本异常或样式失效，用户可能看到不该出现的控制元素。
- **P1-9：Edge 操作、只读读取和 OCR 链路对平台页面结构高度敏感。** 平台 URL、DOM、接口字段、登录态、页面 title 或 frame 变化都会影响采集，当前需要更系统的故障分类和恢复策略。

- **P2-1：README 和旧文档存在明显过时信息。** README 中前端模块数量等描述已不匹配当前 `index.html`，旧 DEFINE 的 Git 判断也不可信。
- **P2-2：前端无构建、无类型检查、无模块边界。** 8 个全局脚本通过加载顺序共享函数和状态，新增功能容易引入隐式依赖或未定义函数。
- **P2-3：`package.json` 测试脚本仍是占位失败命令。** 对新维护者而言，Node/npm 入口会误导验证方式。
- **P2-4：部署说明和配置脚本分散，缺少一键环境检查。** 当前需要人工组合 `.env`、bat、FRP、Nginx、Edge 登录态和 curl 检查。
- **P2-5：Windows 启动 bat 通过进程/端口强制清理，存在误杀或诊断不足。** 当前脚本会尝试结束已有端口进程，适合单机使用但不够商业化可观测。
- **P2-6：日志、指标和告警体系不足。** 后端有 request id 和访问日志，但采集成功率、平台失败原因、缓存新鲜度、MySQL 状态、WebSocket 状态缺少统一监控面。
- **P2-7：部署层只读 allowlist 没有自动化测试覆盖。** 文档列出 curl 预期，但 CI 未验证 Nginx 配置片段是否持续满足只读策略。
- **P2-8：数据文件编码、CSV 字段和目标值格式仍主要靠运行时报错。** `shops.csv` 支持编码 fallback 和字段校验，但缺少独立 schema/fixture 验证命令。
- **P2-9：仓库中存在 `backups/` 历史代码副本，容易干扰搜索和认知。** 当前 Glob 能搜索到备份 JS/测试文件，后续分析需明确排除备份目录。
- **P2-10：发布版本未统一。** `pyproject.toml`、FastAPI app、`package.json`、健康检查和文档版本没有统一来源，发布后难以追溯。

## 11. 商业化代码规范差距

- **安全边界**：生产依赖 Nginx allowlist 与写接口 Token 双层保护，但后端缺少统一的读接口鉴权策略、速率限制、WebSocket 鉴权、部署误配置兜底。
- **可部署性**：项目强依赖 Windows + Edge + 本机登录态，尚未形成清晰的“开发环境、演示环境、生产环境”分层和可复现 bootstrap。
- **数据治理**：运行数据、缓存、配置快照、截图和浏览器 profile 位于同一 `data/` 树下，缺少迁移、备份、脱敏、归档和敏感文件检查规范。
- **测试治理**：关键 pytest 回归未进 CI；前端没有自动化浏览器测试、JS lint/type check；公网 Nginx allowlist 和 Token 策略没有自动化验证。
- **前端工程化**：全局脚本和 DOM 直连方式能快速交付，但对商业化维护不友好；缺少模块导入、类型约束、错误边界和独立公网只读入口。
- **运维观测**：缺少统一健康面板、采集 SLA、缓存状态、外部 MySQL 状态、平台页面变化告警和可追踪发布版本。
- **文档一致性**：README、历史审计/DEFINE 与当前代码不同步，后续人员可能按照旧信息执行错误操作。
- **配置管理**：`.env` 样例覆盖生产安全核心变量，但缺少启动前强校验，例如生产未设置 `GMV_API_TOKEN` 时是否应阻止启动。

## 12. 需要后续 PLAN 阶段重点处理的问题

- **优先方向 1：收敛 P0/P1 安全与入口风险。** 明确后端读/写/WebSocket/API 的安全模型，补齐生产启动强校验，修复缓存刷新 Token 链路，验证 Nginx allowlist 与后端防线一致。
- **优先方向 2：修复前端初始化和数据源一致性。** 处理 `setWsStatus`、`setupDebugPanel()`、`preserveLocalSnapshot` 数据双轨、公共看板按钮暴露等问题，决定是否拆分公网只读入口。
- **优先方向 3：把关键回归纳入 CI 并补齐部署验证。** 在 GitHub Actions 中运行 pytest，加入公网只读策略、Token 中间件、健康版本一致性、店铺配置 schema、MySQL 缓存降级的自动化检查。
- 建议同时规划 `data/` 分层：区分源配置、运行态数据库、缓存、截图、Edge profile、密钥文件和可提交/不可提交边界。
- 建议统一版本来源：FastAPI app、`pyproject.toml`、健康检查、调试接口、部署文档和发布说明使用一致版本。
- 建议整理文档：README 与 DEFINE/PLAN/部署文档统一，以当前代码为真值删除或标记历史过时结论。

## 13. 当前阶段结论

当前项目已经具备可运行的本机 GMV 采集和公网只读看板基础，也已经有 Windows CI、Ruff、自研 smoke/full test、FRP + Nginx 部署说明和部分 pytest 回归用例。

可以进入 PLAN 阶段，但应优先规划 P0/P1 风险收敛。下一阶段前三个重点是：安全与公网入口收敛、前端初始化/数据源一致性修复、关键测试与部署验证纳入 CI。

本阶段没有发现阻止进入 PLAN 的结构性阻塞；主要阻塞风险来自生产安全边界、运行环境不可复现和回归测试未完整执行，需要在 PLAN 阶段明确改造顺序和验收标准。
