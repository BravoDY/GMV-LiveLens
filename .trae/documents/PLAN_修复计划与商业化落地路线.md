# PLAN_修复计划与商业化落地路线

> 生成时间：2026-05-16
> 阶段：PLAN（修复计划与商业化落地路线）
> 基于：DEFINE_项目定义与真实现状报告.md
> 状态：计划设计，未修改任何业务代码

---

## 1. 本轮总体目标

本轮修复的核心目标分为四个层次，按优先级递减：

| 层次 | 目标 | 说明 |
|------|------|------|
| **L1 安全基线** | 消除明文密码泄露风险、建立版本控制 | 项目可交付的最低门槛 |
| **L2 稳定性加固** | 补齐异常处理盲区、日志增强、配置规范化 | 生产环境可稳定运行 |
| **L3 可维护性提升** | 大文件适度拆分、测试补充、文档过期清理 | 降低后续维护成本 |
| **L4 商业化补课** | 前端模块化、API 版本规划、部署方案 | 向可交付标准靠近 |

---

## 2. DEFINE 阶段关键结论复核

### 2.1 复核确认

| DEFINE 结论 | 复核查证 | 结论 |
|-------------|----------|------|
| 后端已分层（routers/services/collectors/core） | 8 个 router 模块 + 7 个 service 模块 + 4 个 collector 模块 | ✅ 确认 |
| 前端为原生 JS 无框架无构建 | 8 个 JS 文件全局作用域按序加载 | ✅ 确认 |
| shops.csv 使用 GBK 编码 | 实际读取显示中文乱码（终端编码不一致导致），但 `_read_csv_text_with_fallbacks()` 支持多编码回退 | ✅ 确认 |
| .env 含明文 MySQL 密码 | `.env` 第 33 行 `MYSQL_PASSWORD=W8y...` | ✅ 确认（P0 风险） |
| 无版本控制 | `.git/` 目录不存在 | ✅ 确认 |
| full_test.py 69 项测试 | 使用 `_check()` 函数，含 A~F 六段 | ✅ 确认 |
| GitHub Actions CI 已配置但无 Runner | `.github/workflows/test.yml` 引用 `scripts/ci_check.py` | ✅ 确认 |
| 9 家店铺 enabled 全为 FALSE | `data/shops.csv` 最后一列全为 FALSE | ✅ 确认 |
| ruff lint 已配置 | `pyproject.toml` `[tool.ruff]` 段 | ✅ 确认 |
| 有 API Token 鉴权中间件但未启用 | `GMV_REQUIRE_API_TOKEN=false` | ✅ 确认 |

### 2.2 需要修正的认知

| DEFINE 项 | 原描述 | 修正 |
|-----------|--------|------|
| P1-2 "Edge 会话状态恢复不稳定" | 描述为风险 | 更准确地说：系统已内置自动恢复机制（`auto_restore_edge_session_task_bindings`），但覆盖率不是 100%。**本轮不变更此逻辑**，仅增强失败日志 |
| P2-6 "历史文档可能过时" | 提及 `main.py 2347 行` 已不适用 | 确认已过时，当前 `main.py` 仅约 72 行。**本轮清理明显过时的文档引用** |

---

## 3. P0 / P1 / P2 问题处理策略

### 3.1 P0 问题（本轮必须处理）

| 编号 | 问题 | 处理策略 | 预期效果 |
|------|------|----------|----------|
| **P0-1** | `.env` 包含明文 MySQL 密码 | 立即将密码移至 Windows 凭据管理器或独立密钥文件，`.env` 中改为占位符；更新 `.env.example` 说明密钥管理方式 | 消除密码泄露风险 |
| **P0-2** | 无版本控制（Git） | 初始化 Git 仓库，创建 `.gitignore`（已存在），编写有意义的初始 commit | 建立代码变更可追溯性 |
| **P0-3** | 仅限 Windows + Edge | **本轮不处理**。这是项目架构决定的，不是 bug。记录为已知限制，后续可评估容器化方案（Windows Container 或迁移 Playwright 到跨平台 API） | 记录，不阻塞交付 |

### 3.2 P1 问题处理策略

| 编号 | 问题 | 本轮处理？ | 策略 |
|------|------|------------|------|
| **P1-1** | shops.csv 编码不稳定 | ✅ 是 | 将 `data/shops.csv` 统一转为 UTF-8 BOM，减少编码回退次数；`_read_csv_text_with_fallbacks` 已足够健壮，但明确推荐编码 |
| **P1-2** | Edge 会话状态恢复不稳定 | ⚠️ 部分 | 增强日志（记录恢复失败原因到 `last_reason`），不变更恢复逻辑 |
| **P1-3** | OCR 精度受页面样式影响 | ❌ 否 | 核心算法已较完善（4 种变体 + 多引擎 + 形近字纠错），进一步优化需要大量样本，本轮不建议动 |
| **P1-4** | 连续确认阈值导致数据延迟 | ⚠️ 部分 | 阈值可配置（`confirm_count`），当前逻辑合理。本轮仅确保前端对此有明确提示 |
| **P1-5** | SQLite 并发连接 | ⚠️ 部分 | 添加 WAL 模式，大幅降低锁争用 |
| **P1-6** | 跨天 GMV 重置逻辑单点 | ✅ 是 | 增强 `_judge()` 中 `is_cross_day` 的时间解析异常兜底，对 None/空字符串/非标准格式增加防御 |
| **P1-7** | 截图存储膨胀 | ✅ 是 | 增加 `GMV_SCREENSHOT_MAX_COUNT` 环境变量，按数量上限清理（保留最近 N 张/任务） |
| **P1-8** | 前端 JS 无构建/模块化 | ⚠️ 部分 | 仅确保加载失败有降级提示，不做大规模模块化重构 |

### 3.3 P2 问题处理策略

| 编号 | 问题 | 本轮处理？ | 策略 |
|------|------|------------|------|
| **P2-1** | app.js/config.js 文件偏大 | ❌ 否 | 功能稳定运行中，大规模拆分风险高。记录为后续重构项 |
| **P2-2** | store.py 职责过重 | ❌ 否 | 同上，功能稳定。仅补充注释说明模块职责边界 |
| **P2-3** | common.py 混合职责 | ❌ 否 | 同上 |
| **P2-4** | shops.csv enabled 全 FALSE | ✅ 是 | 这是配置层问题，本轮转为 TRUE 或在前端初始化时提示用户手动启用 |
| **P2-5** | .bat 路径硬编码 | ✅ 是 | 确认路径逻辑正确，无需修改 |
| **P2-6** | 历史文档过时 | ✅ 是 | 清理明显过时的文档引用，标注历史文档的有效期 |
| **P2-7** | scripts/ 目录混杂 | ✅ 是 | 将城市编码匹配脚本（与 GMV 无关）移至 `scripts/archive/` |
| **P2-8** | 无 API 版本管理 | ❌ 否 | 记录为后续任务，当 API 需要 breaking change 时再引入 |
| **P2-9** | data/ 临时文件未清理 | ✅ 是 | 删除 `run_demo_test.*.log`、`.temp_analyze.py` 等临时文件 |

---

## 4. BUILD 阶段任务队列

以下按执行顺序排列，**每条任务独立可验证**，不依赖后续任务。

| 顺序 | 优先级 | 任务 | 涉及文件 | 修改类型 | 风险 | 验证方式 | 本轮执行 |
|------|--------|------|----------|----------|------|----------|----------|
| **1** | P0 | Git 初始化 + 首次提交 | 根目录 `.git/` | config | 极低 | `git status` 确认仓库正常 | ✅ 是 |
| **2** | P0 | `.env` 密码脱敏 | `.env`, `.env.example` | security | 极低 | 确认 `.env` 中 MYSQL_PASSWORD 已移除，`.gitignore` 排除 `.env` | ✅ 是 |
| **3** | P1 | SQLite WAL 模式开启 | `backend/services/store.py:connect()` | performance | 低 | 启动服务，执行 `PRAGMA journal_mode` 确认为 WAL | ✅ 是 |
| **4** | P1 | shops.csv 编码统一为 UTF-8 BOM | `data/shops.csv` | config | 中（需保留备份） | `shop_config.load_shop_configs()` 正常解析 9 家店铺 | ✅ 是 |
| **5** | P1 | 跨天检测异常兜底 | `backend/services/scheduler.py:_judge()` | bugfix | 低 | `full_test.py` Section B 相关测试通过 | ✅ 是 |
| **6** | P1 | 截图数量上限控制 | `backend/services/scheduler.py` | config | 低 | 设置低上限，观察清理行为 | ✅ 是 |
| **7** | P1 | Edge 恢复失败日志增强 | `backend/routers/common.py`, `backend/services/edge_binding.py` | logging | 极低 | 模拟无 Edge 场景，确认日志输出 | ✅ 是 |
| **8** | P1 | 前端 JS 加载失败降级提示 | `frontend/index.html` | error-handling | 低 | 删除一个 JS 文件引用，确认降级提示出现 | ✅ 是 |
| **9** | P2 | shops.csv enabled 更新 + 提示 | `data/shops.csv` | config | 低（需确认业务需求） | 初始化后查看任务默认启用状态 | ✅ 是 |
| **10** | P2 | 历史过期文档清理 | `.trae/documents/` 部分文件 | docs | 极低 | 确认清理后项目正常运行 | ✅ 是 |
| **11** | P2 | scripts/ 目录整理 | `scripts/` | refactor | 极低 | 确认 CI 脚本仍正常 | ✅ 是 |
| **12** | P2 | data/ 临时文件清理 | `data/` | config | 极低 | 确认清理后无功能影响 | ✅ 是 |
| **13** | P1 | full_test.py 覆盖补充 | `backend/tools/full_test.py` | test | 低 | 运行 full_test.py，新增测试通过 | ✅ 是 |
| **14** | P2 | 部署说明补充（README 更新） | `README.md` | docs | 极低 | 按说明可成功启动 | ✅ 是 |

### 4.2 不建议本轮修改的文件清单

| 文件 | 原因 |
|------|------|
| `backend/collectors/ocr_reader.py` | OCR 核心算法已较完善，改动风险高，验证需要大量真实样本 |
| `backend/collectors/edge/_session.py` | Edge 会话管理逻辑复杂，改动容易引入线程安全问题 |
| `backend/services/scheduler.py`（除 `_judge` 跨天检测外） | 调度核心稳定运行，改动风险高 |
| `frontend/app.js`、`frontend/config.js` | 功能稳定，大规模重构风险高 |
| `backend/services/store.py`（除 WAL 外） | CRUD 逻辑复杂，改动连锁风险高 |
| `backend/routers/common.py` | 涉及多处引用，改动影响面广 |

---

## 5. VERIFY 阶段测试矩阵

### 5.1 测试矩阵

| 序号 | 测试类型 | 测试目标 | 执行命令/方式 | 通过标准 | 失败处理 |
|------|----------|----------|---------------|----------|----------|
| **T1** | 启动测试 | 服务正常启动，端口 8100 可访问 | `第1步_启动GMV服务.bat` 或 `uvicorn` | 无异常日志，`/api/health` 返回 200 | 检查端口占用/依赖安装 |
| **T2** | 依赖安装测试 | 全部依赖可安装 | `pip install -r requirements.txt` | 无错误输出 | 检查 Python 版本兼容 |
| **T3** | Lint 检查 | 代码风格一致 | `ruff check backend/` | 0 error, 允许 warning | 按提示修复后重新检查 |
| **T4** | 全功能测试（纯逻辑） | 模块导入+业务逻辑+DB+OCR | `.venv\Scripts\python.exe backend\tools\full_test.py` | 核心段(A~D)全部 PASS | 定位 FAIL 项，回归修复 |
| **T5** | 全功能测试（API 集成） | API 端点响应正确 | `.venv\Scripts\python.exe backend\tools\full_test.py` （服务运行中） | 段 E 全部 PASS | 检查 API 路径/参数 |
| **T6** | API 冒烟测试 | 14 项 API 健康检查 | `.venv\Scripts\python.exe backend\tools\smoke_api.py` | 14/14 PASS | 查看具体 FAIL 项 |
| **T7** | 前端页面加载测试 | index.html + 8 JS 加载正常 | 浏览器访问 `http://127.0.0.1:8100`，F12 Console 无报错 | 三个视图（看板/配置/管理）正常切换 | 检查 JS 加载顺序/路径 |
| **T8** | WebSocket 连接测试 | WS 实时推送正常 | 浏览器看板页面，启动采集后观察数据自动刷新 | 数据变化时看板自动更新 | 检查 WS 端点/连接状态 |
| **T9** | 数据库完整性测试 | SQLite schema 正确，数据持久化 | 启动服务后检查 `data/gmv_livelens.sqlite3` 表结构 | capture_tasks/edge_sessions/gmv_samples/app_settings 四表存在 | 删除 DB 重新初始化 |
| **T10** | 配置加载测试 | shops.csv 正常解析 | 启动服务 → `/api/shops` 返回 9 家店铺 | 9 条记录，字段完整 | 检查编码/CSV 格式 |
| **T11** | 异常场景测试 | 错误响应格式统一 | 调用不存在任务 ID、无效参数 | 返回统一的 error_response 格式 | 检查 errors.py 处理器 |
| **T12** | 截图清理测试 | 截图按规则自动清理 | 设置短过期时间，等待清理触发 | 旧截图被删除，新截图保留 | 检查 `_cleanup_old_screenshots` |
| **T13** | 回归测试 | 修改未破坏已有功能 | 运行 full_test.py + smoke_api.py 完整套件 | 与修改前结果一致或更多 PASS | git diff 回滚 |

### 5.2 测试执行顺序（VERIFY 阶段）

```
T1 (启动) → T10 (配置) → T4 (逻辑测试) → T9 (DB) → T3 (Lint)
                                             ↓
                                          T5 (API集成) → T6 (冒烟API)
                                             ↓
                                          T7 (前端) → T8 (WS)
                                             ↓
                                          T11 (异常) → T12 (截图清理)
                                             ↓
                                          T13 (回归，全量)
```

---

## 6. REVIEW 阶段审查重点

REVIEW 阶段将对 BUILD 阶段的修改进行代码审查，重点检查：

| 审查项 | 检查要点 |
|--------|----------|
| **安全** | `.env` 是否仍含敏感信息？`.gitignore` 是否排除所有敏感路径？ |
| **功能回归** | 修改后的 `_judge()` 跨天检测是否覆盖所有边界？SQLite WAL 是否影响已有查询？ |
| **编码一致性** | `shops.csv` 转 UTF-8 BOM 后所有中文字段是否正确？ |
| **日志完整性** | Edge 恢复失败日志是否包含 session_id/platform/shop_name？ |
| **配置兼容性** | 新增环境变量是否有默认值？旧配置文件能否兼容？ |
| **测试覆盖** | 新增测试是否覆盖了修改的代码路径？ |
| **文档同步** | README/`.env.example` 是否反映最新配置？ |

---

## 7. SHIP 阶段交付标准

| 标准 | 通过条件 |
|------|----------|
| **启动可用** | `第1步_启动GMV服务.bat` 一次启动成功，无异常日志 |
| **测试全绿** | full_test.py 核心段全部 PASS，smoke_api.py 14/14 PASS |
| **Lint 通过** | `ruff check backend/` 0 error |
| **密码安全** | `.env` 不含明文密码，`.gitignore` 生效 |
| **版本控制** | Git 仓库已初始化，初始 commit 完成 |
| **配置可读** | shops.csv UTF-8 编码可读，`.env.example` 说明完整 |
| **前端可用** | 三个视图正常切换，WebSocket 实时更新正常 |
| **故障可查** | 关键路径有日志输出（含 request_id/平台/店铺） |

---

## 8. 商业化代码规范落地方案

### 8.1 目录结构改进

**本轮操作：**
1. `scripts/` 下与 GMV 无关的脚本移至 `scripts/archive/`
2. `data/` 下临时测试文件清理
3. `.trae/documents/` 下明显过时的计划文档标注 [已过期]

**本轮不操作（后续阶段）：**
- 不再拆分 `store.py` / `common.py` / `app.js` / `config.js`

### 8.2 命名规范

**当前状态：** Python 已统一 snake_case，JS 已统一 camelCase。**无需本轮修改。**

### 8.3 配置管理

**本轮操作：**
1. 新增环境变量及默认值：

```env
# === 截图数量上限（每任务） ===
GMV_SCREENSHOT_MAX_COUNT_PER_TASK=200

# === SQLite 模式 ===
GMV_SQLITE_JOURNAL_MODE=wal
```

2. `.env.example` 同步更新

### 8.4 日志体系

**本轮操作：**
1. Edge 会话恢复失败时，日志增加 `session_id`、`platform`、`shop_name`、恢复原因
2. 跨天检测异常时，记录原始 `last_success_at` 值

### 8.5 错误处理

**当前状态：** `core/errors.py` + `core/response.py` 已统一。**本轮操作：**
1. 增强 `_judge()` 的异常输入防御（None/空字符串/时间戳格式交叉）
2. 前端 JS 加载失败时页面提示而非静默白屏

### 8.6 数据校验

**本轮操作：**
1. shops.csv 字段校验（启动时明确报错行号+字段名+修复建议）

### 8.7 API 返回结构

**当前状态：** `success_response()` / `error_response()` 已统一。**本轮不修改。**

### 8.8 前端状态管理

**本轮操作：**
1. JS 加载失败降级提示（非侵入式）
2. **不进行模块化重构**

### 8.9 测试覆盖

**本轮操作：**
1. full_test.py 新增：跨天检测边界、截图清理逻辑、Screenshot 数量上限
2. smoke_api.py 新增：配置加密检查（快速接口）

### 8.10 部署可读性

**本轮操作：**
1. README.md 更新：明确标注 "仅限 Windows + Edge"
2. 新增 `docs/deployment.md`（可选）：部署前置条件 + 环境变量说明 + 故障排查

### 8.11 可维护性

**本轮操作：**
1. 清理明显过时的历史文档引用
2. 每个待修复问题的验证方式在代码中用注释标注（关键位置）
3. Git 初始化后用 commit message 记录每次修改的原因

---

## 9. 风险控制与回滚策略

### 9.1 高危文件清单（谨慎改动）

| 文件 | 风险 | 保护措施 |
|------|------|----------|
| `backend/services/scheduler.py:_judge()` | 跨天检测修改可能影响 GMV 确认逻辑 | 仅增加 try/except 防御，不改核心逻辑 |
| `backend/services/store.py:connect()` | WAL 模式修改影响所有数据库操作 | 先测试后部署，若异常则回退到 DELETE 模式 |
| `data/shops.csv` | 编码转换可能引入乱码 | **转换前必须备份**，转换后逐条比对 |
| `backend/collectors/edge/` 全部 | 线程模型复杂，改动易引入死锁 | **本轮完全不修改** |

### 9.2 小步修改原则

1. **每个 BUILD 任务单独提交一个 commit**，不混入多个修改
2. **修改 `_judge()` 时**：先写测试用例（full_test.py 新增），确认测试通过后再修改代码
3. **编码转换 shops.csv 时**：先备份为 `shops.csv.gbk.bak`，再转为 UTF-8 BOM，运行 `load_shop_configs()` 验证
4. **修改 SQLite 连接模式时**：先在新 DB 上测试，再切换到生产 DB

### 9.3 回滚策略

| 修改 | 回滚方式 |
|------|----------|
| Git 初始化 | 无需回滚（纯增量操作） |
| `.env` 密码脱敏 | 从备份或密码管理器恢复 |
| shops.csv 编码转换 | `copy shops.csv.gbk.bak shops.csv` |
| SQLite WAL 模式 | 改回 `PRAGMA journal_mode=DELETE` |
| `_judge()` 修改 | `git checkout backend/services/scheduler.py` |
| 文档/脚本清理 | 从 `.trae/documents/` 历史备份恢复 |

### 9.4 不建议本轮处理的问题

| 问题 | 原因 |
|------|------|
| 容器化/Docker 部署 | 项目大量依赖 Win32 API+Edge，需要 Windows Container，评估成本高 |
| 前端 JS 模块化重构 | `app.js`/`config.js` 功能稳定，重构风险 > 收益 |
| `store.py` 拆分 | 1350 行在 Python 中可接受，拆分可能引入循环导入 |
| `common.py` 拆分 | 多处引用，改动影响面广 |
| API 版本管理 | 当前无 breaking change 需求，过度设计 |
| OCR 精度优化 | 需要大量标注样本 + 离线评估，本轮不现实 |
| PaddleOCR/Tesseract 安装 | 当前 RapidOCR + ddddocr 已满足需求，新引擎引入新依赖风险 |

---

## 10. 不建议本轮处理的问题

| 问题 | DEFINE编号 | 理由 |
|------|-----------|------|
| 仅限 Windows + Edge | P0-3 | 架构级限制，不是 bug。后续可评估 Windows Container 方案 |
| OCR 精度受页面样式影响 | P1-3 | 核心算法已完善，进一步优化需要 ML 工程，超出本轮范围 |
| 连续确认阈值导致数据延迟 | P1-4 | `confirm_count` 已可配置，当前逻辑合理 |
| SQLite 连接池/并发 | P1-5（部分） | WAL 模式可缓解，真正连接池需要 ORM，改动过大 |
| 前端 JS 大文件拆分 | P2-1 | 功能稳定，重构风险远大于收益 |
| store.py 拆分 | P2-2 | 同上 |
| common.py 职责混合 | P2-3 | 同上 |
| 无 API 版本管理 | P2-8 | 无 breaking change 需求 |

---

## 11. 当前阶段结论

### 11.1 是否可以进入 BUILD 阶段

**可以进入 BUILD 阶段。**

本计划覆盖了 14 个 BUILD 任务（含 P0 2 项、P1 6 项、P2 6 项），全部为低风险可独立验证的增量修改。不涉及核心算法（OCR）、Edge 线程模型、数据库架构的重构。

### 11.2 BUILD 阶段优先处理的 3 个任务

| 顺序 | 任务 | 理由 |
|------|------|------|
| **第 1 步** | Git 初始化 + 首次提交 | 建立安全基线，后续所有修改都被追踪 |
| **第 2 步** | `.env` 密码脱敏 | 消除安全隐患，可以在任何环境下安全分享代码 |
| **第 3 步** | SQLite WAL 模式开启 | 1 行代码改动，大幅提升并发性能，降低锁争用 |

### 11.3 BUILD 阶段禁止触碰的任务

- 不修改 `backend/collectors/ocr_reader.py`（OCR 核心算法）
- 不修改 `backend/collectors/edge/` 全部（Edge 线程模型）
- 不修改 `backend/services/store.py` 除 WAL 外的任何逻辑
- 不修改 `backend/routers/common.py` 核心函数签名
- 不重构 `frontend/app.js` / `frontend/config.js`
- 不修改 `backend/services/scheduler.py` 调度核心循环

### 11.4 BUILD 阶段执行纪律

1. **每个任务独立 commit**，按任务队列顺序执行
2. **每完成一个任务**，运行 `full_test.py` 快速回归
3. **报错即停**，查原因修复后再继续
4. **高风险任务前**（如 shops.csv 编码转换），先做备份
5. **不跨任务混改**，避免定位困难

---

> 下一步：进入 BUILD 阶段，按任务队列顺序执行。
