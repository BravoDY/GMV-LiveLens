# Tasks
- [x] Task 1: 审查并收口抖音大屏只读平台支持名单
  - [x] SubTask 1.1: 盘点 `backend/main.py`、`backend/services/scheduler.py`、`frontend/config.js` 中的大屏只读平台支持判断
  - [x] SubTask 1.2: 消除抖音在前端、只读接口、正式调度三层之间的白名单不一致
  - [x] SubTask 1.3: 确认抖音与天猫、京东、唯品会在 `screen_readonly` 入口能力上保持同层级支持

- [x] Task 2: 收口抖音单店大屏目标指标与结构化返回规范
  - [x] SubTask 2.1: 审查 `remote_edge.py` 中抖音单店大屏目标页识别是否仅指向 `screen/shop/single`
  - [x] SubTask 2.2: 固化抖音只读目标指标为 `今日用户支付金额(含异常交易)`，避免误读相邻相似金额
  - [x] SubTask 2.3: 对齐抖音与天猫、京东、唯品会的返回字段、等待态、失败态和 reason code 口径

- [x] Task 3: 将抖音正式只读轮询频率收口为 1 秒
  - [x] SubTask 3.1: 审查当前调度器对 `screen_readonly` 间隔的计算方式，区分平台专属轮询与前端全局降级轮询
  - [x] SubTask 3.2: 为抖音正式只读任务明确固定 `1 秒` 的轮询策略
  - [x] SubTask 3.3: 保持天猫、京东、唯品会现有正式只读节奏和前端 WS 失败兜底轮询逻辑不被误改

- [x] Task 4: 做抖音与多平台一致性专项验证
  - [x] SubTask 4.1: 验证抖音只读测试接口能返回统一结构，并读到 `今日用户支付金额(含异常交易)`
  - [x] SubTask 4.2: 验证抖音任务保存为 `screen_readonly` 后，正式 `capture-once` 和调度写入链路可正常工作
  - [x] SubTask 4.3: 验证不会再出现“只读接口支持抖音，但正式调度仍提示平台未配置”的层间不一致
  - [x] SubTask 4.4: 验证天猫、京东、唯品会现有大屏只读链路未被抖音规范收口破坏

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1 and Task 2
- Task 4 depends on Task 2 and Task 3
