# BUILD_修复执行与代码变更报告

## 1. 本阶段执行结论

BUILD 阶段已完成。本轮按当前真实代码与 `DEFINE_项目定义与真实现状报告.md` 执行保守最小修复，未执行过时 PLAN 中的 Git 初始化、提交、`.env` 修改、`data/shops.csv` 编码转换、脚本移动、data/backups 清理或临时文件删除。

执行前检查已完成：

- 项目目录结构：已执行 `Get-ChildItem -Force | Select-Object Mode,Length,LastWriteTime,Name | Format-Table -AutoSize`，确认存在 `.git`、`backend/`、`frontend/`、`tests/`、`scripts/`、`.github/`、`deploy/`、`data/`、`.trae/` 等目录。
- Git 状态：已执行 `git status --short`。检查时存在父阶段/历史工作区改动，包含 `.trae/documents/DEFINE_项目定义与真实现状报告.md`；本轮没有提交。
- 启动入口：已读取 `第1步_启动GMV服务.bat` 和 `backend/main.py`，入口为 `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8100`。
- 依赖文件：已确认 `requirements.txt`、`pyproject.toml`、`package.json`、`.github/workflows/test.yml`、`scripts/ci_check.py` 存在。
- 测试命令：已确认并执行 `python -m pytest tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py`、`.venv\Scripts\ruff.exe check ...`、`python scripts/ci_check.py`、`python scripts/ci_check.py --with-api`。
- PLAN 阶段任务队列和不准确处：PLAN 仍写“无 Git”、`.env` 明文密码、店铺全 FALSE、Git 初始化、移动脚本、删除 data 临时文件、转换 `data/shops.csv` 编码等，与当前 DEFINE 和真实仓库不一致。本轮以当前代码和 DEFINE 为准，仅修复前端初始化、调试面板、Token 链路、版本一致性和 CI 回归。
- 高风险文件：`data/`、`.env`、`backend/collectors/edge/`、`backend/services/scheduler.py`、`backend/services/store.py`、公网部署配置均视为高风险。本轮没有修改 `.env`、`data/shops.csv`、`data/backups`；测试产生的 `data/shops_default.json` 路径副作用已撤回。

## 2. 修改文件清单

| 文件 | 修改类型 | 修改原因 | 影响范围 | 风险等级 |
|------|----------|----------|----------|----------|
| `frontend/core.js` | bugfix | 新增全局 `setWsStatus()`，避免 `app.js` 初始化时引用未定义函数 | 前端状态提示、WebSocket 状态提示 | 低 |
| `frontend/styles.css` | ui | 为 `setWsStatus(..., "bad")` 增加错误态视觉样式 | 顶部实时状态 pill | 低 |
| `frontend/app.js` | bugfix | 在本机管理台入口调用 `setupDebugPanel()` | 调试面板按钮、Token 保存/清空 | 低 |
| `frontend/dashboard-public.js` | security/bugfix | 缓存刷新改用 `api()`，自动携带 `X-API-Token`，并补充公网禁止刷新提示 | 公共看板/本机管理台刷新周期缓存 | 中 |
| `backend/version.py` | refactor | 新增单一版本常量 `APP_VERSION` | 后端版本来源 | 低 |
| `backend/main.py` | refactor | FastAPI app 版本改用 `APP_VERSION` | OpenAPI/应用元信息 | 低 |
| `backend/routers/system.py` | bugfix | `/api/health` 与 `/api/debug/status` 版本统一为 `0.3.0` | 健康检查、调试状态 | 低 |
| `scripts/ci_check.py` | ci | 将两个关键 pytest 文件纳入 CI 编排 | GitHub Actions 与本地 CI | 低 |
| `tests/test_dashboard_regression.py` | test | 覆盖 `setWsStatus`、`setupDebugPanel`、缓存刷新 Token、版本一致性、CI pytest 接入 | 静态回归和接口回归 | 低 |
| `backend/tools/full_test.py` | test | 将过时 `/api/settings` 前端断言替换为缓存刷新 `api()` 断言，并修复导入 lint | 自研 full_test 前端一致性检查 | 低 |
| `backend/collectors/edge/_session.py` | lint | 为队列满异常补充异常链 `from exc`，解除 CI Ruff B904 阻断 | Edge 动作异常栈信息 | 低 |
| `tests/test_screen_readonly_hardening.py` | lint | 修复导入排序，解除 CI Ruff I001 阻断 | 测试文件 | 极低 |
| `.trae/documents/BUILD_修复执行与代码变更报告.md` | docs | 更新 BUILD 阶段真实执行报告 | 阶段交付文档 | 极低 |

## 3. P0 问题处理结果

| 问题 | 是否修复 | 涉及文件 | 验证方式 | 结果 |
|------|----------|----------|----------|------|
| `setWsStatus` 未定义导致 `app.js` 初始化中断 | 是 | `frontend/core.js`, `frontend/app.js`, `frontend/styles.css`, `tests/test_dashboard_regression.py` | `python -m pytest tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py` | 通过，23 passed |
| `POST /api/dashboard-cache/refresh` 裸 `fetch` 不带 Token | 是 | `frontend/dashboard-public.js`, `tests/test_dashboard_regression.py`, `backend/tools/full_test.py` | pytest 静态断言、`python scripts/ci_check.py --with-api` | 通过，缓存刷新检查和 CI 均通过 |

## 4. P1 问题处理结果

| 问题 | 是否修复 | 涉及文件 | 验证方式 | 结果 |
|------|----------|----------|----------|------|
| `setupDebugPanel()` 定义后未调用 | 是 | `frontend/app.js`, `frontend/debug.js`, `tests/test_dashboard_regression.py` | pytest 静态断言 | 通过 |
| `/api/health`、`/api/debug/status` 与 app/pyproject 版本不一致 | 是 | `backend/version.py`, `backend/main.py`, `backend/routers/system.py`, `pyproject.toml`, `tests/test_dashboard_regression.py` | TestClient 调用 `/api/health`、`/api/debug/status` | 通过，统一为 `0.3.0` |
| `scripts/ci_check.py` 未运行关键 pytest 回归 | 是 | `scripts/ci_check.py`, `tests/test_dashboard_regression.py` | `python scripts/ci_check.py`、`python scripts/ci_check.py --with-api` | 通过，CI 已运行两个 pytest 文件 |
| CI 范围内已有 Ruff/full_test 阻断 | 是 | `backend/collectors/edge/_session.py`, `backend/tools/full_test.py`, `tests/test_screen_readonly_hardening.py` | `.venv\Scripts\ruff.exe check ...`、`python scripts/ci_check.py` | 通过 |

## 5. P2 问题处理结果

| 问题 | 是否修复 | 涉及文件 | 验证方式 | 结果 |
|------|----------|----------|----------|------|
| README 明显过时信息 | 否 | 无 | 已评估 | 本轮未改 README，避免扩大文档范围 |
| PLAN 与真实仓库冲突未记录 | 是 | `.trae/documents/BUILD_修复执行与代码变更报告.md` | 本报告第 1 节记录 | 已记录 |
| 测试产生 data 运行态副作用 | 是 | `data/shops_default.json` | `git diff -- data/shops_default.json` | 已撤回，当前无差异 |

## 6. 商业化代码规范落地内容

- 前端入口具备基本错误边界：`setWsStatus()` 作为全局状态函数集中处理文本和错误态，避免页面初始化因单个未定义函数中断。
- 调试面板接入本机入口：管理员可保存/清空 API Token，生产或公网写接口失败时更容易定位。
- 写接口 Token 链路收敛：缓存刷新走统一 `api()` 包装器，沿用已有 `X-API-Token` 机制，不另建鉴权逻辑。
- 版本来源收敛：后端 app、健康检查和调试状态使用 `APP_VERSION`，并用测试校验与 `pyproject.toml` 一致。
- CI 回归增强：关键 pytest 文件进入 `scripts/ci_check.py`，并保留 Ruff、full_test、smoke_edge、API smoke 的验证路径。
- 未对敏感配置和运行数据做非必要变更：未改 `.env`、未转换 `data/shops.csv`、未清理 data/backups。

## 7. 已执行验证

| 命令/方式 | 退出码/结果 | 记录 |
|----------|-------------|------|
| `git status --short` | 0 | 初始/最终均执行；最终显示本轮代码改动、报告改动，以及非本轮的 `.trae/documents/DEFINE_项目定义与真实现状报告.md` 仍为 modified |
| `Get-ChildItem -Force | Select-Object Mode,Length,LastWriteTime,Name | Format-Table -AutoSize` | 0 | 已确认项目顶层目录结构 |
| `python -m pytest tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py` | 0 | 23 passed, 5 warnings；warnings 为 FastAPI `on_event` deprecation 和 `python_multipart` pending deprecation |
| `python -m ruff check backend/main.py backend/routers/system.py backend/version.py scripts/ci_check.py tests/test_dashboard_regression.py` | 1 | 系统 Python 环境无 `ruff` 模块：`No module named ruff` |
| `.venv\Scripts\ruff.exe check ...` | 0 | All checks passed |
| `python scripts/ci_check.py`（首次） | 1 | Ruff 阶段失败：`B904`、`E401`、`I001`；已做最小 lint 修复 |
| `python scripts/ci_check.py`（第二次） | 1 | full_test 失败：过时 F4 仍要求前端引用 `/api/settings`；已改为缓存刷新 `api()` 断言 |
| `python scripts/ci_check.py`（最终） | 0 | Ruff 通过，pytest 23 passed，full_test 55/55 PASS，smoke_edge ok |
| `Get-NetTCPConnection -LocalPort 8100 -State Listen ...` | 0 | 无监听输出，确认可安全启动临时 API smoke |
| `python scripts/ci_check.py --with-api` | 0 | Ruff 通过，pytest 23 passed，full_test 55/55 PASS，smoke_edge ok，API smoke 14/14 PASS |
| `ReadLints` | 通过 | 已改文件无 IDE linter errors |

补充说明：`--with-api` 输出中出现真实 Edge 调试端口未连接的错误日志，但 API smoke 最终 14/14 PASS，属于当前环境没有真实 Edge 调试连接时的受控错误路径，仍建议 VERIFY 阶段手工验证真实 Edge 操作。

## 8. 未解决问题

- 生产只读接口、`/ws/live`、读类管理接口的后端鉴权边界仍未在本轮收敛，属于 DEFINE 中更大的安全模型问题。
- 真实 Edge 启动/显示/隐藏/关闭、平台页面只读采集、OCR 采集需要登录态和人工场景，自动化 CI 只能覆盖 smoke 层。
- FastAPI `on_event` deprecation warnings 仍存在，本轮未改生命周期实现，避免扩大风险。
- 工作区存在非本轮改动：`.trae/documents/DEFINE_项目定义与真实现状报告.md` 仍为 modified。

## 9. 代码变更风险

- `frontend/dashboard-public.js` 改为 `api()` 后，本机管理员页面会自动带 Token；公网 Nginx 仍可能直接返回 403，此时前端会显示明确禁止刷新提示。
- `setupDebugPanel()` 在本机入口调用一次，依赖 DOM 元素存在；函数内部均使用可选 DOM 获取，风险低。
- `backend/collectors/edge/_session.py` 仅补异常链，不改变队列满时抛出的异常类型。
- `backend/tools/full_test.py` 更新了过时静态断言，可能改变历史 full_test 的检查语义，但新断言与当前 DEFINE/P0 Token 链路一致。
- `python scripts/ci_check.py --with-api` 会触发本地服务和 smoke 写接口，已观察到测试会临时改动 `data/shops_default.json` 的本机路径，本轮已撤回该副作用；后续执行仍需注意运行态文件变化。

## 10. 下一阶段 VERIFY 建议

- 建议进入 VERIFY。
- 重点手工验证本机管理台：页面刷新后控制台不再出现 `setWsStatus is not defined`，调试按钮可打开面板，Token 保存/清空可用。
- 重点验证缓存刷新：本机管理员入口填写 Token 后刷新成功；公网只读入口如被 Nginx 禁止应显示明确失败提示。
- 重点验证 `/api/health`、`/api/debug/status` 返回版本均为 `0.3.0`。
- 运行真实 Edge 场景：启动/显示/隐藏/关闭、页签扫描、只读采集、WebSocket 实时刷新。
- VERIFY 前后继续监控 `git status --short`，避免 API smoke 产生的 data 运行态副作用混入交付。
