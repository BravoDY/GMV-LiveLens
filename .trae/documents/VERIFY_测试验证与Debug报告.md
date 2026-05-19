# VERIFY_测试验证与Debug报告

## 1. 本阶段总体结论
- **CONDITIONAL_PASS**。
- 自动化回归、Ruff、完整 CI、API smoke、受控临时服务 API/页面/WebSocket 验证均已完成且关键命令通过。
- 条件项：未做真实浏览器人工交互、真实 Edge 登录态/平台页面采集未验证；虚拟环境存在 `pytest` 未安装问题，系统 Python 可完成测试；系统 Python 全局环境 `pip check` 存在与本项目无关的依赖冲突。

## 2. 执行环境
- OS：Windows `win32 10.0.26300`。
- 目标仓库：`C:/Users/yjd22/Desktop/python项目/GMV-LiveLens`。
- 前置文档：`DEFINE_项目定义与真实现状报告.md`、`PLAN_修复计划与商业化落地路线.md`、`BUILD_修复执行与代码变更报告.md` 均已读取成功。
- 依赖文件：`requirements.txt`、`pyproject.toml`、`package.json` 均存在。
- Python：系统 `Python 3.13.9`；虚拟环境 `.venv` 为 `Python 3.14.3`。
- pip：系统 `pip 25.2`；虚拟环境 `pip 26.1`。
- Node/npm：`node v22.22.0`；`npm 11.8.0`。
- 关键依赖版本：FastAPI `0.110.2`、Uvicorn `0.29.0`、pytest `8.4.1`（系统环境）、Ruff `0.15.12`（虚拟环境）、Playwright `1.58.0`、PyMySQL 系统 `1.1.1`/虚拟环境 `1.1.3`、python-dotenv 系统 `1.0.1`/虚拟环境 `1.2.2`、websockets `16.0`。
- 启动命令：`GMV_SCHEDULER_AUTOSTART=false python -m uvicorn backend.main:app --host 127.0.0.1 --port 8100`。
- 测试命令：`python -m pytest tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py`、`.venv\Scripts\ruff.exe check ...`、`python scripts/ci_check.py --with-api`。

## 3. 验证命令与结果
| 类型 | 命令/方式 | 结果 | 说明 |
|------|-----------|------|------|
| Git 状态（前） | `git status --short` | 退出码 0 | 记录到 BUILD/DEFINE、后端、前端、脚本和测试等既有改动；VERIFY 报告尚未写入。 |
| 依赖文件 | PowerShell `Test-Path requirements.txt/pyproject.toml/package.json` | 退出码 0 | 三个文件均存在。 |
| 版本检查 | `python --version`、`.venv\Scripts\python.exe --version`、`pip --version`、`.venv\Scripts\pip.exe --version`、`node --version`、`npm --version` | 退出码 0 | 版本见执行环境。 |
| 依赖一致性 | `.venv\Scripts\pip.exe check` | 退出码 0 | `No broken requirements found.` |
| 依赖一致性 | `pip check` | 输出全局依赖冲突 | 系统 Python 全局环境存在多项第三方包版本冲突；本项目虚拟环境未发现 broken requirements。 |
| 关键依赖版本 | `.venv\Scripts\python.exe -m pip show ...` | 退出码 0 | 虚拟环境缺少 `pytest`；其他关键包可查询。 |
| 关键依赖版本 | `python -m pip show ...` | 退出码 0 | 系统环境有 `pytest 8.4.1`，无 `ruff` 模块。 |
| pytest（优先虚拟环境） | `.venv\Scripts\python.exe -m pytest tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py` | 退出码 1 | 失败原因：`.venv` 中 `No module named pytest`。 |
| pytest（系统 Python） | `python -m pytest tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py` | 退出码 0 | `23 passed, 5 warnings in 1.12s`；warning 为 FastAPI `on_event` deprecation 与 `python_multipart` pending deprecation。 |
| Ruff（系统 Python） | `python -m ruff check ...` | 不可用 | 系统 Python 输出 `No module named ruff`。 |
| Ruff（虚拟环境） | `.venv\Scripts\ruff.exe check backend/main.py backend/routers/system.py backend/version.py backend/tools/full_test.py backend/collectors/edge/_session.py scripts/ci_check.py tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py` | 退出码 0 | `All checks passed!` |
| 端口检查 | `Get-NetTCPConnection -LocalPort 8100 -State Listen` | 退出码 0 | CI 前、CI 后均无监听；未杀任何非本任务进程。 |
| 完整 CI | `GMV_SCHEDULER_AUTOSTART=false python scripts/ci_check.py --with-api` | 退出码 0 | Ruff 通过；pytest `23 passed`；`full_test.py --skip-api` 为 `55/55 PASS`；`smoke_edge ok`；API smoke `14/14 PASS`。 |
| 受控 API 验证 | 临时启动 uvicorn，设置 `GMV_SCHEDULER_AUTOSTART=false`、`GMV_REQUIRE_API_TOKEN=true`、`GMV_API_TOKEN=verify-token`、MySQL 指向不可用本机端口 | 退出码 0 | `/api/health`、`/api/config/public`、`/api/dashboard`、`/api/dashboard-datasets`、`/api/tasks` 均 200；WebSocket 收到帧；无 Token 写接口 401。 |
| 前端 HTTP 验证 | HTTP GET `/`、`/dashboard`、`/dashboard-test` | 退出码 0 | 三个页面均 HTTP 200；关键 JS 引用存在。未做真实浏览器控制台/交互验证。 |
| 数据副作用检查 | `git diff -- data/shops_default.json` | 发现测试副作用 | API smoke 将 `user_data_dir` 改为本机路径；已按要求撤回。 |
| 数据副作用撤回 | `git checkout -- data/shops_default.json` | 退出码 0 | 仅撤回该运行态文件副作用；未回退其他改动。 |
| Git 状态（后） | `git status --short` | 退出码 0 | `data/shops_default.json` 已不再变更；新增/修改仅剩 BUILD 阶段文件与本 VERIFY 报告。 |

## 4. 核心业务链路验证结果
| 链路 | 验证方式 | 通过标准 | 实际结果 | 是否通过 |
|------|----------|----------|----------|----------|
| 服务启动与健康检查 | 受控启动 uvicorn 后 GET `/api/health` | HTTP 200，`status=ok`，版本正确 | HTTP 200，`version=0.3.0`，调度器自启动已禁用 | 是 |
| 公共配置 | GET `/api/config/public` | HTTP 200，能反映 Token 策略 | HTTP 200，`require_api_token=True`，`api_token_configured=True` | 是 |
| 看板聚合 | GET `/api/dashboard`，MySQL 指向不可用端口 | HTTP 200，不因 MySQL 不可用崩溃 | HTTP 200，返回看板数据结构 | 是 |
| 数据集列表 | GET `/api/dashboard-datasets` | HTTP 200，返回数据集摘要 | HTTP 200，含 `datasets/by_product/shop_names/target_dates` 等字段 | 是 |
| 任务列表 | GET `/api/tasks` | HTTP 200，返回任务列表 | HTTP 200；CI smoke 记录 `tasks=9` | 是 |
| API smoke | `python scripts/ci_check.py --with-api` 内置 `tests/smoke_api.py` | 14 项通过 | `14/14 PASS`，含 health、scheduler、tasks、edge-sessions、shops、OCR、settings、windows、主页、WebSocket、realtime 等 | 是 |
| WebSocket | 连接 `ws://127.0.0.1:8100/ws/live` | 连接成功并收到初始帧 | 收到 `str` 帧，约 `13469` bytes | 是 |
| 前端页面 | HTTP GET `/`、`/dashboard`、`/dashboard-test` | HTTP 200，关键 JS 引用存在 | 三个页面均 200；`/` 与 `/dashboard` 含 8 个主 JS；`/dashboard-test` 含测试看板 JS | 是 |
| 真实浏览器交互 | 人工打开页面、查看 Console、点击调试/刷新/看板切换 | 无控制台错误，交互可用 | 未执行真实浏览器人工交互，仅完成 HTTP/静态引用验证 | 条件通过 |
| 真实 Edge/平台采集 | 登录态 Edge、平台大屏、OCR/只读采集 | 可启动/显示/隐藏/绑定并采集真实数据 | 本阶段未触发真实采集；CI 中 Edge 健康为受控 smoke 层 | 条件通过 |

## 5. BUILD 修复回归验证结果
| BUILD 修改点 | 验证方式 | 结果 | 是否通过 |
|---------------|----------|------|----------|
| `setWsStatus` 已定义 | `rg "function setWsStatus" frontend/core.js`，pytest 静态回归 | `frontend/core.js` 存在 `function setWsStatus(text, tone = "ok")`；pytest 通过 | 是 |
| `setupDebugPanel()` 被调用 | `rg "setupDebugPanel\\(" frontend/app.js`，pytest 静态回归 | `frontend/app.js` 本机入口调用 `setupDebugPanel();` | 是 |
| 缓存刷新使用 `api()` | `rg "api(\"/api/dashboard-cache/refresh\"" frontend/dashboard-public.js`，`full_test.py` F4 | 命中 `await api("/api/dashboard-cache/refresh", ...)`；CI full_test F4 通过 | 是 |
| 后端 `APP_VERSION` 统一为 `0.3.0` | 读取 `backend/version.py`、`pyproject.toml`，请求 `/api/health` | `APP_VERSION="0.3.0"`；`pyproject.toml` 为 `0.3.0`；`/api/health` 返回 `0.3.0` | 是 |
| pytest 纳入 `scripts/ci_check.py` | 读取 `PYTEST_REGRESSION_FILES` 与 CI 输出 | `scripts/ci_check.py` 包含两个 pytest 文件；完整 CI 实际执行并 `23 passed` | 是 |
| `full_test` 断言更新后通过 | `python scripts/ci_check.py --with-api` | `full_test.py --skip-api` 输出 `55/55 PASS`，F4 为“缓存刷新使用 api() Token 包装” | 是 |
| Token 写接口保护 | 强制 `GMV_REQUIRE_API_TOKEN=true` 后 POST `/api/dashboard-cache/refresh` 无 Token | HTTP 401，错误信息明确要求 `X-API-Token` | 是 |
| CI 范围 Ruff | `.venv\Scripts\ruff.exe check ...` 与完整 CI | 单独 Ruff 和 CI Ruff 均 `All checks passed!` | 是 |

## 6. 异常与边界测试结果
| 场景 | 输入/操作 | 预期结果 | 实际结果 | 是否通过 |
|------|-----------|----------|----------|----------|
| 强制 Token 下缓存刷新无 Token | `POST /api/dashboard-cache/refresh`，无 `X-API-Token` | HTTP 401，明确错误 | HTTP 401，`code=UNAUTHORIZED`，提示公网/生产写操作需要 `X-API-Token` | 是 |
| 强制 Token 下设置写入无 Token | `POST /api/settings`，无 `X-API-Token` | HTTP 401，明确错误 | HTTP 401，`code=UNAUTHORIZED` | 是 |
| 不存在历史任务 | `GET /api/history/-1` | HTTP 404，明确错误 | HTTP 404，`code=TASK_NOT_FOUND`，`message=task_not_found` | 是 |
| 无效查询参数 | `GET /api/history/1?limit=999999` | HTTP 422，参数校验错误 | HTTP 422，`code=VALIDATION_ERROR` | 是 |
| 不存在任务页候选 | `GET /api/tasks/99999/page-candidates` | HTTP 404 或明确任务不存在 | HTTP 404，`code=TASK_NOT_FOUND` | 是 |
| MySQL 不可用 | 临时服务设置 `MYSQL_HOST=127.0.0.1`、`MYSQL_PORT=1` 后请求 `/api/dashboard` | 看板接口不崩溃，返回 200 或明确降级状态 | HTTP 200，返回看板数据结构 | 是 |
| 端口占用安全 | CI/API 验证前后检查 8100 监听 | 不占用或只处理本任务进程 | CI 前后均 `NONE`；未杀任何进程 | 是 |
| 运行态数据副作用 | CI/API smoke 后检查 `data/shops_default.json` | 如有副作用必须撤回 | 发现本机路径写入后已 `git checkout -- data/shops_default.json` 撤回 | 是 |
| 前端真实浏览器控制台 | 浏览器打开页面并查看 Console | 无错误 | 未执行；仅 HTTP/静态引用验证 | 条件通过 |

## 7. 本阶段新增修复
无。

说明：本阶段未发现必须做代码修复的新 P0/P1 bug；仅按 VERIFY 要求撤回了 `data/shops_default.json` 的测试运行态副作用，不计为代码修复。

## 8. 仍未解决的问题
### P0
- 无新增 P0。

### P1
- `.venv` 环境缺少 `pytest`，导致优先命令 `.venv\Scripts\python.exe -m pytest ...` 退出码 1；系统 Python 可完成 pytest 与完整 CI。建议后续同步虚拟环境依赖，或明确本机验证统一使用系统 Python/CI Python。
- 未执行真实浏览器人工交互和真实 Edge 登录态/平台大屏采集验证；自动化 smoke 只能证明 HTTP/API/WebSocket 基础链路可用。

### P2
- 系统 Python 全局环境 `pip check` 存在多项与本项目无关的包冲突；项目虚拟环境 `pip check` 通过。
- `package.json` 版本仍为 `1.0.0`，后端 `APP_VERSION`/`pyproject.toml`/健康检查已为 `0.3.0`；如需全仓版本统一，建议 REVIEW 后单独处理。
- FastAPI `@app.on_event` deprecation warning 仍存在；当前不影响测试通过，可后续迁移到 lifespan。
- 未做真实公网 Nginx allowlist 验证；本阶段只验证了后端 Token 写接口保护与本机 HTTP 路径。

## 9. 是否建议进入 REVIEW
**建议进入**。

理由：BUILD 关键修复点均已回归验证，`python scripts/ci_check.py --with-api` 通过，受控 API/页面/WebSocket/Token/错误路径验证通过，未发现新增 P0/P1 代码缺陷。进入 REVIEW 时重点审查 `.venv` 依赖一致性、真实浏览器/Edge 人工验证缺口、`package.json` 版本元数据和生产只读边界。
