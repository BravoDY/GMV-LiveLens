# Tasks
- [x] Task 1: 固化京东大屏只读的数据源与隔离边界
  - [x] SubTask 1.1: 明确京东平台正式大屏只读支持口径，以及与天猫规则并存的边界
  - [x] SubTask 1.2: 明确 `realKanBans.html` 如何作为京东大屏只读的受控页面空间
  - [x] SubTask 1.3: 明确“今日成交金额累计”作为京东正式只读值的读取口径、时间口径和无值提示口径

- [x] Task 2: 补后端京东大屏只读正式链路
  - [x] SubTask 2.1: 扩展平台支持判断，让京东任务允许进入 `screen_readonly` 正式链路
  - [x] SubTask 2.2: 在 `remote_edge` 中新增京东专属页面识别与页面内读取逻辑，返回结构化只读结果
  - [x] SubTask 2.3: 在调度器中复用正式只读运行态写入逻辑，让京东结果写入任务状态、样本历史和实时看板快照

- [x] Task 3: 补前端京东平台通用配置与测试体验
  - [x] SubTask 3.1: 更新配置页平台校验与提示文案，允许京东平台保存 `大屏只读`
  - [x] SubTask 3.2: 更新只读测试面板提示，让京东明确以 `realKanBans.html` 和“今日成交金额累计”为目标
  - [x] SubTask 3.3: 保持天猫现有只读体验不变，避免平台提示和保存逻辑相互污染

- [x] Task 4: 做京东大屏只读专项验证
  - [x] SubTask 4.1: 验证当前京东真实页面进入 `realKanBans.html` 后，测试接口能读取“今日成交金额累计”
  - [x] SubTask 4.2: 验证京东正式任务保存为 `screen_readonly` 后，调度结果能写入任务运行态与实时看板
  - [x] SubTask 4.3: 验证京东未进入目标页时进入等待态，进入目标页后自动恢复正常采集
  - [x] SubTask 4.4: 验证天猫原有大屏只读与 OCR 任务链路未被京东改动破坏

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1 and Task 2
- Task 4 depends on Task 2 and Task 3
