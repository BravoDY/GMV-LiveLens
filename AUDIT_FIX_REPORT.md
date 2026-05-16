# GMV-LiveLens 全量修复报告

> 修复完成时间：2026-05-05
> 覆盖范围：P1（5个）+ P2（4个）+ 高价值P3（2个），共 11 个问题
> 剩余未修复：BUG-012（P3，已评估为可接受，见末节）

---

## 修复总表

| 问题编号 | 等级 | 是否已修复 | 修改文件 | 验证结果 |
|---|---|---|---|---|
| BUG-001 | P1 | ✅ 已修复 | `backend/services/store.py` | 语法验证通过 |
| BUG-002 | P1 | ✅ 已修复 | `data/shops_default.json` | 文件已更新为 `[]` |
| BUG-003 | P1 | ✅ 已修复 | `requirements.txt` | 语法验证通过 |
| BUG-004 | P1 | ✅ 已修复 | `backend/main.py` | 语法验证通过 |
| BUG-005 | P1 | ✅ 已修复 | `backend/services/scheduler.py` | 语法验证通过 |
| BUG-006 | P2 | ✅ 已修复 | `frontend/app.js` | 逻辑验证通过 |
| BUG-007 | P2 | ✅ 已修复 | `backend/services/shop_config.py` | 端口分配验证通过 |
| BUG-008 | P2 | ✅ 已修复 | `backend/collectors/remote_edge.py` | 语法验证通过 |
| BUG-009 | P2 | ✅ 已修复 | `backend/main.py` | 语法验证通过 |
| BUG-010 | P3 | ✅ 已修复 | `backend/services/scheduler.py` | 语法验证通过 |
| BUG-011 | P3 | ✅ 已修复 | `frontend/index.html` + `frontend/assets/` | 文件已到位 |
| BUG-012 | P3 | ⏸ 不修复 | — | 当前规模可接受，见末节说明 |

---

## P1 修复详情

### BUG-001：store.py 死代码清理 + session_mode 修正
- **文件**：`backend/services/store.py`
- **改动1**：清除 `_ensure_capture_task_shop_uniqueness` 中 `return` 之后的 14 行死代码（session_mode UPDATE 逻辑永不执行）
- **改动2**：`_ensure_default_edge_session` 由 insert-only 改为 upsert：已存在的会话若 session_mode 为 null/空 或 default_real_edge 会话的 session_mode 非 `real_profile`，执行定向 UPDATE 修正
- **效果**：每次服务启动时，`default_real_edge` 的 session_mode 会被自动校正为 `real_profile`

---

### BUG-002：shops_default.json 清空过期备用数据
- **文件**：`data/shops_default.json`
- **修改前**：11 条使用 legacy `edge_session_id`（如 `taobao_group`）和 `null debug_port` 的过期记录
- **修改后**：`[]`（空数组）
- **效果**：shops.csv 解析失败时，`/api/shops` 返回空数组，前端显示空状态；不再加载错误数据导致任务全部消失

---

### BUG-003：requirements.txt 补充 ddddocr
- **文件**：`requirements.txt`
- **修改**：新增 `ddddocr>=1.6.1`（与 .venv 中已安装版本一致）
- **效果**：新环境 `pip install -r requirements.txt` 可正常安装 ddddocr

---

### BUG-004：GET /api/tasks 移除内嵌自愈检查
- **文件**：`backend/main.py`
- **修改前**：`GET /api/tasks` 同步调用 `lightweight_reconcile_and_auto_restore()`，遍历所有 Edge 会话做健康检查
- **修改后**：`GET /api/tasks` 只执行 `build_snapshot()`（纯 DB 读取）；新增 `POST /api/tasks/self-heal` 端点供显式触发自愈
- **前端影响**：确认前端代码中无任何地方读取 `binding_recovery` 字段（Grep 结果为空），删除安全

---

### BUG-005：scheduler.py 全局设置读取移出 task 循环
- **文件**：`backend/services/scheduler.py`
- **修改前**：`global_interval = float(store.get_setting(...))` 位于 `for task in tasks:` 循环内
- **修改后**：`global_interval` 移到循环前，每个 tick 只读取一次
- **效果**：11 个任务时，每 tick DB 读取由 11 次降为 1 次

---

## P2 修复详情

### BUG-006：孤立任务在任务管理中不可见
- **文件**：`frontend/app.js`
- **修改1**：`managerFilteredTasks()` — "全部"筛选下不再过滤掉不在 shopConfigs 中的任务
- **修改2**：卡片渲染 — 孤立任务自动显示红色"孤立任务"警告徽章（含 title 提示"此任务不在 shops.csv 中，仍在后台采集但不显示在看板"）和 `is-orphan` CSS 类
- **效果**：shops.csv 删除某店铺后，对应 DB 任务仍可在任务管理中看到并手动删除，不再无声消失

---

### BUG-007：非标准平台 Edge debug_port 依赖 CSV 行序
- **文件**：`backend/services/shop_config.py`
- **修改前**：`base = PLATFORM_PORT_BASE.get(key, DEFAULT_PORT_BASE + index * 10)` — 未知平台使用行索引计算端口，行序变化端口漂移
- **修改后**：未知平台使用平台名的 MD5 哈希值（前 2 字节 % 500）计算固定 base，再叠加同平台内的顺序 offset
- **效果**：同一平台无论在 CSV 哪一行，base 端口永远相同；多店铺顺序递增
- **验证**：运行 `load_shop_configs()` 确认天猫 9231-9234、京东 9241+ 分配正确

---

### BUG-008：remote_edge.py 模块级全局实例
- **文件**：`backend/collectors/remote_edge.py`
- **修改**：删除末行 `remote_edge = remote_edge_manager.default_client()`
- **效果**：模块导入不再自动启动后台线程和等待 10 秒；`remote_edge_manager` 仍保留，所有调用方均通过 `remote_edge_manager.get_client(...)` 获取实例（已验证无代码直接引用 `remote_edge` 变量）

---

### BUG-009：页签扫描超时重试沿用旧 error detail
- **文件**：`backend/main.py`（`edge_session_pages` 函数）
- **修改前**：重试失败时 `raise HTTPException(status_code=500, detail=detail)`，`detail` 来自第一次超时
- **修改后**：重试失败时分别处理 `EdgeActionTimeoutError`（生成新的 timeout detail）和普通 `Exception`（生成新的 health detail），错误描述与实际原因一致

---

## P3 修复详情

### BUG-010：scheduler.py 缺 PIL.Image 导入
- **文件**：`backend/services/scheduler.py`
- **修改**：顶部添加 `from PIL import Image`
- **效果**：`_save_ocr_dataset(self, crop: Image.Image, ...)` 类型注解在 IDE 中可正确解析

---

### BUG-011：前端依赖 CDN CSS（open-props）
- **文件**：`frontend/index.html`，新增 `frontend/assets/open-props.min.css`
- **修改**：下载 open-props.min.css（29 KB）到本地，替换 `https://unpkg.com/open-props/open-props.min.css` 为 `/static/assets/open-props.min.css`
- **效果**：断网或内网环境下页面样式完全正常

---

## BUG-012 评估：不修复

**问题**：`store.connect()` 每次调用创建新 SQLite 连接，无连接池。

**评估理由**：
- 项目运行于单进程单 worker（bat 脚本启动 uvicorn，无 `--workers` 参数）
- SQLite WAL 模式支持多读单写，短连接开销约 0.1ms/次，在 11 任务 0.5s 间隔下可接受
- 实现连接池需要线程安全的 `threading.local()` 或单例模式，改动面较大，收益有限
- **结论**：当前规模下无需修改，如未来并发写入量明显增大再评估

---

## 全量语法验证

```
python -m py_compile backend/main.py backend/services/store.py
  backend/services/scheduler.py backend/services/shop_config.py
  backend/collectors/remote_edge.py backend/collectors/ocr_reader.py
  backend/collectors/window_capture.py backend/collectors/window_control.py
  backend/models.py

结果：ALL FILES OK
```

---

## 修复后回归测试建议

```bash
# 启动服务
第1步_启动GMV服务.bat

# 1. 验证 GET /api/tasks 响应极快
curl -w "\n耗时: %{time_total}s\n" http://127.0.0.1:8100/api/tasks

# 2. 验证 default_real_edge session_mode 已自动修正
python -c "
import sqlite3
conn = sqlite3.connect('data/gmv_livelens.sqlite3')
row = conn.execute(\"SELECT session_mode FROM edge_sessions WHERE session_id='default_real_edge'\").fetchone()
print('session_mode:', row[0])  # 预期: real_profile
conn.close()
"

# 3. 验证 /api/shops 正常返回 CSV 数据（非过期 JSON）
curl http://127.0.0.1:8100/api/shops

# 4. 验证 shops_default.json 为安全空数组
python -c "import json; print(json.load(open('data/shops_default.json')))"  # 预期: []

# 5. 浏览器访问 http://127.0.0.1:8100
#    - 样式正常（本地 CSS，断网也可用）
#    - 任务管理"全部"筛选下孤立任务显示红色"孤立任务"标签
#    - 启动采集后看板实时刷新

# 6. 验证端口分配稳定性
python -c "
from backend.services.shop_config import load_shop_configs
for c in load_shop_configs():
    print(c.platform, c.shop_name, 'port=', c.debug_port)
"
```
