# 修复 GMV 采集报错与目标丢失执行计划

## 1. 需求与目标
- **修复 `parse_failed` 报错**：解决由于 `last_success_at` 字段的类型不匹配导致的 `argument must be int or float, not str` 报错，使 OCR 结果能正常完成调度与入库。
- **恢复目标（Target）金额**：确保前端卡片和看板中店铺目标不再显示为 `--`。

## 2. 当前状态与原因分析
- **报错原因**：`backend/services/scheduler.py` 中的 `_judge` 方法在此前的代码中直接使用了 `datetime.fromtimestamp(task.last_success_at)` 来处理跨天逻辑。由于 `task.last_success_at` 在 SQLite 中以字符串格式（如 `"2026-05-04 18:32:11"`）存储，传入 `fromtimestamp` 时引发了 `TypeError`。此问题在代码层面虽已被修改为兼容 `datetime.strptime`，但由于后端服务（Uvicorn）未被彻底重启，旧代码仍在内存中运行，导致报错持续发生。
- **目标丢失原因**：目标值已成功通过脚本从 `shops.csv` 同步到 SQLite 数据库的 `capture_tasks` 表中，且后端 API `/api/tasks` 已能正确返回 `target` 字段。前端未更新显示大概率是因为服务状态未完全刷新。

## 3. 具体执行步骤

### 步骤 1：彻底重启后端服务
- 终止当前正在运行的 Python 后端进程（通过 `taskkill` 或在终端中手动停止）。
- 重新启动 FastAPI 后端服务（例如执行 `python -m uvicorn backend.main:app --reload`），确保 `scheduler.py` 中的时间解析修复代码被正确加载。

### 步骤 2：前端验证与监控
- 在浏览器中刷新前端页面（`http://127.0.0.1:8000/`）。
- 观察前端卡片，确认各个店铺的“目标”金额正确呈现，不再是 `--`。
- 观察任务管理列表，确认不再出现新的 `parse_failed: argument must be int or float, not str` 错误，任务状态应恢复正常（如 `pending_confirm` 或 `ok`）。

## 4. 验收标准
- 后端控制台不再输出由 `_judge` 引发的 `TypeError` 异常。
- 前端 UI 的 Target 正常显示为具体的金额（如 `4,200,000`）。
- 采集调度链路恢复正常，状态标签更新正常。