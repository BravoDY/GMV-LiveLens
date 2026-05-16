# GMV-LiveLens 审计问题清单（含证据链）

> 审计时间：2026-05-05 | 每项均有代码证据

---

## BUG-001

| 字段 | 内容 |
|---|---|
| **问题编号** | BUG-001 |
| **问题等级** | P1 |
| **问题类型** | 后端 / 逻辑 |
| **问题描述** | `_ensure_capture_task_shop_uniqueness` 函数在 `return dedupe_result` 之后还有 12 行代码（修正 edge_sessions.session_mode 字段的 UPDATE 语句），这些代码**永远不会执行**（死代码），导致 `default_real_edge` 如果以错误的 `session_mode` 存入 DB，将永远无法被自动修正。 |
| **影响范围** | `default_real_edge` 会话的 session_mode 可能长期为 'isolated' 而非 'real_profile'，导致 RemoteEdge 用错误的隔离模式连接；任何 session_mode 为 null 或空字符串的会话也无法被自动修正。 |
| **代码位置** | `backend/services/store.py:235-256` |
| **复现方式** | 1. 查看 store.py:241 `return dedupe_result` 之后的代码；2. 搜索这段 UPDATE edge_sessions 代码是否在任何其他地方被调用 → 否。 |
| **实际结果** | session_mode 修正 UPDATE 永不执行 |
| **预期结果** | `_ensure_capture_task_shop_uniqueness` 应在创建唯一索引后，修正所有 null/空 session_mode；`default_real_edge` 应确保 session_mode = 'real_profile' |
| **证据** | `store.py:235-256`：`return dedupe_result` 在 line 241，之后是 `session_rows = conn.execute(...)` 等死代码；`_ensure_default_edge_session` 只 INSERT 不 UPDATE（line 275-296 `if row: continue`）；`normalize_session_mode` 对合法值原样返回（'isolated' → 'isolated'），不会自动纠正。 |
| **根因分析** | 函数在重构过程中提前加了 return，但迁移代码没有被删除，形成死代码。`_ensure_default_edge_session` 也没有更新已有记录的逻辑，两处同时缺失导致修复链断裂。 |
| **修复建议** | 将死代码的 UPDATE 逻辑移到 `_ensure_default_edge_session` 中，改为"不存在则插入，存在则更新 session_mode"；或单独创建 `_ensure_session_mode_correct(conn)` 函数并在 init_db 中调用。 |
| **修复风险** | 低。只修改 `session_mode` 字段，不影响其他字段；添加 UPDATE 语句幂等安全。 |
| **是否建议立即修复** | 是 |
| **是否需要确认** | 否 |

---

## BUG-002

| 字段 | 内容 |
|---|---|
| **问题编号** | BUG-002 |
| **问题等级** | P1 |
| **问题类型** | 配置 / 数据 |
| **问题描述** | `data/shops_default.json` 是 shops.csv 解析失败时的备用数据源。该 JSON 包含过期的 legacy 数据：`edge_session_id: "taobao_group"`（已废弃的分组 session），`debug_port: null`，缺少 `target`、`sort_order` 字段。如果 shops.csv 损坏或被删除，`/api/shops` 返回错误数据，前端 `shopConfigForTask()` 将无法匹配任何任务，导致任务全部从 UI 消失。 |
| **影响范围** | `/api/shops` 返回值；前端 `shopConfigForTask` 匹配；任务管理列表、实时看板、采集配置工作台均依赖此数据 |
| **代码位置** | `backend/main.py:1908-1918 (_load_shops_default)`, `data/shops_default.json` |
| **复现方式** | 1. 备份 shops.csv，临时删除；2. 重启服务；3. 访问 `/api/shops` → 返回包含 `edge_session_id: "taobao_group"` 的数据；4. 前端 shop 配置与实际任务不匹配 |
| **实际结果** | JSON 中 `edge_session_id: "taobao_group"`, `debug_port: null`，`target` 字段缺失 |
| **预期结果** | 备用 JSON 应与实际 shops.csv 数据结构一致，使用正确的 edge_session_id（如 `天猫_迪桑特天猫官方旗舰店`）和 debug_port |
| **证据** | `shops_default.json` 第一条记录：`"edge_session_id": "taobao_group"`, `"debug_port": null`；`_LEGACY_GROUP_SESSIONS = ("taobao_group", "jd_group", "douyin_group", "other_group")` 明确标记为废弃 |
| **根因分析** | shops_default.json 在项目迁移到独立 Edge 会话模式前生成，未随代码更新同步。 |
| **修复建议** | 重新生成 shops_default.json：让服务在 shops.csv 存在时运行 `GET /api/shops`，将结果保存为新的 shops_default.json；或删除 shops_default.json 备用机制，改为在 CSV 缺失时明确报错。 |
| **修复风险** | 低。shops_default.json 仅在 CSV 失败时使用。 |
| **是否建议立即修复** | 是 |
| **是否需要确认** | 否 |

---

## BUG-003

| 字段 | 内容 |
|---|---|
| **问题编号** | BUG-003 |
| **问题等级** | P1 |
| **问题类型** | 部署 / 配置 |
| **问题描述** | `requirements.txt` 缺少 `ddddocr`。代码中 `ocr_reader.py` 明确导入并使用 ddddocr（`importlib.util.find_spec("ddddocr")`，`_dddd_engine()` 函数）。`.venv` 中已安装，但 `pip install -r requirements.txt` 不会安装它。新环境部署时，若用 requirements.txt 安装依赖后选择 ddddocr 引擎，调用将失败。 |
| **影响范围** | 新环境部署；选择 ddddocr 作为 OCR 引擎时 |
| **代码位置** | `requirements.txt`, `backend/collectors/ocr_reader.py:48,79-81` |
| **复现方式** | 新环境 `pip install -r requirements.txt` → `python -c "import ddddocr"` → ImportError |
| **实际结果** | requirements.txt 无 ddddocr 条目 |
| **预期结果** | requirements.txt 应包含 `ddddocr>=0.9` 或固定版本 |
| **证据** | requirements.txt 全文 11 行（已读取），无 ddddocr；`.venv/Scripts/ddddocr.exe` 存在（已扫描） |
| **根因分析** | 可能通过手动 `pip install ddddocr` 安装但未写入 requirements.txt |
| **修复建议** | 在 requirements.txt 中添加 `ddddocr` 条目（可检查 `.venv` 中的版本号后固定） |
| **修复风险** | 极低 |
| **是否建议立即修复** | 是 |
| **是否需要确认** | 否 |

---

## BUG-004

| 字段 | 内容 |
|---|---|
| **问题编号** | BUG-004 |
| **问题等级** | P1 |
| **问题类型** | 逻辑 / 前端 |
| **问题描述** | `GET /api/tasks` 在每次调用时触发 `lightweight_reconcile_and_auto_restore()`（自愈检查）。前端 WebSocket 断线降级为轮询时，每 2 秒调用一次 `GET /api/tasks`，导致每 2 秒触发一次跨所有 Edge 会话的自愈检查，包括逐个调用 `client.debug_available_quick()`（每次 1.5s HTTP 超时）和 `list_pages()`（15s 超时）。在 Edge 未运行或网络慢时，此操作可能导致 GET /api/tasks 本身超时，前端显示持续"连接失败"。 |
| **影响范围** | WS 断线后的轮询降级场景；任务管理页面首次加载（调用 GET /api/tasks） |
| **代码位置** | `backend/main.py:1530-1535` |
| **复现方式** | 1. 关闭所有 Edge；2. 断开 WebSocket（强制降级轮询）；3. 观察 GET /api/tasks 响应时间，可能因 debug_available_quick() 每个会话 1.5s 超时而大幅延迟。 |
| **实际结果** | GET /api/tasks 每次都触发 N 个 Edge 会话的健康检查 |
| **预期结果** | GET /api/tasks 应该快速返回快照，自愈检查应该异步或在后台执行 |
| **证据** | `main.py:1531-1535`：`recovery_report = await lightweight_reconcile_and_auto_restore()` 在 `GET /api/tasks` 同步执行；`lightweight_reconcile_and_auto_restore` 内部对每个 session 调用 `client.debug_available_quick()` |
| **根因分析** | 自愈检查逻辑被嵌入了数据读取 API，未分离关注点 |
| **修复建议** | 将 `lightweight_reconcile_and_auto_restore()` 从 `GET /api/tasks` 中移出，改为通过独立定时器（30s 间隔）或 WS 连接事件触发；`GET /api/tasks` 只返回 `build_snapshot()` |
| **修复风险** | 中。需要在前端对应调整（移除对 `binding_recovery` 字段的依赖，或改为独立 API 触发）。 |
| **是否建议立即修复** | 是 |
| **是否需要确认** | 是（需确认前端是否使用 binding_recovery 字段） |

---

## BUG-005

| 字段 | 内容 |
|---|---|
| **问题编号** | BUG-005 |
| **问题等级** | P1 |
| **问题类型** | 逻辑 / 后端 |
| **问题描述** | `scheduler.py` 调度循环在每个 tick 对每个任务独立读取全局采集间隔设置：`global_interval = float(store.get_setting("interval_seconds", "0.5"))`。这意味着在 0.5s 间隔、11 个任务的情况下，每秒 22 次 DB 读取仅用于获取同一个设置值。且每次读取均打开新的 SQLite 连接（`connect()`）。 |
| **影响范围** | 调度循环性能；SQLite 连接创建频率；CPU/IO 开销 |
| **代码位置** | `backend/services/scheduler.py:91` |
| **复现方式** | 启动服务，`lsof -p <pid>` 或监控 SQLite 连接数，可见高频打开关闭。 |
| **实际结果** | 每次循环每任务独立读 DB 设置 |
| **预期结果** | 应在每次循环外读一次（`global_interval = float(store.get_setting(...))` 移到 tasks 循环外） |
| **证据** | `scheduler.py:83-93` 循环体内，第 91 行在 `for task in tasks` 内调用 `store.get_setting` |
| **根因分析** | 代码嵌套层级未注意，将全局设置读取放在了 task 级别的循环内 |
| **修复建议** | 将 `global_interval` 移到 `for task in tasks` 循环外，在循环开始前读取一次 |
| **修复风险** | 极低。纯代码位置调整，逻辑不变。 |
| **是否建议立即修复** | 是 |
| **是否需要确认** | 否 |

---

## BUG-006

| 字段 | 内容 |
|---|---|
| **问题编号** | BUG-006 |
| **问题等级** | P2 |
| **问题类型** | 逻辑 / 数据 |
| **问题描述** | 前端 `managerFilteredTasks()` 和 `liveTasks()` 均使用 `shopConfigForTask(task)` 过滤：若任务的 `platform + shop_name` 不在 `/api/shops` 返回的 shopConfigs 中，该任务在任务管理、实时看板均不可见（"任务黑洞"）。这意味着手动创建的任务、或者 CSV 中已删除但 DB 中仍存在的历史任务，会从 UI 完全消失，但仍在 DB 中被调度采集。 |
| **影响范围** | 任务管理列表；实时看板；采集配置工作台 |
| **代码位置** | `frontend/core.js:293-295, 347-350, 441-443` |
| **复现方式** | 在 DB 中手动插入一条 platform='测试平台' 的任务，刷新前端 → 该任务不在任务管理列表中显示，但调度器仍会对它执行采集。 |
| **实际结果** | 不在 shopConfigs 的任务完全不可见 |
| **预期结果** | 不在 shopConfigs 的任务至少应在任务管理中可见（带标记），或有 UI 提示存在孤立任务 |
| **证据** | `core.js:294` `liveTasks()` 中 `shopConfigForTask(task)` 过滤；`core.js:347-350` `shopConfigForTask` 实现为精确 platform+shop_name 匹配 |
| **根因分析** | 设计上 shopConfig 是任务的"规格书"，没有规格书的任务被认为不应展示。但没有防范 CSV 变更导致任务孤立的场景。 |
| **修复建议** | 在任务管理中额外显示"孤立任务"（shopConfig 为 null 的任务），带警告标签；或在 `/api/tasks` 响应中增加 `orphan_tasks` 字段 |
| **修复风险** | 低。仅影响 UI 展示，不影响后端逻辑。 |
| **是否建议立即修复** | 建议修复 |
| **是否需要确认** | 是（需确认业务方是否有意隐藏孤立任务） |

---

## BUG-007

| 字段 | 内容 |
|---|---|
| **问题编号** | BUG-007 |
| **问题等级** | P2 |
| **问题类型** | 部署 / 逻辑 |
| **问题描述** | `shop_config.py` 中 `DEFAULT_PORT_BASE + index * 10` 计算非天猫/京东/抖音平台的 debug_port，端口号依赖 CSV 行序（`index` 是 enumerate 的序号）。若 CSV 中行顺序变化（新增或删除行），未配置 debug_port 的店铺会获得不同的端口号，导致现有 Edge 会话端口错误，需要重新启动 Edge。 |
| **影响范围** | 非天猫/京东/抖音平台的 Edge 会话端口稳定性 |
| **代码位置** | `backend/services/shop_config.py:194-195` |
| **证据** | `shop_config.py:194-195`：`base = PLATFORM_PORT_BASE.get(key, DEFAULT_PORT_BASE + index * 10)` |
| **修复建议** | 要求在 CSV 中为每个店铺明确填写 debug_port；或使用 shop_name 的哈希值计算固定端口 |
| **修复风险** | 中。修改端口逻辑可能影响现有配置。 |
| **是否建议立即修复** | 建议修复 |
| **是否需要确认** | 是 |

---

## BUG-008

| 字段 | 内容 |
|---|---|
| **问题编号** | BUG-008 |
| **问题等级** | P2 |
| **问题类型** | 后端 / 部署 |
| **问题描述** | `remote_edge.py` 最后两行（1535-1536）在模块导入时立即创建 `RemoteEdge` 实例（默认会话），该实例在 `__init__` 中启动一个后台线程并 `wait(timeout=10)`。这意味着每次 `import backend.collectors.remote_edge` 都会启动后台线程并等待最多 10 秒。在单元测试、工具脚本等场景下，这是不必要的副作用。 |
| **影响范围** | 模块导入性能；测试环境（任何 import 都会启动线程）；工具脚本 |
| **代码位置** | `backend/collectors/remote_edge.py:1535-1536` |
| **证据** | `remote_edge.py:1535-1536`：`remote_edge_manager = RemoteEdgeManager()` 和 `remote_edge = remote_edge_manager.default_client()` |
| **修复建议** | 移除 `remote_edge = remote_edge_manager.default_client()` 这行（全局实例），调用处改用 `remote_edge_manager.default_client()` 或直接通过 `remote_edge_manager.get_client(...)` 获取 |
| **修复风险** | 低。但需要检查是否有代码直接引用 `remote_edge` 这个全局变量。 |
| **是否建议立即修复** | 建议修复 |
| **是否需要确认** | 否 |

---

## BUG-009

| 字段 | 内容 |
|---|---|
| **问题编号** | BUG-009 |
| **问题等级** | P2 |
| **问题类型** | 后端 / 逻辑 |
| **问题描述** | `edge_session_pages` API（`GET /api/edge-sessions/{session_id}/pages`）的超时重试逻辑（line 1285）在第一次超时后重置 client 并用新 client 重试。但重试使用 `edge_client_for(session_id)` 而非已重置的 client（会重新从 manager 获取），且若重试也失败，抛出的 HTTPException 仍使用第一次失败的错误详情 `detail`，而非第二次失败的原因，可能误导用户排查。 |
| **影响范围** | 页签扫描失败时的错误提示准确性 |
| **代码位置** | `backend/main.py:1278-1291` |
| **证据** | line 1285-1288：重试失败的 `except Exception: raise HTTPException(status_code=500, detail=detail) from exc`，`detail` 是第一次超时的内容 |
| **修复建议** | 重试失败时应生成新的错误详情，而非复用第一次超时的 detail |
| **修复风险** | 极低 |
| **是否建议立即修复** | 建议修复 |
| **是否需要确认** | 否 |

---

## BUG-010

| 字段 | 内容 |
|---|---|
| **问题编号** | BUG-010 |
| **问题等级** | P3 |
| **问题类型** | 代码质量 |
| **问题描述** | `scheduler.py` 第 129 行方法签名：`def _save_ocr_dataset(self, crop: Image.Image, ...)` 使用了 `Image.Image` 类型注解，但 `scheduler.py` 未导入 `from PIL import Image`。因为文件顶部有 `from __future__ import annotations`，注解被推迟为字符串，不会造成运行时错误，但 IDE 类型检查和文档生成会报错。 |
| **影响范围** | IDE 类型检查、代码可读性 |
| **代码位置** | `backend/services/scheduler.py:129` |
| **证据** | scheduler.py imports：无 `from PIL import Image`；第 129 行使用 `Image.Image`；第 1 行有 `from __future__ import annotations` |
| **修复建议** | 在 scheduler.py 顶部添加 `from PIL import Image` |
| **修复风险** | 无 |
| **是否建议立即修复** | P3，可随时修复 |
| **是否需要确认** | 否 |

---

## BUG-011

| 字段 | 内容 |
|---|---|
| **问题编号** | BUG-011 |
| **问题等级** | P3 |
| **问题类型** | 代码质量 / 逻辑 |
| **问题描述** | `index.html` 在 CDN 加载 `open-props.min.css`（`https://unpkg.com/open-props/open-props.min.css`）。若 CDN 不可用或网络受限（企业内网、大促期间带宽限制），页面样式将严重受损，因为该文件包含项目大量 CSS 变量（颜色、字体、间距）。 |
| **影响范围** | 所有页面样式（依赖 CDN 的 CSS 变量） |
| **代码位置** | `frontend/index.html:8` |
| **复现方式** | 断开外网访问，刷新页面 → 样式崩溃 |
| **修复建议** | 将 open-props.min.css 下载到本地 `frontend/assets/` 并使用本地路径 |
| **修复风险** | 无 |
| **是否建议立即修复** | P3，但强烈建议在交付前完成（生产/内网环境） |
| **是否需要确认** | 否 |

---

## BUG-012

| 字段 | 内容 |
|---|---|
| **问题编号** | BUG-012 |
| **问题等级** | P3 |
| **问题类型** | 代码质量 |
| **问题描述** | `store.py` 中 `connect()` 每次被调用时都创建一个新的 `sqlite3.connect()` 连接，没有连接池或连接复用。在高频调度场景（0.5s 采集、11 任务），每秒约 22 次采集各自触发多次 `connect()`，加上 GET /api/tasks 的自愈检查，可能每秒创建 50+ 个 SQLite 连接（每次用完即关）。SQLite 默认为文件锁，但频繁创建连接有额外开销。 |
| **影响范围** | 数据库层性能 |
| **代码位置** | `backend/services/store.py:34-40` |
| **修复建议** | 使用 threading.local() 实现简单连接复用，或使用 `check_same_thread=False` 的单例连接 |
| **修复风险** | 中。SQLite 线程模式需要谨慎处理并发写入。 |
| **是否建议立即修复** | P3，性能优化，非阻断性 |
| **是否需要确认** | 否 |

---

## 附：已确认正常工作的项目

| 项目 | 验证结果 |
|---|---|
| Python 语法检查（所有后端文件） | ✅ ALL SYNTAX OK |
| FastAPI 路由注册 | ✅ 结构完整 |
| SQLite init_db 逻辑 | ✅ 表结构正确，迁移完整（除 BUG-001 死代码外） |
| OCR 多引擎调度逻辑 | ✅ 引擎顺序、变体预处理、候选评分完整 |
| WebSocket 推送 + 轮询降级 | ✅ 逻辑完整（onopen/onmessage/onclose/onerror 全覆盖） |
| Edge 会话控制（启动/显示/隐藏/关闭） | ✅ 每个动作都有超时、重置、恢复逻辑 |
| 任务唯一约束防重 | ✅ DB 级 UNIQUE INDEX + 应用层 IntegrityError → 409 |
| 采集判断状态机 | ✅ ok/pending_confirm/suspect/parse_failed 四态合理 |
| 跨天重置逻辑 | ✅ 检测日期变化并接受新初始值 |
| 启动脚本 | ✅ 端口检测、进程清理逻辑完整 |
