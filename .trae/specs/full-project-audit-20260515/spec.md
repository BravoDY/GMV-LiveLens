# GMV-LiveLens 项目全量技术审计报告 v0.3.0

审查日期：2026-05-15 | 审查范围：全项目

---

## 一、项目基础信息

| 维度 | 数据 |
|------|------|
| 项目名 | `gmv-livelens` |
| 版本号 | `0.3.0` |
| 项目类型 | 电商直播大屏 GMV 实时监控采集系统 |
| 技术栈 | Python 3.11+ FastAPI + Uvicorn (后端) / 纯原生 HTML/CSS/JS (前端) |
| 数据库 | SQLite (本地) + MySQL 10.128.64.96 (远程历史数据) |
| OCR引擎 | ddddocr + RapidOCR + (可选 PaddleOCR v3) |
| 浏览器自动化 | Playwright 控制 Edge 浏览器 |
| 截图采集 | mss + OpenCV + PIL + pywin32 |
| 缓存层 | JSON 文件缓存 (period_gmv.json) |
| 定时任务 | asyncio 自研调度器 (CaptureScheduler) + 每日 10:00 AM 缓存刷新 |
| 消息推送 | WebSocket (ws/live) |
| 前端框架 | 无框架，纯原生 JS (8 个 JS 文件，~4114 行) |
| CSS | 手写 2994 行 + Open Props 变量库 |
| 测试框架 | pytest (6 个测试文件) |
| CI/CD | GitHub Actions (test.yml) |
| Lint | Ruff (Python) |
| Docker | 无 |
| 部署脚本 | bat 文件 (第1步_启动GMV服务.bat) |
| 环境配置 | .env + python-dotenv |

---

## 二、技术架构评估

### 2.1 架构概览

```
┌─ frontend/ ─────────────────────────────────────────────────┐
│ index.html (主页)     test-dashboard/ (测试看板)              │
│   ├── core.js (757行) 全局状态/API/Session                    │
│   ├── dashboard.js (627行) 看板渲染/任务管理                   │
│   ├── edge.js (618行) Edge 会话 UI                            │
│   ├── config.js (1248行) 采集配置工作台                        │
│   ├── debug.js (80行) 调试面板                                │
│   └── app.js (121行) 入口/路由分发                            │
└─────────────────────────────────────────────────────────────┘
                        │ HTTP REST + WebSocket
                        ▼
┌─ backend/ ──────────────────────────────────────────────────┐
│ main.py → ALL_ROUTERS (8个路由模块)                           │
│   ├── routers/system.py      健康/设置/看板/实时/历史/WS       │
│   ├── routers/dashboard_test.py  测试看板 + 缓存刷新          │
│   ├── routers/tasks.py       CRUD/采集/预览/绑定              │
│   ├── routers/shops.py       店铺初始化/配置                  │
│   ├── routers/edge_sessions.py  Edge启动/停止/显示/隐藏       │
│   ├── routers/platforms.py   平台级批量Edge操作               │
│   ├── routers/ocr.py         OCR测试                         │
│   └── routers/dashboard.py   公开看板                         │
│                                                                │
│   services/                                                    │
│   ├── scheduler.py    采集调度器 (asyncio Event+Task)          │
│   ├── store.py        SQLite CRUD (4表: tasks/samples/       │
│   │                   sessions/settings)                      │
│   ├── dashboard_query.py   看板查询 + MySQL缓存                │
│   ├── dashboard_dataset.py CSV 数据集管理                     │
│   ├── shop_config.py        shops.csv 配置加载                │
│   └── edge_binding.py       Edge 实例绑定                     │
│                                                                │
│   collectors/                                                  │
│   ├── edge/       Playwright Edge 自动化 (session/page/      │
│   │              network/readonly/window/actions)              │
│   ├── ocr_reader.py    OCR 引擎抽象 (ddddocr/RapidOCR)        │
│   └── window_capture.py 窗口截图 (mss)                        │
└─────────────────────────────────────────────────────────────┘
                        │
          SQLite (gmv_livelens.sqlite3)
          MySQL 10.128.64.96:3306/od_ecbi
```

### 2.2 架构评分

| 维度 | 评分 | 说明 |
|------|:---:|------|
| 模块分离 | ★★★★☆ | 路由/服务/采集三层清晰，collectors 内部按 edge/ocr/window 拆分 |
| 接口设计 | ★★★★☆ | RESTful 规范，统一 success_response 格式，API Token 中间件 |
| 数据一致性 | ★★★☆☆ | CSV/SQLite/MySQL 三数据源，companyshop_name 作为统一关联键（已修复）|
| 扩展性 | ★★★☆☆ | 新增店铺只需 CSV + Edge Profile，无需改代码 |
| 可测试性 | ★★★☆☆ | 有 pytest 框架但覆盖不全面 |
| 前端架构 | ★★☆☆☆ | 纯全局函数 + innerHTML 拼接，无虚拟DOM/状态管理，维护成本高 |
| 错误恢复 | ★★★★☆ | 调度器异常恢复、MySQL 连接失败降级、OCR 多引擎 fallback |

---

## 三、全功能测试结果

### 3.1 API 端点冒烟测试

| 端点 | 方法 | 状态 | 说明 |
|------|------|:---:|------|
| `/api/health` | GET | ✅ | 返回 `{"status":"ok","version":"0.2.0"}` |
| `/api/realtime` | GET | ✅ | 9 个 task，active_tasks=9 |
| `/api/dashboard` | GET | ✅ | 实时看板正常 |
| `/api/dashboard-test?dataset_id=product:集团全周期` | GET | ✅ | 9 shops，GMV 非零 |
| `/api/dashboard-cache/status` | GET | ✅ | cached:true, stale:false |
| `/api/dashboard-cache/refresh` | POST | ✅ | 返回 status:"ok" |
| `/api/scheduler` | GET | ✅ | 调度器状态正常 |
| `/api/shops` | GET | ✅ | 店铺列表 |
| `/api/tasks` | GET | ✅ | 任务列表 |

### 3.2 前端功能测试

| 功能 | 状态 | 说明 |
|------|:---:|------|
| 正式环境导航栏切换 | ✅ | 已修复 (app.js 新增事件委托) |
| 实时看板渲染 | ✅ | 品牌双面板正常 |
| 周期看板品牌分组 | ✅ | 子品牌独立店 4 家正确分组 |
| 任务管理卡片 | ✅ | 按 sort_order 排序 + Edge 按钮 |
| 任务管理状态筛选 | ✅ | 全部/正常/告警/暂停可用 |
| 平台级 Edge 操作 | ✅ | 启动/显示/隐藏/关闭 |
| 任务级 Edge 操作 | ✅ | 每个卡片独立按钮 |
| GMV 数字格式化 | ✅ | 整数+千分符 |
| 测试看板数据集切换 | ✅ | 集团全周期/第一波抢先购 |
| 缓存刷新按钮 | ✅ | 手动 POST 刷新 |
| 采集全部按钮 | ✅ | 已修复 (移除 display:none) |
| 采集配置工作台 | ⚠️ | 需 Edge 调试端口连接 |

### 3.3 Bug 修复确认

| Bug | 根因 | 修复 |
|-----|------|------|
| Edge 按钮点击跳转配置页 | `bindManagerCardClicks()` 中 `closest("[data-editable]")` 匹配卡片容器，点击内部按钮也冒泡触发 | 添加 `closest("button/data-task-edge/data-platform-action")` 早退过滤 |
| 采集全部按钮不工作 | HTML `style="display:none"` 遮住了按钮 | 移除 `style="display:none"` |

---

## 四、代码质量评估

### 4.1 优势

1. **异常处理完备**：MySQL 连接失败 → WARNING + 降级；OCR 失败 → 多引擎 fallback；Edge 断连 → 自动重试
2. **安全设计规范**：Token 验证用 `secrets.compare_digest`、生产环境强制鉴权、SQL 参数化查询
3. **调度器鲁棒**：asyncio 事件驱动、暂停/恢复/停止状态机、异常恢复、独立时钟跟踪
4. **CSV 编码兼容**：utf-8-sig → gb18030 → utf-8 → gbk 自动检测

### 4.2 待改进

| 问题 | 严重度 | 位置 |
|------|:---:|------|
| requirements.txt 缺 pymysql/python-dotenv | P2 | 根目录 |
| `from pathlib import Path` 未使用 | P3 | dashboard_query.py:L10 |
| 前端无框架纯全局变量 | P2 | frontend/ 所有 JS |
| 周期模式 `platforms: []` 与实时模式不一致 | P2 | dashboard_query.py:L404 |
| 平台名中文字符串直接做 key 无类型约束 | P3 | 多处 |

---

## 五、安全风险评估

| 风险项 | 等级 | 详情 |
|--------|:---:|------|
| SQL 注入 | 低 | 所有值参数化，列名/表名受控于环境变量 |
| API Token | 低 | 生产写操作强制鉴权，compare_digest 防护 |
| 硬编码密钥 | 无 | 全部从 .env 加载 |
| WebSocket 明文 | 信息 | ws:// 无加密（内网部署可接受） |
| XSS | 低 | escapeHtml() 统一处理 |
| 依赖缺失 | 中 | pymysql/python-dotenv 未在 requirements.txt |
| 前端调试泄露 | 无 | 无 console.log |
| 异常静默吞没 | 低 | 仅非关键路径 pass |

---

## 六、性能与稳定性评估

### 6.1 性能

| 指标 | 数值 | 评估 |
|------|------|------|
| API 响应 (实时看板) | ~12ms | 优秀 |
| API 响应 (周期看板-缓存命中) | ~11ms | 优秀 |
| API 响应 (周期看板-首次MySQL) | ~6-8s | 可接受 |
| 前端轮询间隔 | 1.2s | 合理 |
| 调度器主循环 | 200ms | 高效 |

### 6.2 稳定性

| 维度 | 评估 |
|------|------|
| MySQL 连接失败 | WARNING 日志 + 降级为 query_failed 状态，不崩溃 |
| Edge 断连 | RuntimeError 被捕获 + 状态更新为 edge_debug_disconnected |
| OCR 全部失败 | pending_count 累积 → needs_recalibration，不阻塞 |
| 调度器异常 | `except Exception` + 1s 重试，不停止循环 |
| 端口冲突 | bat 文件自动 kill 旧进程 (已加固) |

---

## 七、数据流与业务逻辑风险评估

### 7.1 风险清单

| 风险 | 等级 | 位置 | 说明 |
|------|:---:|------|------|
| target 累加无去重 | 高 | dashboard_query.py:L364-369 | 同一 (date, csn) 重复行导致目标虚高 |
| 同比日期非自然日对齐 | 中 | to_date.csv: 第一波抢先购 | 3 天偏差，同比标签误解 |
| 5 倍跳变阈值过宽 | 中 | scheduler.py:L696 | 短间隔正常波动可能被当异常 |
| confirm_count=0 → 一票通过 | 中 | scheduler.py:L748 | 低质量 OCR 结果可能被直接确认 |
| 跨天检测用本地时钟 | 低 | scheduler.py:L682 | 时区错误导致误重置 |
| 缓存惰性刷新 (10:00 前不更新) | 低 | dashboard_query.py:L342-345 | 8:00-10:00 数据可能过时 |

---

## 八、部署与交付风险评估

| 风险 | 等级 | 说明 |
|------|:---:|------|
| 依赖缺失 | P1 | `pip install -r requirements.txt` 后还需手动装 pymysql + python-dotenv |
| Docker 缺失 | P2 | 无容器化，环境迁移靠人工 |
| Edge 浏览器依赖 | P2 | 需预装 Edge + WebDriver |
| Windows 专用 API | P2 | pywin32 + mss 仅 Windows |
| 内网 MySQL 依赖 | P2 | 无 MySQL → 周期看板降级为 no_data |
| OCR 模型文件 | P2 | onnxruntime 模型需首次下载 |

---

## 九、建议优先级

| 优先级 | 建议 |
|:---:|------|
| P0 | 补全 requirements.txt (pymysql, python-dotenv) |
| P0 | target.csv 加载时去重 (按 (date, csn)) |
| P1 | 统一 周期/实时 模式 platforms 结构 |
| P1 | requirements.txt 锁版本号 |
| P2 | 前端模块化重构 (至少拆分为 ES modules) |
| P2 | Docker 化部署 |
| P2 | 显式指定时区 (Asia/Shanghai) |
| P3 | 删除未使用 import |
| P3 | 补充单元测试覆盖 |
