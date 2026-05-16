# GMV-LiveLens 测试计划矩阵

> 审计时间：2026-05-05 | 基于代码扫描设计，非文档推断

---

## 1. 启动测试

| 测试项 | 验证方式 | 预期结果 | 风险点 |
|---|---|---|---|
| 依赖完整性 | `pip install -r requirements.txt`，再 `python -c "import ddddocr"` | **预期失败**：ddddocr 未在 requirements.txt 中 | BUG-003 |
| Python 语法 | `python -m py_compile backend/**/*.py` | ✅ 已验证：ALL SYNTAX OK | - |
| 端口占用检测 | 运行 `第1步_启动GMV服务.bat` 时 8100 已被占用 | 询问用户是否关闭旧进程，逻辑完整 | - |
| 服务启动 | `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8100` | 服务正常启动，无错误日志 | - |
| init_db 执行 | 启动后检查 `data/gmv_livelens.sqlite3` 是否创建 | 4 张表创建完毕，default_real_edge 会话存在 | BUG-001（session_mode） |
| 首页加载 | 浏览器访问 `http://127.0.0.1:8100` | 页面正常加载，非白屏 | BUG-011（CDN CSS） |
| WebSocket 连接 | 浏览器控制台观察 WS 连接状态 | 显示"实时连接"绿色状态 | - |

---

## 2. 核心功能链路测试

### 链路 1：店铺配置读取

| 功能链路 | 入口 | 正常路径 | 异常路径 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|
| 读取 shops.csv | `GET /api/shops` | shops.csv 存在且编码正确 → 返回 11 条记录 | shops.csv 不存在 → fallback 到 shops_default.json（BUG-002：返回过期数据） | 正常：11 条正确记录 | curl `http://127.0.0.1:8100/api/shops` |
| 任务同步 | `POST /api/shops/init` | 创建/更新 DB 中的采集任务 | CSV 有重复行 → 抛出 ValueError | 正常：created/updated/unchanged 统计正确 | POST `/api/shops/init` |
| 任务列表 | `GET /api/tasks` | 返回 snapshot 含所有任务 | Edge 会话全部离线 → 自愈检查超时（BUG-004） | 正常：快速返回 | curl + 计时 |

### 链路 2：Edge 会话控制

| 功能链路 | 入口 | 正常路径 | 异常路径 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|
| 启动/显示 Edge | `POST /api/edge-sessions/{id}/show` | Edge 未运行 → 启动并显示窗口 | Edge binary 不存在 → 返回 edge_binary_not_found | 窗口出现在主屏，debug_available=true | 任务管理点击"启动Edge" |
| 隐藏 Edge | `POST /api/edge-sessions/{id}/hide` | Edge 已显示 → 移出主屏 | Edge 未运行 → 返回 edge_debug_unavailable | 窗口不可见 | 任务管理点击"隐藏Edge" |
| 关闭 Edge | `POST /api/edge-sessions/{id}/close` | 优雅关闭（WM_CLOSE） → closed=true | 关闭超时 → 返回 safe_close_timeout | closed=true；登录态保留 | 任务管理点击"关闭Edge" |
| 平台级批量操作 | `POST /api/platforms/{platform}/launch-edge` | 对平台所有店铺顺序执行 | 部分失败 → 返回 ok/failed 分组 | 部分成功时正确报告 | 任务管理平台级按钮 |

### 链路 3：采集配置标定

| 功能链路 | 入口 | 正常路径 | 异常路径 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|
| 扫描页签 | `GET /api/tasks/{id}/page-candidates` | Edge 已运行有页签 → 返回候选列表 | Edge 未运行 → 409 + edge_debug_unavailable | 正常：候选列表含评分 | 采集配置 → 扫描页签 |
| 生成预览 | `POST /api/edge-sessions/{id}/pages/{page_id}/preview` | CDP 截图 → base64 图片 | page_id 失效 → 404 + remote_page_not_found | 返回图片数据，宽高正确 | 采集配置 → 生成预览 |
| 测试 OCR | `POST /api/test-ocr` | 截图 + 框选区域 → 候选值 | 截图为空 → 返回空 candidates | 返回 suggested_value | 采集配置 → 测试识别 |
| 保存任务 | `POST /api/tasks` | 含 x_ratio/y_ratio → 写入 DB | 同平台同店铺重复 → 409 + duplicate_shop_task | 返回完整 task 对象 | 采集配置 → 保存 |

### 链路 4：GMV 采集主循环

| 功能链路 | 入口 | 正常路径 | 异常路径 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|
| 启动采集 | `POST /api/scheduler/start` + UI"启动采集"按钮 | 调度器开始心跳 | 任务未绑定页签 → status=remote_page_not_found | scheduler.running=true | `GET /api/scheduler` |
| 单次采集 | `POST /api/tasks/{id}/capture-once` | OCR 识别成功 → status=ok / pending_confirm | Edge 断开 → edge_debug_unavailable | 返回 status+reason+candidates | 任务管理 → 采一次 |
| 连续采集判断 | 调度器循环 | 同值出现 confirm_count 次 → ok | 跳变 > 5x → suspect → 等待 max(3, confirm_count+1) 次 | 状态机正确转换 | 观察 last_reason |
| 跨天重置 | 调度器 _judge | 新一天首次采集值低于昨天可信值 → 接受 | 同天下降 → 忽略（ok，不更新可信值） | 跨天重置正常 | 手动设置 last_success_at 为昨天 |

### 链路 5：实时看板显示

| 功能链路 | 入口 | 正常路径 | 异常路径 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|
| WS 实时推送 | `ws://127.0.0.1:8100/ws/live` | 采集成功 → 2s 内看板更新 | WS 断开 → 自动切轮询（2s 间隔） | 看板数值实时刷新 | 浏览器 Network → WS |
| 店铺卡片渲染 | `renderDashboard()` | task.last_trusted_value → 显示金额 | task 不在 shopConfigs → 卡片不显示（BUG-006） | 11 个任务对应 11 张卡片 | 实时看板页面 |
| 汇总 GMV | `build_snapshot()` | sum of enabled tasks' last_trusted_value | 全部 None → total=0 | 合计值正确 | `GET /api/realtime` |
| 状态标签 | 前端 taskStatusMeta | status=ok → 绿色"正常" | 未知 status key → 灰色显示 key | 所有状态有对应标签 | 观察任务管理卡片 |

### 链路 6：手工纠错

| 功能链路 | 入口 | 正常路径 | 异常路径 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|
| 人工纠错 | `POST /api/tasks/{id}/manual-correction` | value=12345 → trusted_value=12345, status=ok | task 不存在 → 404 | 看板值立即更新 | 任务管理 → 历史 → 设为可信 |

### 链路 7：数据历史查询

| 功能链路 | 入口 | 正常路径 | 异常路径 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|
| 采样历史 | `GET /api/tasks/{id}/samples` | 返回最近 20 条 | task 不存在 → 404 | candidates 字段被正确反序列化为 list | 任务管理 → 历史 |

---

## 3. 数据链路测试

| 测试点 | 验证方式 | 预期 | 风险 |
|---|---|---|---|
| 字段映射：task_to_dict 完整性 | 对比 CaptureTask dataclass 字段与 task_to_dict 输出 | 无字段缺失 | ✅ 已验证完整 |
| OCR 候选评分：金额优先于日期 | 截图含日期和金额 → candidates[0] 为金额 | score 中 date_like 惩罚 -60 生效 | 需实测 |
| 多任务不串数据 | 两个 Edge 会话各自采集 → 各自的 task 记录独立 | DB 中 task_id 不同 | ✅ 逻辑隔离 |
| 空数据处理 | 截图全白（无文字） → selected=None → status=parse_failed | 不崩溃，状态正确 | ✅ extract_candidates 返回空列表 |
| 脏数据：金额异常大 | selected > 1e12 → score -= 60 (too_long) | 不被采信 | ✅ 评分逻辑有惩罚 |
| 前端展示与后端一致 | `fmtMoney(last_trusted_value)` 格式 | 前端 ¥{toLocaleString} 与后端整数一致 | ✅ |

---

## 4. API 测试

| 接口 | 参数校验 | 错误处理 | 风险 |
|---|---|---|---|
| `POST /api/tasks` | window_keyword 必填，否则 422 | ✅ Pydantic 校验 | - |
| `POST /api/edge-sessions` | debug_port 范围 1024-65535 | ✅ Field(ge=1024, le=65535) | - |
| `POST /api/test-ocr` | capture_mode=remote_edge 但 page_id 为空 | 调用 edge_client_for → 截图 page_id="" → remote_page_not_found | 需实测 |
| `GET /api/edge-sessions/{id}/health` | session_id 不存在 → 404 | ✅ edge_session_for raises 404 | - |
| `DELETE /api/edge-sessions/default_real_edge` | 禁止删除 | ✅ raise ValueError("default_session_cannot_be_deleted") | - |
| `POST /api/shops/bind` | task_id 无效 → 跳过（不报错） | ✅ results.append({status:"not_found"}) | - |

---

## 5. 前端测试

| 测试点 | 验证方式 | 预期 | 风险 |
|---|---|---|---|
| 无 shopConfig 任务不可见 | shops.csv 删除一行，刷新 → 该任务在 UI 消失 | 确认 BUG-006 复现 | BUG-006 |
| CDN 断网样式 | 断网刷新 → 样式是否崩溃 | 确认 BUG-011 复现 | BUG-011 |
| WS 断线降级 | 后端重启后前端状态恢复 | 轮询 2 秒后恢复连接 | ✅ |
| 采集配置工作台 | 进入配置 Tab → 自动定位待配置店铺 | setupCurrentCard 显示正确店铺 | 需实测 |
| 全屏按钮 | 点击全屏 → 浏览器全屏模式 | HTML5 fullscreen API 正常 | ✅ |
| 任务管理分页/过滤 | 点击"正常"/"告警"/"暂停"筛选 | 正确过滤任务 | ✅ |

---

## 6. 配置与部署测试

| 测试点 | 状态 | 备注 |
|---|---|---|
| .env.example | ❌ 不存在 | 环境变量通过 os.environ 读取（GMV_OCR_ENGINE 等），无 .env.example 文档 |
| Docker/docker-compose | ❌ 不存在 | 无容器化配置 |
| 硬编码路径 | ✅ 使用 Path(__file__).resolve().parents 动态解析 | 无硬编码路径 |
| 硬编码账号/密钥 | ✅ 无 | 无敏感信息硬编码 |
| 端口配置 | ✅ 通过 bat 启动脚本参数化 `APP_PORT=8100` | - |
| 数据目录自动创建 | ✅ `DATA_DIR.mkdir(parents=True, exist_ok=True)` | - |
| 未文档化环境变量 | ⚠️ GMV_SCREENSHOT_MAX_AGE_DAYS, GMV_PREVIEW_MIN/MAX_INTERVAL_SECONDS, GMV_PREVIEW_MAX_WIDTH, GMV_OCR_ENGINE | 无 .env.example 说明 |
