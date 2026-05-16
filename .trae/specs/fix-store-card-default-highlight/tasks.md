# Tasks
- [x] Task 1: 明确默认态与变化态样式职责
  - [x] SubTask 1.1: 复核当前 `.store-card::before` 默认样式是否包含强白色高光与强发光
  - [x] SubTask 1.2: 复核 `.store-card.is-flashing::before` 动画是否仍可见且仅变化时触发
- [x] Task 2: 调整 CSS 让默认态克制、变化态明显
  - [x] SubTask 2.1: 将默认态顶边改回“平台色为主 + 轻微阴影”，去掉默认白色中心高光
  - [x] SubTask 2.2: 仅在 `is-flashing` 动画阶段引入“白色亮斑 + 渐变扫光 + 发光扩散”
  - [x] SubTask 2.3: 确保平台汇总卡与总卡相关选择器不受影响
- [x] Task 3: 验证与回归
  - [x] SubTask 3.1: 静态检查：确认无 CSS 诊断错误
  - [x] SubTask 3.2: 行为检查：GMV 未变时不显著高亮；GMV 变动时扫光明显且仅目标店铺触发

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
