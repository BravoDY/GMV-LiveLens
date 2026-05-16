# 修复采集报错与目标丢失计划

## 1. 需求与目标
- **修复 `parse_failed` 报错**：解决 `argument must be int or float, not str` 的报错，使 OCR 结果能正常走完评估流程。
- **修复目标（Target）丢失**：解决前端卡片和看板中店铺目标变成 `--` 的问题。

## 2. 当前状态与原因分析
- **报错原因**：在 `backend/services/scheduler.py` 的 `_judge` 方法中，处理“跨天检测”时使用了 `datetime.fromtimestamp(task.last_success_at)`。但由于 `task.last_success_at` 存在 SQLite 数据库中是由 `now_sql()` 生成的字符串格式（如 `"2026-05-04 18:32:11"`），传入 `fromtimestamp` 会直接抛出 `TypeError: argument must be int or float, not str`，导致每次只要存在上次成功时间，就会采集失败并标记为 `parse_failed`。
- **目标丢失原因**：此前调整了数据库表结构和任务逻辑，部分任务的同步逻辑未被重新触发，导致部分店铺（如京东官方旗舰店、天猫官方旗舰店等）在数据库中的 `target` 变为了 0，从而前端显示 `--`。

## 3. 具体修改步骤

### 步骤 3.1 修复跨天检测的时间解析逻辑
- **文件**：`backend/services/scheduler.py`
- **修改内容**：将 `datetime.fromtimestamp` 改为安全的字符串时间解析（`datetime.strptime`）。
  ```python
  # 跨天检测 (使用本地时间)
  is_cross_day = False
  if last is not None and task.last_success_at:
      try:
          if isinstance(task.last_success_at, (int, float)):
              last_date = datetime.fromtimestamp(task.last_success_at).date()
          else:
              last_date = datetime.strptime(str(task.last_success_at), "%Y-%m-%d %H:%M:%S").date()
          current_date = datetime.now().date()
          if current_date > last_date:
              is_cross_day = True
      except Exception:
          pass
  ```

### 步骤 3.2 重新同步 CSV 目标数据
- **操作**：通过 Python 脚本触发一次后端的 `sync_tasks_with_shop_configs()`，让所有存在于 `shops.csv` 中的 Target（如 1300000, 4200000 等）重新写入 SQLite 数据库中的 `capture_tasks` 表。

## 4. 测试与验证标准
1. **报错验证**：重启后端服务后，等待下一次采集调度，确认不再抛出 `parse_failed` 及 `int or float` 的 TypeError。
2. **目标验证**：刷新前端页面，确认卡片上的“目标”金额恢复正常，不再是 `--`。