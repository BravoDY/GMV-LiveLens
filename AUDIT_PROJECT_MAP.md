# GMV-LiveLens 项目全貌地图（基于代码扫描）

> 审计时间：2026-05-05 | 以实际代码为准，不依赖旧文档

---

## 1. 项目目录结构解读

| 目录/文件 | 实际作用 | 重要程度 | 风险判断 |
|---|---|---|---|
| `backend/main.py` | FastAPI 应用主入口：路由注册、CORS、WS 广播、Edge 控制逻辑、OCR 测试 | ★★★★★ | 核心文件，2000+ 行，逻辑密集 |
| `backend/models.py` | dataclass 数据模型：CaptureTask、EdgeSession、CandidateAmount | ★★★★★ | 干净无问题 |
| `backend/services/store.py` | SQLite 操作层：init_db、upsert_task、edge_session CRUD | ★★★★★ | **发现死代码 BUG** |
| `backend/services/scheduler.py` | 采集调度心跳：定时截图→OCR→写入 | ★★★★★ | 类型注解引用未导入的 Image（无运行时影响） |
| `backend/services/shop_config.py` | 读取 shops.csv/shops_default.json，转换为 ShopConfig | ★★★★★ | 端口分配逻辑依赖行序 |
| `backend/collectors/ocr_reader.py` | OCR 核心：多引擎调度、图像预处理、金额候选提取 | ★★★★★ | 形近字纠错库，逻辑复杂但完整 |
| `backend/collectors/remote_edge.py` | Edge 浏览器自动化：Playwright CDP、窗口控制、页签管理 | ★★★★★ | **模块级实例化启动后台线程** |
| `backend/collectors/window_capture.py` | 窗口截图（mss+ctypes） | ★★★ | Windows 平台专属，非 Windows 无法运行 |
| `backend/collectors/window_control.py` | pywin32 窗口显示/隐藏/关闭 | ★★★ | Windows 平台专属 |
| `frontend/index.html` | 页面骨架：4 个 Tab 视图 | ★★★★ | 外链 CDN（open-props.min.css） |
| `frontend/core.js` | 全局状态、辅助函数、API 封装、Edge 会话接口 | ★★★★★ | `shopConfigForTask` 过滤影响任务可见性 |
| `frontend/dashboard.js` | 实时看板渲染 | ★★★★ | 未读完整，需验证 |
| `frontend/app.js` | 任务管理渲染、任务操作、WS 连接、调度器 UI | ★★★★★ | WS 断线降级轮询逻辑完整 |
| `frontend/config.js` | 采集配置工作台、页签绑定、OCR 标定 | ★★★★★ | 未完整读取 |
| `frontend/edge.js` | Edge 操作相关 UI | ★★★ | 未读 |
| `data/shops.csv` | 店铺配置主数据源（CSV，GBK/UTF-8） | ★★★★★ | 11 条记录，编码测试通过 |
| `data/shops_default.json` | shops.csv 的备用 JSON（**已过期**） | ★★ | **包含 legacy edge_session_id，缺少 debug_port** |
| `data/gmv_livelens.sqlite3` | SQLite 数据库（运行时生成） | ★★★★★ | 4 张表 |
| `requirements.txt` | Python 依赖（11 行） | ★★★★ | **缺少 ddddocr** |
| `第1步_启动GMV服务.bat` | 启动脚本：端口检查、uvicorn 启动 | ★★★ | 逻辑完整，端口 8100 |

---

## 2. 核心模块地图

| 模块 | 代码位置 | 上游依赖 | 下游影响 | 可能风险 |
|---|---|---|---|---|
| HTTP API 路由层 | `backend/main.py` | FastAPI | 前端所有 API 调用 | 死代码段在 store 中导致 session_mode 可能不正确 |
| SQLite 存储层 | `backend/services/store.py` | sqlite3 | scheduler、main.py | `_ensure_capture_task_shop_uniqueness` 存在死代码 |
| 采集调度器 | `backend/services/scheduler.py` | store、ocr_reader、remote_edge | WebSocket 广播 | 每个 tick 独立读 DB 全局设置（无缓存） |
| 店铺配置读取 | `backend/services/shop_config.py` | shops.csv / shops_default.json | store.sync_tasks | 端口分配依赖 CSV 行序，JSON 备用数据过期 |
| OCR 识别引擎 | `backend/collectors/ocr_reader.py` | rapidocr/ddddocr/paddleocr | scheduler、main.py | ddddocr 未在 requirements.txt 中声明 |
| Edge 浏览器控制 | `backend/collectors/remote_edge.py` | playwright、window_control | scheduler、main.py | **模块导入即启动后台线程** |
| 窗口截图 | `backend/collectors/window_capture.py` | mss、ctypes | scheduler、main.py | 仅支持 Windows |
| 前端状态管理 | `frontend/core.js` | browser | 所有渲染模块 | `shopConfigForTask` 过滤：DB 里有但 CSV 里没有的任务被隐藏 |
| WebSocket 实时推送 | `backend/main.py` `/ws/live` | scheduler 回调 | 前端看板实时刷新 | 全局 clients Set 在单进程单 worker 场景下安全 |

---

## 3. 核心业务链路图

### 链路 A：GMV 采集主链路

```
调度器心跳（每 0.5s）
  -> store.list_tasks(enabled only)
  -> 对每个 due 任务 capture_once(task_id)
  -> [remote_edge 模式] RemoteEdge.screenshot_page(page_id)
     -> CDP 截图 → PIL Image
  -> crop_by_ratio(image, x_ratio, y_ratio, w_ratio, h_ratio)
  -> read_text(crop) → rapidocr/ddddocr → 多引擎多变体
  -> extract_candidates(ocr_text) → 金额正则匹配 + 评分排序
  -> _judge(task, selected) → 状态机判断：ok / pending_confirm / suspect / parse_failed
  -> store.update_task_runtime(task_id, updates)
  -> store.add_sample(task_id, ...)
  -> broadcast_snapshot() → WebSocket 推送给所有 clients
  -> 前端 renderSnapshot() → 更新实时看板
```

### 链路 B：Edge 启动/显示链路

```
前端点击"启动Edge"或"显示Edge"
  -> POST /api/edge-sessions/{session_id}/show (或 start)
  -> edge_client_for(session_id) → RemoteEdgeManager.get_client()
  -> client.show_edge(launch_url)
     -> _ensure_browser() → Playwright CDP 连接
     -> 窗口查找（window_control）→ 显示主窗口
     -> _enforce_single_page(launch_url) → 关闭多余标签
  -> reconcile_edge_session_task_runtime(session_id, pages)
  -> auto_restore_edge_session_task_bindings() → 自动恢复绑定
  -> broadcast_snapshot()
```

### 链路 C：采集配置标定链路

```
用户进入"采集配置"Tab
  -> ensureSetupTaskFocused() → 自动定位当前待配置店铺
  -> 点击"扫描当前会话页签"
     -> GET /api/tasks/{task_id}/page-candidates
     -> client.list_pages() → 枚举 Edge 所有页签
     -> _build_task_page_candidates() → 页签评分排列
  -> 用户选择页签点击"使用此页面"
     -> POST /api/tasks/{task_id}/rebind-page
  -> 点击"生成预览"
     -> POST /api/edge-sessions/{session_id}/pages/{page_id}/preview
     -> CDP 截图 → base64 → 前端显示
  -> 拖拽框选 GMV 区域
     → 记录 x/y/width/height 比例
  -> 点击"测试识别"
     -> POST /api/test-ocr (preview_image=当前截图)
     → 返回候选值、OCR 文本
  -> 点击"保存并进入下一家"
     -> POST /api/tasks (包含 x_ratio/y_ratio/width_ratio/height_ratio)
     -> 自动 focusNextPendingTask()
```

### 链路 D：看板数据刷新链路

```
WebSocket 连接 /ws/live
  -> 服务端推送 snapshot
  -> 前端 renderSnapshot(snapshot)
     -> state.snapshot = snapshot
     -> renderDashboard() → 店铺卡片网格
     -> renderManager() → 任务管理列表（filtered by shopConfigForTask）
     -> renderSetupWorkbench() → 配置工作台状态

降级轮询（WS 断线时）
  -> GET /api/tasks → 触发 lightweight_reconcile_and_auto_restore()
     → 每次 GET /api/tasks 都做一次自愈检查（可能较慢）
```

---

## 4. 数据库表结构

| 表名 | 用途 | 关键字段 |
|---|---|---|
| `capture_tasks` | 采集任务（主表） | id, platform, shop_name, edge_session_id, x_ratio, y_ratio, w_ratio, h_ratio, status, last_trusted_value |
| `gmv_samples` | 历史采样记录 | task_id, sampled_at, ocr_text, candidates_json, trusted_value, status |
| `edge_sessions` | Edge 浏览器会话 | session_id, debug_port, user_data_dir, session_mode |
| `app_settings` | 全局设置（OCR 引擎、采集间隔） | key, value |

---

## 5. 高风险区域识别

| 区域 | 风险类型 | 位置 |
|---|---|---|
| `_ensure_capture_task_shop_uniqueness` 死代码 | 逻辑断裂 | store.py:235-256 |
| `shops_default.json` 过期备用数据 | 数据错误 | data/shops_default.json |
| `requirements.txt` 缺少 ddddocr | 部署失败 | requirements.txt |
| `shopConfigForTask` 过滤 | 任务黑洞（UI 不可见） | frontend/core.js:347-350 |
| `remote_edge` 模块级全局实例 | 导入副作用 | remote_edge.py:1536 |
| `_ensure_default_edge_session` 不更新已有记录 | session_mode 可能错误 | store.py:273-296 |
| GET /api/tasks 触发自愈检查 | 每次轮询都有边界操作 | main.py:1531-1535 |
