# GMV-LiveLens 项目全量说明书

> 版本：2026-05-03 | 适用范围：整个项目 | 读者：维护者、接手者、AI 辅助工具

> 给其它 AI 的阅读提示：本文件是了解 GMV-LiveLens 当前真实行为的第一入口；`.trae/documents/项目全量说明文档编写计划.md` 是文档维护计划，不是项目事实主入口。

---

## A. 项目定位与目标

### 解决什么问题

电商运营团队在大促期间需要同时监控多个平台（天猫、京东、抖音、唯品会等）的实时 GMV（成交金额）。这些平台的数据分散在各自的后台管理系统网页中，没有统一 API，只能人工盯屏。GMV-LiveLens 通过控制真实浏览器、对页面截图并用 OCR 识别数字，将多平台 GMV 汇聚到一个实时看板上，实现自动化监控。

### 典型使用场景

- 大促活动期间（双11、618），运营同时监控 11 个店铺 GMV，数据每 1-2 秒自动刷新
- 发现某店铺 GMV 异常下跌时，系统自动标记 `suspect` 状态，运营立刻介入排查
- 运营不在电脑旁时，看板持续采集，回来后通过历史样本回溯数据

### 当前支持的平台和模式

- **平台**：天猫、京东、抖音、其他平台（含唯品会、微信小程序等）
- **采集模式**：
  - `remote_edge`（主要）：通过 Chrome DevTools Protocol (CDP) 控制真实 Edge 浏览器截图
  - `window_capture`（兼容）：通过 Win32 API 截取任意窗口画面
- **操作系统**：Windows only（依赖 Win32 API 和 msedge.exe）
- **浏览器**：Microsoft Edge only（Chromium 内核，支持 CDP）

### 当前不支持什么

- Linux / macOS（依赖 ctypes.windll）
- Chrome、Firefox 等非 Edge 浏览器
- 通过官方 API 直接拉取数据（平台均无开放 GMV 实时 API）
- 移动端浏览器页面
- 多台机器分布式部署

---

## B. 系统总览

### 文字化架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      前端（浏览器）                            │
│  实时看板 │ 任务管理 │ 采集配置 │ 配置流程图                    │
│   WebSocket 实时接收快照  /  HTTP 请求 API                     │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP / WebSocket
┌───────────────────────▼─────────────────────────────────────┐
│                   FastAPI 后端（端口 8100）                    │
│  main.py：路由层 / WebSocket 推送 / 平台级批量控制逻辑          │
├────────────────┬──────────────────┬─────────────────────────┤
│  store.py      │  scheduler.py    │  shop_config.py          │
│  SQLite CRUD   │  定时采集调度     │  CSV/JSON 配置解析       │
│  DB 迁移       │  状态判断         │  session/port 分配       │
└────────────────┴──────┬───────────┴─────────────────────────┘
                        │ 调用
┌───────────────────────▼─────────────────────────────────────┐
│                       采集层                                   │
│  remote_edge.py        │  window_capture.py                  │
│  Playwright CDP        │  mss 截图 + 比例裁剪                 │
│  Win32 窗口控制        │                                      │
├────────────────────────┴────────────────────────────────────┤
│  ocr_reader.py：RapidOCR / PaddleOCR / Tesseract 多引擎      │
└─────────────────────────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│  data/gmv_livelens.sqlite3  │  data/screenshots/             │
│  data/edge_profiles/        │  data/shops_default.json       │
└─────────────────────────────────────────────────────────────┘
```

### 主链路（正常采集流）

```
scheduler._run_loop()
  → store.list_tasks(enabled=True)
  → capture_once(task_id)
    → remote_edge.screenshot_page(page_id)   或  capture_window(hwnd)
    → window_capture.crop_by_ratio()
    → ocr_reader.read_text(crop)
    → ocr_reader.extract_candidates(text, details, keyword_hint, last_value)
    → scheduler._judge(task, selected_value)
    → store.update_task_runtime(task_id, updates)
    → store.add_sample(...)
  → broadcast_snapshot()  →  WebSocket 推送前端
```

### 次级链路

| 链路 | 触发 | 目标 |
|------|------|------|
| 配置初始化 | `POST /api/shops/init` | shop_config → SQLite 任务 + Edge 会话 |
| 任务管理手动动作 | 前端按钮 | 启动/显示/隐藏/关闭 Edge |
| 自动绑定恢复 | show/start Edge 成功后 | 比对页签列表自动恢复 page_id 绑定 |
| WebSocket 快照 | 每次采集完成 / 手动操作后 | 前端实时刷新 |

---

## C. 技术栈与依赖

### 后端

| 技术 | 版本要求 | 在项目中的职责 |
|------|----------|---------------|
| Python | 3.11+ | 主语言 |
| FastAPI | ≥0.110 | HTTP/WebSocket 服务框架 |
| Uvicorn | ≥0.29 | ASGI 服务器，运行 FastAPI |
| SQLite3 | 内置 | 任务、会话、样本持久化 |
| Playwright (sync_api) | ≥1.40 | CDP 连接 Edge，截图、页面操作 |
| ctypes (windll) | 内置 | Win32 API：窗口枚举/显示/隐藏/关闭 |
| mss | ≥9.0 | 高性能屏幕区域截图（window_capture 模式） |
| Pillow (PIL) | ≥10.0 | 图像处理：裁剪、格式转换、base64 编码 |
| OpenCV (cv2) | ≥4.8 | OCR 预处理：灰度、对比度增强、Otsu 二值化、HSV 黄色提取 |
| numpy | ≥1.26 | 图像矩阵操作 |
| RapidOCR | ≥1.3 | 主 OCR 引擎（ONNX Runtime，CPU 推理） |
| pydantic | v2 | API 请求体验证（BaseModel + field_validator） |

### 前端

| 技术 | 说明 |
|------|------|
| 原生 HTML5 | 单页应用，无构建工具，无框架 |
| 原生 CSS | 自定义 CSS 变量实现主题，CSS Grid/Flex 布局 |
| 原生 JavaScript (ES2020+) | 模块无打包，直接 `<script>` 引入 |
| WebSocket API | 浏览器内置，实时接收快照推送 |
| Fetch API | HTTP 请求封装，带超时控制 |

### 为什么选这些技术

- **FastAPI**：异步原生支持 WebSocket，pydantic 校验省去大量手写验证代码
- **Playwright CDP**：比 Selenium 更稳定地接管已运行的浏览器，不需要额外驱动
- **RapidOCR**：纯 Python + ONNX，不依赖 CUDA，CPU 上也能在 100ms 内完成识别
- **原生 JS**：项目是单机桌面工具，避免 Node.js 构建链的环境复杂度
- **SQLite**：单机本地存储，无需数据库服务器，数据文件可直接备份

---

## D. 目录结构与模块地图

```
GMV-LiveLens/
├── backend/
│   ├── main.py              # FastAPI 应用入口，所有 HTTP/WS 路由
│   ├── models.py            # 数据类：CaptureTask, EdgeSession, CandidateAmount
│   ├── services/
│   │   ├── store.py         # SQLite 全部 CRUD + DB 迁移 + session 同步
│   │   ├── scheduler.py     # 定时采集调度器（asyncio）
│   │   └── shop_config.py   # CSV/JSON 配置解析 + ShopConfig 数据类
│   ├── collectors/
│   │   ├── remote_edge.py   # RemoteEdge 类：CDP 控制 + Win32 窗口管理
│   │   ├── window_control.py# Win32 API 封装：窗口枚举/显示/隐藏/关闭/进程管理
│   │   ├── window_capture.py# mss 截图 + crop_by_ratio + image_to_data_url
│   │   └── ocr_reader.py    # 多引擎 OCR + 图像预处理 + 候选评分
│   └── tools/
│       ├── start_shop_edges.py      # 批量启动店铺 Edge 会话
│       ├── smoke_edge_buttons.py    # 四按钮真实冒烟测试脚本（需 Edge 在线）
│       ├── smoke_api.py             # API 接口自动化冒烟测试（14 项，无需 Edge）
│       ├── full_test.py             # 全功能测试（65 项：导入/业务逻辑/DB/OCR/API/前端）
│       ├── find_ocr_anomalies.py    # OCR 特征库异常监控（扫描历史采样挖掘未收录字符）
│       └── benchmark_ocr_engines.py # OCR 引擎准确率基准测试
├── frontend/
│   ├── index.html           # 单页应用 HTML，引入所有 JS/CSS
│   ├── core.js              # 全局状态 / API 封装 / Edge 会话 API / 排序工具
│   ├── app.js               # 任务管理渲染 / 事件路由 / WebSocket 管理 / 拖拽框选
│   ├── dashboard.js         # 实时看板渲染（平台卡片、店铺卡片、sparkline）
│   ├── config.js            # 采集配置工作台（绑定流程、OCR 测试、保存）
│   ├── edge.js              # Edge 会话 UI / 页签列表 / 预览截图
│   └── styles.css           # 全局样式
├── data/
│   ├── gmv_livelens.sqlite3 # 主数据库（运行时生成）
│   ├── shops_default.json   # 备选店铺配置（shops.csv 不存在时的 fallback）
│   ├── shops.csv            # 首选店铺配置（优先级高于 JSON，支持 GBK/GB18030/UTF-8 自动检测）
│   ├── screenshots/         # 历史截图缩略图（自动清理，默认保留 1 天）
│   └── edge_profiles/       # 各店铺 Edge 独立 Profile 目录
│       ├── 天猫_BLANC旗舰店/
│       ├── 天猫_GOLF旗舰店/
│       └── ...（每个店铺一个子目录）
├── .trae/
│   └── documents/           # 项目规划和说明文档
├── requirements.txt         # Python 依赖声明
└── 第1步_启动GMV服务.bat    # 一键启动脚本
```

### 关键文件职责详解

**`backend/main.py`**
- FastAPI 应用对象、CORS 中间件、静态文件挂载
- 全部 HTTP 路由（约 40 个端点）和 1 个 WebSocket 端点
- `build_snapshot()`：构建实时快照 JSON，被 `/api/tasks` 和 WS 共用
- `broadcast_snapshot()`：向所有已连接 WS 客户端推送快照
- `run_platform_edge_action()`：平台级批量 Edge 操作的通用执行框架（顺序执行）
- `auto_restore_edge_session_task_bindings()`：Edge 显示/启动后自动恢复 page_id 绑定
- `_page_match_score()`：对页签列表评分，用于自动绑定恢复和候选页排序
- 应用启动时：`init_db()` → `sync_tasks_with_shop_configs()` → 调度器启动（默认暂停）；不会自动结束现有 Edge 进程

**`backend/models.py`**
- `CaptureTask`：采集任务的完整字段（配置字段 + 运行时字段）
- `EdgeSession`：Edge 会话记录（session_id、debug_port、user_data_dir、session_mode）
- `CandidateAmount`：OCR 候选金额（value、text、score、reason）

**`backend/services/store.py`**
- `init_db()`：建表 + `_ensure_columns()`（列迁移） + 默认 session 补齐 + legacy session 迁移 + shop session 同步
- `sync_tasks_with_shop_configs()`：将 shop_config 的变更同步到 SQLite，不覆盖运行时字段
- `upsert_task()` / `upsert_edge_session()`：幂等写入
- `preferred_launch_url_for_task()`：优先返回 `target_page_url`（配置的业务入口），再退回 `page_url`
- `update_task_runtime()`：只允许写入运行时字段白名单，防止误覆盖配置字段

**`backend/services/scheduler.py`**
- `CaptureScheduler`：asyncio 单事件循环调度器
- `_run_loop()`：每 0.2s 轮询 due 任务，通过 `asyncio.gather + asyncio.to_thread` 并发执行
- `capture_once(task_id)`：单次同步采集（在线程中运行，不阻塞事件循环）
- `_judge()`：候选值可信度判断，返回 status/reason/trusted/pending_value/pending_count
- `_cleanup_old_screenshots(task_id)`：清理超过 `GMV_SCREENSHOT_MAX_AGE_DAYS`（默认 1 天）的截图

**`backend/services/shop_config.py`**
- `ShopConfig`：冻结数据类，持有一个店铺的全部配置
- `load_shop_configs()`：优先读 `shops.csv`，备选 `shops_default.json`，支持 UTF-8/GBK/GB18030 编码
- `edge_session_id_for(platform, shop_name)`：生成规范化 session_id（如 `天猫_BLANC旗舰店`）
- `platform_key(platform)`：平台归一化（含"天猫/淘宝/生意参谋" → "天猫"）
- `PLATFORM_PORT_BASE`：天猫从 9231、京东从 9241、抖音从 9251，按平台内顺序递增

**`backend/collectors/remote_edge.py`**
- `RemoteEdge`：核心类，每个 Edge 会话对应一个实例
  - 内部维护一个 `threading.Thread`（worker）和一个 `queue.Queue`
  - 所有 Playwright 操作通过 `_call()` 投入队列，由 worker 线程串行执行
  - `start_edge()` / `show_edge()` / `hide_edge()` / `close_edge()`：四个主要操作
  - `health()`：检查调试端口 + Playwright 连接状态 + 窗口诊断
  - `debug_available_quick()`：**不进入队列**，直接 HTTP 检查调试端口（用于平台级批量 show 的快速预判）
  - `_stale` / `_stale_reason`：会话是否已过期（超时后标记，下次 get_client 时重建）
  - `_window_op_running`：窗口操作进行中标志，调度器跳过该会话的采集
- `RemoteEdgeManager`：管理所有 `RemoteEdge` 实例的缓存池（`_clients` dict + lock）
- `remote_edge_manager`：全局单例
- 数据类：`RemoteEdgeHealth` / `RemoteEdgeWindowState` / `RemoteEdgeCloseState` / `RemoteEdgeNavigationState` / `RemotePageInfo` / `PageCleanupResult`
- 严格单页策略：`_enforce_single_page()` 在启动、显示、平台批量启动后只保留一个主标签，并把 `page_count`、`primary_page_url`、`closed_extra_pages_count` 回写给 API。

**`backend/collectors/window_control.py`**
- Win32 API 封装（`ctypes.windll.user32` / `kernel32`）
- `list_edge_windows()`：枚举所有符合条件的顶层窗口
- `edge_window_diagnostics()`：根据 debug_port / user_data_dir / pid 匹配 Edge 进程和窗口
- `show_edge_window()` / `hide_edge_window()` / `close_edge_window_native()` / `kill_edge_process_tree()`
- `kill_all_edge_processes()`：底层紧急能力，默认启动和关闭流程不调用，避免破坏登录态
- `_edge_processes()`：通过 PowerShell `Get-CimInstance` 获取进程列表，有 1s TTL 缓存

---

## D2. 数据目录与运行产物

| 路径 | 内容 | 是否自动生成 | 是否可删除 |
|------|------|-------------|------------|
| `data/gmv_livelens.sqlite3` | 主数据库：任务、会话、采样历史 | 是 | **不能删**（删后丢失所有配置和历史） |
| `data/screenshots/` | 每次采集的截图缩略图（480px 宽） | 是 | 可以（服务重启后重建目录；默认 1 天后自动清理） |
| `data/ocr_datasets/` | 自动收集的纯数字 OCR 样本截图 | 是 | 可以（用于未来 AI 引擎微调，可定期清理） |
| `data/edge_profiles/天猫_xxx/` | Edge 独立 Profile（含 Cookie/登录态） | 首次启动 Edge 时生成 | **不能删**（删后需要重新登录） |
| `data/shops_default.json` | 店铺默认配置（手动维护） | 否 | **不能删**（是采集的核心配置源） |
| `data/shops.csv` | 店铺配置的 CSV 格式（优先级更高） | 否 | 如不使用可删 |
| `data/browser_profile/` | window_capture 模式的公共 Profile（如有） | 按需生成 | 删后需重新登录该公共账号 |

---

## E. 数据模型与数据库

### 四张表

#### `app_settings` — 全局设置表

| 字段 | 类型 | 说明 |
|------|------|------|
| `key` | TEXT PK | 配置键名（如 `ocr_engine`, `interval_seconds`） |
| `value` | TEXT | 配置的字符串值 |

#### `capture_tasks` — 采集任务表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `capture_mode` | TEXT | `remote_edge` 或 `window_capture` |
| `page_id` | TEXT | 当前绑定的 Edge 页签 ID（CDP 分配的 UUID 片段，会话重启后失效） |
| `page_url` | TEXT | 当前绑定页签的 URL（运行时记录） |
| `target_page_url` | TEXT | 配置的目标业务页 URL（shop_config 中的 `default_page_url`） |
| `page_title` | TEXT | 当前绑定页签的标题 |
| `edge_session_id` | TEXT | 关联的 Edge 会话 ID（如 `天猫_BLANC旗舰店`） |
| `platform` | TEXT | 平台（天猫/京东/抖音/其他平台） |
| `shop_name` | TEXT | 店铺名 |
| `keyword_hint` | TEXT | OCR 关键词（如"成交金额"），提高候选值评分 |
| `interval_seconds` | REAL | 采集间隔，最小 0.5s |
| `enabled` | INTEGER | 0/1，是否启用 |
| `base_width` / `base_height` | INTEGER | 截图时浏览器窗口的参考分辨率 |
| `x`, `y`, `width`, `height` | INTEGER | GMV 区域的像素坐标（基于 base_width/height） |
| `x_ratio`, `y_ratio`, `width_ratio`, `height_ratio` | REAL | GMV 区域的比例坐标（0~1，相对于截图尺寸） |
| `safety_margin` | REAL | 裁剪时的额外边距比例（默认 0.3，防止框选太小） |
| `confirm_count` | INTEGER | 连续确认次数阈值（默认 2，达到后才设为 ok） |
| `last_trusted_value` | INTEGER | 最近一次可信 GMV 值 |
| `pending_value` | INTEGER | 当前待确认的候选值 |
| `pending_count` | INTEGER | 已连续出现相同候选值的次数 |
| `status` | TEXT | 任务运行状态（见状态机章节） |
| `last_success_at` | TEXT | 最近一次成功采集的时间 |
| `last_sample_at` | TEXT | 最近一次采样的时间（包括失败） |
| `last_ocr_text` | TEXT | 最近一次 OCR 识别的原始文本 |
| `last_reason` | TEXT | 最近一次状态变更的原因描述 |
| `last_screenshot_path` | TEXT | 最近一次截图的本地路径 |

#### `edge_sessions` — Edge 会话表

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | TEXT PK | 唯一标识（如 `天猫_BLANC旗舰店`，默认会话为 `default_real_edge`） |
| `name` | TEXT | 显示名称 |
| `platform` | TEXT | 所属平台 |
| `shop_name` | TEXT | 所属店铺名 |
| `debug_port` | INTEGER UNIQUE | Edge 调试端口（如 9231）|
| `user_data_dir` | TEXT | Edge Profile 目录路径（real_profile 模式为空） |
| `session_mode` | TEXT | `isolated`（独立店铺环境）或 `real_profile`（真实个人环境） |
| `enabled` | INTEGER | 是否启用 |

#### `gmv_samples` — 采样历史表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `task_id` | INTEGER FK | 关联任务 |
| `sampled_at` | TEXT | 采样时间 |
| `ocr_text` | TEXT | 原始 OCR 文本 |
| `candidates_json` | TEXT | 候选值 JSON 数组 |
| `selected_value` | INTEGER | 本次选中的候选值 |
| `trusted_value` | INTEGER | 本次最终可信值（可能延迟到连续确认后才更新） |
| `status` | TEXT | 采样状态 |
| `reason` | TEXT | 状态原因 |
| `screenshot_path` | TEXT | 截图路径 |

### 关键字段关系

- `task.edge_session_id` → `edge_sessions.session_id`（逻辑外键，不是数据库外键约束）
- `task.page_id`：CDP 分配的页签 UUID 片段，**跨会话不稳定**，Edge 重启后会变
- `task.page_url` vs `task.target_page_url`：`page_url` 是运行时绑定的实际 URL；`target_page_url` 是 shop_config 中的配置 URL，Edge 启动时优先导航到这个地址
- `session.debug_port`：全局唯一，不同 session 不能共用同一端口

---

## F. 配置系统

### 配置文件优先级

`data/shops.csv`（存在则优先）> `data/shops_default.json`（备选）

### shops_default.json / shops.csv 字段说明

| 字段 | 类型 | 是否必填 | 说明 |
|------|------|---------|------|
| `platform` | string | 是 | 平台名，含"天猫"/"淘宝"/"生意参谋"都归一化为"天猫" |
| `shop_name` | string | 是 | 店铺名，与 platform 组合唯一 |
| `keyword_hint` | string | 否 | OCR 关键词，默认"成交金额" |
| `default_page_url` | string | 推荐填 | 店铺数据页 URL，Edge 启动时优先导航到此 |
| `url_patterns` | string/list | 可选 | 用于 `/api/shops/match` 自动匹配页签 |
| `url_must_contain` | string/list | 可选 | 匹配时的必含关键词（AND 逻辑） |
| `enabled` | bool/string | 否 | 是否自动启用采集，默认 false |
| `debug_port` | int | 否 | 手动指定调试端口，不填则自动分配 |
| `interval_seconds` | float | 否 | 采集间隔，默认 2s |
| `confirm_count` | int | 否 | 连续确认次数，默认 2 |
| `safety_margin` | float | 否 | 裁剪边距比例，默认 0.2 |

> **注意：全局采集频率覆盖**
> 虽然 `shops.csv` 中仍保留 `interval_seconds` 字段，但目前系统调度器已升级为采用全局采集频率（存储在 `app_settings` 中，默认 0.5 秒）。该全局设置会覆盖单个任务配置的时间间隔，以便于大促期间统一调整。

### 端口自动分配规则

```python
PLATFORM_PORT_BASE = {
    "天猫": 9231,
    "京东": 9241,
    "抖音": 9251,
    "其他平台": 9261,
}
DEFAULT_PORT_BASE = 9301  # 未匹配平台的兜底起始
default_real_edge = 9222  # 真实个人环境固定端口
```

平台内按配置顺序递增（天猫第1家=9231，第2家=9232，以此类推）。

### 初始化任务时的字段映射

```
ShopConfig.to_task_payload() → {
    page_id: "",           # 未绑定
    page_url: default_page_url,
    target_page_url: default_page_url,
    edge_session_id: slugify(f"{platform}_{shop_name}"),
    ...
}
```

### 什么时候填 url_patterns vs url_must_contain

- `url_patterns`：页签 URL 中含有其中任意一个字符串则匹配（OR 逻辑），用于 `/api/shops/match` 自动匹配
- `url_must_contain`：所有关键词都必须存在才匹配（AND 逻辑），用于过滤掉相似但错误的 URL
- 如果只有一个明确的业务页 URL，直接填 `default_page_url` 即可，`url_patterns` 和 `url_must_contain` 可以不填

---

## G. 后端能力总表

### 系统与健康检查

| API | 方法 | 说明 |
|-----|------|------|
| `GET /api/health` | GET | 服务健康状态 + 调度器状态 |
| `GET /api/realtime` | GET | 同 `/api/tasks`，返回完整快照 |
| `GET /api/windows` | GET | 枚举当前所有可见窗口（window_capture 模式使用） |

### 任务管理

| API | 方法 | 说明 |
|-----|------|------|
| `GET /api/tasks` | GET | 返回完整快照（含所有任务、汇总数据） |
| `POST /api/tasks` | POST | 新建或更新任务（upsert by id） |
| `POST /api/tasks/{id}/enabled` | POST | 启用/禁用任务 |
| `POST /api/tasks/{id}/capture-once` | POST | 手动触发单次采集 |
| `POST /api/tasks/{id}/manual-correction` | POST | 人工纠错（强制设置可信值为 ok 状态） |
| `POST /api/tasks/{id}/rebind-page` | POST | 重新绑定页签（更新 page_id/page_url/edge_session_id） |
| `POST /api/tasks/{id}/delete` | POST | 删除任务（含历史采样） |
| `DELETE /api/tasks/{id}` | DELETE | 同上 |
| `GET /api/tasks/{id}/samples` | GET | 获取历史采样记录（最多 500 条） |
| `GET /api/history/{id}` | GET | 同 samples，别名 |
| `GET /api/tasks/{id}/page-candidates` | GET | 扫描当前会话页签，返回候选绑定列表（含评分和 flow_state） |
| `POST /api/tasks/{id}/resume-after-login` | POST | 登录后自动继续：打开 target_page_url 并恢复绑定 |

### 调度器控制

| API | 方法 | 说明 |
|-----|------|------|
| `GET /api/scheduler` | GET | 调度器当前状态（running / loop_alive / tracked_tasks） |
| `POST /api/scheduler/start` | POST | 恢复调度（resume） |
| `POST /api/scheduler/pause` | POST | 暂停调度 |

### 店铺配置

| API | 方法 | 说明 |
|-----|------|------|
| `GET /api/shops` | GET | 返回 shop_config 配置列表（来自 CSV/JSON） |
| `POST /api/shops/init` | POST | 将 shop_config 同步到数据库（创建/更新任务和会话） |
| `GET /api/shops/match` | GET | 扫描指定 session 的页签，按 url_patterns 返回匹配建议 |
| `POST /api/shops/bind` | POST | 批量绑定（task_id → page_id） |

### Edge 会话管理

| API | 方法 | 说明 |
|-----|------|------|
| `GET /api/edge-sessions` | GET | 列出所有会话（含 health 字段）|
| `POST /api/edge-sessions` | POST | 新建或更新 Edge 会话 |
| `DELETE /api/edge-sessions/{id}` | DELETE | 删除会话（关联任务转到 default_real_edge） |
| `GET /api/edge-sessions/{id}/health` | GET | 单个会话健康状态 |
| `GET /api/edge-sessions/{id}/pages` | GET | 列出会话当前所有页签（debug 未连接时返回 [] ） |
| `POST /api/edge-sessions/{id}/start` | POST | 启动 Edge（若已运行则直接连接） |
| `POST /api/edge-sessions/{id}/show` | POST | 显示 Edge 窗口（若未运行则先启动） |
| `POST /api/edge-sessions/{id}/hide` | POST | 隐藏 Edge 窗口（move_offscreen → minimize → SW_HIDE）|
| `POST /api/edge-sessions/{id}/close` | POST | 安全关闭 Edge（WM_CLOSE → CDP close，不自动强杀）|
| `POST /api/edge-sessions/{id}/open` | POST | 在会话中打开新页面 |
| `POST /api/edge-sessions/{id}/pages/{page_id}/preview` | POST | 对指定页签截图，返回 base64 图片 |
| `POST /api/edge-sessions/{id}/pages/{page_id}/reload` | POST | 重载指定页签 |

### 平台级批量 Edge 控制

| API | 方法 | 说明 |
|-----|------|------|
| `POST /api/platforms/{platform}/launch-edge` | POST | 批量启动+显示（start + show，顺序执行） |
| `POST /api/platforms/{platform}/show-edge` | POST | 批量显示（仅对已运行的 Edge 生效，不自动启动） |
| `POST /api/platforms/{platform}/hide-edge` | POST | 批量隐藏（顺序执行） |
| `POST /api/platforms/{platform}/close-edge` | POST | 批量关闭（顺序执行） |
| `POST /api/platforms/{platform}/start-edge` | POST | 批量启动+显示（兼容旧入口，当前与 launch-edge 语义一致） |

> **重要**：平台"显示"与任务"显示"语义不同。任务级"显示Edge"会自动启动未运行的 Edge；平台级"显示Edge"只显示已在运行的实例，未运行则跳过（返回 edge_debug_unavailable）。平台"启动Edge"和店铺"启动Edge"都表示“启动并显示”。

### OCR 与窗口预览

| API | 方法 | 说明 |
|-----|------|------|
| `GET /api/ocr/engines` | GET | 返回可用 OCR 引擎列表 |
| `POST /api/test-ocr` | POST | 对指定截图区域执行 OCR，返回候选值和调试信息 |
| `POST /api/window-preview` | POST | 对窗口截图并返回 base64 图片（window_capture 模式） |

### WebSocket

| API | 协议 | 说明 |
|-----|------|------|
| `WS /ws/live` | WebSocket | 实时快照推送，连接后立即推送一次全量快照 |

---

## G2. 服务层职责拆解

### `store.py` 内部子能力

```
init_db()
  ├── CREATE TABLE IF NOT EXISTS (三张表)
  ├── _ensure_columns()    ← 列迁移（支持老版本 DB 升级）
  ├── _ensure_default_edge_session()  ← 保证 default_real_edge 始终存在
  ├── _migrate_legacy_group_sessions()  ← 迁移旧的 taobao_group/jd_group 等
  └── _ensure_shop_edge_sessions()  ← 将 shop_config 的 session 同步到 DB

CRUD 层：
  upsert_task / get_task / list_tasks / delete_task / set_task_enabled
  update_task_runtime  ← 白名单保护，只允许写运行时字段
  add_sample / recent_samples
  upsert_edge_session / get_edge_session / list_edge_sessions / delete_edge_session

辅助函数：
  preferred_launch_url_for_task()  ← 优先 target_page_url，备选 page_url
  preferred_launch_url_for_session()  ← 从该 session 的所有任务中找最佳启动 URL
  normalize_session_mode()  ← 兼容旧数据的 session_mode 归一化
```

### `scheduler.py` 内部子能力

```
CaptureScheduler
  ├── start() / pause() / resume() / stop()
  ├── _run_loop()  ← asyncio 任务，每 0.2s 检查 due tasks
  │     └── asyncio.gather(*[to_thread(capture_once, id) for id in due_ids])
  ├── capture_once(task_id)  ← 同步，在线程中执行
  │     ├── remote_edge 模式: find_page → screenshot_page
  │     ├── window_capture 模式: find_window → capture_window
  │     ├── crop_by_ratio → read_text → extract_candidates
  │     ├── _judge()  ← 状态判断
  │     └── update_task_runtime + add_sample
  ├── _judge(task, selected)  ← 核心评判逻辑（见 J 章节）
  ├── _is_plausible_next(previous, current)  ← 相邻值合理性检查（0.85-1.35 倍率范围内）
  └── _cleanup_old_screenshots(task_id)  ← 清理超龄截图文件
```

### `shop_config.py` 内部子能力

```
load_shop_configs()
  ├── _rows_from_csv() 或 _rows_from_json()
  ├── 编码容错：utf-8-sig → gb18030 → utf-8 → gbk
  ├── platform_key()  ← 平台归一化
  ├── split_list()  ← 解析多值字段（支持 ;,/换行 分隔）
  ├── default_page_url_for()  ← 优先 explicit URL，备选 url_patterns 中的第一个 http URL
  └── 去重检查：(platform, shop_name) 和 edge_session_id 都不允许重复
```

---

## H. 前端页面与交互能力

### 实时看板（`/` 默认视图）

**文件**：`dashboard.js`

**展示内容**：
- 顶部：总 GMV（所有启用任务之和）、任务数/正常数、刷新时间
- 平台汇总卡片：每个平台的 GMV 合计、占比、sparkline（伪随机波形，基于 GMV 值作种子）
- 平台筛选栏：点击平台名过滤下方店铺卡片
- 店铺卡片网格：每家店铺的最新可信 GMV、最近更新时间、异常状态高亮

**依赖接口**：`/api/tasks`（初次加载）+ `/ws/live`（后续实时更新）

**刷新机制**：
- 优先 WebSocket，连接成功后接收服务端推送，3s 内连接超时则切换轮询（2s 间隔）
- 断线后 1.5s 自动重连 WebSocket，并在轮询期间继续推送

**平台聚合逻辑**：`aggregatePlatforms()` 在前端将任务按 `normalizePlatform(task.platform)` 分组，同一平台的 GMV 累加；排序按 GMV 合计降序。

### 采集配置工作台（视图 `config`）

**文件**：`config.js`

**全局顶部导航栏设置**：
- **全局 OCR 引擎切换**：默认自动（RapidOCR优先），可手动切换为 `ddddocr`（适合极高干扰和验证码艺术字）。
- **全局采集频率**：默认 0.5s（秒），输入框支持精确到 0.5 秒，替换了旧版单任务独立的频率配置。保存后立刻生效于后台调度器。

**三步主流程**：

```
STEP 01 初始化任务
  └── "一键初始化默认店铺" → POST /api/shops/init → 自动聚焦第一家待配置店铺

STEP 02 绑定业务页
  └── 扫描页签 → GET /api/tasks/{id}/page-candidates
      ├── 返回 pages 列表（含评分和标签：is_current_bound / is_target_page / is_login_page）
      ├── 手动选择目标页签 → 点击"使用此页面"
      └── POST /api/tasks/{id}/rebind-page → 保存绑定

STEP 03 标定 + 保存
  ├── "生成预览" → POST /api/edge-sessions/{id}/pages/{page_id}/preview → 显示截图
  ├── 拖拽框选 GMV 区域 → 记录 x/y/width/height 比例坐标
  ├── "测试识别" → POST /api/test-ocr → 返回候选值和引擎信息
  └── "保存并进入下一家" → POST /api/tasks → 写入 DB，自动切换到下一家待配置店铺
```

**flow_state 状态机**（由 `setupFlowState()` 计算）：

| flow_state | 条件 | 下一步操作 |
|------------|------|-----------|
| `idle` | 无当前任务 | 先初始化店铺 |
| `bind` | 无 page_id 或 waiting_page | 扫描页签并选择 |
| `rebind_required` | 旧 page_id 失效 | 重新选择页签 |
| `preview` | 有 page_id 但无预览 | 生成预览（已放宽绑定限制，不再强制拦截登录页或非目标业务页） |
| `region_selected` | 有预览但无框选 | 拖拽框选 GMV |
| `ready_to_save` | 有预览+有框选 | 测试识别，保存 |

**进度汇总**（`setupStageMeta()`）：
- `pending_bind`：无 page_id 或 page_id 失效
- `pending_calibrate`：有 page_id 但坐标与默认值相同（未真正标定）
- `completed`：有 page_id 且坐标已自定义

### 采集配置流程图（视图 `config-flow`）

**文件**：`app.js` 中的 `renderConfigFlowPage()`

纯前端渲染的静态流程说明页，包含：
- 6 步主流程思维导图（STEP 01-06）
- 4 种高频异常分支（扫描不到页签 / 会话未就绪 / 预览失败 / OCR 不准）
- 3 个页面模块职责说明（配置工作台 / 截图标定区 / 任务管理区）
- 推荐操作手册（按序列出 6 步操作）

### 任务管理（视图 `manager`）

**文件**：`app.js` 中的 `renderManager()`

**平台卡片**：按平台分组，显示平台名、任务数、可控 Edge 数
**平台级四按钮**：启动Edge / 显示Edge / 隐藏Edge / 关闭Edge（对平台内所有 remote_edge 任务批量操作，后端顺序执行，单个店铺失败不阻塞后续店铺）
**店铺卡片**：每家店铺显示最新 GMV、运行状态、最近采样时间、Edge 健康摘要
**店铺级四按钮**：与平台级相同，但仅操作单个会话；店铺级“启动Edge”当前直接走后端 `show` 单入口，避免前端先 `start` 再 `show` 造成双窗口
**其他操作**：采一次 / 编辑 / 启用/暂停 / 历史 / 重绑页面 / 删除

**状态筛选**：全部 / 暂停中 / 正常(ok) / 异常

**Edge 健康摘要格式**：`端口在线/离线 / 有窗口/无窗口 / 窗口动作中/空闲 / 陈旧/正常 / 阶段`

---

## H2. 前端基础能力

### 全局状态（`core.js` 中的 `state` 对象）

```javascript
state = {
  snapshot: { tasks: [], summary: {} },  // 最新快照
  preview: null,                          // 当前预览图
  selection: null,                        // 拖拽框选区域
  editingTaskId: null,                    // 正在编辑的任务 ID
  currentPreviewSource: null,             // 预览来源（capture_mode, page_id 等）
  platformFilter: "all",                  // 实时看板平台筛选
  statusFilter: "all",                    // 任务管理状态筛选
  edgeSessions: [],                       // Edge 会话列表缓存
  shopConfigs: [],                        // shop_config 列表缓存
  setupQueue: [],                         // 待配置任务队列（按优先级排序）
  currentSetupTaskId: null,               // 当前工作台聚焦的任务
  setupSummary: {...},                    // 配置进度汇总
  lastBindSessionId: "",                  // 最近使用的 Edge 会话
  setupRecovery: null,                    // 工作台恢复状态提示
  bindCandidates: null,                   // 页签候选列表（/page-candidates 响应）
  selectedBindPageId: "",                 // 当前选中的候选页签
  expandedTaskIdentities: {},             // 双击展开的任务 URL 映射
}
```

### API 请求封装

```javascript
api(path, options)
  ├── 支持 timeoutMs 参数（AbortController 实现）
  ├── 支持 actionName 参数（超时错误信息更友好）
  ├── response.ok 为 false 时 throw Error(await response.text())
  └── 超时时 throw Error(JSON.stringify({detail: {reason_code: "edge_action_timeout"}}))
```

### Edge 操作 API 封装（`core.js`）

| 函数 | 对应 API | 超时 |
|------|---------|------|
| `startEdgeSession()` | `POST /api/edge-sessions/{id}/start` | 18s |
| `showEdgeSession()` | `POST /api/edge-sessions/{id}/show` | 35s |
| `startAndShowEdgeSession()` | 直接调用 `showEdgeSession()` 单入口 | 35s |
| `hideEdgeSession()` | `POST /api/edge-sessions/{id}/hide` | 22s |
| `closeEdgeSession()` | `POST /api/edge-sessions/{id}/close` | 35s |
| `callPlatformEdgeAction()` | `/api/platforms/{p}/{action}-edge` | 45s |

---

## I. Edge 控制体系

### 会话模式

| 模式 | `session_mode` | `user_data_dir` | 适用场景 |
|------|-------------|-----------------|---------|
| 独立店铺环境 | `isolated` | `data/edge_profiles/天猫_xxx/` | 多账号，每家店铺固定一个 Profile，首次手动登录后长期复用 |
| 真实个人环境 | `real_profile` | `""` (空) | 使用个人日常 Edge，适合临时调试；启动前必须关闭所有普通 Edge |

### `default_real_edge` 的特殊性

- 固定 session_id = `default_real_edge`，固定端口 9222
- `session_mode = real_profile`，使用个人默认 Profile
- 不能被删除（store.py 中有保护）
- 启动时会检测是否有普通 Edge 在运行；若有，返回 `edge_running_conflict` 错误

### 四个操作的真实执行链路

#### 启动（start_edge）

`start_edge` 是后端底层启动能力；当前前端店铺级“启动Edge”按钮不再直接走 `start -> show`，而是直接调用 `show_edge` 单入口，由后端负责“未运行时启动并显示、已运行时只恢复窗口”。

```
client.start_edge(launch_url)
  → _call("start_edge", lambda: _start_edge(launch_url))  [Worker Thread]
    → _start_edge()
      1. 检查调试端口是否已开（_debug_available()）
         → 若已开：_ensure_launch_page(target_url) → _enforce_single_page(target_url) → 返回 health
      2. 若 real_profile 模式：检测是否有普通 Edge 运行（_edge_running()）
         → 若有：返回 edge_running_conflict 错误
      3. 若 isolated 模式且进程在运行但无调试标志：返回 profile_locked_without_debug，不自动强杀重启
      4. subprocess.Popen(args) 启动 msedge.exe（带 --remote-debugging-port）
         - target_url 存在：直接以目标业务 URL 启动
         - target_url 为空：只打开 about:blank
         - visible=False 且 isolated 模式：窗口移到屏幕外
         - visible=True：窗口放到主屏可见区域
      5. 轮询 20 次（每次 0.5s）等待调试端口就绪
      6. 连接 Playwright Browser（connect_over_cdp）
      7. _ensure_launch_page(target_url)
      8. _enforce_single_page(target_url)
      9. 返回 RemoteEdgeHealth（含 page_count / primary_page_url / closed_extra_pages_count）
```

#### 显示（show_edge）

```
client.show_edge(launch_url)
  → _call("show_edge", lambda: _show_edge(launch_url))  [Worker Thread]
    → _show_edge()
      ├── 设置 _window_op_running = True（调度器跳过）
      └── __show_edge()
          1. 若有窗口但调试端口未开：直接 show 窗口（不启动新进程）
          2. 调用 _start_edge(target_url, visible=True)（若未运行则可见启动）
          3. 若 debug 不可用：返回 window_found=False
          4. _try_show_window()
             → show_edge_window(debug_port, user_data_dir, pid, cached_hwnd)
             → SW_SHOW + SW_RESTORE + _move_window_into_view + _activate_window + SW_MAXIMIZE（3次重试）
          5. 若窗口找不到：
             → 只有 diagnostics 中没有任何 candidate_pids 时才允许 _spawn_native_window()
             → 若已有 profile/端口进程但无可恢复窗口，则返回 window_restart_blocked_for_login_safety，不自动强杀重启
          6. show 成功后执行 _enforce_single_page(target_url)
          7. 返回 RemoteEdgeWindowState（含 window_found、window_action、maximized、page_count、primary_page_url）
```

**为什么店铺级启动不再前端 start → show**：  
旧链路中，前端点击“启动Edge”会先请求 `/start`，再请求 `/show`。`/start` 可能已经打开一个窗口和一个 newtab，`/show` 又可能因为窗口诊断不稳定而补开 native window，最终表现为“只启动一个任务却出现两个 Edge”。当前按钮改为单次 `show_edge` 后端入口，启动、显示、窗口恢复、单页清理都在同一条串行链路里完成。

#### 隐藏（hide_edge）

```
client.hide_edge()
  → __hide_edge()
    1. 若调试端口未开且无窗口：返回 edge_debug_unavailable
    2. hide_edge_window(debug_port, user_data_dir, pid, cached_hwnd)
       按顺序尝试三种策略（任意一种使窗口 hidden_like 则成功）：
       ① move_offscreen：移到 (32000, 0) 超出屏幕外（首选，CDP 仍可截图）
       ② minimize_window：SW_MINIMIZE 最小化
       ③ hide_window：SW_HIDE 完全隐藏
    3. 验证：_window_is_hidden_like(window) = is_minimized OR is_offscreen OR NOT is_visible
    4. 返回 RemoteEdgeWindowState
```

**为什么优先 move_offscreen 而非直接 SW_HIDE**：  
SW_HIDE 后 CDP 截图会失败（页面渲染被暂停），而移到屏幕外的窗口仍在渲染，CDP 截图照常工作。

#### 关闭（close_edge）

```
client.close_edge()
  → __close_edge()
    1. _try_graceful_shutdown()
       ① 发送 WM_CLOSE 到主窗口（等同用户点 X，Edge 自动 flush Cookie）
       ② 若失败：通过 CDP 关闭所有页面并 browser.close()
    2. 若优雅关闭失败：返回 safe_close_timeout，不自动 taskkill /F
    3. _reset_browser()（清理 Playwright 连接）
    4. 验证：debug_available + residual_pids
    5. 返回 RemoteEdgeCloseState（含 closed、force_kill_used、close_mode）
```

### 平台级四按钮 vs 任务级四按钮

| 维度 | 任务级 | 平台级 |
|------|--------|--------|
| 操作粒度 | 单个 session | 该平台所有 session |
| 执行方式 | 单次 HTTP 请求 | 顺序执行（for 循环），全部完成后返回 |
| "显示"语义 | 未运行则先启动 | 仅显示已运行的，未运行则跳过 |
| "启动"语义 | 调用 show 单入口，启动并显示 | `start-edge` 与 `launch-edge` 都顺序启动并显示 |
| 结果结构 | 单个 windowState/health | `{results: [...], succeeded, controlled_edge_tasks, execution_mode: "sequential"}` |
| 前端超时 | 35s | 45s |

### 严格单页策略

受控店铺 Edge 的产品策略是“一个店铺会话只保留一个主标签”。每次 `start_edge`、`show_edge`、平台 `launch-edge` / `start-edge` 成功后都会执行 `_enforce_single_page(target_url)`：

- 优先保留目标业务页（匹配 `target_page_url` / `launch_url`）。
- 其次保留登录页或第一个有效用户页。
- 关闭 `about:blank`、Edge 新标签页、Edge 首页、历史恢复页、重复目标页和其它额外页。
- API 返回 `page_count`、`primary_page_id`、`primary_page_url`、`closed_extra_pages_count`、`closed_extra_pages`，前端提示会显示清理结果。

这个策略解决了“启动 N 个 Edge 时，每个 Edge 随机出现几个网页标签”的问题；代价是受控 Edge 不保留用户额外手动打开的标签。

### RemoteEdgeHealth 关键字段说明

```
debug_available: bool      # 调试端口 HTTP 200 可达
connected: bool            # Playwright Browser.is_connected()
stage: str                 # 当前操作阶段（如 "show:window_ready", "idle"）
is_window_op_running: bool # 是否正在执行窗口操作（调度器据此跳过）
is_stale: bool             # 会话是否已标记为过期（需要重建）
stale_reason: str          # 过期原因（如 "show_edge@start:debug_port_timeout"）
profile_initialized: bool  # Profile 目录是否已有数据（有则可能保留登录态）
window_diagnostics: dict   # 窗口诊断信息（candidate_pids, candidate_windows, has_no_startup_window）
profile_diagnostics: dict  # Profile 目录诊断信息（exists, entry_count, cookie_files, last_modified）
reason_code: str           # 最近一次操作的错误码
recovery_attempted: list   # 已尝试的恢复动作列表
page_count: int            # 当前保留的 CDP page 标签数量
primary_page_url: str      # 严格单页策略保留的主标签 URL
closed_extra_pages_count: int # 本次自动关闭的多余标签数量
```

---

## J. OCR 与可信值判断

### OCR 形近字特征库与监控 (2026-05-03 新增)

系统在 `backend/collectors/ocr_reader.py` 顶部维护了一个**集中的特征库**：
- `OCR_CHAR_REPLACEMENTS`：用于将数字中间夹杂的英文字母/汉字强制替换回数字（例如 `o/O/D->0`, `l/I/i/j->1`, `P/h/H/旧/忙->4`, `s/S->5`, `门/->7` 等）。
- `OCR_CURRENCY_ALIASES`：用于容忍前缀货币符号 `￥` 被误识别的场景（如 `半、举、夫、羊、旧`），动态生成到 `AMOUNT_PATTERN` 正则中并赋予相同的 +35 评分。

**特征库自动化监控机制**：
我们提供了独立的脚本 `backend/tools/find_ocr_anomalies.py`。
- **作用**：遍历 `gmv_samples` 全量历史采样数据，挖掘“夹在数字中间的非数字字符”以及“紧挨数字左侧的非数字字符”。
- **单点维护**：该脚本直接导入主项目的特征库进行比对，若发现大量高频且带有 `❌ 未收录` 标记的字符，开发者只需在 `ocr_reader.py` 顶部的特征库中补充即可，主逻辑与脚本将自动同步生效。
- **使用方法**：在项目根目录执行 `python backend/tools/find_ocr_anomalies.py`。

### 图像预处理（`ocr_reader._preprocess_variants()`）

对同一张截图生成 4 个变体，逐一尝试：
1. `color`：原始彩色图（放大至最小高度 160px）
2. `contrast_gray`：灰度 + 对比度增强（alpha=1.55, beta=8）
3. `yellow_digits`：HSV 提取黄色区域（GMV 数字常为亮黄色），反转为白底黑字
4. `otsu`：Otsu 自动阈值二值化

### 多引擎回退机制与验证码引擎（`read_text()`）

```python
for engine in _engine_order():      # 优先级：rapidocr > legacy_rapidocr > paddleocr > ddddocr > tesseract
    for variant in variants:        # 逐一尝试 4 个预处理变体
        rows = runner(variant)
        if extract_candidates(joined, all_rows, keyword_hint, last_value):
            return text, all_rows   # 提前返回：当前结果已有有效候选
return text, all_rows               # 全部跑完后返回
```

- **ddddocr（验证码/艺术字引擎）**：系统已集成 `ddddocr` 作为高精度兜底引擎。该引擎专为识别图形验证码、连体字、粗体艺术字设计，抗干扰能力极强。
- **取消纯数字限制**：`ddddocr` 取消了 `set_ranges(0)` 纯数字限制，允许其输出货币符号（如 `¥`）甚至乱码（如被误认为汉字“羊”的 `¥`），随后交由后置的 `AMOUNT_PATTERN` 正则表达式统一清洗。
- **自动样本收集（零成本训练集）**：每次成功的采集（后台定时或前台测试），系统都会自动将裁剪后的纯数字小图保存到 `data/ocr_datasets/`，命名格式为 `平台_店铺_识别值_时间戳.png`。这为您未来进行 PaddleOCR 或 ddddocr 的针对性微调积累了完美的训练数据集。

### 金额候选提取（`extract_candidates()`）

**实际正则模式（`AMOUNT_PATTERN`）：**

```
(?:(?:RMB|CNY|¥|￥|Y|半|举|夫|羊|旧)\s*)?([0-9][0-9,，.\s]{2,})(?:\s*(万|亿))?
```

> **注意（P11-1 修复历史）**：该模式在 `ocr_reader.py` 中用 f-string（`rf"..."`）构造，`{2,}` 量词需写成 `{{2,}}` 才能被 f-string 正确转义，否则 Python 会将 `{2,}` 求值为字符串 `"(2,)"` 导致量词失效。此 P0 Bug 已于 2026-05-03 修复。

各字符分类含义：
- `[0-9]` — 必须以数字开头
- `[0-9,，.\s]{2,}` — 后跟至少2个"数字/英文逗号/全角逗号/小数点/空白"字符（允许千分位格式和带空格的金额）
- `(万|亿)` — 可选中文单位，乘以对应倍数

提取步骤：
1. 对 `ocr_text` 及 `details` 中每条独立识别结果分别匹配
2. 跳过日期（`2024-05-01` 这类）、时间、百分比
3. 识别万/亿单位，乘以对应倍数
4. 尝试重建被 OCR 误分割的千分位（如 `4.379` + `653` → `4379653`）
5. 过滤掉小于 100 的值（GMV 不可能是两位数）
6. 同一 value 只保留评分最高的候选，按 score 降序返回

### 候选评分维度（`_candidate_reason()`）

| 维度 | 加分/减分 | 说明 |
|------|-----------|------|
| 含货币符号（¥/RMB/CNY/半/羊等） | +35 | 强信号（支持特征库配置的各种误识别字符） |
| 含千分位逗号 | +18 | 正规金额写法 |
| 数值 ≥ 1000 | +25 | 量级合理 |
| 位数越多 | +3×位数，上限+24；4位起再加 min(20,(位数-3)×5) | 大额 GMV 优先 |
| 数值 ≥ 100万 | +12 | GMV 常见量级 |
| 数值 ≥ 1亿 | +8 | 超大额 GMV |
| 与关键词在同一行 | +25 | 关键词命中 |
| 不低于上次可信值 | +18 | GMV 不应减少 |
| 轻微下跌（≥97%） | +5 | 可接受的小幅波动 |
| 大幅下跌（<97%） | -40 | 疑似识别错误 |
| 跳变超 5 倍 | -35 | 疑似误识别 |
| 超过 1 万亿 | -60 | 必定是误识别 |
| 日期格式且以"20"开头 | -60 | 年份误识别为 GMV |

### 可信值判断与自愈跳变逻辑（`scheduler._judge()`）

```
输入：task（含历史状态）+ selected（本次 OCR 最优候选值）

if selected is None:
    failure_count++（连续5次 → needs_recalibration，否则 parse_failed）
    return parse_failed / needs_recalibration

if last_value is not None:
    if selected < last_value:
        return suspect（只要下跌，必定预警，取消原先的 10% 容忍度）
    if selected > last_value * 5 and last_value > 0:
        return suspect（爆发式跳变，进入红框高亮预警）

# 连续确认自愈机制
if confirm_count <= 1 and (没有触发 suspect):
    return ok

if pending_value is None:
    pending_count = 1
elif _is_plausible_next(pending_value, selected) or selected == pending_value:
    pending_count += 1
else:
    保留 pending_value 或切换到更完整的候选（按位数判断）

# 动态确认阈值：如果是跳变（下跌或剧增），系统会要求“额外 2 次”连续确认（max(3, confirm_count + 1)）
dynamic_confirm_count = confirm_count
if 发生了跳变 (selected < last_value 或 > 5倍):
    dynamic_confirm_count = max(3, confirm_count + 1)

if pending_count >= dynamic_confirm_count:
    return ok（连续确认完成，系统自愈接纳新数字，更新 last_trusted_value）
else:
    return pending_confirm / suspect（继续等待）
```

`_is_plausible_next(previous, current)`：两个值位数差不超过 1，且倍率在 0.85-1.35 之间。对于异常跳变（大促爆发），系统不再死锁，只要连续多次识别到同一个跳变大数字，就能自愈恢复为 `ok`。

### 状态枚举

| status | 含义 | 触发条件 |
|--------|------|---------|
| `ok` | 可信 | 连续确认次数达标，或 confirm_count=1 |
| `pending_confirm` | 等待确认 | 候选值稳定但次数不足 |
| `suspect` | 疑似异常 | 金额明显低于或高于上次可信值 |
| `parse_failed` | 识别失败 | OCR 未提取到有效候选（<5次） |
| `needs_recalibration` | 需要重标定 | 连续5次识别失败 |
| `remote_page_not_found` | Edge 页签失效 | page_id 在当前会话中找不到 |
| `edge_debug_unavailable` | 调试端口未接通 | Edge 已关闭或调试端口未开 |
| `edge_debug_disconnected` | 控制连接未恢复 | 端口在线但 Playwright 未连接 |
| `edge_session_not_found` | 会话记录不存在 | DB 中找不到对应 session |
| `edge_login_page_bound` | 绑定了登录页 | 页签 URL 含 login/passport/signin |
| `edge_page_bound` | 绑定了非目标页 | 页签存在但 URL 不匹配 target_page_url |
| `edge_target_page_ready` | 已就绪 | 绑定的是目标业务页 |

---

## K. 运行流程分解

### 首次使用完整流程

```
1. 双击 "第1步_启动GMV服务.bat"
2. 浏览器访问 http://localhost:8100
3. 进入"采集配置"视图
4. 点击"一键初始化默认店铺" → POST /api/shops/init
5. 系统自动聚焦第一家待配置店铺
6. 进入"任务管理"视图 → 点击该平台的"启动Edge"（平台级）
   → 每家店铺依次打开 Edge，导航到 target_page_url
7. 在每个 Edge 窗口中手动登录对应账号
8. 回到"采集配置" → 点击"重新扫描" → 选择目标页签 → 点击"使用此页面"
9. 点击"生成预览" → 在截图上拖拽框选 GMV 数字区域
10. 点击"测试识别" → 确认结果正确
11. 点击"保存并进入下一家" → 自动切换到下一家
12. 重复 8-11，完成所有店铺配置
13. 回到"任务管理" → 启用需要采集的任务
14. 点击"启动采集"按钮 → 调度器开始运行
```

### 登录失效后的恢复流程

```
1. 系统检测到任务状态变为 edge_login_page_bound（Edge 会话恢复到登录页）
2. 用户在 Edge 中重新登录
3. 在"采集配置"工作台点击"已登录，打开业务页并自动继续"
   → POST /api/tasks/{id}/resume-after-login
   → 系统调用 client.ensure_launch_page(target_page_url)
   → 如果目标页打开成功：自动恢复 page_id 绑定，状态变为 edge_target_page_ready
4. 系统自动生成预览（前端 config.js 在 resumeAfterLogin 成功后自动调用 previewRemotePage）
```

### 页签失效后的恢复流程

```
1. 状态显示 remote_page_not_found（page_id 失效）
2. 在任务管理点击"显示Edge"（任务级）→ 系统走 `show_edge` 单入口恢复窗口，必要时由后端启动并显示
3. show 成功后，auto_restore_edge_session_task_bindings() 自动比对页签列表
   → 若 target_page_url 匹配唯一页签：自动恢复 page_id 绑定
   → 若无法自动恢复：返回 rebind_required，需用户手动重新绑定
4. 若自动恢复成功：状态变为 edge_target_page_ready，无需手动操作
```

### 手动单次采集流程

```
任务管理 → 点击"采一次"
→ POST /api/tasks/{id}/capture-once
→ scheduler.capture_once(task_id)（在 asyncio.to_thread 中同步执行）
→ 返回 {status, reason, selected_value, trusted_value, ocr_text, candidates, crop_rect}
→ 触发 broadcast_snapshot()
→ 前端 WebSocket 收到新快照，更新任务状态显示
```

---

## K2. 调度器工作方式

### 定时轮询

```python
async def _run_loop(self):
    while not self._stop.is_set():
        if not self._running:     # pause() 后跳过
            await asyncio.sleep(0.5)
            continue
        tasks = store.list_tasks(include_disabled=False)
        now = time.time()
        due_ids = [t.id for t in tasks if now - self._last_run.get(t.id, 0) >= t.interval_seconds]
        for id in due_ids:
            self._last_run[id] = now  # 记录本轮执行时间
        if due_ids:
            await asyncio.gather(*[asyncio.to_thread(self.capture_once, id) for id in due_ids])
            await self._notify()     # broadcast_snapshot
        await asyncio.sleep(0.2)     # 主循环 0.2s 间隔
```

### 并发与串行

- `asyncio.gather` 将所有 due 任务并发提交到线程池
- 每个 `capture_once(task_id)` 在独立线程中执行（同步阻塞）
- 不同任务之间并发执行；**同一 session 的多个任务共用一个 `RemoteEdge` 客户端**，其操作在 worker 队列中串行化

### 调度器跳过条件

```python
if client.is_window_op_running:
    return {"status": "skipped_window_op_in_progress"}
```

当某个 session 的 show/hide/close 操作正在进行时，调度器跳过该 session 的当次采集，避免 CDP 操作冲突。

### 截图清理规则

```python
_SCREENSHOT_MAX_AGE_DAYS = int(os.environ.get("GMV_SCREENSHOT_MAX_AGE_DAYS", "1"))

def _cleanup_old_screenshots(task_id):
    cutoff = time.time() - _SCREENSHOT_MAX_AGE_DAYS * 86400
    for file in SCREENSHOT_DIR.glob(f"task_{task_id}_*.png"):
        if file.stat().st_mtime < cutoff:
            file.unlink(missing_ok=True)
```

每次采集成功后清理当前任务超过保留期的旧截图。通过环境变量 `GMV_SCREENSHOT_MAX_AGE_DAYS` 可调整保留天数。

---

## L. API 全量清单

（按功能分组，★ 表示前端主要调用入口）

### 系统与全局设置类
```
GET  /api/health                    健康检查
GET  /api/realtime                  快照别名
GET  /api/windows                   枚举可见窗口
GET  /api/ocr/engines               OCR 引擎状态
GET  /api/settings                  获取全局设置（OCR引擎、采集频率等）
POST /api/settings                  更新全局设置
```

### 任务类
```
★ GET  /api/tasks                         完整快照
★ POST /api/tasks                         保存/更新任务
★ POST /api/tasks/{id}/enabled            启用/禁用
★ POST /api/tasks/{id}/capture-once       手动采集
   POST /api/tasks/{id}/manual-correction 人工纠错
★ POST /api/tasks/{id}/rebind-page        重绑页签
★ POST /api/tasks/{id}/delete             删除（POST 兼容）
   DELETE /api/tasks/{id}                 删除
★ GET  /api/tasks/{id}/samples            历史采样
   GET  /api/history/{id}                 历史别名
★ GET  /api/tasks/{id}/page-candidates    页签候选列表
★ POST /api/tasks/{id}/resume-after-login 登录后自动继续
```

### 调度器类
```
★ GET  /api/scheduler           调度器状态
★ POST /api/scheduler/start     启动采集
★ POST /api/scheduler/pause     暂停采集
```

### 店铺配置类
```
★ GET  /api/shops               shop_config 列表
★ POST /api/shops/init          同步到 DB
   GET  /api/shops/match         自动匹配页签（按 url_patterns）
   POST /api/shops/bind          批量绑定
```

### Edge 会话类
```
★ GET  /api/edge-sessions                           所有会话+health
   POST /api/edge-sessions                          新建/更新会话
   DELETE /api/edge-sessions/{id}                   删除会话
★ GET  /api/edge-sessions/{id}/health               单会话健康
★ GET  /api/edge-sessions/{id}/pages                页签列表
   POST /api/edge-sessions/{id}/start               启动
★ POST /api/edge-sessions/{id}/show                 显示
★ POST /api/edge-sessions/{id}/hide                 隐藏
★ POST /api/edge-sessions/{id}/close                关闭
   POST /api/edge-sessions/{id}/open                打开新页面
★ POST /api/edge-sessions/{id}/pages/{pid}/preview  截图预览
   POST /api/edge-sessions/{id}/pages/{pid}/reload  重载
```

### 平台级批量类
```
★ POST /api/platforms/{p}/launch-edge   启动+显示（所有）
★ POST /api/platforms/{p}/show-edge     显示（仅已运行）
★ POST /api/platforms/{p}/hide-edge     隐藏（所有）
★ POST /api/platforms/{p}/close-edge    关闭（所有）
   POST /api/platforms/{p}/start-edge   启动+显示（兼容旧入口）
```

### OCR 与预览类
```
★ POST /api/test-ocr            OCR 测试
   POST /api/window-preview      窗口截图预览
   GET  /api/task-previews/{f}   获取指定截图文件的预览图
```

### WebSocket
```
★ WS /ws/live                   实时快照推送
```

---

## L2. WebSocket 与快照结构

### 连接与推送时机

- 前端连接 `/ws/live` 后立即收到一次全量快照
- 之后在以下情况触发服务端主动推送：
  - 调度器每次完成一批任务的采集（`await self._notify()`）
  - 任何 HTTP 操作修改了状态后调用 `broadcast_snapshot()`
- 前端维护心跳（每次连接后发送 `"hello"`，由服务端 `receive_text()` 轮询维持连接）

### 快照 JSON 结构

```json
{
  "type": "snapshot",
  "updated_at": "2026-05-02 11:30:00",
  "summary": {
    "total_gmv": 123456789,
    "active_tasks": 11,
    "ok_tasks": 8,
    "alert_tasks": 3
  },
  "tasks": [
    {
      "id": 41,
      "platform": "天猫",
      "shop_name": "BLANC旗舰店",
      "capture_mode": "remote_edge",
      "edge_session_id": "天猫_BLANC旗舰店",
      "page_id": "abc123def456",
      "page_url": "https://...",
      "target_page_url": "https://...",
      "enabled": true,
      "status": "ok",
      "last_trusted_value": 8888888,
      "pending_value": null,
      "pending_count": 0,
      "last_success_at": "2026-05-02 11:29:58",
      "last_sample_at": "2026-05-02 11:30:00",
      "last_ocr_text": "成交金额 8,888,888",
      "last_reason": "连续 2 次确认",
      "last_screenshot_path": "data/screenshots/task_41_1746...",
      "interval_seconds": 2.0,
      "x_ratio": 0.15, "y_ratio": 0.42, "width_ratio": 0.25, "height_ratio": 0.08,
      ...
    }
  ]
}
```

### WebSocket 与 `/api/tasks` 的关系

二者返回相同的 `build_snapshot()` 结果，格式完全一致。`/api/tasks` 是同步拉取；`/ws/live` 是服务端推送。前端断线时自动降级为 2s 轮询 `/api/tasks`。

---

## M. 状态机与关键概念

### 三套状态机

#### 1. 任务状态机（`task.status`）

见 J 章节状态枚举，核心转换：
```
pending_confirm → ok（连续确认达标）
ok → suspect（金额异常）
ok → remote_page_not_found（页签失效）
任意 → edge_debug_unavailable（Edge 关闭）
```

#### 2. 配置工作台状态机（`setupFlowState()`）

见 H 章节 flow_state，核心转换：
```
idle → bind（初始化后）
bind → preview（绑定页签后，任意 URL 均可绑定）
preview → region_selected（生成预览后）
region_selected → ready_to_save（框选后）
ready_to_save → idle（保存后自动跳到下一家）
任意 → rebind_required（page_id 失效时）
```

#### 3. Edge 会话运行状态（`RemoteEdge` 内部）

```
idle → start_edge 执行中 → debug_port_ready / debug_port_timeout
idle → show_edge 执行中（_window_op_running=True）→ window_ready / window_failed
idle → hide_edge 执行中（_window_op_running=True）→ hidden / window_failed
idle → close_edge 执行中（_window_op_running=True）→ closed / close_failed
任意操作超时 → _stale=True（下次 get_client 重建实例）
```

### `page_id` 为什么不稳定

`page_id` 是由 GMV-LiveLens 自己生成的 UUID 片段（`uuid.uuid4().hex[:12]`），在内存中映射到 Playwright 的 `Page` 对象。**当 Edge 进程重启后，所有 Page 对象消失，page_id 映射全部失效**，需要重新扫描页签建立新映射。这是 `remote_page_not_found` 状态的根本原因。

### `page_url` / `target_page_url` / `default_page_url` 的区别

| 字段 | 来源 | 用途 | 是否稳定 |
|------|------|------|---------|
| `default_page_url`（shop_config 字段） | 人工配置 | 业务入口 URL | 稳定（人工维护） |
| `target_page_url`（task 字段） | 来自 default_page_url | 启动 Edge 时优先导航的 URL | 稳定 |
| `page_url`（task 字段） | 运行时记录的绑定页 URL | 备用启动 URL | 相对稳定（URL 不变就可用） |

启动/显示 Edge 时的 URL 选择优先级：`target_page_url` > `page_url` > ""（空则不导航）。

---

## N. 重要注意事项与风险

### 高风险操作

1. **服务启动不会再自动杀掉 msedge.exe 进程**  
   后端重启只初始化数据库和调度器，不会关闭用户个人 Edge 或店铺 Edge，以保护登录态和未保存页面状态。

2. **isolated 模式的 Edge 登录态保存依赖优雅关闭**  
   使用"关闭Edge"（WM_CLOSE → CDP 关闭）可安全 flush Cookie 到磁盘。  
   默认关闭流程不再自动强杀；若用户在系统外部手动结束进程，仍可能导致 Cookie 未写盘，**下次启动需要重新登录**。

3. **`data/edge_profiles/` 目录不能随意删除**  
   删除后该店铺的 Edge 登录态丢失，必须手动重新登录。

4. **`data/gmv_livelens.sqlite3` 删除后配置丢失**  
   所有任务配置（包括 page_id、坐标比例、已标定历史）全部消失，需要重新配置所有店铺。

### 已知限制

| 限制 | 说明 |
|------|------|
| Windows only | 依赖 `ctypes.windll`，Linux/macOS 不可用 |
| Edge only | Playwright CDP 连接硬编码 `chromium.connect_over_cdp`，只测试过 Edge |
| OCR 精度受页面样式影响 | 黄字紫背景、动态数字滚动时识别率下降 |
| SQLite 并发边界 | 多线程写入通过连接超时（30s）+事务规避，但高并发场景下可能有锁等待 |
| `page_id` 跨会话失效 | Edge 重启必须重新绑定 |
| real_profile 冲突 | 用真实个人环境时，系统会检测到任何 msedge.exe 进程（包括 isolated 模式的 debug Edge）并报冲突 |
| 平台级"启动Edge"耗时长 | 平台级按 session 顺序执行；当前京东 3 店铺真实烟测已通过，更多店铺时仍建议分批操作或调大前端超时 |

### 编码问题

`shops.csv` 支持 UTF-8/GBK/GB18030，但 Excel 默认保存为 GBK。编辑后另存为 UTF-8 可避免乱码。

### 已知未修复问题

| 编号 | 优先级 | 问题描述 | 影响 |
|------|--------|---------|------|
| P2-1 | P2 | `/ws/live` 与 `/ws/realtime` 是完全相同逻辑的重复 WebSocket 端点，前者已弃用但未删除 | 前端统一接入 `/ws/live` 即可；两者并存无功能影响，但维护时需注意同步修改 |
| P2-2 | P2 | `remote_edge.py` 中 `sync_playwright().start()` 在模块级调用，没有对应的 `stop()`；服务长时间运行时 Playwright 进程资源可能泄漏 | 短期运行无明显影响；如需修复，在 FastAPI `shutdown` 事件中调用 `playwright.stop()` |

---

## O. 排障手册

### Edge 不启动

| 现象 | 可能原因 | 处理 |
|------|---------|------|
| `edge_binary_not_found` | msedge.exe 不在 PATH 或默认路径 | 确认 Edge 已安装到 `C:/Program Files/Microsoft/Edge/Application/` |
| `edge_running_conflict` | real_profile 模式时检测到 Edge 在运行 | 关闭所有 Edge 窗口（包括其他 isolated 模式的 debug Edge）后重试 |
| `profile_locked_without_debug` | isolated 模式进程无调试标志，占用该店铺 Profile | 手动关闭对应店铺 Edge 窗口后重试 |
| `window_restart_blocked_for_login_safety` | Edge 有进程但无可显示主窗口 | 手动关闭对应店铺 Edge 后重新启动 |
| `debug_port_unavailable` | 进程启动但端口20s内未就绪 | 检查端口是否被其他程序占用；重试"启动Edge" |

### 能启动但不显示

| 现象 | 可能原因 | 处理 |
|------|---------|------|
| `no_startup_window` | 以 `--no-startup-window` 启动 | 系统会自动尝试补窗口；若仍失败，关闭后重新启动 |
| `show_window_failed` | 窗口存在但 SW_RESTORE 未生效 | 重试"显示Edge"；必要时关闭后重启 |
| `window_still_offscreen` | 窗口已找到但仍在屏幕外 | 系统已尝试 move_into_view；检查多显示器配置后重试 |

### 隐藏后再显示失败

根因：`hide_edge` 优先用 move_offscreen，若窗口坐标记录错误，找窗口时可能判断为不可见。  
处理：多次重试"显示Edge"；若连续失败则关闭后重启。

### page_id 失效

根因：Edge 进程重启后所有 CDP 页面 ID 重新分配。  
处理：点击"显示Edge"（任务级），系统会自动尝试恢复绑定；若无法自动恢复，回到"采集配置"重新扫描绑定。

### OCR 识别不到

排查步骤：
1. 在采集配置生成预览，确认截图区域包含 GMV 数字
2. 检查框选区域是否覆盖完整数字（安全边距 30% 保险）
3. 查看`last_ocr_text`：若有文字但无候选值，说明数字格式不符（如含字母、日期）
4. 检查 `keyword_hint` 是否设置正确（如"成交金额"）
5. 在"采集配置"重新框选后测试识别，观察候选值列表

### 截图预览失败或超时

根因：Edge 在某些包含特殊动画或未加载完成的 WebFonts 时，Playwright 的 `page.screenshot(animations="disabled")` 会发生死锁并等待满 20 秒超时。
处理：系统现在已内置 **5秒超时降级策略**。当截图在 5 秒内卡死时，后台会自动取消 `animations="disabled"` 参数并再次重试，从而瞬间强制截取画面，解决页面卡死导致的采集超时问题。

### 登录态丢失

触发场景：
- 用户在系统外部强制结束了仍在写盘的 Edge 进程
- `data/edge_profiles/` 下对应店铺 Profile 被删除、移动或损坏

处理：在任务管理点击"启动Edge"（任务级），系统导航到 `target_page_url`，若跳转到登录页则重新登录，再点击"已登录，打开业务页并自动继续"。

### 平台级批量动作异常

| 现象 | 处理 |
|------|------|
| 平台"显示"全部失败，reason=edge_debug_unavailable | 需先用平台或任务级"启动Edge" |
| 平台"启动"超时 | 多家店铺串行启动，耗时正常，等待或分批操作 |
| 平台"关闭"后有残留进程 | taskkill 返回 `profile_process_still_running`；稍后重试关闭；或手动任务管理器结束 |

---

## P. 最近重要改造记录（2026-05-02 至 2026-05-03，P1~P11）

以下为本次全量代码审查和冒烟测试期间完成的改造，当前系统行为已因此改变。

### P1. 页签标题永远为空 → 已修复

**文件**：`backend/collectors/remote_edge.py`，`_page_info()` 方法  
**改前**：`RemotePageInfo(page_id=page_id, title="", ...)`，标题硬编码空字符串  
**改后**：`title = page.title()` 通过 Playwright 读取真实页面标题  
**影响**：工作台页签列表现在显示真实标题；自动绑定恢复的标题匹配逻辑开始生效；登录页检测（`"登录" in title`）开始有效

### P2. OCR 早退检查缺少业务参数 → 已修复

**文件**：`backend/collectors/ocr_reader.py`，`read_text()` 函数  
**改前**：`read_text(image)` 无额外参数，早退检查 `extract_candidates(joined, all_rows)` 缺少 `keyword_hint` 和 `last_value`  
**改后**：`read_text(image, keyword_hint="", last_value=None)`，早退检查传入这两个参数  
**配套**：`scheduler.py` 和 `main.py` 的 `test_ocr` 接口均已更新调用  
**影响**：早退检查结合关键词和历史值评分，避免因无关数字触发早退

### P3. 数据库列迁移不完整 → 已修复

**文件**：`backend/services/store.py`，`_ensure_columns()` 函数  
**改前**：`additions` 字典只覆盖 7 个迁移列，`status`、`confirm_count`、`last_xxx` 等 12 个运行时列未包含  
**改后**：补充全部运行时列，老版本数据库升级时不再报 `OperationalError: no such column`

### P4. 配置工作台 scanBind() null guard → 已修复

**文件**：`frontend/config.js`，`scanBind()` 函数  
**改前**：`sessionId` 存在但 `task` 为 null 时，`task.id` 抛出 TypeError  
**改后**：在调用 `task.id` 前增加 null guard，返回 `{status: "no_task"}`

### P5. `edge_session_for()` 静默 fallback → 已修复

**文件**：`backend/main.py`，`edge_session_for()` 函数  
**改前**：不存在的 `session_id` 会静默 fallback 到 `default_real_edge`，操作被路由到错误会话  
**改后**：移除双重 fallback，非空但不存在的 `session_id` 直接返回 `HTTP 404 edge_session_not_found`  
**注意**：空 `session_id` 仍解析到 `default_real_edge`（向后兼容）

### P6. 平台级"显示"自动启动所有 Edge → 已修复

**文件**：`backend/main.py`，`show_platform_edge()` 函数；`backend/collectors/remote_edge.py`，新增 `debug_available_quick()`  
**改前**：平台"显示Edge"内部调用 `client.show_edge()`，后者始终调用 `_start_edge()`，4 个未运行的 session 串行执行 × 35s = 最长 140s，超过前端 45s 超时  
**改后**：平台"显示"先调用 `debug_available_quick()`（绕过 worker queue，直接 HTTP 检查端口，1.5s 超时），若端口未开则直接返回 `edge_debug_unavailable` 错误，不进入启动流程；4 个未运行 session 耗时从 >40s 降低至 6s  
**语义变化**：平台级"显示Edge"现在只显示已在运行的实例；若要批量启动，使用"启动Edge"按钮

### P7. 截图清理周期改为环境变量配置

**文件**：`backend/services/scheduler.py`  
**改前**：`_SCREENSHOT_MAX_AGE_DAYS = 7`（硬编码）  
**改后**：`_SCREENSHOT_MAX_AGE_DAYS = int(os.environ.get("GMV_SCREENSHOT_MAX_AGE_DAYS", "1"))`  
**默认值**：1 天（原来 7 天）

### P8. SVG 渐变 ID 碰撞 → 已修复

**文件**：`frontend/dashboard.js`，`sparklineSvg()` 函数  
**改前**：`id="spark-${Math.abs(seed)}"` 以 GMV 值为 ID，两家店铺 GMV 相同时渐变色错乱  
**改后**：`const gradId = \`spark-${Math.floor(Math.random() * 0xffffff).toString(16)}\``，每次渲染生成随机唯一 ID

### P9. 启动 URL 优先级对调

**文件**：`backend/services/store.py`，`preferred_launch_url_for_task()`  
**改前**：优先返回 `page_url`（运行时绑定页），备选 `target_page_url`  
**改后**：优先返回 `target_page_url`（配置的业务入口），备选 `page_url`  
**原因**：`target_page_url` 是 shop_config 中配置的固定业务 URL，更稳定；`page_url` 是运行时记录，在会话重启后可能失效

### P10. Edge 四按钮彻底收口（2026-05-03）

**文件**：`backend/collectors/remote_edge.py`、`backend/main.py`、`frontend/core.js`、`frontend/app.js`、`backend/tools/smoke_edge_buttons.py`

**改前问题 1：只启动第一个任务，却出现两个 Edge 窗口**  
历史链路中，店铺级“启动Edge”由前端先调 `/start`，再调 `/show`。`/start` 已经可能启动窗口；`/show` 在窗口诊断不稳定时又会 `_spawn_native_window()` 补开窗口，因此可能出现双窗口。

**当前修复**  
店铺级和平台级“启动Edge”统一走后端 `show_edge` 单入口。未运行时由后端可见启动，已运行时只恢复窗口。`show` 只有在确认没有任何可恢复主窗口、也没有候选 profile/端口进程时，才允许补开 native window；已有候选进程但无可恢复窗口时，为保护登录态返回安全失败提示，不自动强杀重启。

**改前问题 2：启动 N 个 Edge，每个 Edge 随机出现多个网页标签**  
历史链路中，后端启动固定先打开 `edge://newtab/`，随后又根据任务打开目标页；Edge 自身还可能恢复新标签页、首页或历史页，最终留下多个标签。

**当前修复**  
启动命令优先直接打开目标业务 URL；没有目标 URL 时只打开 `about:blank`。每次 `start/show/launch` 后执行 `_enforce_single_page()`，只保留一个主标签，并关闭 newtab、Edge 首页、历史恢复页、重复目标页等额外页。

**统一返回字段**  
四按钮接口返回统一携带 `action`、`stage`、`reason_code`、`window_action`、`window_diagnostics`、`recovery_attempted`、`debug_available`、`window_found`、`closed`、`page_count`、`primary_page_url`、`closed_extra_pages_count` 等字段，便于前端提示和后续 AI 排障。

**真实冒烟测试**  
新增 `backend/tools/smoke_edge_buttons.py`，可自动调用后端 API、查询 Edge 进程命令行、读取 CDP `/json/list`、检查窗口诊断。该脚本会真实启动、隐藏、显示、关闭受控 Edge，运行前必须提醒用户。

已通过命令：

```bat
.venv\Scripts\python.exe backend\tools\smoke_edge_buttons.py --base-url http://127.0.0.1:8100 --live --loops 3 --include-platform
```

验证结果：
- 单店铺：冷启动、连续启动/显示 3 次、隐藏->显示 3 轮、关闭、关闭后重启均 PASS。
- 平台级京东 3 个店铺：启动、显示、隐藏、隐藏后显示、关闭均 PASS。
- 平台级启动后最多 3 个受控窗口，每个结果 `page_count=1`。
- 平台级关闭后 3 个店铺均 `closed=true`。
- 最终 `failures=0`。

### P11. 全功能冒烟测试与核心 Bug 修复（2026-05-03）

#### P11-1【P0】`AMOUNT_PATTERN` 量词失效 → 金额从未提取成功

**文件**：`backend/collectors/ocr_reader.py`，第 37 行  
**改前**：`rf"...([0-9][0-9,，.\s]{2,})..."` — f-string 中 `{2,}` 被 Python 当作表达式求值为字符串 `"(2,)"`，编译后的正则变为 `[char_class](2,)` 而非 `[char_class]{2,}`  
**影响**：`AMOUNT_PATTERN.finditer()` 对任何金额文本均无匹配，`extract_candidates()` 恒返回 `[]`，所有采集任务永久处于 `parse_failed` 状态，历史上从未成功提取过 GMV  
**改后**：`{{2,}}` — 双花括号转义，f-string 不再干扰量词，正则正确编译为 `{2,}`  
**验证**：`extract_candidates("RMB474487", [], "", None)` 现在返回 `[CandidateAmount(value=474487, score=136.0)]`

#### P11-2【P0】`scheduler.py` `logger` 未定义

**文件**：`backend/services/scheduler.py`  
**改前**：`_save_ocr_dataset()` 的 except 分支调用 `logger.warning()`，但全文件无 `import logging` / `logger = ...`，触发 `NameError`，capture_once 以异常结束  
**改后**：顶部增加 `import logging` 和 `logger = logging.getLogger(__name__)`

#### P11-3【P1】`_run_loop()` 无整体异常保护

**文件**：`backend/services/scheduler.py`  
**改前**：`_run_loop()` 主体无 try/except，任何未预期异常会让调度循环静默死亡，看板停止刷新但前端无提示  
**改后**：主体加 `try/except Exception`，捕获后 `logger.error()` 记录并 1s 后继续，`asyncio.CancelledError` 单独 re-raise 不阻断

#### P11-4【P2】`next_edge_debug_port()` 无端口上界

**文件**：`backend/services/store.py`  
**改前**：while 循环无上界，大量会话被创建时端口可能超过 65535  
**改后**：`if port > 65000: raise ValueError("...")`

#### P11-5 新增全功能测试脚本

**文件**：`backend/tools/smoke_api.py`（新建）、`backend/tools/full_test.py`（新建）  
- `smoke_api.py`：14 项 API 接口冒烟测试，无需 Edge 在线，全部 PASS  
- `full_test.py`：65 项全功能测试，覆盖 A. 模块导入与 Bug 验证 / B. 业务逻辑单元测试（shop_config、OCR、_judge 状态机）/ C. DB CRUD / D. OCR 管道（合成图片）/ E. API 集成 / F. 前端文件一致性，全部 PASS

**运行方式**（服务需在 8100 端口运行）：
```bat
.venv\Scripts\python.exe backend\tools\full_test.py
```

---

## Q. 维护者阅读顺序建议

### 第一次接手项目

1. 本文档 A~C 章节（了解定位和技术选型）
2. `data/shops_default.json`（了解当前配置的店铺）
3. `backend/main.py` 前 200 行（了解应用结构和 startup 流程）
4. `backend/services/store.py`（了解数据库结构）
5. 运行服务，打开浏览器，走一遍"采集配置"流程

### 如果要改 OCR 识别精度

1. `backend/collectors/ocr_reader.py`（全文，重点：`_preprocess_variants`、`extract_candidates`、`_candidate_reason`）
2. `backend/services/scheduler.py` 的 `_judge()` 方法
3. `backend/main.py` 的 `test_ocr` 接口

### 如果要改任务/数据库

1. `backend/models.py`（字段定义）
2. `backend/services/store.py`（`init_db`、`_ensure_columns`、`upsert_task`）
3. `backend/services/shop_config.py`（配置和任务字段的映射关系）
4. `backend/main.py` 的 `TaskPayload` 模型（API 层验证）

### 如果要改 Edge 控制逻辑

1. `backend/collectors/window_control.py`（Win32 API 层，show/hide/close 的真实执行）
2. `backend/collectors/remote_edge.py`（Playwright 层 + 窗口控制编排，重点：`__show_edge`、`_hide_edge`、`__close_edge`）
3. `backend/main.py` 中的 `run_platform_edge_action`（平台级批量逻辑）

### 如果要改前端工作台流程

1. `frontend/config.js`（工作台主逻辑：绑定、预览、OCR 测试、保存）
2. `frontend/core.js`（状态管理、API 封装、`setupStageMeta`、`setupFlowState`）
3. `frontend/edge.js`（Edge 会话相关 UI：`previewRemotePage`、`refreshEdgeSessions`）
4. `frontend/app.js`（事件路由：`handleTaskAction`、平台按钮逻辑）

### 如果要添加新平台

1. `backend/services/shop_config.py`：`platform_key()` 添加新平台的归一化规则，`PLATFORM_PORT_BASE` 添加新平台的端口起始值
2. `frontend/core.js`：`normalizePlatform()` 和 `platformMeta` 添加新平台的 UI 配置（颜色、图标）
3. `data/shops_default.json`：添加新平台的店铺配置
4. 执行 `POST /api/shops/init` 初始化

---

## R. 环境变量速查表

所有环境变量在服务启动时读取，修改后需重启服务（`第1步_启动GMV服务.bat`）生效。

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `GMV_SCREENSHOT_MAX_AGE_DAYS` | `1` | 截图文件保留天数。每次采集成功后清理过期截图，1 = 只保留当天。设为 `7` 可保留一周用于回溯分析。 |
| `GMV_PREVIEW_MIN_INTERVAL_SECONDS` | `180` | 后台静默预览最短间隔（秒）。Preview 截图不触发 OCR，只用于实时前端刷新；设置过小会增加 Edge 请求频率。 |
| `GMV_PREVIEW_MAX_INTERVAL_SECONDS` | `480` | 后台静默预览最长间隔（秒）。实际间隔在 MIN~MAX 之间随机，用于错峰避免所有任务同时截图。 |
| `GMV_PREVIEW_MAX_WIDTH` | `720` | 预览截图最大宽度（像素）。超出则等比缩放后返回前端，节省带宽；OCR 截图不受此限制。 |
| `GMV_OCR_ENGINE` | `auto` | 指定 OCR 引擎。可选值：`auto`（按优先级自动选）、`rapidocr`、`legacy_rapidocr`、`paddleocr`、`ddddocr`、`tesseract`。`auto` 顺序：rapidocr → legacy_rapidocr → paddleocr → ddddocr → tesseract，取第一个成功初始化的引擎。 |

### 设置方式

**临时（当前会话）**：在命令行启动服务前执行：
```cmd
set GMV_OCR_ENGINE=ddddocr
第1步_启动GMV服务.bat
```

**永久**：在 Windows 系统环境变量中添加，或修改 `.bat` 启动脚本，在 `python` 命令前加 `set` 行。

---

*文档最后更新：2026-05-04*  
*覆盖代码版本：包含 P1~P11 全部改造后的当前系统*
