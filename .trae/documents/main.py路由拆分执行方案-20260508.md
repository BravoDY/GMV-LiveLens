# main.py 路由拆分执行方案

> 制定日期：2026-05-08  
> 基于：第一阶段整改完成后的 main.py (2347行)  
> **本轮只输出方案，不修改代码**  

---

## 1. 当前 main.py 职责分析

当前 `backend/main.py` (2347 行) 实际承担了 **6 种职责**：

| 职责 | 行数估计 | 说明 |
|---|---|---|
| 1. FastAPI app 初始化 | ~30 | `app = FastAPI()`、CORS、mount 静态文件 |
| 2. 路由定义 (56个) | ~1090 | 56 个 `@app.{get,post,delete,websocket}` 路由 |
| 3. 共享工具函数 (20个) | ~650 | `edge_session_for`、`edge_client_for`、`lightweight_reconcile_and_auto_restore`、`run_platform_edge_action` 等 |
| 4. Pydantic 请求模型 (14个) | ~110 | `TaskPayload`、`EdgeSessionPayload` 等 |
| 5. 全局状态 (2个) | ~5 | `clients: set[WebSocket]` |
| 6. 生命周期事件 (2个) | ~15 | `startup`、`shutdown` |

**核心问题**：一个团队无论谁新增一个 API、修改任何一个路由的异常处理，都会在这个 2347 行文件中产生冲突。

---

## 2. 路由清单

共 **55 个路由**（不含根和 WS），按业务域分类：

### 2.1 系统/根路由 (system.py)

| 当前路由 | 方法 | 当前函数名 | 行号 | 依赖对象 | 风险 |
|---|---|---|---|---|---|
| GET /api/health | GET | `health` | 2185 | `scheduler` | 极低 |
| GET /api/realtime | GET | `realtime` | 2194 | `build_snapshot` | 极低 |
| GET /api/history/{task_id} | GET | `history` | 2199 | `store` | 极低 |
| GET /api/settings | GET | `get_settings` | 1796 | `store` | 极低 |
| POST /api/settings | POST | `update_settings` | 1803 | `store` | 极低 |
| GET /api/scheduler | GET | `scheduler_status` | 1822 | `scheduler` | 极低 |
| POST /api/scheduler/start | POST | `scheduler_start` | 1827 | `scheduler`、`broadcast_snapshot` | 低 |
| POST /api/scheduler/pause | POST | `scheduler_pause` | 1834 | `scheduler`、`broadcast_snapshot` | 低 |
| GET /api/windows | GET | `windows` | 992 | `window_capture.list_windows` | 极低 |
| POST /api/window-preview | POST | `window_preview` | 1644 | `window_capture` | 极低 |

### 2.2 任务路由 (tasks.py)

| 当前路由 | 方法 | 当前函数名 | 行号 | 依赖对象 | 风险 |
|---|---|---|---|---|---|
| GET /api/tasks | GET | `tasks` | 1810 | `build_snapshot` | 极低 |
| POST /api/tasks | POST | `save_task` | 1841 | `safe_upsert_task`、`store`、`broadcast_snapshot` | 低 |
| DELETE /api/tasks/{task_id} | DELETE | `delete_task` | 2102 | `store`、`broadcast_snapshot` | 低 |
| POST /api/tasks/{task_id}/delete | POST | `delete_task_fallback` | 2111 | `delete_task` | 极低 |
| POST /api/tasks/{task_id}/enabled | POST | `enable_task` | 1849 | `store`、`broadcast_snapshot` | 低 |
| POST /api/tasks/{task_id}/capture-once | POST | `capture_once` | 2116 | `scheduler`、`broadcast_snapshot` | 低 |
| POST /api/tasks/{task_id}/manual-correction | POST | `manual_correction` | 2123 | `store`、`broadcast_snapshot` | 低 |
| GET /api/tasks/{task_id}/samples | GET | `samples` | 2163 | `store` | 极低 |
| POST /api/tasks/{task_id}/rebind-page | POST | `rebind_page` | 1858 | `safe_upsert_task`、`_task_runtime_for_bound_page`、`store` | 中 |
| POST /api/tasks/{task_id}/resume-after-login | POST | `resume_after_login` | 1886 | `edge_session_for`、`edge_client_for`、`edge_control_unavailable_detail` 等 | **高** |
| GET /api/tasks/{task_id}/page-candidates | GET | `task_page_candidates` | 2014 | `edge_client_for`、`_build_task_page_candidates` 等 | **高** |
| GET /api/tasks/{task_id}/screen-readonly | GET | `get_task_screen_readonly` | 1549 | `task_screen_readonly_payload` | 中 |
| POST /api/tasks/self-heal | POST | `tasks_self_heal` | 1815 | `lightweight_reconcile_and_auto_restore`、`broadcast_snapshot` | 中 |

### 2.3 Edge 会话路由 (edge_sessions.py)

| 当前路由 | 方法 | 当前函数名 | 行号 | 依赖对象 | 风险 |
|---|---|---|---|---|---|
| GET /api/edge-sessions | GET | `edge_sessions` | 999 | `build_edge_session_item`、`store` | 低 |
| POST /api/edge-sessions | POST | `save_edge_session` | 1004 | `build_edge_session_item`、`store` | 低 |
| DELETE /api/edge-sessions/{session_id} | DELETE | `delete_edge_session` | 1013 | `store`、`broadcast_snapshot` | 低 |
| GET /api/edge-sessions/{session_id}/health | GET | `edge_session_health` | 1023 | `edge_client_for`、`edge_health_payload` | 低 |
| POST /api/edge-sessions/{session_id}/start | POST | `start_edge_session` | 1033 | `edge_client_for`、`reconcile`、`broadcast_snapshot` | 中 |
| POST /api/edge-sessions/{session_id}/show | POST | `show_edge_session` | 1076 | `edge_client_for`、`reconcile`、`broadcast_snapshot` | 中 |
| POST /api/edge-sessions/{session_id}/hide | POST | `hide_edge_session` | 1136 | `edge_client_for`、`broadcast_snapshot` | 低 |
| POST /api/edge-sessions/{session_id}/close | POST | `close_edge_session` | 1177 | `edge_client_for`、`broadcast_snapshot` | 低 |
| GET /api/edge-sessions/{session_id}/pages | GET | `edge_session_pages` | 1283 | `edge_client_for`、`edge_timeout_detail` | 低 |
| POST /api/edge-sessions/{session_id}/open | POST | `open_edge_session_page` | 1318 | `edge_client_for` | 中 |
| POST /../{session_id}/pages/{page_id}/preview | POST | `edge_session_preview` | 1342 | `edge_client_for`、`image_to_data_url` | 低 |
| POST /../{session_id}/pages/{page_id}/reload | POST | `reload_edge_session_page` | 1408 | `edge_client_for` | 极低 |
| POST /../{session_id}/pages/{page_id}/network-watch | POST | `start_edge_session_page_network_watch` | 1417 | `edge_client_for` | 低 |
| GET /../{session_id}/pages/{page_id}/network-watch | GET | `get_edge_session_page_network_watch` | 1453 | `edge_client_for` | 极低 |
| DELETE /../{session_id}/pages/{page_id}/network-watch | DELETE | `clear_edge_session_page_network_watch` | 1479 | `edge_client_for` | 极低 |
| GET /../{session_id}/pages/{page_id}/screen-readonly | GET | `get_edge_session_page_screen_readonly` | 1505 | `edge_client_for`、`edge_timeout_detail` | 中 |
| POST /../{session_id}/pages/{page_id}/click-text | POST | `click_edge_session_page_text` | 1557 | `edge_client_for` | 低 |
| GET /../{session_id}/pages/{page_id}/inspect-text | GET | `inspect_edge_session_page_text` | 1596 | `edge_client_for` | 极低 |

### 2.4 平台批量路由 (platforms.py)

| 当前路由 | 方法 | 当前函数名 | 行号 | 依赖对象 | 风险 |
|---|---|---|---|---|---|
| POST /api/platforms/{p}/start-edge | POST | `start_platform_edge` | 1218 | `run_platform_edge_action` | 低 |
| POST /api/platforms/{p}/launch-edge | POST | `launch_platform_edge` | 1229 | `run_platform_edge_action` | 低 |
| POST /api/platforms/{p}/show-edge | POST | `show_platform_edge` | 1240 | `run_platform_edge_action`、`RemoteEdgeWindowState` | 低 |
| POST /api/platforms/{p}/hide-edge | POST | `hide_platform_edge` | 1269 | `run_platform_edge_action` | 低 |
| POST /api/platforms/{p}/close-edge | POST | `close_platform_edge` | 1276 | `run_platform_edge_action` | 低 |

### 2.5 店铺配置路由 (shops.py)

| 当前路由 | 方法 | 当前函数名 | 行号 | 依赖对象 | 风险 |
|---|---|---|---|---|---|
| GET /api/shops | GET | `shops` | 2219 | `shop_config`、`_load_shops_default` | 极低 |
| POST /api/shops/init | POST | `init_shops` | 2224 | `shop_config`、`store`、`broadcast_snapshot` | 低 |
| GET /api/shops/match | GET | `shops_match` | 2238 | `store`、`_load_shops_default`、`edge_session_for`、`edge_client_for` | 中 |
| POST /api/shops/bind | POST | `shops_bind` | 2316 | `safe_upsert_task`、`store`、`broadcast_snapshot` | 低 |

### 2.6 OCR 路由 (ocr.py)

| 当前路由 | 方法 | 当前函数名 | 行号 | 依赖对象 | 风险 |
|---|---|---|---|---|---|
| GET /api/ocr/engines | GET | `ocr_engines` | 1635 | `available_engines` | 极低 |
| POST /api/test-ocr | POST | `test_ocr` | 1658 | **极多**：`image_from_data_url`、`edge_client_for`、`capture_window`、`read_text`、`store`、`broadcast_snapshot`、`edge_timeout_detail`、`edge_control_unavailable_detail` | **高** |

### 2.7 根路由 + WebSocket (保留在 main.py)

| 当前路由 | 方法 | 当前函数名 | 行号 | 依赖对象 |
|---|---|---|---|---|
| GET / | GET | `index` | 981 | `FRONTEND_DIR` |
| GET /favicon.ico | GET | `favicon` | 202 | `FRONTEND_DIR` |
| GET /api/task-previews/{filename} | GET | `task_preview_image` | 207 | `store.SCREENSHOT_DIR` |
| WS /ws/live | WS | `websocket_live` | 2170 | `clients`、`build_snapshot` |

---

## 3. 公共函数清单

### 3.1 必须保留在 main.py 的

| 函数/变量 | 当前作用 | 原因 |
|---|---|---|
| `app` | FastAPI 实例 | 唯一入口，所有 router 注册到此 |
| `clients` | WebSocket 连接池 | `broadcast_snapshot` 直接依赖 |
| `ROOT_DIR` / `FRONTEND_DIR` | 路径常量 | `startup` 和静态文件 mount 依赖 |
| `startup()` | 生命周期 | 需要调用 `store.init_db()`、`setup_logging()` |
| `shutdown()` | 生命周期 | `@app.on_event` 必须在此 |
| `index()` | 前端入口 | 直接访问 `FRONTEND_DIR` |
| `favicon()` | 网站图标 | 简单路由 |
| `task_preview_image()` | 预览图片 | 简单路由 |
| `websocket_live()` | WebSocket | 直接操作 `clients` |

### 3.2 抽到 `backend/routers/_common.py` 的共享函数

| 函数 | 使用方 | 使用频次 |
|---|---|---|
| `build_snapshot()` | system, tasks, ws | 4 路由 |
| `broadcast_snapshot()` | tasks, edge_sessions, shops, platforms, ocr | 20+ 路由 |
| `safe_upsert_task()` | tasks, shops_bind | 2 路由 |
| `image_from_data_url()` | test_ocr | 1 路由 |
| `edge_session_for()` | tasks, edge_sessions, shops | 10+ 路由 |
| `edge_client_for()` | tasks, edge_sessions, shops, ocr | 18+ 路由 |
| `edge_health_payload()` | edge_sessions, tasks | 8+ 路由 |
| `edge_timeout_detail()` | edge_sessions, tasks, ocr | 12+ 路由 |
| `edge_control_unavailable_detail()` | edge_sessions, tasks, ocr | 8+ 路由 |
| `edge_action_payload()` | edge_sessions, platforms | 6 路由 |
| `build_edge_session_item()` | edge_sessions | 2 路由 |
| `reconcile_edge_session_task_runtime()` | edge_sessions, tasks, platforms | 8+ 路由 |
| `auto_restore_edge_session_task_bindings()` | edge_sessions, tasks, platforms | 8+ 路由 |
| `auto_restore_edge_session_task_bindings_with_report()` | edge_sessions, tasks | 3 路由 |
| `lightweight_reconcile_and_auto_restore()` | tasks | 1 路由 |
| `_build_task_page_candidates()` | tasks | 1 路由 |
| `_build_binding_resolution()` | tasks | 1 路由 |
| `_task_runtime_for_bound_page()` | tasks, shops | 2 路由 |
| `_page_match_score()` | (通过 `_build_task_page_candidates`) | 1 路由 |
| `_resume_after_login_message()` | tasks | 1 路由 |
| `task_screen_readonly_payload()` | tasks | 1 路由 |
| `edge_tasks_for_platform()` | platforms | 5 路由 |
| `run_platform_edge_action()` | platforms | 5 路由 |
| `_load_shops_default()` | shops | 2 路由 |
| `screen_readonly_platform_unsupported_detail()` | task_screen_readonly_payload | 1 路由 |

### 3.3 Pydantic 模型

| 模型 | 使用方 | 建议 |
|---|---|---|
| `PreviewRequest` | window_preview | 放 system.py |
| `SettingsPayload` | system (settings) | 放 system.py |
| `TestOcrRequest` | ocr | 放 ocr.py |
| `TaskPayload` | tasks | 放 tasks.py |
| `EnablePayload` | tasks | 放 tasks.py |
| `OpenManagedPagePayload` | edge_sessions | 放 edge_sessions.py |
| `NetworkWatchPayload` | edge_sessions | 放 edge_sessions.py |
| `PageClickTextPayload` | edge_sessions | 放 edge_sessions.py |
| `EdgeSessionPayload` | edge_sessions | 放 edge_sessions.py |
| `RebindPagePayload` | tasks | 放 tasks.py |
| `ManualCorrectionPayload` | tasks | 放 tasks.py |
| `ShopsBindPayload` | shops | 放 shops.py |

### 3.4 常量

| 常量 | 使用方 | 建议 |
|---|---|---|
| `EDGE_RUNTIME_STALE_STATUSES` | `_common.py` | 放 `_common.py` |
| `AMBIGUOUS_BINDING_REASON_CODES` | `_common.py` | 放 `_common.py` |
| `_SHOPS_DEFAULT_PATH` | shops | 放 shops.py |

---

## 4. 新目录结构

```
backend/routers/
├── __init__.py                 # 空
├── _common.py                  # 共享：clients、build_snapshot、broadcast_snapshot、
│                               #       edge_session_for、edge_client_for、
│                               #       edge_health_payload、edge_timeout_detail、
│                               #       edge_control_unavailable_detail、
│                               #       所有 auto_restore_*、reconcile_*、run_platform_*
│                               #       safe_upsert_task、image_from_data_url、
│                               #       _build_task_*、_resume_after_login_message 等
├── system.py                   # /api/health /api/realtime /api/history
│                               # /api/settings /api/scheduler/* /api/windows /api/window-preview
├── tasks.py                    # /api/tasks/* (含 screen-readonly, page-candidates, resume-after-login)
├── edge_sessions.py            # /api/edge-sessions/* (含 4按键 + pages + preview + network-watch + screen-readonly)
├── platforms.py                # /api/platforms/* (5 个批量 Edge 控制)
├── shops.py                    # /api/shops*
└── ocr.py                      # /api/ocr/engines /api/test-ocr
```

main.py 保留：
```
backend/main.py (~180行)
├── 顶层 import
├── ROOT_DIR / FRONTEND_DIR / logger
├── app = FastAPI() + CORS
├── from routers._common import clients, build_snapshot, broadcast_snapshot
├── 注册 routers
│   app.include_router(system_router)
│   app.include_router(tasks_router)
│   app.include_router(edge_sessions_router)
│   app.include_router(platforms_router)
│   app.include_router(shops_router)
│   app.include_router(ocr_router)
├── startup / shutdown
├── index() / favicon() / task_preview_image()
├── websocket_live()
└── app.mount("/static", ...)
```

---

## 5. import 风险分析

### 5.1 核心循环依赖风险

```
main.py
  → from backend.routers._common import ...
  → from backend.routers.tasks import router as tasks_router
  → app.include_router(tasks_router)

routers/_common.py
  → from backend.services.store import ...    (✅ 无循环)
  → from backend.collectors.remote_edge import ... (✅ 无循环)

routers/tasks.py
  → from ._common import broadcast_snapshot, edge_session_for, ...  (✅ 无循环)
  → from backend.services.store import ...  (✅ 无循环)
```

**结论：不会产生循环依赖。** 原因：
- `_common.py` 只 import `backend.services.*` 和 `backend.collectors.*`（业务层）
- 各 router 文件只 import `._common` 和 `backend.services.*`
- `main.py` 只 import `backend.routers.*`
- 没有 router → main.py 的 import

### 5.2 关键注意事项

| 风险点 | 描述 | 缓解 |
|---|---|---|
| `clients` set 的归属 | 需从 main.py 搬到 `_common.py` | `_common.py` 中 `clients: set[WebSocket] = set()` |
| `broadcast_snapshot` 的 `clients` 引用 | 原代码直接引用模块级 `clients` | 和 `clients` 一起搬到 `_common.py` |
| `startup()` 中调用 `broadcast_snapshot` | scheduler.add_callback 需要函数引用 | `main.py` 中 `from .routers._common import broadcast_snapshot` |
| `test_ocr` 的函数内 import | 函数内有 `from backend.collectors.window_capture import crop_by_ratio` | 函数内 import 无需改变 |

### 5.3 依赖关系图

```
backend.services.store ←┐
backend.services.scheduler ←┐
backend.collectors.remote_edge ←┐
backend.collectors.window_capture ←┐
backend.collectors.ocr_reader ←┐
                                │
routers/_common.py ─────────────┼── (imports all above)
                                │
routers/tasks.py ──→ _common ───┘
routers/edge_sessions.py ──→ _common
routers/platforms.py ──→ _common
routers/shp.py ──→ _common
routers/ocr.py ──→ _common
routers/system.py ──→ _common
                         ↑
backend/main.py ─────────┘ (imports routers + uses _common's broadcast_snapshot for scheduler callback)
```

---

## 6. 拆分步骤

### 总体顺序（由易到难，每步独立可回滚）

```
Step 0: 创建 _common.py，逐步移入共享函数（不断测试，不破坏现有 main.py）
Step 1: 拆分 system.py (10 路由，最简单，无 Edge 依赖)
Step 2: 拆分 ocr.py (2 路由，但 test_ocr 依赖复杂)
Step 3: 拆分 shops.py (4 路由，中等复杂度)
Step 4: 拆分 platforms.py (5 路由，依赖 run_platform_edge_action)
Step 5: 拆分 tasks.py (13 路由，最复杂)
Step 6: 拆分 edge_sessions.py (18 路由，路径层级最深)
Step 7: 清理 main.py，移除已迁移的路由函数
```

### Step-by-Step 细节

#### Step 0: 创建 `_common.py` (最安全的基础动作)

1. 创建 `backend/routers/__init__.py` (空文件)
2. 创建 `backend/routers/_common.py`：
   - 复制 `clients: set[WebSocket] = set()` 
   - 复制 `build_snapshot()`、`broadcast_snapshot()`
   - 复制 `edge_session_for()`、`edge_client_for()`、`edge_health_payload()`
   - 复制 `edge_timeout_detail()`、`edge_control_unavailable_detail()`
   - 复制 `edge_action_payload()`、`build_edge_session_item()`
   - 复制 `reconcile_edge_session_task_runtime()`、`auto_restore_*` 系列
   - 复制 `lightweight_reconcile_and_auto_restore()`
   - 复制 `run_platform_edge_action()`、`edge_tasks_for_platform()`
   - 复制 `safe_upsert_task()`、`image_from_data_url()`
   - 复制 `_build_task_page_candidates()`、`_build_binding_resolution()`、`_task_runtime_for_bound_page()` 等
   - 复制 `screen_readonly_platform_unsupported_detail()`、`task_screen_readonly_payload()`
   - 复制所有 Pydantic 模型（或暂留 main.py，Step 5/6 再搬）
3. **关键：暂不从 main.py 删除原函数**，仅验证 `_common.py` 可正常 import
4. 运行 `tests/full_test.py --skip-api` 验证无 import 错误
5. 逐步修改各 router 和 main.py 的 import 来源（从 `_common` import 替代 main.py 内联定义）

> **回滚方式**：删除 `_common.py`，main.py 原封未动。

#### Step 1: 拆分 system.py

1. 创建 `backend/routers/system.py`
2. `router = APIRouter()`
3. 复制 10 个系统路由函数（health/realtime/history/settings/scheduler/windows）
4. Pydantic 模型一同移入
5. main.py 中 `from backend.routers.system import router as system_router`
6. `app.include_router(system_router)`
7. main.py 中原函数**暂时保留但注释**（验证通过后再删除）
8. 运行 `tests/full_test.py --skip-api` + 启动服务跑 `smoke_api.py`

#### Step 2-6: 同上模式，逐个迁移

每个 Step 完成后执行：`ruff check` + `tests/full_test.py` + `smoke_api.py`

---

## 7. 验收标准

| 验收项 | 命令 | 通过标准 |
|---|---|---|
| 全功能测试 | `python tests/full_test.py --skip-api` | 47/47 PASS |
| 冒烟测试 | `python tests/smoke_api.py` | 14/14 PASS |
| lint 检查 | `ruff check backend/` | 错误数 ≤ 91（业务代码类型风格可忽略） |
| 服务启动 | `uvicorn backend.main:app` | 正常启动，无 import 错误 |
| 路由完整性 | `GET /docs` | Swagger UI 显示全部路由 |
| 旧路径兼容 | `python backend/tools/full_test.py` | 仍可运行 |

### 特别关注的 API（最易遗漏）

| API | 原因 |
|---|---|
| `POST /api/tasks/{id}/resume-after-login` | 依赖链最长（Edge + 绑定 + 健康检查） |
| `POST /api/test-ocr` | 最复杂路由函数，约 120 行逻辑 |
| `WS /ws/live` | 直接操作 `clients` set |
| `GET /api/tasks/{id}/page-candidates` | 依赖 `_build_task_page_candidates` + 自动绑定 |
| `POST /api/shops/match` | 函数内定义了闭包 `_url_score` |

---

## 8. 结论

| 判断项 | 结论 |
|---|---|
| **是否建议执行 main.py 拆分** | ✅ **强烈建议** — 收益大(2347→~180行)、风险低(无循环依赖) |
| **拆分风险等级** | **低** — 本质是剪切粘贴 + import 路径替换，不改变业务逻辑 |
| **最危险的操作** | `_common.py` 中 `clients` set 的迁移 — 需确保 `broadcast_snapshot` 引用一致 |
| **是否需要确认后再执行** | ✅ 建议确认后再动手 |
| **预计总时间** | 2~3 小时（含每步验证） |
| **回滚方案** | 删除 `backend/routers/` 目录，还原 main.py 备份即可 |

### 建议执行策略

```
优先执行 Step 0 (_common.py) + Step 1 (system.py)
  → 验证流程跑通，积累信心
  → 然后 Step 2 (ocr.py) → Step 3 (shops.py) → Step 4 (platforms.py)
  → 最后处理最复杂的 Step 5 (tasks.py) + Step 6 (edge_sessions.py)
```

---

> **方案制定人：AI 架构师** | **日期：2026-05-08** | **本轮只输出方案**
