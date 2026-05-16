# Tasks
- [x] Task 1: 建立目标值现状证据
  - [x] SubTask 1.1: 查询 `capture_tasks` 中异常任务的 `target`、`platform`、`shop_name`
  - [x] SubTask 1.2: 校验 `load_shop_configs()` 解析到的同店铺 `target` 是否非零
  - [x] SubTask 1.3: 对比数据库与配置源，确认“源正确但落库为 0”的差异

- [x] Task 2: 定位覆盖链路而非只看同步链路
  - [x] SubTask 2.1: 阅读 `sync_tasks_with_shop_configs()`，确认其更新条件
  - [x] SubTask 2.2: 阅读前端 `saveTask()` 构建 payload 的 `target` 取值逻辑
  - [x] SubTask 2.3: 阅读后端 `upsert_task()` 的 `target` 写入逻辑并确认回写风险

- [x] Task 3: 产出根因说明与可复现条件
  - [x] SubTask 3.1: 形成“为什么上次看似修复、本次又复发”的时间序结论
  - [x] SubTask 3.2: 给出最小复现路径（不改代码）
  - [x] SubTask 3.3: 输出用户可验证的检查步骤

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
