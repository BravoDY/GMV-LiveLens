# Tasks
- [x] Task 1: 固化大屏只读模式的数据源与状态边界
  - [x] SubTask 1.1: 明确当前店铺页面如何判断“已进入大屏 `screen.htm`”
  - [x] SubTask 1.2: 明确 `payAmt.value` 的读取口径、更新时间口径和无值时提示口径
  - [x] SubTask 1.3: 明确测试版只读模式与现有 OCR/保存/正式采集链路的隔离边界

- [x] Task 2: 补大屏只读模式的后端调试接口
  - [x] SubTask 2.1: 在真实 Edge 页面上下文中增加“读取当前大屏只读值”的后端能力
  - [x] SubTask 2.2: 返回结构至少包含最新 `payAmt`、读取时间、页面状态和错误原因
  - [x] SubTask 2.3: 遇到未进入大屏、页面失效或读取失败时返回明确 reason_code

- [x] Task 3: 在采集配置工作台增加测试版 UI
  - [x] SubTask 3.1: 增加“开启只读 / 刷新只读结果 / 清空测试记录”之类的最小按钮组
  - [x] SubTask 3.2: 在页面中增加一个可视区域，展示最新 `payAmt`、更新时间和最近若干条记录
  - [x] SubTask 3.3: 明确文案，提示该能力仅用于测试稳定性，不写正式采集结果

- [x] Task 4: 做真实大屏专项验证
  - [x] SubTask 4.1: 在当前真实店铺大屏页验证能成功读取 `payAmt.value`
  - [x] SubTask 4.2: 验证数值跳动时，测试区域能持续刷新并保留最近记录
  - [x] SubTask 4.3: 验证未进入大屏时会给出明确提示，而不是静默失败
  - [x] SubTask 4.4: 验证启用只读模式后，现有 OCR 预览、OCR 测试、保存配置链路未被破坏

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1 and Task 2
- Task 4 depends on Task 2 and Task 3
