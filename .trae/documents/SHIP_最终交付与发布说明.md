# SHIP_最终交付与发布说明

## 1. 最终交付结论

- 最终交付状态：`CONDITIONAL_READY`。
- 结论依据：REVIEW 最终为 `CONDITIONAL_PASS`，当前未发现 P0 阻塞问题；自动化回归、Ruff、完整 CI、API smoke、受控 API/页面/WebSocket/Token/错误路径验证均已通过。
- 交付限制：真实浏览器人工交互、真实 Edge 登录态/平台采集、公网 Nginx allowlist 尚未完成验证，因此不能标记为无条件 `READY`。
- 是否可以交付使用：可以有条件交付给明确知晓限制的本机/内网试运行场景；面向公网生产发布前必须完成剩余人工和部署验证。

## 2. 本轮六阶段执行摘要

- DEFINE：确认项目真实定位为 Windows 本机 + Microsoft Edge CDP 的 GMV 实时监控与公网只读看板；识别后端 FastAPI、前端 Vanilla JS、SQLite、CSV、Playwright、OCR、FRP + Nginx 等真实技术栈，并指出安全边界、真实 Edge 依赖、运行数据治理、测试覆盖和文档一致性风险。
- PLAN：提出按 P0/P1/P2 收敛的修复路线，但其中存在“无 Git”、`.env` 明文密码、店铺全 FALSE、部分文件改动计划等与后续真实仓库状态不一致的内容；BUILD 阶段已明确不机械执行过时计划，以当前 DEFINE 和代码为准。
- BUILD：完成前端初始化、调试面板、缓存刷新 Token、后端版本统一、CI pytest 接入和 lint 阻断修复；未修改 `.env`、`data/shops.csv`、README、运行态数据或 Edge 核心采集逻辑。
- VERIFY：最终为 `CONDITIONAL_PASS`；`pytest 23 passed`、Ruff 通过、`python scripts/ci_check.py --with-api` 通过、API smoke `14/14 PASS`，受控 API/页面/WebSocket/Token/错误路径验证通过；真实浏览器、真实 Edge、真实公网未验证。
- REVIEW：最终为 `CONDITIONAL_PASS`；未发现明确 P0，未做新增代码修复；确认 BUILD 修复点与代码、VERIFY 结果一致，同时明确真实浏览器、真实 Edge 登录态/平台采集、公网 Nginx allowlist 是 SHIP 必须说明的条件项。
- SHIP：本阶段只输出最终交付整理、发布检查、运行说明、风险说明和交接文档；未做代码修改、新增功能或重构。最终状态定为 `CONDITIONAL_READY`。

## 3. 最终变更清单

- 文档变更：
  - `.trae/documents/DEFINE_项目定义与真实现状报告.md`：更新项目真实现状、技术栈、核心链路、风险和后续方向。
  - `.trae/documents/BUILD_修复执行与代码变更报告.md`：记录 BUILD 真实执行范围、修改文件、P0/P1/P2 处理结果、验证命令和风险。
  - `.trae/documents/VERIFY_测试验证与Debug报告.md`：记录 VERIFY 执行环境、命令结果、核心链路验证、异常边界和未验证项。
  - `.trae/documents/REVIEW_商业级代码审查与质量兜底报告.md`：记录商业级代码审查结论、剩余风险和进入 SHIP 条件。
  - `.trae/documents/SHIP_最终交付与发布说明.md`：本阶段新增最终交付、发布检查、运行说明、回滚方案和风险交接文档。
- 代码与测试变更（来自 BUILD/VERIFY/REVIEW 汇总）：
  - `frontend/core.js`：新增全局 `setWsStatus()`，避免管理台初始化因未定义函数中断。
  - `frontend/styles.css`：增加 WebSocket 状态错误态样式。
  - `frontend/app.js`：本机管理台入口调用 `setupDebugPanel()`。
  - `frontend/dashboard-public.js`：缓存刷新改用统一 `api()`，自动携带 `X-API-Token`，并对公网禁止刷新给出提示。
  - `backend/version.py`：新增统一版本常量 `APP_VERSION`。
  - `backend/main.py`：FastAPI app 版本使用 `APP_VERSION`。
  - `backend/routers/system.py`：`/api/health`、`/api/debug/status` 版本统一。
  - `scripts/ci_check.py`：将两个关键 pytest 回归文件纳入 CI 编排。
  - `tests/test_dashboard_regression.py`：覆盖前端初始化、调试面板、Token 链路、版本一致性和 CI pytest 接入。
  - `backend/tools/full_test.py`：更新过时前端断言为缓存刷新 `api()` Token 断言，并修复 lint。
  - `backend/collectors/edge/_session.py`：补充异常链，解除 Ruff B904 阻断。
  - `tests/test_screen_readonly_hardening.py`：修复导入排序，解除 Ruff I001 阻断。
- 明确未修改项：
  - 未修改 README，不能将 README 写作已更新。
  - 未修改 `.env`、`data/shops.csv`、生产 Nginx 配置、FRP 配置、真实 Edge profile、SQLite 运行数据或 OCR/Edge 核心采集算法。

## 4. 最终修复问题清单

- 已修复 P0：
  - `setWsStatus` 未定义导致 `app.js` 初始化可能中断：已通过 `frontend/core.js`、`frontend/app.js`、`frontend/styles.css` 和回归测试修复。
  - `POST /api/dashboard-cache/refresh` 裸 `fetch` 不带 Token：已改为统一 `api()` 包装器，受控 Token 写接口验证通过。
- 已修复 P1：
  - `setupDebugPanel()` 定义后未在本机入口调用：已接入 `frontend/app.js`。
  - `/api/health`、`/api/debug/status` 与 app/pyproject 版本不一致：已通过 `backend/version.py` 统一为 `0.3.0`。
  - `scripts/ci_check.py` 未运行关键 pytest 回归：已将 `tests/test_dashboard_regression.py`、`tests/test_screen_readonly_hardening.py` 纳入 CI。
  - CI 范围内 Ruff/full_test 阻断：已完成最小修复并验证通过。
- 已修复 P2：
  - PLAN 与真实仓库冲突未记录：已在 BUILD 报告中明确说明以当前 DEFINE 和真实代码为准。
  - 测试产生 `data/shops_default.json` 运行态副作用：VERIFY 已撤回该副作用。
- 未修复/条件项：
  - 真实浏览器人工交互未验证。
  - 真实 Edge 登录态/平台页面采集未验证。
  - 公网 Nginx allowlist 未在真实公网入口验证。
  - `.venv` 缺少 `pytest`，影响本机虚拟环境复现。
  - 后端读接口和 `/ws/live` 默认无统一鉴权，生产安全仍依赖 Nginx allowlist 和端口不误暴露。
  - `/api/window-preview`、`/api/test-ocr` 未纳入写 Token 保护，部署层误放行时可能被滥用。
  - README、`package.json` 版本、FastAPI lifespan、前端全局脚本架构等 P2 事项未在本轮处理。

## 5. 最终测试与验证结果

- 已真实执行并通过：
  - `python -m pytest tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py`：`23 passed`，存在 FastAPI `on_event` deprecation 与 `python_multipart` pending deprecation warning。
  - `.venv\Scripts\ruff.exe check backend/main.py backend/routers/system.py backend/version.py backend/tools/full_test.py backend/collectors/edge/_session.py scripts/ci_check.py tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py`：通过，`All checks passed!`。
  - `python scripts/ci_check.py --with-api`：通过；包含 Ruff 通过、pytest `23 passed`、`full_test.py --skip-api` 为 `55/55 PASS`、`smoke_edge ok`、API smoke `14/14 PASS`。
  - 受控 API 验证：`/api/health`、`/api/config/public`、`/api/dashboard`、`/api/dashboard-datasets`、`/api/tasks` 均返回 200。
  - 受控页面验证：HTTP GET `/`、`/dashboard`、`/dashboard-test` 均返回 200，关键 JS 引用存在。
  - 受控 WebSocket 验证：`ws://127.0.0.1:8100/ws/live` 可连接并收到初始帧。
  - 受控 Token 验证：强制 `GMV_REQUIRE_API_TOKEN=true` 后，无 Token 写接口返回 401。
  - 受控错误路径验证：不存在任务、无效参数、MySQL 不可用等场景返回明确错误或稳定降级，不导致服务崩溃。
- 已知验证环境差异：
  - 系统 Python 可运行 pytest；`.venv` 中缺少 `pytest`，`.venv\Scripts\python.exe -m pytest ...` 未通过。
  - 系统 Python 无 Ruff 模块；Ruff 使用 `.venv\Scripts\ruff.exe` 验证通过。
  - 系统 Python 全局 `pip check` 存在与本项目无关的第三方包冲突；项目虚拟环境 `pip check` 通过。
- 明确未执行：
  - 未执行真实浏览器人工打开页面、查看 Console、点击调试面板、Token 保存/清空、缓存刷新、看板切换等交互验证。
  - 未执行真实 Microsoft Edge 登录态、平台大屏、页签扫描、启动/显示/隐藏/关闭、只读采集、OCR fallback 和随采集 WebSocket 刷新验证。
  - 未执行真实公网 Nginx allowlist 验证；本轮只验证了后端 Token 写接口保护与本机 HTTP 路径。

## 6. 最终运行说明

- 环境要求：
  - Windows 运行环境，目标机器需安装 Microsoft Edge。
  - Python `>=3.11`。
  - Playwright Chromium 浏览器依赖。
  - 可选：真实平台登录态、FRP 客户端、腾讯云 Nginx/FRP 服务端、MySQL 周期数据源。
- 安装依赖：
  - 建议在项目根目录创建并激活虚拟环境后执行：`pip install -r requirements.txt`。
  - 安装 Playwright 浏览器：`python -m playwright install chromium`。
  - 如果使用 `.venv` 运行 pytest，需确认 `.venv` 已安装 `pytest`；VERIFY 中发现当前 `.venv` 缺少 `pytest`。
- 配置说明：
  - 复制或维护 `.env`，按部署环境设置 `GMV_APP_ENV`、`GMV_REQUIRE_API_TOKEN`、`GMV_API_TOKEN`、`GMV_DEBUG_API_ENABLED`、`GMV_SCHEDULER_AUTOSTART`、`GMV_CORS_ORIGIN_REGEX` 和 `MYSQL_*`。
  - 生产/公网场景必须设置 `GMV_APP_ENV=production` 或 `GMV_REQUIRE_API_TOKEN=true`，并设置强随机 `GMV_API_TOKEN`。
  - 生产/公网场景建议设置 `GMV_DEBUG_API_ENABLED=false`。
  - 店铺配置主要来自 `data/shops.csv`；真实采集依赖 Edge 登录态、业务页和页面绑定状态。
  - 公网只读访问必须通过 Nginx allowlist 限制，只放行只读看板路径和必要静态/API 路径。
- 启动方式：
  - Windows 推荐入口：双击或执行 `第1步_启动GMV服务.bat`。
  - 开发/受控验证入口：`python -m uvicorn backend.main:app --host 127.0.0.1 --port 8100`。
  - 如需禁用调度器自启动进行验证，可设置 `GMV_SCHEDULER_AUTOSTART=false` 后启动。
  - 默认本机访问：`http://127.0.0.1:8100/`；公共看板路径：`http://127.0.0.1:8100/dashboard`。
- 测试方式：
  - pytest 回归：`python -m pytest tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py`。
  - Ruff 检查：`.venv\Scripts\ruff.exe check backend/main.py backend/routers/system.py backend/version.py backend/tools/full_test.py backend/collectors/edge/_session.py scripts/ci_check.py tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py`。
  - 完整 CI/API smoke：`python scripts/ci_check.py --with-api`。
  - 执行 API smoke 后需检查 `git status --short`，避免运行态数据副作用混入交付。
- 构建方式：
  - 前端无构建流程，HTML/CSS/JS 由 FastAPI 直接作为静态资源提供。
  - 后端无独立打包流程，本轮交付以 Python 源码、依赖文件和运行脚本为准。
  - `package.json` 当前不是有效前端构建入口，不应使用 npm 作为交付验证依据。
- 日志位置：
  - 应用日志位于 `logs/gmv_livelens.log`。
  - 排障时同时查看终端输出、服务日志、浏览器 Console、Network、Edge CDP 状态和 Nginx/FRP 日志。
- 常见问题：
  - 服务无法启动：检查 Python 版本、依赖安装、端口 `8100` 是否被占用、`.env` 是否存在非法配置。
  - pytest 在 `.venv` 失败：当前 VERIFY 发现 `.venv` 缺少 `pytest`，请执行 `pip install -r requirements.txt` 或使用已安装依赖的 Python。
  - Ruff 在系统 Python 失败：系统 Python 未安装 Ruff，可使用 `.venv\Scripts\ruff.exe`。
  - 页面 200 但无实时数据：检查调度器是否启动、店铺是否启用、Edge 登录态是否有效、任务是否绑定页面。
  - 公网刷新缓存失败：公网 Nginx 设计上应禁止写接口；管理员应在本机入口带 Token 操作。
  - 看板周期数据为空或不更新：检查 MySQL 配置、网络、周期缓存和 `data/.cache/period_gmv.json` 状态。

## 7. 发布前 Checklist

- [ ] 依赖：目标机器 Python `>=3.11`，已执行 `pip install -r requirements.txt`。
- [ ] 依赖：已执行 `python -m playwright install chromium`。
- [ ] 依赖：Microsoft Edge 已安装，真实平台登录态已准备。
- [ ] 配置：`.env` 已按生产/演示环境配置，不包含不应提交的敏感信息。
- [ ] 配置：生产/公网已设置 `GMV_APP_ENV=production` 或 `GMV_REQUIRE_API_TOKEN=true`。
- [ ] 配置：生产/公网已设置强随机 `GMV_API_TOKEN`，并确认管理员知道如何保存和轮换。
- [ ] 配置：生产/公网已设置 `GMV_DEBUG_API_ENABLED=false`。
- [ ] 端口：`127.0.0.1:8100` 可用，未被其他服务占用。
- [ ] 端口：公网场景未直接暴露 Windows 后端端口。
- [ ] 数据：`data/shops.csv` 店铺配置、目标值、启用状态和业务页配置已确认。
- [ ] 数据：SQLite、缓存、Edge profile、截图等运行态文件已完成备份策略确认。
- [ ] 服务：`第1步_启动GMV服务.bat` 或 uvicorn 命令可启动服务。
- [ ] 服务：`/api/health` 返回 200 且版本为 `0.3.0`。
- [ ] 核心功能：本机管理台真实浏览器 Console 无错误。
- [ ] 核心功能：调试面板可打开，Token 保存/清空可用。
- [ ] 核心功能：真实 Edge 可启动、显示、隐藏、关闭和扫描页签。
- [ ] 核心功能：至少一个真实平台登录态页面完成只读采集或 OCR fallback 验证。
- [ ] 核心功能：WebSocket 在真实采集数据变化时可刷新看板。
- [ ] 测试：pytest `23 passed`。
- [ ] 测试：Ruff 通过。
- [ ] 测试：`python scripts/ci_check.py --with-api` 通过。
- [ ] 测试：API smoke `14/14 PASS`。
- [ ] 公网：Nginx allowlist 已真实验证，只读路径 200，管理/写接口 403。
- [ ] 敏感信息：`.env`、真实 FRP 配置、SQLite、Edge profile、截图、密钥文件未被提交或公开。
- [ ] 文档：DEFINE、PLAN、BUILD、VERIFY、REVIEW、SHIP 文档均存在且交付状态一致。
- [ ] 文档：交付对象已知晓当前为 `CONDITIONAL_READY`，不是完全生产就绪。
- [ ] 回滚：已准备上一可用版本、配置备份、数据备份和端口/进程恢复步骤。

## 8. 回滚方案

- 启动失败：
  - 查看终端输出和 `logs/gmv_livelens.log`。
  - 检查 Python 版本、依赖、`.env`、端口 `8100`、Playwright 浏览器安装。
  - 回退到上一可用代码版本或恢复上一份 `.env` 配置后重启。
- 核心功能异常：
  - 先确认 `/api/health`、`/api/dashboard`、`/api/tasks`、`/ws/live` 是否正常。
  - 若前端初始化异常，重点检查 `frontend/core.js`、`frontend/app.js`、`frontend/dashboard-public.js` 与浏览器 Console。
  - 若 Edge 采集异常，先切换为暂停采集或关闭对应任务，保留看板只读展示，再检查 Edge 登录态、页面绑定、CDP 端口和平台页面结构。
- 配置错误：
  - 恢复上一份 `.env`、Nginx、FRP、`data/shops.csv` 和 Edge profile 配置。
  - 生产 Token 配置错误时，重新设置 `GMV_API_TOKEN` 并重启服务，不在公网共享 Token。
- 依赖失败：
  - 重新执行 `pip install -r requirements.txt` 和 `python -m playwright install chromium`。
  - 若 `.venv` 损坏或缺少 pytest，可重建虚拟环境或使用 CI/系统 Python 进行验证。
  - 确认 `.venv\Scripts\ruff.exe`、pytest、FastAPI、Uvicorn、Playwright 均可用。
- 部署异常定位：
  - 本机先验证 `http://127.0.0.1:8100/api/health`。
  - 再验证 FRP 链路和腾讯云 Nginx 日志。
  - 最后验证公网入口 allowlist：`/dashboard`、`/static/`、`/api/dashboard`、`/api/dashboard-datasets`、`/api/health` 应可访问；管理和写接口应返回 403。
  - 若公网存在误暴露，立即关闭 FRP/Nginx 转发或收紧 allowlist，再检查 Windows 后端端口是否只监听本机。

## 9. 剩余风险

- P0：
  - 当前未发现 P0 阻塞问题。
- P1：
  - 真实浏览器交互未验证，调试面板、Token 保存/清空、缓存刷新按钮、页面切换和 Console 仍需人工确认。
  - 真实 Edge 登录态/平台页面采集未验证，启动、显示、隐藏、关闭、页签扫描、只读采集、OCR fallback 和 WebSocket 随采集刷新仍需人工确认。
  - 公网 Nginx allowlist 未真实验证，必须在腾讯云入口确认只读路径 200、管理/写接口 403。
  - `.venv` 缺少 `pytest`，与 `requirements.txt` 和 CI 预期不一致，影响本机复现。
  - 后端读接口和 `/ws/live` 默认无统一鉴权，若 Windows 端口、FRP 或 Nginx 误暴露，会泄露运行态信息或实时数据。
  - `/api/window-preview`、`/api/test-ocr` 未纳入写 Token 保护，部署层误放行时可能造成资源消耗风险。
- P2：
  - `package.json` 版本仍为 `1.0.0`，后端版本为 `0.3.0`，版本口径不统一。
  - FastAPI `@app.on_event` deprecation warning 仍存在，后续应迁移到 lifespan。
  - README 仍包含旧描述，不能作为本轮交付事实来源。
  - 前端全局脚本依赖加载顺序，长期维护和测试成本较高。
  - 管理员 Token 存在浏览器 `localStorage`，不适合在公网共享设备保存。
  - MySQL/周期缓存降级在用户界面提示不足，运维可能误判为业务波动。
  - `backups/` 和历史文档较多，后续搜索和交接容易混淆。

## 10. 后续版本建议

- 必须尽快处理：
  - 完成真实浏览器人工交互验证，并记录 Console、Network、关键点击路径和截图。
  - 完成真实 Edge 登录态/平台页面采集验证，至少覆盖启动/显示/隐藏/关闭、页签扫描、只读采集、OCR fallback 和 WebSocket 刷新。
  - 完成真实公网 Nginx allowlist 验证，确认只读路径可访问、管理/写接口被 403 阻断。
  - 同步 `.venv` 依赖，确保 `pip install -r requirements.txt` 后 pytest、Ruff、Playwright 可复现。
  - 制定后端读接口和 `/ws/live` 的生产安全兜底策略，降低部署误暴露风险。
- 建议近期处理：
  - 更新 README，删除或修正前端模块数量等过时描述。
  - 统一 `package.json` 与后端版本口径，或明确 package.json 不参与发布版本。
  - 将 FastAPI startup/shutdown 迁移到 lifespan，消除 deprecation warning。
  - 增加公网 allowlist、Token 策略、真实浏览器关键路径的自动化或半自动化验证。
  - 增强 MySQL/周期缓存降级提示，让运维能区分外部数据源失败和真实业务波动。
- 长期优化方向：
  - 拆分公共看板和本机管理台入口，降低公网只读页面暴露管理 DOM 的风险。
  - 推进前端模块化、类型检查和浏览器端自动化测试。
  - 规范 `data/` 运行态、缓存、截图、Edge profile、密钥和可提交配置的边界。
  - 建立采集 SLA、平台失败分类、缓存新鲜度、MySQL 状态和告警体系。
  - 评估 Edge/平台采集能力的插件化边界，降低新增平台和页面结构变更成本。

## 11. 商业化交付判断

| 维度 | 状态 | 说明 |
|------|------|------|
| 可启动 | 有条件通过 | 受控 uvicorn 启动、健康检查和 CI smoke 通过；真实 Windows + Edge 完整运行仍需人工确认。 |
| 可验证 | 有条件通过 | pytest、Ruff、CI、API smoke、受控 API/页面/WebSocket/Token/错误路径通过；真实浏览器、真实 Edge、公网未验证。 |
| 可维护 | 有条件通过 | 后端分层清晰，关键回归已纳入 CI；前端全局脚本、README 过时和历史文件仍增加维护成本。 |
| 可排障 | 有条件通过 | 有日志、request id、调试面板和受控错误路径；真实平台采集失败分类、MySQL 降级提示和公网链路观测仍需加强。 |
| 可配置 | 有条件通过 | `.env`、`data/shops.csv`、Token 和部署配置路径明确；生产安全依赖正确配置和 allowlist。 |
| 可交接 | 有条件通过 | 六阶段文档齐全，本 SHIP 报告给出运行、测试、风险和回滚说明；README 仍不能作为唯一交接依据。 |
| 可部署 | 有条件通过 | 本机服务、FRP + Nginx 部署设计存在；真实公网 allowlist 和真实 Edge 采集未完成发布前验证。 |

## 12. 最终结论

- 是否可以交付：可以有条件交付，最终状态为 `CONDITIONAL_READY`。
- 交付时必须说明的风险：真实浏览器人工交互、真实 Edge 登录态/平台采集、公网 Nginx allowlist 尚未验证；后端读接口和 `/ws/live` 默认无统一鉴权，公网安全依赖正确的 Nginx allowlist、Token 配置和端口不误暴露；当前 `.venv` 缺少 `pytest`，本机复现需先同步依赖。
- 后续第一优先级：完成真实环境验收闭环，优先顺序为真实浏览器交互验证、真实 Edge/平台采集验证、公网 Nginx allowlist 验证，并同步 `.venv` 依赖以保证验证命令可复现。
- 是否存在阻塞：当前未发现 P0 阻塞问题；存在 P1 条件项，阻止标记为无条件 `READY`，但不阻止在明确风险告知下进行有条件交付。
