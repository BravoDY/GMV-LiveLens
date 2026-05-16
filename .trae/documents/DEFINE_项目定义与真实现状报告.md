# DEFINE_项目定义与真实现状报告

> 生成时间：2026-05-16
> 阶段：DEFINE（项目定义与真实现状）
> 状态：只读分析，未修改任何业务代码
> 所有结论均基于当前真实代码验证，README/历史文档仅作参考，不以之为准

---

## 1. 项目一句话定位

**全渠道实时 GMV 采集看板系统**——通过 Playwright 控制 Microsoft Edge 浏览器 CDP 协议截图 + 多引擎 OCR 识别电商平台页面中的 GMV 数值，汇总展示在本地 Web 实时看板中。

---

## 2. 当前项目真实目标

| 维度 | 说明 |
|------|------|
| **业务目标** | 实时监控 DESCENTE（迪桑特）品牌在天猫、京东、抖音、得物、唯品会等多个电商平台的成交金额（GMV），汇总到统一看板 |
| **核心用户** | 运营人员 / 数据监控人员，需要在一个屏幕上看到所有平台的实时 GMV 汇总 |
| **使用场景** | 大促期间（双11/618等）或日常运营时，监控各平台销售额变化趋势 |
| **当前状态** | **已可运行**，已从早期单体架构重构为模块化架构（routers/services/collectors分离），前端已包含实时看板 + 采集配置 + 任务管理三个视图 |

---

## 3. 核心用户与使用场景

### 3.1 角色分类

| 角色 | 典型操作 | 关注视图 |
|------|----------|----------|
| **运营监控人员** | 查看实时看板、启动/暂停采集、手动纠错 | 实时看板 |
| **系统配置人员** | 配置店铺 Edge 会话、绑定页面、标定 OCR 区域 | 采集配置 + 任务管理 |
| **运维排障人员** | 检查 Edge 会话健康、查看采样历史、排查 OCR 异常 | 任务管理 + 调试面板 |

### 3.2 核心工作流

```
首次配置：shops.csv → 一键初始化 → 绑定Edge页面 → 标定OCR区域 → 启动采集 → 查看看板
日常使用：启动服务 → 启动Edge(如已关闭) → 启动采集 → 监控看板
```

---

## 4. 技术栈识别结果

### 4.1 确认项（均由真实代码/文件验证）

| 层级 | 技术 | 证据来源 |
|------|------|----------|
| **主语言** | Python 3.11+ | `pyproject.toml` requires-python = ">=3.11"；当前运行 3.14.3 |
| **后端框架** | FastAPI 0.110.2 + Uvicorn 0.29.0 | `requirements.txt` + `backend/main.py` |
| **数据库** | SQLite 3（标准库 `sqlite3`，无 ORM） | `backend/services/store.py` - `connect()` 使用 `sqlite3.connect` |
| **浏览器控制** | Playwright 1.58.0（CDP 协议，同步 API） | `requirements.txt` + `backend/collectors/edge/_session.py` |
| **图像采集兼容** | mss 10.1.0（Win32 窗口截图） | `requirements.txt` + `backend/collectors/window_capture.py` |
| **OCR 引擎** | RapidOCR 3.8.1（首选）+ ddddocr 1.6.1（兜底） | `requirements.txt` + `backend/collectors/ocr_reader.py` |
| **图像预处理** | OpenCV 4.13 + Pillow 12.2 | `requirements.txt` + `backend/collectors/ocr_reader.py` |
| **实时推送** | WebSocket（`/ws/live`） | `backend/routers/system.py` |
| **前端** | 原生 HTML5 + CSS3 + JavaScript（无构建工具，8 个 JS 模块） | `frontend/` 目录，按序加载 |
| **前端 CSS 框架** | Open Props | `frontend/index.html` 引用 `open-props.min.css` |
| **系统依赖** | Windows Win32 API（`ctypes`）+ Microsoft Edge | `backend/collectors/window_control.py`、`window_capture.py` |
| **包管理** | pip + `requirements.txt` | 根目录 `requirements.txt` |
| **虚拟环境** | `.venv/` (Windows venv) | `.venv/` 目录存在，含 `pyvenv.cfg` |
| **Lint/Format** | Ruff (pyproject.toml 配置) | `pyproject.toml` `[tool.ruff]` 段 |
| **环境变量** | python-dotenv 1.1.0 + `.env` | `backend/main.py` 调用 `load_dotenv()` |
| **CI** | GitHub Actions (Windows Runner) | `.github/workflows/test.yml` |
| **历史数据源(MySQL)** | PyMySQL 1.1.1 | `requirements.txt` + `backend/services/dashboard_query.py` |

### 4.2 未确认项

| 项目 | 状态 | 原因 |
|------|------|------|
| **Docker 支持** | ❌ 无 | 不存在 `Dockerfile` |
| **版本控制** | ❌ 无 | 不存在 `.git/` 目录（历史基线报告已确认） |
| **PaddleOCR** | ❌ 未安装 | `importlib.util.find_spec("paddleocr")` 返回 None |
| **Tesseract** | ❌ 未安装 | 无 `pytesseract` 且 CLI 不可用 |
| **部署方式** | 仅本地 | 只有 `.bat` 启动脚本，无容器化/守护进程/服务注册 |

---

## 5. 项目目录与模块地图

### 5.1 根目录结构

```
GMV-LiveLens/
├── backend/                     # 后端 Python 代码
│   ├── main.py                  # FastAPI 应用入口
│   ├── models.py                # 数据类定义 (CaptureTask/EdgeSession/CandidateAmount)
│   ├── logging_config.py        # 统一日志配置
│   ├── collectors/              # 采集器层
│   │   ├── edge/                #   Playwright Edge CDP 控制（含7个模块文件）
│   │   │   ├── __init__.py      #     RemoteEdge 组合类 + RemoteEdgeManager 单例
│   │   │   ├── _session.py      #     会话管理、连接、超时、线程模型
│   │   │   ├── _page.py         #     页面管理、截图、URL匹配
│   │   │   ├── _window.py       #     Edge 窗口启动/显示/隐藏/关闭
│   │   │   ├── _actions.py      #     页面操作封装
│   │   │   ├── _network.py      #     网络监听（大屏只读用）
│   │   │   └── _readonly.py     #     大屏只读数据提取
│   │   ├── remote_edge.py        #   对外暴露的统一接口（重导出）
│   │   ├── ocr_reader.py         #   OCR 引擎封装 + 金额候选提取与评分
│   │   ├── window_capture.py     #   Win32 窗口截图（兼容模式）
│   │   └── window_control.py    #   Win32 Edge 窗口控制
│   ├── core/                    # 核心基础设施层
│   │   ├── __init__.py
│   │   ├── config.py            #   环境变量配置（AppSettings dataclass）
│   │   ├── errors.py            #   统一异常处理（HTTP/Validation/Unhandled）
│   │   ├── middleware.py         #   RequestId + WriteToken 中间件
│   │   ├── request_id.py        #   Request ID 上下文管理
│   │   ├── response.py          #   统一响应格式（success/error）
│   │   └── security.py          #   API Token 鉴权 + 路径白名单
│   ├── routers/                 # 路由层（API 端点）
│   │   ├── __init__.py          #   路由汇总导出
│   │   ├── common.py            #   共用类型/工具函数/WS广播/Edge交互逻辑
│   │   ├── system.py            #   健康检查/WebSocket/设置/首页等
│   │   ├── tasks.py             #   任务 CRUD + 采集触发 + 手动纠错
│   │   ├── dashboard.py         #   看板数据集 API
│   │   ├── dashboard_test.py    #   测试看板页面 + 缓存刷新
│   │   ├── edge_sessions.py     #   Edge 会话 CRUD + 启动/显示/隐藏/关闭
│   │   ├── ocr.py               #   OCR 测试/引擎查询
│   │   ├── shops.py             #   店铺配置/初始化/绑定
│   │   └── platforms.py         #   平台批量 Edge 控制
│   ├── services/                # 服务层（业务逻辑）
│   │   ├── store.py             #   SQLite CRUD + Schema迁移 + 会话/任务同步
│   │   ├── scheduler.py         #   定时采集调度器（asyncio + to_thread）
│   │   ├── shop_config.py       #   shops.csv/JSON 解析 + ShopConfig 模型
│   │   ├── edge_binding.py      #   Edge 页面绑定评分与恢复逻辑
│   │   ├── dashboard_service.py #   看板数据聚合
│   │   ├── dashboard_query.py   #   MySQL 历史数据查询 + 缓存
│   │   └── dashboard_dataset.py #   数据集管理
│   └── tools/                   # 测试与运维工具脚本
│       ├── full_test.py         #   全功能测试（65项）
│       ├── smoke_api.py         #   API 冒烟测试（14项）
│       ├── smoke_edge_buttons.py#   Edge 四按钮冒烟测试
│       ├── start_shop_edges.py  #   批量启动店铺 Edge
│       └── find_ocr_anomalies.py#   OCR 异常监控
├── frontend/                    # 前端静态文件
│   ├── index.html               #   单页应用入口
│   ├── styles.css               #   全局样式
│   ├── core.js                  #   全局状态、工具函数、API 封装
│   ├── dashboard.js             #   实时看板渲染
│   ├── dashboard-shared.js      #   看板共享逻辑
│   ├── dashboard-public.js      #   公开看板
│   ├── config.js                #   采集配置面板
│   ├── edge.js                  #   Edge 会话管理 UI
│   ├── app.js                   #   任务管理 + 事件 + 调度器 + 初始化
│   ├── debug.js                 #   调试面板
│   ├── assets/                  #   静态资源（CSS/Logo）
│   └── test-dashboard/          #   测试看板（独立入口）
│       ├── index.html
│       ├── app.js
│       ├── dashboard.js
│       └── styles.css
├── data/                        # 数据与配置
│   ├── shops.csv                #   店铺清单（GBK编码，主配置）
│   ├── shops_default.json       #   店铺配置 JSON 备份
│   ├── shops_page_data.json     #   额外店铺页面数据
│   ├── shops_name.csv           #   店铺别名数据
│   ├── target.csv               #   目标值数据
│   ├── to_date.csv              #   周期截止日期数据
│   ├── gmv_livelens.sqlite3     #   SQLite 数据库（运行时生成）
│   ├── screenshots/             #   截图缩略图
│   ├── edge_profiles/           #   各店铺独立 Edge user_data_dir
│   ├── .cache/                  #   MySQL 查询缓存
│   └── ocr_datasets/            #   OCR 训练数据集（自动采集）
├── scripts/                     # 辅助脚本
│   ├── ci_check.py              #   CI 检查入口
│   └── ... (城市编码匹配相关脚本)
├── .github/workflows/test.yml   # GitHub Actions CI 配置
├── requirements.txt             # Python 依赖
├── pyproject.toml               # 项目配置 + Ruff Lint 配置
├── .env / .env.example          # 环境变量（.env 含真实 MySQL 密码）
├── .gitignore                   # Git 忽略规则
├── 第1步_启动GMV服务.bat          # 一键启动脚本（端口 8100）
├── README.md                    # 项目说明
├── AUDIT_*.md                   # 历史审计报告
├── FULL_CHAIN_TEST_REPORT.md    # 全链路测试报告
├── SMOKE_TEST_REPORT.md         # 冒烟测试报告
└── .trae/documents/             # 项目文档（27+ 份计划/报告）
```

### 5.2 模块调用关系

```
main.py (FastAPI App)
  ├── core/config.py          ← 环境变量配置
  ├── core/middleware.py       ← RequestId + Token 中间件
  ├── core/errors.py          ← 统一异常处理
  ├── logging_config.py       ← 日志初始化
  ├── services/store.py       ← SQLite CRUD + Schema迁移
  │     └── services/shop_config.py  ← shops.csv/JSON 解析
  ├── routers/                ← 8 个路由模块
  │     ├── routers/common.py      ← 共用逻辑（WS广播/Edge交互/快照构建）
  │     ├── routers/tasks.py       → services/store.py, scheduler.py, edge/
  │     ├── routers/system.py      → scheduler.py, dashboard_query.py
  │     ├── routers/edge_sessions.py → collectors/edge/ (RemoteEdgeManager)
  │     └── ...
  └── services/scheduler.py   ← 定时采集调度器
        ├── collectors/edge/  ← Playwright CDP 浏览器控制
        ├── collectors/ocr_reader.py  ← OCR 引擎
        └── collectors/window_capture.py ← 窗口截图兼容模式
```

### 5.3 数据流向

```
shops.csv/JSON → shop_config.py → store.py (SQLite capture_tasks + edge_sessions)
                                         ↓
用户前端操作 → routers/*.py → store.py → SQLite 持久化
                                         ↓
scheduler.py (asyncio loop) → ThreadPoolExecutor → collectors/edge/ (CDP截图)
                                         ↓                              ↓
                                    ocr_reader.py (OCR识别)    _readonly.py (大屏只读)
                                         ↓
                                    store.py → SQLite (gmv_samples + task_runtime)
                                         ↓
                                    WebSocket /ws/live → 前端看板实时更新
                                         ↓
                          dashboard_query.py → MySQL (历史周期数据) → 看板聚合
```

---

## 6. 核心业务链路

### 6.1 链路 1：服务启动与初始化

| 环节 | 说明 |
|------|------|
| **入口** | `第1步_启动GMV服务.bat` 或 `uvicorn backend.main:app --port 8100` |
| **关键步骤** | `main.py:startup()` → `setup_logging()` → `store.init_db()` → `store.sync_tasks_with_shop_configs()` → `scheduler.start()` |
| **依赖数据** | `shops.csv` (GBK编码) 或 `shops_default.json` / `shops_page_data.json` |
| **输出结果** | SQLite 数据库初始化、Edge 会话按配置同步、采集调度器启动 |
| **潜在失败点** | shops.csv 编码错误 → 启动跳过同步；端口 8100 占用 → .bat 自动杀进程重试；.venv 缺失 → 启动失败 |

### 6.2 链路 2：店铺 Edge 会话配置

| 环节 | 说明 |
|------|------|
| **入口** | 前端「采集配置」→ 选择店铺 → 启动 Edge |
| **关键函数** | `routers/edge_sessions.py:start_edge_session()` → `RemoteEdgeManager.get_client()` → `RemoteEdge._start_edge()` → `subprocess.Popen("msedge.exe ...")` |
| **依赖数据** | `edge_sessions` 表（debug_port, user_data_dir, session_mode） |
| **输出结果** | Edge 浏览器进程启动（隐藏到屏幕外 32000,y），CDP 端口打开 |
| **潜在失败点** | debug_port 被占用 → 连接失败；user_data_dir 权限不足 → 启动异常；Edge 版本不兼容 |

### 6.3 链路 3：页面绑定与 OCR 标定

| 环节 | 说明 |
|------|------|
| **入口** | 前端「采集配置」→ 扫描页签 → 选择页面 → 生成预览 → 框选区域 → 测试识别 → 保存 |
| **关键函数** | `routers/tasks.py:task_page_candidates()` → `edge_binding.py:page_match_score()` → `routers/common.py:_build_task_page_candidates()` |
| **依赖数据** | Edge 当前标签页列表、URL 匹配规则（url_patterns/url_must_contain） |
| **输出结果** | task.page_id 写入 SQLite、x_ratio/y_ratio/... 标定坐标写入 |
| **潜在失败点** | Edge 未启动/调试端口不通 → 扫描失败；页面 URL 不匹配 → 找不到目标页；截图尺寸与标定坐标不一致 |

### 6.4 链路 4：定时 GMV 采集（核心主链路）

| 环节 | 说明 |
|------|------|
| **入口** | `services/scheduler.py:CaptureScheduler._run_loop()`（asyncio 事件循环） |
| **关键函数** | `scheduler.capture_once(task_id)` → `RemoteEdge.screenshot_page()` → `window_capture.crop_by_ratio()` → `ocr_reader.read_text()` → `ocr_reader.extract_candidates()` → `scheduler._judge()` → `store.add_sample()` |
| **依赖数据** | task 的 page_id、标定坐标（x_ratio/y_ratio/...）、keyword_hint、last_trusted_value |
| **输出结果** | gmv_samples 表新增采样记录、capture_tasks 表更新 last_trusted_value/status |
| **潜在失败点** | page_id 失效 → edge_session_not_found/remote_page_not_found；OCR 识别失败 → parse_failed/needs_recalibration；数值异常下降 → suspect；截图超时 → edge_action_timeout |

### 6.5 链路 5：金额候选识别与连续确认

| 环节 | 说明 |
|------|------|
| **入口** | `ocr_reader.read_text(image, keyword_hint, last_value)` |
| **关键函数** | 图像预处理（颜色/对比度/黄色提取/Otsu 二值化×4变体） → 多引擎 OCR（RapidOCR → ddddocr） → 形近字纠错 → 正则提取金额候选（排除日期/时间/百分比） → 评分（货币符号+35/逗号分隔+18/量级+20/关键词+25/历史值±分） → 连续确认 |
| **依赖数据** | 截图区域、OCR 引擎可用性、历史可信值 |
| **输出结果** | 排序后的候选金额列表 + 确认状态 |
| **潜在失败点** | 页面样式变化 → OCR 精度下降；特殊字体 → ddddocr 误识别；数值跳变 → suspect |

### 6.6 链路 6：大屏只读模式（非 OCR 采集）

| 环节 | 说明 |
|------|------|
| **入口** | `scheduler._capture_screen_readonly_once()` |
| **关键函数** | `RemoteEdge.read_screen_pay_amount()` → 网络监听提取 `payAmt.value` |
| **依赖数据** | 页面 JS 上下文中的 payAmt 对象 |
| **输出结果** | 直接从页面 JS 读取支付金额（无 OCR 误差） |
| **潜在失败点** | 目标平台不在支持列表（天猫/京东/唯品会/抖音/得物） → readonly_failed；页面尚未渲染大屏数据 → readonly_waiting；前端 JS 结构变化 → payAmt 提取失败 |

### 6.7 链路 7：WebSocket 实时推送

| 环节 | 说明 |
|------|------|
| **入口** | `system.py:websocket_live()` → `clients.add(websocket)` |
| **关键函数** | `scheduler.add_callback(broadcast_snapshot)` → 每次采集完成后 `broadcast_snapshot()` → `build_snapshot()` → `websocket.send_json(snapshot)` |
| **依赖数据** | store.list_tasks() → task_to_dict() |
| **输出结果** | 前端实时更新看板数据 |
| **潜在失败点** | WS 连接断开 → 前端不更新；大量任务 → JSON 序列化开销 |

### 6.8 链路 8：测试看板与历史数据查询

| 环节 | 说明 |
|------|------|
| **入口** | `/dashboard-test` 页面 → MySQL 历史数据查询 |
| **关键函数** | `dashboard_query.py:_query_mysql_or_range()` → PyMySQL 连接 → 查询 `descente_al店铺整体取数源` 表 |
| **依赖数据** | MySQL 连接配置（.env 中的 MYSQL_* 变量）、to_date.csv |
| **输出结果** | 历史 GMV 周期数据缓存 → 前端测试看板展示 |
| **潜在失败点** | MySQL 连接失败 → 回退到本地缓存；网络不可达 → 查询超时；密码泄露风险（.env 含明文密码） |

---

## 7. 数据流与调用关系

### 7.1 数据层

```
┌──────────────────────────────────────────────────────────┐
│                    SQLite (gmv_livelens.sqlite3)          │
├──────────────────┬───────────────────┬───────────────────┤
│ capture_tasks    │  edge_sessions     │  app_settings     │
│ (任务配置+状态)   │  (Edge会话配置)     │  (全局设置)       │
├──────────────────┼───────────────────┼───────────────────┤
│         gmv_samples (采集历史记录)                       │
├──────────────────────────────────────────────────────────┤
│                    MySQL (远程)                           │
│         descente_al店铺整体取数源 (历史数据)               │
└──────────────────────────────────────────────────────────┘
```

### 7.2 API 路由汇总

| 路由模块 | 端点数 | 主要职责 |
|----------|--------|----------|
| system.py | ~15 | 健康检查、WebSocket、设置、首页、调试、看板 |
| tasks.py | ~12 | 任务 CRUD、采集触发、手动纠错、页签扫描、登录恢复 |
| edge_sessions.py | ~12 | 会话 CRUD、Edge 启动/显示/隐藏/关闭、页面操作 |
| shops.py | ~5 | 店铺列表、初始化、页面匹配、批量绑定 |
| platforms.py | ~4 | 平台批量 Edge 控制（启动/显示/隐藏/关闭） |
| ocr.py | ~3 | OCR 测试、引擎查询 |
| dashboard.py | ~1 | 看板数据集 |
| dashboard_test.py | ~5 | 测试看板页面、缓存管理 |

### 7.3 前端 JS 依赖关系

```
core.js (最先加载)
  ├── dashboard-shared.js
  ├── dashboard.js
  ├── dashboard-public.js
  ├── edge.js
  ├── config.js
  ├── debug.js
  └── app.js (最后加载，依赖所有模块)
```

---

## 8. 启动方式与运行依赖

### 8.1 启动入口

| 方式 | 命令 | 说明 |
|------|------|------|
| **推荐** | 双击 `第1步_启动GMV服务.bat` | 自动检测端口占用、杀旧进程、启动服务 |
| **命令行** | `.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8100` | 手动启动 |
| **前端** | `http://127.0.0.1:8100` | 服务启动后浏览器访问 |

### 8.2 运行依赖清单

| 类型 | 依赖项 | 必需？ | 说明 |
|------|--------|--------|------|
| **Python** | 3.11+ | ✅ 必需 | pyproject.toml 声明，当前 3.14.3 |
| **pip 包** | requirements.txt (16 个包) | ✅ 必需 | FastAPI/Uvicorn/Playwright/RapidOCR/OpenCV等 |
| **浏览器驱动** | Playwright Chromium | ✅ 必需 | `playwright install chromium` |
| **系统** | Windows | ✅ 必需 | 使用 Win32 API (ctypes.windll) |
| **浏览器** | Microsoft Edge | ✅ 必需 | 仅支持 Edge，不支持 Chrome |
| **数据库** | SQLite 3 | ✅ 必需 | 标准库自带 |
| **MySQL** | 远程数据库 | ⚠️ 可选 | 仅测试看板历史数据查询需要 |

---

## 9. 已有测试与验证方式

### 9.1 测试文件清单

| 文件 | 类型 | 规模 | 说明 |
|------|------|------|------|
| `backend/tools/full_test.py` | 单元+集成 | 65项 | 模块导入/业务逻辑/DB CRUD/OCR 管道/前端检查 |
| `backend/tools/smoke_api.py` | API 集成 | 14项 | 需要服务运行，含健康/任务/Edge/OCR/WS |
| `backend/tools/smoke_edge_buttons.py` | E2E | - | Edge 四按钮真实验证（需 Edge 在线） |
| `backend/tools/find_ocr_anomalies.py` | 监控 | - | OCR 特征库异常监控 |
| `scripts/ci_check.py` | CI | - | GitHub Actions 自动执行，含 lint + API 测试 |

### 9.2 验证结果（基于历史基线报告）

| 测试 | 结果 | 日期 |
|------|------|------|
| full_test.py (65项) | ✅ 47/47 PASS (100%) | 2026-05-08 |
| smoke_api.py (14项) | ✅ 14/14 PASS | 2026-05-08 |
| Ruff Lint | ✅ 通过（pyproject.toml 已配置） | - |

---

## 10. 当前主要风险

### P0 风险（会导致项目无法启动、核心功能不可用、数据错误、严重安全风险）

| 编号 | 风险描述 | 涉及文件/位置 | 详细说明 |
|------|----------|---------------|----------|
| **P0-1** | **`.env` 包含明文 MySQL 密码** | `.env` L34 | `MYSQL_PASSWORD=W8y...` 已写在 `.env` 文件中。虽然 `.gitignore` 排除了 `.env`，但当前无 Git 仓库，文件存在于本地目录中，任何能访问该目录的人都能看到密码 |
| **P0-2** | **无版本控制 (Git)** | 根目录 | 不存在 `.git/` 目录，所有代码变更无历史记录，无法回滚。一旦出问题只能依赖手动备份 |
| **P0-3** | **仅限 Windows + Edge** | 全局 | `window_control.py`/`window_capture.py` 使用 `ctypes.windll`，`scheduler.py` 使用 `tasklist/taskkill`。无法在任何其他 OS 运行，且必须安装 Microsoft Edge |

### P1 风险（影响稳定性、可维护性、局部功能正确性）

| 编号 | 风险描述 | 涉及文件/位置 | 详细说明 |
|------|----------|---------------|----------|
| **P1-1** | **shops.csv 编码不稳定** | `data/shops.csv` | 文件使用 GBK 编码，部分中文字段在非 GBK 环境下显示乱码。`shop_config.py` 已实现 UTF-8/GB18030/GBK 多编码回退，但如果编码不一致会导致解析失败 |
| **P1-2** | **Edge 会话状态恢复不稳定** | `collectors/edge/_session.py` | Edge 进程可能被意外关闭或崩溃，page_id 失效后需人工重绑。系统虽有自动恢复逻辑，但不能100%覆盖 |
| **P1-3** | **OCR 精度受页面样式影响** | `collectors/ocr_reader.py` | 动态图表、动画数字、高对比度背景会影响识别。黄色数字提取（HSV 阈值）对非标准配色可能失效 |
| **P1-4** | **连续确认阈值可能导致数据延迟** | `services/scheduler.py:_judge()` | confirm_count ≥ 2 时，新值需要连续 2 次相同才确认。异常跳变需要 3-4 次。在高频采集下影响小，但低频（>10s）时确认延迟可能数十秒 |
| **P1-5** | **SQLite 并发连接模式** | `services/store.py:connect()` | 使用 `check_same_thread=False` + 每次操作新建连接，无连接池。高并发或多任务同时写入时存在性能瓶颈和潜在的 WAL 锁争用 |
| **P1-6** | **跨天 GMV 重置逻辑单点** | `services/scheduler.py:_judge()` | `is_cross_day` 检测依赖 `task.last_success_at` 字段，通过 `datetime.strptime` 解析。如果该字段为 None 或格式异常（时间戳 vs 日期字符串），跨天检测会静默失败 |
| **P1-7** | **截图存储膨胀** | `data/screenshots/` | 默认 1 天清理，但高频采集（0.5s）下 1 天可产生大量截图。当前清理仅按 mtime<cutoff 删除，无总量上限控制 |
| **P1-8** | **前端 JS 文件无构建/压缩** | `frontend/*.js` | 8 个 JS 文件按顺序全局作用域加载，无模块化。任一文件加载失败会导致后续模块不可用，且无加载失败降级 |

### P2 风险（代码规范、体验优化、结构优化、长期维护）

| 编号 | 风险描述 | 涉及文件/位置 | 详细说明 |
|------|----------|---------------|----------|
| **P2-1** | **`app.js` (~1125 行) 和 `config.js` (~835 行) 规模较大** | `frontend/app.js`, `frontend/config.js` | 过大的 JS 文件增加维护难度，内部职责混杂 |
| **P2-2** | **`store.py` (~1350 行) 职责过重** | `backend/services/store.py` | 包含 CRUD、Schema 迁移、数据去重、会话同步、任务诊断等，可考虑进一步拆分 |
| **P2-3** | **`routers/common.py` 混合过多职责** | `backend/routers/common.py` | 包含类型定义、WS 广播、Edge 交互、快照构建、绑定恢复等，职责不够单一 |
| **P2-4** | **`shops.csv` 中 enabled 全为 FALSE** | `data/shops.csv` | 当前 9 家店铺的 enabled 字段全为 FALSE，意味着初始化后所有任务默认暂停，需要手动启用 |
| **P2-5** | **Shell/Bat 脚本路径硬编码** | `第1步_启动GMV服务.bat` | 使用 `%~dp0` 相对路径，工作正常但 `.venv\Scripts\python.exe` 路径假设 `.venv` 在项目根目录 |
| **P2-6** | **部分历史文档可能过时** | `.trae/documents/` (27+ 份) | 如 `main.py 2347 行未拆分路由` 等描述已不适用当前架构（已拆分为 routers/） |
| **P2-7** | **脚本目录混杂** | `scripts/` | 包含 CI 工具和城市编码匹配脚本（analyze_excel.py 等），后者与 GMV 项目核心功能无关 |
| **P2-8** | **无 API 版本管理** | `routers/` | 所有 API 路径均为 `/api/*`，无版本号前缀（如 `/api/v1/*`），未来 API 变更难以兼容 |
| **P2-9** | **data 目录混杂临时文件** | `data/` | 存在 `run_demo_test.err.log`、`.temp_analyze.py` 等临时/测试文件，未清理 |

---

## 11. 商业化代码规范差距

### 11.1 检查结果汇总

| 检查项 | 评分 | 说明 |
|--------|------|------|
| 代码结构清晰度 | ⭐⭐⭐⭐ | 后端已分层（routers/services/collectors/core），前端为原生模块化加载 |
| 模块边界合理性 | ⭐⭐⭐ | `routers/common.py` 和 `services/store.py` 职责较重，但整体分层合理 |
| 命名统一性 | ⭐⭐⭐⭐ | Python 代码命名风格统一（snake_case），前端 JS 使用 camelCase |
| 大文件/大函数 | ⭐⭐⭐ | `store.py` 1350行、`app.js` 1125行、`config.js` 835行偏大但函数粒度尚可 |
| 硬编码程度 | ⭐⭐⭐⭐ | 配置通过环境变量 + `.env` + `app_settings` 表管理，少量路径硬编码 |
| 统一错误处理 | ⭐⭐⭐⭐⭐ | `core/errors.py` 统一 HTTP/Validation/Unhandled 异常处理，`core/response.py` 统一响应格式 |
| 日志体系 | ⭐⭐⭐⭐ | `logging_config.py` 统一配置，RotatingFileHandler (10MB×5)，RequestId 中间件关联 |
| 配置管理 | ⭐⭐⭐⭐ | `.env` + `AppSettings` dataclass + `app_settings` SQLite 表三重配置体系 |
| 测试体系 | ⭐⭐⭐ | 有 full_test(65项) + smoke_api(14项) + CI 自动化，但缺少单元测试覆盖率和 E2E 测试 |
| 启动说明 | ⭐⭐⭐⭐ | `README.md` 含启动命令 + `.bat` 一键启动脚本 |
| 部署说明 | ⭐⭐ | 仅有本地启动说明，无容器化部署、无守护进程配置、无反向代理配置 |
| 数据校验 | ⭐⭐⭐ | Pydantic BaseModel 用于请求体校验，但采集数据无格式校验（信任 OCR 输出） |
| 异常兜底 | ⭐⭐⭐⭐ | 调度器循环有 try/except 保护，Edge 超时有降级重试，OCR 引擎有多级回退 |
| 回滚思路 | ⭐⭐ | 无版本控制（无 Git），历史基线报告提及手动备份，但无自动化回滚机制 |

### 11.2 主要差距

1. **无版本控制**（P0）：这是商业化交付的最大阻塞项，没有 Git 意味着无法协作、无法回滚、无法审计
2. **无容器化部署**（P1）：仅 Windows + .bat 启动，无法在服务器环境部署
3. **前端无构建工具**（P1）：8 个 JS 文件直接加载，无 tree-shaking/压缩/模块化
4. **无 API 版本管理**（P2）：未来 API 变更无兼容路径
5. **测试覆盖率未知**（P1）：虽然有测试文件，但无覆盖率报告
6. **部分大文件待拆分**（P2）：`store.py`/`common.py`/`app.js`/`config.js` 可进一步模块化

---

## 12. 需要后续 PLAN 阶段重点处理的问题

### 12.1 优先级排序

| 优先级 | 问题 | 理由 |
|--------|------|------|
| **最高** | Git 初始化 + 版本控制 | 安全基线，一切改造的前提 |
| **最高** | `.env` 安全加固（移除明文密码，使用密钥管理） | 安全风险 |
| **高** | 补充单元测试覆盖率 | 后续改造的安全网 |
| **高** | containers/ 云部署方案 | 脱离单 Windows 机器限制 |
| **中** | `store.py` 拆分（读写分离、诊断独立） | 可维护性 |
| **中** | 前端 JS 模块化（引入构建工具或至少 IIFE 隔离） | 前端稳定性 |
|