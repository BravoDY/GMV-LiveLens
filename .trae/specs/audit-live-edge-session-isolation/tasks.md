# Tasks
- [ ] Task 1: 确认审计口径与数据源
  - [ ] 盘点本次审计需要使用的真实数据源：`edge_sessions`、`capture_tasks`、店铺配置与默认推导目录
  - [ ] 明确哪些字段用于识别“共用目录”“目录漂移”“落到 real_profile”
  - [ ] 明确本次审计严格只读，不修改数据库和店铺配置

- [ ] Task 2: 核对当前会话与店铺配置映射
  - [ ] 逐条读取现有 `edge_sessions`
  - [ ] 将会话与店铺配置、任务绑定进行关联
  - [ ] 标出没有命中店铺配置、绑定来源异常或任务落点异常的会话

- [ ] Task 3: 审计 Profile 目录隔离风险
  - [ ] 识别多个店铺是否共用同一非空 `user_data_dir`
  - [ ] 对比每家店当前目录与按现有配置推导的期望目录，识别目录漂移
  - [ ] 识别哪些店铺或任务落在 `real_profile`

- [ ] Task 4: 输出逐店审计结果
  - [ ] 逐店列出平台、店铺、会话 ID、端口、当前目录、期望目录、模式和绑定来源
  - [ ] 按“正常隔离 / 共用目录 / 目录漂移 / real_profile”分类输出
  - [ ] 对每项异常给出证据链和风险说明

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
