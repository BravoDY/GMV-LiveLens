# REVIEW_商业级代码审查与质量兜底报告

## 1. 本阶段最终结论
- **CONDITIONAL_PASS**。
- 本阶段已读取并确认存在 `DEFINE_项目定义与真实现状报告.md`、`PLAN_修复计划与商业化落地路线.md`、`BUILD_修复执行与代码变更报告.md`、`VERIFY_测试验证与Debug报告.md`。
- 未发现明确 P0；未做新增代码修复。
- BUILD 修复点与当前代码基本一致：`setWsStatus()`、`setupDebugPanel()`、缓存刷新 Token、`APP_VERSION` 统一、pytest 纳入 CI 均可从代码和 VERIFY 结果中确认。
- 自动化验证可信度较高，但真实浏览器交互、真实 Edge 登录态/平台采集、公网 Nginx allowlist 未完成验证，因此不应写成无条件 PASS。
- 建议可以进入 SHIP，但必须带人工验证清单和生产部署风险说明。

## 2. 架构审查结果
- 后端仍保持 `main.py` 组合根、`core/` 基础设施、`routers/` 路由、`services/` 业务服务、`collectors/` 采集底层的分层结构，依赖方向整体清晰。
- `backend/main.py` 只负责加载配置、注册中间件、挂载静态资源、注册路由和生命周期，入口职责收敛。
- `backend/routers/system.py` 同时包含页面入口、健康检查、设置、调度器、看板和 WebSocket，职责偏多但尚未形成阻塞；更适合后续按 `pages/system/realtime` 拆分。
- 前端仍为 8 个全局脚本按顺序加载，`core.js` 提供全局状态、API 包装、WebSocket、任务辅助函数；`app.js` 作为入口依赖多个全局函数。该模式短期可交付，长期维护风险较高。
- 当前较大的维护风险集中在 `frontend/core.js`、`backend/tools/full_test.py`、`backend/routers/system.py`、`backend/routers/edge_sessions.py` 等文件；本阶段不建议拆分，以免扩大变更面。
- 未发现新增循环依赖。路由层调用 `services/collectors/core`，采集层未反向依赖路由层。
- `backups/` 和历史文档会干扰搜索认知，属于 P2 维护风险；本阶段只记录。

## 3. 业务逻辑审查结果
- 输入链路：`data/shops.csv` 仍是主要店铺配置来源，服务启动时通过 `store.sync_tasks_with_shop_configs()` 同步任务；当前审查未修改 `data/shops.csv`。
- 处理链路：调度器、Edge CDP、只读大屏读取、OCR、SQLite 采样、看板聚合仍按 DEFINE 描述闭环运行；BUILD 未触碰核心采集算法和 Edge 核心采集逻辑。
- 输出链路：`/api/dashboard`、`/api/dashboard-datasets`、`/api/health`、`/ws/live` 与前端看板字段基本对齐，VERIFY 已通过受控 API/页面/WebSocket 验证。
- 缓存刷新链路已从裸 `fetch` 改为 `api()`，可自动携带 `X-API-Token`；公网入口仍由 Nginx 对 `POST /api/dashboard-cache/refresh` 返回 403。
- `APP_VERSION` 已成为后端 app、`/api/health`、`/api/debug/status` 的统一来源，并与 `pyproject.toml` 的 `0.3.0` 对齐。
- `package.json` 仍为 `1.0.0`，与后端版本 `0.3.0` 不一致。该文件当前不是实际构建入口，但会误导交付版本识别，列为 P2。
- 真实业务理想路径仍未完整闭环验证：真实浏览器点击、真实 Edge 登录态、真实平台页面只读采集、真实公网 allowlist 均未验证。

## 4. 代码质量审查结果
- BUILD 改动整体克制，集中在前端初始化、调试面板、Token 请求链路、版本常量和 CI 回归，符合“不无边界开发”的要求。
- `frontend/core.js` 新增 `setWsStatus(text, tone = "ok")`，处理 DOM 缺失时直接返回，避免旧的未定义函数导致初始化中断。
- `frontend/app.js` 在本机入口调用 `setupDebugPanel()`，且用 `typeof` 判断，低风险。
- `frontend/dashboard-public.js` 的缓存刷新使用 `api("/api/dashboard-cache/refresh", { method: "POST", cache: "no-store" })`，与现有 API 包装器一致。
- `scripts/ci_check.py` 新增 `PYTEST_REGRESSION_FILES`，将两个关键 pytest 文件纳入 CI，结构清晰。
- `backend/version.py` 仅提供 `APP_VERSION = "0.3.0"`，简单直接，但后续若进入发布流程建议由单一配置源生成或校验。
- 代码中未发现 `eval()`、`exec()`、`pickle.load()`、`os.system()`、`shell=True`。Edge 与 CI 的 `subprocess` 均采用参数列表。
- 前端测试以静态字符串断言为主，能防止本轮回归，但无法替代真实浏览器交互测试。
- 旧 REVIEW 报告内容与当前事实不一致，本阶段已整体更新报告，避免交付文档误导。

## 5. 稳定性审查结果
- 启动链路仍使用 FastAPI + Uvicorn，`GMV_SCHEDULER_AUTOSTART` 可禁用调度器，VERIFY 已用受控环境验证临时服务启动。
- `backend/main.py` 仍使用 `@app.on_event("startup")` 和 `@app.on_event("shutdown")`，FastAPI deprecation warning 已在 VERIFY 中出现；当前不影响运行，列为 P2 后续迁移到 lifespan。
- `.venv` 缺少 `pytest`，导致优先虚拟环境 pytest 命令失败；系统 Python 可运行 pytest，CI 安装 `requirements.txt` 后应具备 pytest。该问题影响本机复现一致性，列为 P1 环境风险。
- `scripts/ci_check.py --with-api` 会启动临时服务并执行 smoke，VERIFY 已观察到可能写入 `data/shops_default.json` 的运行态副作用；VERIFY 已撤回，但后续执行仍需检查 `git status`。
- MySQL 不可用时 `/api/dashboard` 已在受控验证中返回 200，不因外部数据源失败崩溃；但看板对周期数据降级的用户可见提示仍有限，列为 P2。
- WebSocket `/ws/live` 已受控验证可连接并收到帧；真实采集过程中的持续推送仍未人工验证。
- Edge 操作大量依赖 Windows、真实 Edge、登录态和平台页面结构，自动化只覆盖 smoke 层，商业交付前必须人工确认。

## 6. 安全与配置审查结果
- 写接口保护依赖 `WriteTokenMiddleware`，在 `GMV_APP_ENV=production` 或 `GMV_REQUIRE_API_TOKEN=true` 时对 `POST/PUT/PATCH/DELETE` 且命中敏感路径前缀的请求校验 `X-API-Token`。
- 当前敏感写前缀覆盖 `/api/settings`、`/api/scheduler/*`、`/api/tasks*`、`/api/shops/init`、`/api/shops/bind`、`/api/edge-sessions*`、`/api/platforms*`、`/api/dashboard-cache/refresh`，与主要写操作匹配。
- `/api/window-preview`、`/api/test-ocr` 属于 POST 但未列入敏感写前缀；它们更偏诊断/计算接口，公网 Nginx 默认 403 阻断。若后端端口被误暴露，仍可能被滥用消耗资源，列为 P1 安全边界风险。
- 后端读接口和 `/ws/live` 默认无统一鉴权，公网安全主要依赖 Nginx allowlist；这与 DEFINE/VERIFY 的已知事实一致，是进入 SHIP 前必须强调的主要风险。
- `deploy/nginx/snippets/gmv-livelens-public-locations.conf` 只放行 `/dashboard`、`/static/`、`/api/dashboard`、`/api/dashboard-datasets`、`/api/health`、`/favicon.ico`，并对 `/api/dashboard-cache/refresh` 与其他路径返回 403；配置设计符合只读公网入口目标，但 VERIFY 未在真实公网执行。
- `frontend/core.js` 将 API Token 存在 `localStorage`。对本机管理员工具可接受，但不应在公网共享浏览器上保存管理员 Token，列为 P2 使用规范风险。
- `backend/collectors/edge/_session.py` 的 `_validate_user_data_dir()` 只拒绝 `..` 路径遍历，未强制限制到 `data/edge_profiles`。由于 Edge 会话写接口在生产需 Token，本阶段不作为 P0；后续可增加路径白名单或显式 real_profile 例外。
- `.gitignore` 已排除 `.env`、生产 env、FRP 实际配置、SQLite、日志、Edge profiles、截图、MySQL 密钥文件等敏感运行态文件。

## 7. 测试可信度审查结果
- VERIFY 最终为 `CONDITIONAL_PASS`，不是无条件 PASS；该结论合理。
- 已可信验证：`python -m pytest tests/test_dashboard_regression.py tests/test_screen_readonly_hardening.py` 通过，`23 passed`；`.venv\Scripts\ruff.exe check ...` 通过；`python scripts/ci_check.py --with-api` 通过；受控 API/页面/WebSocket/Token/错误路径验证通过。
- CI 现在会运行两个关键 pytest 回归文件，修复了此前“只被 Ruff 检查但未执行断言”的缺口。
- 测试仍有明显边界：缺少真实浏览器控制台/点击交互验证，缺少真实 Edge 登录态和平台页面采集验证，缺少真实公网 Nginx allowlist 验证。
- 前端多数回归是静态文件断言，能覆盖加载顺序和关键字符串，但无法发现运行时 DOM 事件绑定、真实点击、控制台错误和 CSS 隐藏失效。
- `.venv` 缺少 `pytest` 与 `requirements.txt` 声明不一致，说明本机虚拟环境未完全同步；进入 SHIP 前需说明验证命令应以 CI 或已安装依赖的 Python 为准。
- 本阶段未重复跑完整 VERIFY，因为未做代码修复，符合用户要求。

## 8. 商业化交付能力评估
| 维度 | 评分 1-5 | 结论 | 主要问题 |
|------|----------|------|----------|
| 可启动性 | 4 | 条件可交付 | 受控启动和 CI smoke 通过；真实 Windows + Edge 运行仍需人工确认。 |
| 可维护性 | 3 | 可维护但偏脆 | 后端分层清楚；前端全局脚本、大文件和历史备份目录增加维护成本。 |
| 可排障性 | 4 | 基本可排障 | 有 request id、Edge 错误详情、调试面板；真实平台采集失败分类仍需加强。 |
| 可扩展性 | 3 | 可扩展但成本高 | 新平台需改只读解析/OCR/配置，缺少插件化边界。 |
| 可测试性 | 4 | 自动化可信 | pytest、Ruff、full_test、smoke_api 已纳入 CI；真实浏览器/公网未自动化。 |
| 配置规范性 | 3 | 基本规范 | `.gitignore` 和 env example 可用；`.venv` 依赖未同步，版本源仍不完全一致。 |
| 日志完整性 | 4 | 基本完整 | 请求和 Edge 异常日志可定位；MySQL 降级、缓存新鲜度、采集 SLA 缺少统一观测。 |
| 异常处理 | 4 | 较稳健 | API 错误路径和受控 MySQL 失败通过；真实 Edge 复杂失败仍需人工场景验证。 |
| 文档一致性 | 3 | 阶段文档较新 | README 仍有前端模块数量等旧信息，旧 REVIEW 已由本报告修正。 |
| 交付成熟度 | 3 | 可进入 SHIP 但需带风险 | 自动化通过；真实 Edge/公网/浏览器人工验证是交付前条件项。 |

总体评分：**3.5 / 5**。达到可进入 SHIP 的条件，但属于带明确人工验证项的商业化交付，不适合宣称完全生产就绪。

## 9. 本阶段新增修复
无。

本阶段只更新审查报告：`.trae/documents/REVIEW_商业级代码审查与质量兜底报告.md`。未修改业务代码、测试代码、配置、`.env`、`data/shops.csv`、运行态数据或 Edge 核心采集逻辑；因此未重新运行完整 VERIFY。

## 10. 剩余问题清单
### P0
- 无新增 P0。

### P1
- `.venv` 缺少 `pytest`，与 `requirements.txt` 和 CI 预期不一致，影响本机验证复现。
- 真实浏览器交互未验证：调试面板、Token 保存/清空、刷新缓存按钮、页面切换、控制台错误仍需人工确认。
- 真实 Edge 登录态/平台页面采集未验证：启动、显示、隐藏、关闭、页签扫描、只读采集、OCR fallback 和 WebSocket 随采集刷新均需人工确认。
- 公网 Nginx allowlist 未真实验证：必须在腾讯云入口确认只读路径 200、管理/写接口 403。
- 后端读接口和 `/ws/live` 无统一鉴权，若 Windows 端口、FRP 或 Nginx 误暴露，会泄露运行态信息或实时数据。
- `/api/window-preview`、`/api/test-ocr` 未纳入写 Token 保护，部署层误放行时可能被滥用为资源消耗接口。

### P2
- `package.json` 版本仍为 `1.0.0`，后端版本为 `0.3.0`，交付版本口径不统一。
- FastAPI `@app.on_event` deprecation warning 仍存在，后续应迁移到 lifespan。
- README 仍包含“前端 5 个模块文件”等旧描述，与当前 8 个主 JS 模块不一致。
- 前端全局脚本架构依赖加载顺序，长期维护和回归定位成本较高。
- `localStorage` 保存管理员 Token 需要使用规范，不应在公网共享设备保存。
- `_validate_user_data_dir()` 未强制限制 isolated profile 在 `data/edge_profiles` 下，后续可增强路径白名单。
- MySQL/周期缓存降级在用户界面上的可见提示不足，运维可能误判为业务波动。
- `backups/` 和历史 `.trae/documents/` 文件较多，后续搜索和交接容易混淆。

## 11. 是否建议进入 SHIP
**建议进入 SHIP，但状态必须标注为 `CONDITIONAL_PASS`。**

依据：未发现明确 P0；BUILD 关键修复点已通过代码审查和 VERIFY 自动化验证；CI、pytest、Ruff、API smoke、受控 WebSocket 与 Token 保护均有可信结果。

进入 SHIP 前必须注意：
- 不要把当前状态描述为完全生产 PASS，应说明真实 Edge、真实浏览器、公网 allowlist 尚未验证。
- SHIP 报告必须附人工验证清单：本机管理台交互、真实 Edge 登录态采集、公网只读路径和 403 阻断。
- 发布口径应说明 `.venv` 缺少 `pytest` 的环境风险，并建议同步依赖或以 CI Python 为准。
- 生产部署必须设置 `GMV_APP_ENV=production`、`GMV_REQUIRE_API_TOKEN=true`、强随机 `GMV_API_TOKEN`、`GMV_DEBUG_API_ENABLED=false`，并确认 Nginx 只读 allowlist 生效。
