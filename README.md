# GMV-LiveLens

全渠道实时 GMV 采集看板，Windows 专用。通过 Playwright 控制 Microsoft Edge（CDP 协议）截图，结合 OCR 识别电商平台页面中的 GMV 数值，汇总展示在本地实时看板。

> 完整项目说明书：新接手维护者或其它 AI 请优先阅读 [.trae/documents/GMV-LiveLens项目全量说明书.md](.trae/documents/GMV-LiveLens项目全量说明书.md)。README 只保留快速启动和总览。

---

## 目录

- [完整项目说明书](#完整项目说明书)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速启动](#快速启动)
- [核心架构说明](#核心架构说明)
- [配置文件说明](#配置文件说明)
- [数据库结构](#数据库结构)
- [API 接口一览](#api-接口一览)
- [前端模块说明](#前端模块说明)
- [采集工作流](#采集工作流)
- [Edge 会话模式](#edge-会话模式)
- [多账号方案](#多账号方案)
- [OCR 引擎](#ocr-引擎)
- [故障排查](#故障排查)
- [已知限制](#已知限制)

---

## 完整项目说明书

系统级项目理解、模块职责、API、状态机、Edge 四按钮、OCR、调度器、数据目录、排障和最近改造记录，统一维护在：

`.trae/documents/GMV-LiveLens项目全量说明书.md`

其中 `.trae/documents/项目全量说明文档编写计划.md` 是文档维护计划，不是项目事实主入口。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI 0.110 + Uvicorn 0.29 |
| 数据库 | SQLite 3（通过 `sqlite3` 标准库，无 ORM） |
| 浏览器控制 | Playwright（CDP 协议，同步 API，独立线程） |
| 图像采集 | `mss`（窗口截图兼容模式） |
| OCR | RapidOCR（首选）/ PaddleOCR / Tesseract（自动降级） |
| 图像预处理 | OpenCV + Pillow |
| 实时推送 | WebSocket（`/ws/live`） |
| 前端 | 原生 HTML5 + CSS3 + JavaScript（无框架，5 个模块文件） |
| 系统依赖 | Windows Win32 API（`ctypes`）、Microsoft Edge |
| Python 版本 | 3.11+（已验证 3.14.3） |

---

## 项目结构

```
GMV-LiveLens/
├── backend/
│   ├── main.py                  # FastAPI 应用入口，所有路由定义
│   ├── models.py                # 数据类：CaptureTask / EdgeSession / CandidateAmount
│   ├── collectors/
│   │   ├── remote_edge.py       # Playwright CDP：Edge 启动/控制/截图/页面管理
│   │   ├── ocr_reader.py        # OCR 引擎封装 + 金额候选提取与评分
│   │   ├── window_capture.py    # Win32 窗口截图（兼容模式）
│   │   └── window_control.py    # Win32 Edge 窗口显示/隐藏/最大化/关闭
│   ├── services/
│   │   ├── store.py             # SQLite 所有 CRUD、schema 迁移、任务状态更新
│   │   ├── scheduler.py         # 定时采集调度器（asyncio + to_thread）
│   │   └── shop_config.py       # shops.csv / shops_default.json 解析
│   └── tools/
│       ├── start_shop_edges.py       # 批量启动店铺 Edge 会话的命令行工具
│       ├── smoke_edge_buttons.py     # 四按钮真实冒烟测试脚本（需 Edge 在线）
│       ├── smoke_api.py              # API 接口自动化冒烟测试脚本（14 项）
│       ├── full_test.py              # 全功能测试脚本（65 项，含 OCR 管道/DB/API）
│       ├── find_ocr_anomalies.py     # OCR 特征库异常监控脚本
│       └── benchmark_ocr_engines.py  # OCR 引擎准确率基准测试
├── frontend/
│   ├── index.html               # 单页应用 HTML 骨架，按序加载 5 个 JS 模块
│   ├── core.js                  # 全局状态、工具函数、API 封装、数据聚合逻辑
│   ├── dashboard.js             # 实时看板渲染（GMV 汇总 + 店铺卡片 + 折线图）
│   ├── edge.js                  # Edge 会话管理 UI（创建/选择/健康检查/页面控制）
│   ├── config.js                # 采集配置面板（工作台 + OCR 标定 + 页面绑定）
│   ├── app.js                   # 任务管理 + 事件绑定 + 调度器 + WebSocket + 初始化
│   └── styles.css               # 全局样式
├── data/
│   ├── shops.csv                # 店铺清单（GBK 编码，优先于 shops_default.json）
│   ├── shops_default.json       # 店铺清单 JSON 备选格式
│   ├── gmv_livelens.sqlite3     # SQLite 数据库（运行时自动创建）
│   ├── screenshots/             # 截图缩略图，默认 1 天自动清理（环境变量 GMV_SCREENSHOT_MAX_AGE_DAYS 可调）
│   └── edge_profiles/           # 各店铺独立 Edge user_data_dir（独立会话模式）
├── requirements.txt             # Python 依赖
└── 第1步_启动GMV服务.bat         # 一键启动脚本（端口 8100）
```

---

## 快速启动

### 方式一：批处理文件（推荐）

双击 `第1步_启动GMV服务.bat`，服务启动后访问：

```
http://127.0.0.1:8100
```

### 方式二：命令行

```bat
cd "C:\Users\yjd22\Desktop\python项目\GMV-LiveLens"
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8100
```

### 依赖安装（首次或新环境）

```bat
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

> **注意**：`playwright install` 是必要步骤，仅 pip 安装 playwright 包不够，还需下载浏览器驱动。

---

## 核心架构说明

### 采集流程

```
调度器（asyncio loop）
  └─ 每 interval_seconds(全局设置) 秒触发一次
       └─ capture_once(task_id)  ← 在 ThreadPoolExecutor 线程中执行
            ├─ [remote_edge 模式] Playwright CDP 截图
            │     RemoteEdge._call(func)  → 线程安全队列 → 专用工作线程
            │     _ensure_page() → screenshot_page()
            └─ [window_capture 模式] mss 截取 Win32 窗口
            └─ crop_by_ratio() → read_text() → extract_candidates()
            └─ _judge()  ← 连续确认逻辑（pending_confirm → ok）
            └─ store.update_task_runtime() + store.add_sample()
            └─ _cleanup_old_screenshots()  ← 清理 7 天前截图
```

### 线程模型

- `asyncio` 主事件循环处理 HTTP 请求和 WebSocket 推送
- 每个 `RemoteEdge` 实例有一个**专用守护线程**（`_worker_loop`），所有 Playwright 操作都通过 `queue.Queue` 串行执行
- 采集任务通过 `asyncio.to_thread` 在线程池中执行，不阻塞事件循环
- SQLite 使用 `check_same_thread=False`，每次操作新建连接

### 金额识别逻辑（`ocr_reader.py`）

1. 图像预处理：颜色、对比度、黄色数字提取、Otsu 二值化（4 种变体）
2. 多引擎 OCR：RapidOCR → PaddleOCR → Tesseract（按可用性降级）
3. 正则提取金额候选，过滤日期/时间/百分比
4. 候选评分：货币符号(+35)、逗号分隔(+18)、量级(+20)、关键词命中(+25)、与上次值比较(±分)
5. 连续确认：`pending_confirm` → 连续 N 次一致 → `ok`；异常降级 → `suspect` / `needs_recalibration`

---

## 配置文件说明

### `data/shops.csv`（GBK 编码，优先加载）

```csv
platform,shop_name,keyword_hint,url_patterns,url_must_contain,enabled
天猫,DESCENTE官方旗舰店,成交金额,sycm.taobao.com,,FALSE
京东,DESCENTE京东自营,成交金额,jd.com/merchant;shangzhi.jd.com,,FALSE
```

| 字段 | 说明 |
|------|------|
| `platform` | 平台名，支持：天猫/淘宝/生意参谋 → 天猫；京东/商智 → 京东；抖音/巨量 → 抖音 |
| `shop_name` | 店铺名，与 platform 组合唯一标识店铺 |
| `keyword_hint` | OCR 关键词提示，用于候选评分（如"成交金额"） |
| `url_patterns` | 分号分隔的 URL 关键词，用于自动匹配 Edge 标签页 |
| `url_must_contain` | 必须包含的 URL 关键词（AND 条件） |
| `enabled` | 任务默认是否启用（TRUE/FALSE） |
| `interval_seconds` | *(已弃用)* 系统现已统一使用前端配置的全局采集频率 |

CSV 不存在时自动 fallback 到 `data/shops_default.json`。

### `data/shops_default.json`

与 CSV 相同字段的 JSON 数组格式，UTF-8 编码。

### Edge 会话端口分配规则

| 平台 | 端口范围（默认）|
|------|----------------|
| 天猫 | 9231, 9232, ... |
| 京东 | 9241, 9242, ... |
| 抖音 | 9251, 9252, ... |
| 其他平台 | 9261, 9262, ... |
| default_real_edge | 9222（真实 Profile 模式） |

端口由 `shop_config.py` 的 `PLATFORM_PORT_BASE` 字典控制，CSV 中可通过 `debug_port` 字段覆盖。

---

## 数据库结构

数据库路径：`data/gmv_livelens.sqlite3`，启动时自动创建/迁移。

### `app_settings` 表

全局设置表，存储 `ocr_engine`（全局 OCR 引擎选择）、`interval_seconds`（全局采集频率）等配置。

### `capture_tasks` 表

| 列名 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `capture_mode` | TEXT | `remote_edge` / `window_capture` |
| `page_id` | TEXT | Playwright 页面唯一 ID（remote_edge 模式，会话重启后失效） |
| `page_url` | TEXT | 绑定的页面 URL（运行时记录） |
| `target_page_url` | TEXT | 配置的目标业务页 URL（Edge 启动时优先导航） |
| `page_title` | TEXT | 当前绑定页签的标题 |
| `edge_session_id` | TEXT | 关联 `edge_sessions.session_id` |
| `platform` | TEXT | 平台名 |
| `shop_name` | TEXT | 店铺名 |
| `keyword_hint` | TEXT | OCR 关键词提示（如"成交金额"） |
| `window_keyword` | TEXT | 窗口标题关键词（window_capture 模式） |
| `base_width` / `base_height` | INTEGER | 标定时的截图参考分辨率 |
| `x`, `y`, `width`, `height` | INTEGER | GMV 区域像素坐标（基于 base_width/height） |
| `x_ratio/y_ratio/width_ratio/height_ratio` | REAL | GMV 区域相对坐标（0-1） |
| `safety_margin` | REAL | OCR 裁剪安全边距（默认 0.3） |
| `confirm_count` | INTEGER | 连续确认次数阈值（默认 2） |
| `last_trusted_value` | INTEGER | 最后可信 GMV 数值 |
| `pending_value` | INTEGER | 当前待确认的候选值 |
| `pending_count` | INTEGER | 已连续出现相同候选值的次数 |
| `status` | TEXT | `ok/pending_confirm/suspect/parse_failed/needs_recalibration/window_not_found` 等 |
| `last_success_at` | TEXT | 最近一次成功采集的时间 |
| `last_sample_at` | TEXT | 最近一次采样的时间（包括失败） |
| `last_ocr_text` | TEXT | 最近一次 OCR 识别的原始文本 |
| `last_reason` | TEXT | 最近一次状态变更的原因描述 |
| `last_screenshot_path` | TEXT | 最近一次截图的本地路径 |

### `gmv_samples` 表

每次采集的完整记录，含 OCR 原文、候选列表、最终可信值。

### `edge_sessions` 表

| 列名 | 说明 |
|------|------|
| `session_id` | 唯一标识（如 `天猫_DESCENTE官方旗舰店`） |
| `debug_port` | Edge CDP 调试端口（UNIQUE 约束） |
| `user_data_dir` | Edge 用户数据目录（isolated 模式非空，real_profile 为空） |
| `session_mode` | `isolated`（独立店铺）/ `real_profile`（真实个人环境） |

---

## API 接口一览

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 服务健康状态 + 调度器状态 |
| GET | `/api/scheduler` | 调度器运行状态 |
| POST | `/api/scheduler/start` | 启动采集调度 |
| POST | `/api/scheduler/pause` | 暂停采集调度 |

### 任务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tasks` | 所有任务快照（含汇总） |
| POST | `/api/tasks` | 新建/更新任务 |
| DELETE | `/api/tasks/{id}` | 删除任务 |
| POST | `/api/tasks/{id}/enabled` | 启用/暂停任务 |
| POST | `/api/tasks/{id}/capture-once` | 手动触发一次采集 |
| POST | `/api/tasks/{id}/manual-correction` | 人工纠错（强制设置可信值） |
| POST | `/api/tasks/{id}/rebind-page` | 重新绑定 Edge 页面 |
| GET | `/api/tasks/{id}/page-candidates` | 扫描当前会话页签，返回候选绑定列表（含评分） |
| POST | `/api/tasks/{id}/resume-after-login` | 登录后自动继续：打开目标业务页并恢复绑定 |
| GET | `/api/tasks/{id}/samples` | 最近采样历史（默认 20 条） |
| GET | `/api/history/{id}` | 同上（别名） |

### 店铺配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/shops` | 读取 shops.csv / shops_default.json |
| POST | `/api/shops/init` | 按配置批量创建/同步任务 |
| GET | `/api/shops/match?session_id=xxx` | 扫描 Edge 标签页，自动匹配店铺 |
| POST | `/api/shops/bind` | 批量绑定页面到任务 |

### Edge 会话

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/edge-sessions` | 所有会话列表（含健康状态） |
| POST | `/api/edge-sessions` | 新建/更新会话 |
| DELETE | `/api/edge-sessions/{id}` | 删除会话（任务会重置到 default） |
| GET | `/api/edge-sessions/{id}/health` | 单个会话健康检查 |
| POST | `/api/edge-sessions/{id}/start` | 后台启动 Edge 进程 |
| POST | `/api/edge-sessions/{id}/show` | 启动并将 Edge 窗口置前最大化 |
| POST | `/api/edge-sessions/{id}/hide` | 将 Edge 窗口移到屏幕外（CDP 仍可截图） |
| POST | `/api/edge-sessions/{id}/close` | 关闭 Edge 进程树 |
| GET | `/api/edge-sessions/{id}/pages` | 列出该会话所有 HTTP/HTTPS 标签页 |
| POST | `/api/edge-sessions/{id}/open` | 在会话中打开新页面 |
| POST | `/api/edge-sessions/{id}/pages/{page_id}/preview` | 截取页面截图（base64） |
| POST | `/api/edge-sessions/{id}/pages/{page_id}/reload` | 重载页面 |

### 平台批量控制

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/platforms/{platform}/launch-edge` | 启动该平台所有店铺的 Edge |
| POST | `/api/platforms/{platform}/show-edge` | 显示该平台所有 Edge 窗口 |
| POST | `/api/platforms/{platform}/hide-edge` | 隐藏该平台所有 Edge 窗口 |
| POST | `/api/platforms/{platform}/close-edge` | 关闭该平台所有 Edge 进程 |

### 全局设置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/settings` | 读取全局设置（OCR 引擎、采集频率等） |
| POST | `/api/settings` | 更新全局设置 |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/windows` | 列出当前所有可见 Win32 窗口 |
| POST | `/api/window-preview` | 截取指定 hwnd 窗口截图 |
| POST | `/api/test-ocr` | 测试 OCR 识别（返回候选列表） |
| GET | `/api/ocr/engines` | 当前可用 OCR 引擎 |
| GET | `/api/realtime` | 同 `/api/tasks`（快捷别名） |
| WS | `/ws/live` | WebSocket 实时推送（快照格式） |
| GET | `/` | 前端 index.html |

---

## 前端模块说明

前端为纯原生 JS，**无构建工具**，5 个脚本文件按顺序加载：

```html
<script src="/static/core.js">      <!-- 1. 全局状态 + 工具函数 + API + 数据逻辑 -->
<script src="/static/dashboard.js"> <!-- 2. 实时看板渲染（依赖 core） -->
<script src="/static/edge.js">      <!-- 3. Edge 会话管理 UI（依赖 core） -->
<script src="/static/config.js">    <!-- 4. 配置面板（依赖 core + edge） -->
<script src="/static/app.js">       <!-- 5. 任务管理 + 事件 + 调度器 + WS + 初始化（依赖全部） -->
```

| 文件 | 行数 | 主要职责 |
|------|------|----------|
| `core.js` | ~375 | `state`、`$`、`escapeHtml`、`api()`、Edge API 封装、`buildSetupSummary` |
| `dashboard.js` | ~95 | `renderDashboard`、`sparklineSvg`、`renderTotalSpark` |
| `edge.js` | ~290 | `setupRemoteEdgeUi`、`refreshEdgeSessions`、Edge 页面预览/重载 |
| `config.js` | ~835 | `renderSetupWorkbench`、OCR 测试、`saveTask`、`scanBind`、`confirmBind` |
| `app.js` | ~1125 | `renderManager`、`handleTaskAction`、WebSocket、事件注册、调度器、全屏 |

---

## 采集工作流

### 标准流程（remote_edge 模式）

```
1. 初始化
   shops.csv → [一键初始化] → 批量创建 capture_tasks + edge_sessions

2. 绑定页面
   启动对应店铺的 Edge（端口 9231+）
   → [扫描当前店铺候选页面] → URL 匹配评分 → 选择并确认绑定
   → task.page_id 写入数据库

3. 标定区域
   [截取真实 Edge 预览] → 在预览图上拖拽框选 GMV 数字区域
   → [测试识别] → 确认 OCR 输出正确
   → [保存并启用] → task.enabled = 1，x_ratio/y_ratio/... 写入

4. 采集
   [启动采集] → 调度器每 interval_seconds(全局设置) 秒执行一次 capture_once
   → Playwright CDP 截图 → OCR → 候选评分 → 连续确认 → WebSocket 推送
```

### 连续确认逻辑

```
新值 = OCR 候选[0]

if 新值 与上次可信值偏差 > 10%:  → suspect（疑似异常，不更新）
elif 新值 == None:               → parse_failed（连续5次 → needs_recalibration）
elif confirm_count <= 1:         → 直接 ok
elif pending_value 连续相近:
    pending_count += 1
    if pending_count >= confirm_count: → ok（更新 last_trusted_value）
    else:                              → pending_confirm
```

---

## Edge 会话模式

| 模式 | `session_mode` | `user_data_dir` | 适用场景 |
|------|----------------|-----------------|----------|
| 独立店铺环境 | `isolated` | `data/edge_profiles/<session_id>/` | 多账号并行（推荐） |
| 真实个人环境 | `real_profile` | `""`（空，使用系统默认 Profile） | 临时调试、单账号 |

`default_real_edge`（端口 9222）固定为 `real_profile` 模式，启动前需关闭所有普通 Edge 窗口。

独立会话的 Edge 启动参数：

```bat
msedge.exe --user-data-dir="data/edge_profiles/<session_id>" \
           --remote-debugging-port=<port> \
           --remote-debugging-address=127.0.0.1 \
           --remote-allow-origins=http://127.0.0.1:<port> \
           --window-position=32000,0   ← 隐藏到屏幕外，不影响 CDP 截图
```

---

## 多账号方案

- 每个店铺分配一个独立 `user_data_dir`，完全隔离 Cookie/登录态
- 首次使用需人工在该 Edge 窗口登录对应平台账号
- `data/edge_profiles/<session_id>/` 目录就是该账号的持久化登录态，**不要随意删除**
- `hide_edge`（移出屏幕）后 CDP 截图仍可用，无需保持窗口可见
- `close_edge` 默认只做安全关闭（WM_CLOSE → CDP 关闭），失败时不会自动强杀，避免破坏登录态写盘
- 服务重启不会再自动杀掉所有 Edge；若 Profile 被普通 Edge 占用，请手动关闭该店铺 Edge 后再启动
- 若某些平台仍频繁要求重新登录，需要结合平台自身风控判断，不应简单视为项目一定能完全规避

---

## OCR 引擎

| 引擎 | Python 包 | 优先级（auto 模式） | 当前状态 |
|------|-----------|--------|----------|
| RapidOCR | `rapidocr` | 1（首选） | ✅ 可用 |
| Legacy RapidOCR | `rapidocr_onnxruntime` | 2 | ❌（Python 3.13+ 不兼容） |
| PaddleOCR | `paddleocr` | 3 | ❌ 未安装 |
| ddddocr | `ddddocr` | 4（抗干扰/艺术字兜底） | ✅ 可用 |
| Tesseract | `pytesseract` + tesseract CLI | 5 | ❌ 未安装 |

支持在前端界面全局切换 OCR 引擎。
> **自动样本收集**：系统会自动将纯数字的截图裁剪保存至 `data/ocr_datasets/` 目录下，作为零成本的后续 AI 微调高质量训练集。

GMV 金额按大额整数解析，`.`、`,`、`，`、空格会优先按千分位分隔符处理；例如 `￥474.487` 会解析为 `474487`，十亿级 `￥1.234.567.890` 会解析为 `1234567890`。只有明确带 `万/亿` 单位时才保留小数换算语义，如 `1.23亿` → `123000000`。

真实截图评估可把裁剪后的金额图片放入 `data/ocr_samples/`，文件名包含期望数字（如 `474487.png`），或提供 `labels.csv`（`file,expected`），然后运行：

```bat
.venv\Scripts\python.exe backend\tools\benchmark_ocr_engines.py --samples data\ocr_samples
```

---

## 故障排查

| 现象 | 排查方向 |
|------|----------|
| `edge_session_not_found` | 该任务的 edge_session_id 在 edge_sessions 表中不存在，重新初始化 |
| `remote_page_not_found` | Edge 未启动或 page_id 已失效，点"重绑页面"重新绑定 |
| `parse_failed` | OCR 未识别到金额，检查框选区域和 keyword_hint |
| `needs_recalibration` | 连续 5 次识别失败，需人工重标 |
| `suspect` | 新值低于上次可信值 10% 以上，检查页面数据是否异常 |
| Edge 调试端口不通 | 检查 Edge 是否已用正确参数启动，端口是否被占用 |
| 服务启动失败 | 检查端口 8100 是否被占用（bat 脚本会自动检测） |
| 中文乱码 | shops.csv 保存为 UTF-8 with BOM 或 GB18030 格式 |

查看采集历史：

```
GET http://127.0.0.1:8100/api/tasks/{task_id}/samples?limit=20
```

---

## 已知限制

1. **仅限 Windows**：使用 Win32 API（`ctypes.windll`）、`mss` 截图、`tasklist/taskkill` 进程管理，不支持 macOS/Linux
2. **仅支持 Microsoft Edge**（Chromium 内核），不支持 Chrome 或其他浏览器
3. **OCR 精度依赖页面样式**：动态图表、动画数字、高对比度背景会影响识别
4. **SQLite 并发**：连接池为每次操作新建连接，高并发下存在轻微性能开销
5. **截图存储**：`data/screenshots/` 按任务保留截图，默认 1 天后自动清理（可通过环境变量 `GMV_SCREENSHOT_MAX_AGE_DAYS` 调整），长期运行会有一定磁盘占用
6. **严格单页策略**：为保证多店铺稳定采集，受控 Edge 会自动关闭额外标签页，仅保留一个主业务页或登录页。
7. **Playwright 截图死锁**：针对含有特殊字体的页面可能导致 `animations="disabled"` 截图超时的问题，系统已内置 5 秒降级重试机制。
